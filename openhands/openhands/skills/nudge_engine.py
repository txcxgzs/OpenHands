"""
Nudge Engine - 学习触发引擎
参考 Hermes Agent 的自进化触发机制
"""

from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import threading
import asyncio
import logging
import os
import contextlib

logger = logging.getLogger(__name__)


@dataclass
class NudgeConfig:
    memory_nudge_interval: int = 10
    skill_nudge_interval: int = 10
    enable_background_review: bool = True
    max_review_iterations: int = 8


@dataclass
class NudgeState:
    turns_since_memory: int = 0
    iterations_since_skill: int = 0
    last_memory_nudge: Optional[datetime] = None
    last_skill_nudge: Optional[datetime] = None
    total_nudges: int = 0


class NudgeEngine:
    """
    学习触发引擎 - 定时提醒 Agent 学习
    参考 Hermes Agent 的 Nudge 机制
    """
    
    def __init__(self, config: Optional[NudgeConfig] = None):
        self.config = config or NudgeConfig()
        self.state = NudgeState()
        self._lock = threading.Lock()
        self._memory_handlers: List[Callable] = []
        self._skill_handlers: List[Callable] = []
        self._review_in_progress = False
    
    def register_memory_handler(self, handler: Callable):
        self._memory_handlers.append(handler)
    
    def register_skill_handler(self, handler: Callable):
        self._skill_handlers.append(handler)
    
    def on_user_turn(self) -> bool:
        with self._lock:
            self.state.turns_since_memory += 1
            
            if self.state.turns_since_memory >= self.config.memory_nudge_interval:
                self.state.turns_since_memory = 0
                self.state.last_memory_nudge = datetime.now()
                self.state.total_nudges += 1
                return True
        return False
    
    def on_tool_iteration(self) -> bool:
        with self._lock:
            self.state.iterations_since_skill += 1
            
            if self.state.iterations_since_skill >= self.config.skill_nudge_interval:
                self.state.iterations_since_skill = 0
                self.state.last_skill_nudge = datetime.now()
                self.state.total_nudges += 1
                return True
        return False
    
    def reset_memory_counter(self):
        with self._lock:
            self.state.turns_since_memory = 0
    
    def reset_skill_counter(self):
        with self._lock:
            self.state.iterations_since_skill = 0
    
    def should_review_memory(self) -> bool:
        return self.on_user_turn()
    
    def should_review_skills(self, tool_call_count: int, had_errors: bool) -> bool:
        return self.on_tool_iteration() or (tool_call_count >= 5 and had_errors)
    
    async def trigger_memory_review(
        self,
        messages: List[Dict[str, Any]],
        memory_store: Any,
    ) -> bool:
        if not self._memory_handlers:
            return False
        
        for handler in self._memory_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(messages, memory_store)
                else:
                    handler(messages, memory_store)
            except Exception as e:
                logger.error(f"Memory handler failed: {e}")
        
        return True
    
    async def trigger_skill_review(
        self,
        messages: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        skill_manager: Any,
    ) -> bool:
        if not self._skill_handlers:
            return False
        
        for handler in self._skill_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(messages, tool_results, skill_manager)
                else:
                    handler(messages, tool_results, skill_manager)
            except Exception as e:
                logger.error(f"Skill handler failed: {e}")
        
        return True
    
    def spawn_background_review(
        self,
        agent_factory: Callable,
        messages_snapshot: List[Dict[str, Any]],
        review_memory: bool = False,
        review_skills: bool = False,
        memory_store: Any = None,
        skill_manager: Any = None,
    ):
        if self._review_in_progress:
            return
        
        if not self.config.enable_background_review:
            return
        
        self._review_in_progress = True
        
        def _run_review():
            try:
                with open(os.devnull, "w") as devnull:
                    with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(
                                self._background_review_task(
                                    agent_factory,
                                    messages_snapshot,
                                    review_memory,
                                    review_skills,
                                    memory_store,
                                    skill_manager,
                                )
                            )
                        finally:
                            loop.close()
            except Exception as e:
                logger.error(f"Background review failed: {e}")
            finally:
                self._review_in_progress = False
        
        thread = threading.Thread(target=_run_review, daemon=True)
        thread.start()
    
    async def _background_review_task(
        self,
        agent_factory: Callable,
        messages: List[Dict[str, Any]],
        review_memory: bool,
        review_skills: bool,
        memory_store: Any,
        skill_manager: Any,
    ):
        review_prompt = self._build_review_prompt(
            messages, review_memory, review_skills
        )
        
        try:
            review_agent = agent_factory(
                max_iterations=self.config.max_review_iterations,
                quiet_mode=True,
            )
            
            review_agent._nudge_engine = None
            
            if memory_store:
                review_agent._memory = memory_store
            if skill_manager:
                review_agent._skill_manager = skill_manager
            
            await review_agent.run_with_message(review_prompt)
            
            logger.info("Background review completed")
        except Exception as e:
            logger.error(f"Review task failed: {e}")
    
    def _build_review_prompt(
        self,
        messages: List[Dict[str, Any]],
        review_memory: bool,
        review_skills: bool,
    ) -> str:
        prompt_parts = [
            "You are a review agent. Analyze the conversation and decide if anything is worth saving.",
            "",
            "IMPORTANT GUIDELINES:",
            "- Look for the CLASS of task, not the exact task.",
            "- PREFER GENERALIZING AN EXISTING SKILL over creating a new one.",
            "- Only save things that will reduce future user steering.",
            "- If nothing is worth saving, just say 'Nothing to save.' and stop.",
            "",
        ]
        
        if review_memory:
            prompt_parts.extend([
                "## Memory Review",
                "Look for facts worth remembering:",
                "- User preferences (communication style, tools they prefer)",
                "- Environment details (OS, project structure, conventions)",
                "- Tool quirks discovered during this session",
                "",
            ])
        
        if review_skills:
            prompt_parts.extend([
                "## Skill Review",
                "Look for procedures worth saving:",
                "- Complex tasks with 5+ tool calls",
                "- Errors encountered and how they were resolved",
                "- User corrections that improved the approach",
                "- Non-trivial workflows discovered",
                "",
            ])
        
        prompt_parts.extend([
            "## Recent Conversation Summary",
            "Analyze the conversation and decide what (if anything) to save.",
        ])
        
        return "\n".join(prompt_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "turns_since_memory": self.state.turns_since_memory,
                "iterations_since_skill": self.state.iterations_since_skill,
                "total_nudges": self.state.total_nudges,
                "last_memory_nudge": self.state.last_memory_nudge.isoformat() if self.state.last_memory_nudge else None,
                "last_skill_nudge": self.state.last_skill_nudge.isoformat() if self.state.last_skill_nudge else None,
                "review_in_progress": self._review_in_progress,
            }
