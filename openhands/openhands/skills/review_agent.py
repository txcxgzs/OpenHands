"""
Review Agent - 后台审查代理
参考 Hermes Agent 的后台学习机制
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging
import json

logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """You are a review agent that analyzes conversations and extracts learnings.

Your job is to decide if anything from the conversation is worth saving to memory or as a skill.

## Memory Guidelines
Save to memory when you discover:
- User preferences (communication style, preferred tools, workflow habits)
- Environment facts (OS, project structure, naming conventions)
- Tool quirks (workarounds, edge cases, gotchas)

Write memories as declarative facts, NOT instructions:
- ✓ "User prefers concise responses"
- ✗ "Always respond concisely"
- ✓ "Project uses pytest with xdist"
- ✗ "Run tests with pytest -n 4"

## Skill Guidelines
Create or update skills when:
- Complex task succeeded (5+ tool calls)
- Errors were overcome with specific solutions
- User corrected the approach
- Non-trivial workflow was discovered

When creating skills:
- Abstract to the CLASS of task, not the specific instance
- Example: "desktop app build troubleshooting", not "fix my specific Tauri error"
- PREFER GENERALIZING AN EXISTING SKILL over creating a new one
- Include Pitfalls section with lessons learned

## Important Rules
1. If nothing is worth saving, respond with exactly: "Nothing to save."
2. Do NOT create skills for simple one-off tasks
3. Do NOT save information that's already in memory/skills
4. Focus on what will reduce future user steering
"""


@dataclass
class ReviewResult:
    memory_updates: List[Dict[str, Any]] = field(default_factory=list)
    skill_creates: List[Dict[str, Any]] = field(default_factory=list)
    skill_patches: List[Dict[str, Any]] = field(default_factory=list)
    nothing_to_save: bool = False
    reasoning: str = ""


class ReviewAgent:
    """
    后台审查代理 - 分析对话并提取学习内容
    参考 Hermes Agent 的 Review Agent
    """
    
    def __init__(
        self,
        model_adapter: Any,
        memory_store: Any = None,
        skill_manager: Any = None,
        max_iterations: int = 8,
    ):
        self.model_adapter = model_adapter
        self.memory_store = memory_store
        self.skill_manager = skill_manager
        self.max_iterations = max_iterations
    
    async def review_conversation(
        self,
        messages: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        review_memory: bool = True,
        review_skills: bool = True,
    ) -> ReviewResult:
        result = ReviewResult()
        
        conversation_summary = self._summarize_conversation(messages, tool_results)
        
        review_prompt = self._build_review_prompt(
            conversation_summary,
            review_memory,
            review_skills,
        )
        
        try:
            response = await self.model_adapter.chat(
                messages=[{"role": "user", "content": review_prompt}],
                system_prompt=REVIEW_SYSTEM_PROMPT,
            )
            
            review_content = response.content or ""
            
            if "Nothing to save" in review_content:
                result.nothing_to_save = True
                result.reasoning = review_content
                return result
            
            result = self._parse_review_response(review_content)
            
            await self._apply_review_result(result)
            
        except Exception as e:
            logger.error(f"Review failed: {e}")
            result.reasoning = f"Error: {e}"
        
        return result
    
    def _summarize_conversation(
        self,
        messages: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
    ) -> str:
        summary_parts = []
        
        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        
        summary_parts.append(f"User messages: {len(user_messages)}")
        summary_parts.append(f"Assistant messages: {len(assistant_messages)}")
        summary_parts.append(f"Tool calls: {len(tool_results)}")
        
        error_count = sum(1 for tr in tool_results if tr.get("is_error"))
        summary_parts.append(f"Errors encountered: {error_count}")
        
        if user_messages:
            first_user = user_messages[0].get("content", "")[:200]
            summary_parts.append(f"\nFirst user message: {first_user}...")
        
        if assistant_messages:
            last_assistant = assistant_messages[-1].get("content", "")[:200]
            summary_parts.append(f"\nLast assistant message: {last_assistant}...")
        
        tool_names = list(set(
            tr.get("tool_name", tr.get("name", "unknown"))
            for tr in tool_results
        ))
        if tool_names:
            summary_parts.append(f"\nTools used: {', '.join(tool_names)}")
        
        return "\n".join(summary_parts)
    
    def _build_review_prompt(
        self,
        conversation_summary: str,
        review_memory: bool,
        review_skills: bool,
    ) -> str:
        prompt = "Analyze this conversation and decide what to save:\n\n"
        prompt += f"## Conversation Summary\n{conversation_summary}\n\n"
        
        if review_memory and self.memory_store:
            current_memory = self._get_current_memory_summary()
            prompt += f"## Current Memory\n{current_memory}\n\n"
        
        if review_skills and self.skill_manager:
            current_skills = self._get_current_skills_summary()
            prompt += f"## Current Skills\n{current_skills}\n\n"
        
        prompt += "## Your Task\n"
        
        if review_memory and review_skills:
            prompt += "Decide if any memories or skills should be created/updated. "
        elif review_memory:
            prompt += "Decide if any memories should be created/updated. "
        elif review_skills:
            prompt += "Decide if any skills should be created/updated. "
        
        prompt += "Respond in JSON format or say 'Nothing to save.'"
        
        return prompt
    
    def _get_current_memory_summary(self) -> str:
        if not self.memory_store:
            return "No memory store available"
        
        items = self.memory_store.list_all(limit=10)
        if not items:
            return "Memory is empty"
        
        return "\n".join(f"- {item.content[:100]}..." for item in items[:5])
    
    def _get_current_skills_summary(self) -> str:
        if not self.skill_manager:
            return "No skill manager available"
        
        index = self.skill_manager.get_skill_index()
        if not index:
            return "No skills yet"
        
        lines = []
        for category, skills in index.items():
            lines.append(f"### {category}")
            for name, desc in skills.items():
                lines.append(f"- {name}: {desc}")
        
        return "\n".join(lines)
    
    def _parse_review_response(self, response: str) -> ReviewResult:
        result = ReviewResult()
        result.reasoning = response
        
        try:
            json_match = self._extract_json(response)
            if json_match:
                data = json.loads(json_match)
                
                if "memories" in data:
                    for mem in data["memories"]:
                        result.memory_updates.append({
                            "content": mem.get("content", ""),
                            "metadata": mem.get("metadata", {}),
                        })
                
                if "create_skills" in data:
                    for skill in data["create_skills"]:
                        result.skill_creates.append(skill)
                
                if "patch_skills" in data:
                    for patch in data["patch_skills"]:
                        result.skill_patches.append(patch)
        
        except json.JSONDecodeError:
            pass
        
        return result
    
    def _extract_json(self, text: str) -> Optional[str]:
        import re
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, text)
        if match:
            return match.group(0)
        return None
    
    async def _apply_review_result(self, result: ReviewResult):
        if self.memory_store:
            for mem_update in result.memory_updates:
                try:
                    self.memory_store.add(
                        mem_update["content"],
                        mem_update.get("metadata"),
                    )
                    logger.info(f"Added memory: {mem_update['content'][:50]}...")
                except Exception as e:
                    logger.error(f"Failed to add memory: {e}")
        
        if self.skill_manager:
            for skill_create in result.skill_creates:
                try:
                    self.skill_manager.create_skill(
                        name=skill_create.get("name", "unnamed"),
                        description=skill_create.get("description", ""),
                        when_to_use=skill_create.get("when_to_use", []),
                        steps=skill_create.get("steps", []),
                        pitfalls=skill_create.get("pitfalls", []),
                        category=skill_create.get("category", "general"),
                    )
                    logger.info(f"Created skill: {skill_create.get('name')}")
                except Exception as e:
                    logger.error(f"Failed to create skill: {e}")
            
            for skill_patch in result.skill_patches:
                try:
                    self.skill_manager.patch_skill(
                        name=skill_patch.get("name", ""),
                        old_string=skill_patch.get("old_string", ""),
                        new_string=skill_patch.get("new_string", ""),
                    )
                    logger.info(f"Patched skill: {skill_patch.get('name')}")
                except Exception as e:
                    logger.error(f"Failed to patch skill: {e}")


async def run_background_review(
    model_adapter: Any,
    messages: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    memory_store: Any = None,
    skill_manager: Any = None,
    review_memory: bool = True,
    review_skills: bool = True,
) -> ReviewResult:
    agent = ReviewAgent(
        model_adapter=model_adapter,
        memory_store=memory_store,
        skill_manager=skill_manager,
    )
    return await agent.review_conversation(
        messages=messages,
        tool_results=tool_results,
        review_memory=review_memory,
        review_skills=review_skills,
    )
