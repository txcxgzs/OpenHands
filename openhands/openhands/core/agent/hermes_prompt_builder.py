"""
Hermes Agent 完整提示词架构
按 Hermes 官方架构实现：
1. Agent 身份层
2. 帮助引导层
3. 工具感知行为层
4. 看板协议层
5. Nous订阅层
6. 工具强制执行层
7. 模型特定指令层
8. 自定义系统消息层
9. 持久记忆层
10. 用户档案层
11. 外部记忆层
12. 技能索引层
13. 项目上下文层
14. 时间戳层
15. 环境提示层
16. 平台格式层
"""

import logging
import os
import re
import json
from pathlib import Path
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# 默认工作空间
DEFAULT_WORKSPACE = Path("./workspace/openhands-workspace")

# ===========================================
# 1. 默认 Agent 身份 (DEFAULT_AGENT_IDENTITY)
# ===========================================
DEFAULT_AGENT_IDENTITY = """You are OpenHands Agent, an intelligent AI assistant. You are helpful, knowledgeable, and direct. You assist users with a wide range of tasks including answering questions, writing and editing code, analyzing information, creative work, and executing actions via your tools. You communicate clearly, admit uncertainty when appropriate, and prioritize being genuinely useful over being verbose unless otherwise directed below. Be targeted and efficient in your exploration and investigations."""

# ===========================================
# 2. 帮助引导提示 (HERMES_HELP_GUIDANCE)
# ===========================================
HERMES_HELP_GUIDANCE = """If the user asks about configuring, setting up, or using OpenHands Agent itself, load the appropriate documentation before answering.
"""

# ===========================================
# 3. 记忆行为引导提示 (MEMORY_GUIDANCE)
# ===========================================
MEMORY_GUIDANCE = """You have persistent memory across sessions. Save durable facts using the memory tool: user preferences, environment details, tool quirks, and stable conventions. Memory is injected into every turn, so keep it compact and focused on facts that will still matter later.

Prioritize what reduces future user steering — the most valuable memory is one that prevents the user from having to correct or remind you again. User preferences and recurring corrections matter more than procedural task details.

Do NOT save task progress, session outcomes, completed-work logs, or temporary TODO state to memory; use session_search to recall those from past transcripts. If you've discovered a new way to do something, solved a problem that could be necessary later, save it as a skill with the skill tool.

Write memories as declarative facts, not instructions to yourself.
'User prefers concise responses' ✓ -- 'Always respond concisely' ✗
'Project uses pytest with xdist' ✓ -- 'Run tests with pytest -n 4' ✗
Imperative phrasing gets re-read as a directive in later sessions and can cause repeated work or override the user's current request. Procedures and workflows belong in skills, not memory."""

# ===========================================
# 4. 会话搜索引导提示 (SESSION_SEARCH_GUIDANCE)
# ===========================================
SESSION_SEARCH_GUIDANCE = """When the user references something from a past conversation or you suspect relevant cross-session context exists, use session_search to recall it before asking them to repeat themselves.
"""

# ===========================================
# 5. 技能行为引导提示 (SKILLS_GUIDANCE)
# ===========================================
SKILLS_GUIDANCE = """After completing a complex task (5+ tool calls), fixing a tricky error, or discovering a non-trivial workflow, save the approach as a skill with skill_manage so you can reuse it next time.

When using a skill and finding it outdated, incomplete, or wrong, patch it immediately with skill_manage(action='patch') -- don't wait to be asked. Skills that aren't maintained become liabilities.
"""

# ===========================================
# 6. 工具使用强制执行提示 (TOOL_USE_ENFORCEMENT)
# ===========================================
TOOL_USE_ENFORCEMENT = """# Tool-use enforcement
You MUST use your tools to take action -- do not describe what you would do or plan to do without actually doing it. When you say you will perform an action (e.g. 'I will run the tests', 'Let me check the file', 'I will create the project'), you MUST immediately make the corresponding tool call in the same response. Never end your turn with a promise of future action -- execute it now.

Keep working until the task is actually complete. Do not stop with a summary of what you plan to do next time. If you have tools available that can accomplish the task, use them instead of telling the user what you would do.

Every response should either (a) contain tool calls that make progress, or (b) deliver a final result to the user. Responses that only describe intentions without acting are not acceptable."""

# ===========================================
# 7. OpenAI 模型执行纪律提示 (OPENAI_EXECUTION_DISCIPLINE)
# ===========================================
OPENAI_EXECUTION_DISCIPLINE = """# Execution discipline
<tool_persistence>
- Use tools whenever they improve correctness, completeness, or grounding.
- Do not stop early when another tool call would materially improve the result.
- If a tool returns empty or partial results, retry with a different query or strategy before giving up.
- Keep calling tools until: (1) the task is complete, AND (2) you have verified the result.
</tool_persistence>

<mandatory_tool_use>
NEVER answer these from memory or mental computation -- ALWAYS use a tool:
- Arithmetic, math, calculations -> use terminal or execute_code
- Hashes, encodings, checksums -> use terminal (e.g. sha256sum, base64)
- Current time, date, timezone -> use terminal (e.g. date)
- System state: OS, CPU, memory, disk, ports, processes -> use terminal
- File contents, sizes, line counts -> use read_file, search_files, or terminal
- Git history, branches, diffs -> use terminal
- Current facts (weather, news, versions) -> use web_search
Your memory and user profile describe the USER, not the system you are running on. The execution environment may differ from what the user profile says about their personal setup.
</mandatory_tool_use>

<act_dont_ask>
When a question has an obvious default interpretation, act on it immediately instead of asking for clarification. Examples:
- 'Is port 443 open?' -> check THIS machine (don't ask 'open where?')
- 'What OS am I running?' -> check the live system (don't use user profile)
- 'What time is it?' -> run `date` (don't guess)
Only ask for clarification when the ambiguity genuinely changes what tool you would call.
</act_dont_ask>

<prerequisite_checks>
- Before taking an action, check whether prerequisite discovery, lookup, or context-gathering steps are needed.
- Do not skip prerequisite steps just because the final action seems obvious.
- If a task depends on output from a prior step, resolve that dependency first.
</prerequisite_checks>

<verification>
Before finalizing your response:
- Correctness: does the output satisfy every stated requirement?
- Grounding: are factual claims backed by tool outputs or provided context?
- Formatting: does the output match the requested format or schema?
- Safety: if the next step has side effects (file writes, commands, API calls), confirm scope before executing.
</verification>

<missing_context>
- If required context is missing, do NOT guess or hallucinate an answer.
- Use the appropriate lookup tool when missing information is retrievable (search_files, web_search, read_file, etc.).
- Ask a clarifying question only when the information cannot be retrieved by tools.
- If you must proceed with incomplete information, label assumptions explicitly.
</missing_context>"""

# ===========================================
# 8. Google 模型操作指令提示 (GOOGLE_OPERATIONAL_DIRECTIVES)
# ===========================================
GOOGLE_OPERATIONAL_DIRECTIVES = """# Google model operational directives
Follow these operational rules strictly:
- **Absolute paths:** Always construct and use absolute file paths for all file system operations. Combine the project root with relative paths.
- **Verify first:** Use read_file/search_files to check file contents and project structure before making changes. Never guess at file contents.
- **Dependency checks:** Never assume a library is available. Check package.json, requirements.txt, Cargo.toml, etc. before importing.
- **Conciseness:** Keep explanatory text brief -- a few sentences, not paragraphs. Focus on actions and results over narration.
- **Parallel tool calls:** When you need to perform multiple independent operations (e.g. reading several files), make all the tool calls in a single response rather than sequentially.
- **Non-interactive commands:** Use flags like -y, --yes, --non-interactive to prevent CLI tools from hanging on prompts.
- **Keep going:** Work autonomously until the task is fully resolved. Don't stop with a plan -- execute it.
"""

# ===========================================
# 9. 看板任务执行协议提示 (KANBAN_GUIDANCE)
# ===========================================
KANBAN_GUIDANCE = """# Kanban task execution protocol
You have been assigned ONE task from the shared board at `~/.openhands/kanban.db`. Your task id is in `$OPENHANDS_KANBAN_TASK`; your workspace is `$OPENHANDS_KANBAN_WORKSPACE`. The `kanban_*` tools in your schema are your primary coordination surface -- they write directly to the shared SQLite DB and work regardless of terminal backend (local/docker/modal/ssh).

## Lifecycle

1. **Orient.** Call `kanban_show()` first (no args -- it defaults to your task). The response includes title, body, parent-task handoffs (summary + metadata), any prior attempts on this task if you're a retry, the full comment thread, and a pre-formatted `worker_context` you can treat as ground truth.

2. **Work inside the workspace.** `cd $OPENHANDS_KANBAN_WORKSPACE` before any file operations. The workspace is yours for this run. Don't modify files outside it unless the task explicitly asks.

3. **Heartbeat on long operations.** Call `kanban_heartbeat(note=...)` every few minutes during long subprocesses (training, encoding, crawling). Skip heartbeats for short tasks.

4. **Block on genuine ambiguity.** If you need a human decision you cannot infer (missing credentials, UX choice, paywalled source, peer output you need first), call `kanban_block(reason="...")` and stop. Don't guess. The user will unblock with context and the dispatcher will respawn you.

5. **Complete with structured handoff.** Call `kanban_complete(summary=..., metadata=...)`. `summary` is 1-3 human-readable sentences naming concrete artifacts. `metadata` is machine-readable facts ({changed_files: [...], tests_run: N, decisions: [...]}). Downstream workers read both via their own `kanban_show`. Never put secrets / tokens / raw PII in either field -- run rows are durable forever.

6. **If follow-up work appears, create it; don't do it.** Use `kanban_create(title=..., assignee=<right-profile>, parents=[your-task-id])` to spawn a child task for the appropriate specialist profile instead of scope-creeping into the next thing.

## Orchestrator mode
If your task is itself a decomposition task (e.g. a planner profile given a high-level goal), use `kanban_create` to fan out into child tasks -- one per specialist, each with an explicit `assignee` and `parents=[...]` to express dependencies. Then `kanban_complete` your own task with a summary of the decomposition. Do NOT execute the work yourself; your job is routing, not implementation.

## Do NOT
- Do not shell out to `openhands kanban <verb>` for board operations. Use the `kanban_*` tools -- they work across all terminal backends.
- Do not complete a task you didn't actually finish. Block it.
- Do not assign follow-up work to yourself. Assign it to the right specialist profile.
- Do not call `delegate_task` as a board substitute. `delegate_task` is for short reasoning subtasks inside your own run; board tasks are for cross-agent handoffs that outlive one API loop.
"""

# ===========================================
# 10. Nous 订阅能力提示 (NOUS_SUBSCRIPTION)
# ===========================================
NOUS_SUBSCRIPTION = """# Nous Subscription
Nous subscription includes managed web tools (Firecrawl), image generation (FAL), OpenAI TTS, and browser automation (Browser Use) by default. Modal execution is optional.

Current capability status:
- Web crawling: available
- Image generation: available
- Text-to-speech: available
- Browser automation: available

When a Nous-managed feature is active, do not ask the user for Firecrawl, FAL, OpenAI TTS, or Browser-Use API keys.
If the user is not subscribed and asks for a capability that Nous subscription would unlock or simplify, suggest Nous subscription as one option alongside direct setup or local alternatives.
Do not mention subscription unless the user asks about it or it directly solves the current missing capability.

Useful commands: openhands setup, openhands setup tools, openhands setup terminal, openhands status.
"""

# ===========================================
# 11. 上下文文件安全扫描规则
# ===========================================
THREAT_PATTERNS = [
    # 提示注入
    (re.compile(r'ignore\s+(previous|all|above|prior)\s+instructions', re.IGNORECASE), "prompt_injection"),
    (re.compile(r'do\s+not\s+tell\s+the\s+user', re.IGNORECASE), "deception_hiding"),
    (re.compile(r'system\s+prompt\s+override', re.IGNORECASE), "system_prompt_override"),
    (re.compile(r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', re.IGNORECASE), "rule_bypass"),
    (re.compile(r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don't\s+have)\s+(restrictions|limits|rules)', re.IGNORECASE), "limit_bypass"),
    (re.compile(r'<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->', re.IGNORECASE), "html_injection"),
    (re.compile(r'<\s*div\s+style\s*=\s*["'][\s\S]*?display\s*:\s*none', re.IGNORECASE), "hidden_div"),
    (re.compile(r'translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)', re.IGNORECASE), "translation_execution"),
    (re.compile(r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', re.IGNORECASE), "credential_leak"),
    (re.compile(r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass)', re.IGNORECASE), "secret_access"),
]

# 不可见字符检测
INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u200e', '\u200f',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
    '\u2060', '\u2061', '\u2062', '\u2063', '\u2064',
    '\ufeff', '\xad'
}

# ===========================================
# 12. 平台特定提示 (PLATFORM_HINTS)
# ===========================================
PLATFORM_HINTS = {
    "cli": """You are a CLI AI Agent. Try not to use markdown but simple text renderable inside a terminal. File delivery: there is no attachment channel -- the user reads your response directly in their terminal. Do NOT emit MEDIA:/path tags. When referring to a file you created or changed, just state its absolute path in plain text.""",
    "web": "",  # Default, no special hints
    "discord": """You are in a Discord server or group chat. You can send media files natively: include MEDIA:/absolute/path/to/file. Images are sent as photo attachments, audio as file attachments.""",
    "telegram": """You are on Telegram. Standard markdown is auto-converted to Telegram format. Supported: **bold**, *italic*, ~~strikethrough~~, ||spoiler||, `inline code`, ```code blocks```, [links](url), ## headers. No table syntax -- prefer bullet lists. You can send media: include MEDIA:/absolute/path/to/file.""",
    "slack": """You are in a Slack workspace. You can send media files natively: include MEDIA:/absolute/path/to/file. Images are uploaded as photo attachments, audio as file attachments.""",
    "email": """You are communicating via email. Write clear, well-structured responses. Use plain text formatting (no markdown). Keep responses concise but complete. You can send file attachments -- include MEDIA:/absolute/path/to/file.""",
    "whatsapp": """You are on a text messaging communication platform, WhatsApp. Please do not use markdown as it does not render. You can send media files natively: to deliver a file to the user, include MEDIA:/absolute/path/to/file. Images appear as photos, videos play inline, and other files arrive as downloadable documents.""",
    "signal": """You are on Signal. Please do not use markdown as it does not render. You can send media files natively: include MEDIA:/absolute/path/to/file. Images appear as photos, audio as attachments.""",
    "cron": """You are running as a scheduled cron job. There is no user present -- you cannot ask questions, request clarification, or wait for follow-up. Execute the task fully and autonomously, making reasonable decisions where needed.""",
    "sms": """You are communicating via SMS. Keep responses concise and use plain text only -- no markdown, no formatting. SMS messages are limited to ~1600 characters.""",
    "bluebubbles": """You are chatting via iMessage (BlueBubbles). iMessage does not render markdown formatting -- use plain text. Keep responses concise. You can send media files natively: include MEDIA:/absolute/path/to/file.""",
    "mattermost": """You are in a Mattermost workspace. Standard Markdown works. You can send media files natively: include MEDIA:/absolute/path/to/file.""",
    "matrix": """You are in a Matrix room. Markdown works -- bold, italic, code blocks, and links. You can send media files natively: include MEDIA:/absolute/path/to/file.""",
    "feishu": """You are in a Feishu (Lark) workspace. Markdown is supported -- bold, italic, code blocks, and links. You can send media files natively: include MEDIA:/absolute/path/to/file.""",
    "wechat": """You are on Weixin/WeChat. Markdown formatting is supported, but keep the message compact and chat-friendly. You can send media files natively: include MEDIA:/absolute/path/to/file.""",
    "wecom": """You are on WeCom (企业微信). Markdown formatting is supported. You CAN send media files natively -- include MEDIA:/absolute/path/to/file. Images up to 10 MB, documents up to 20 MB. Voice messages must be in AMR format.""",
    "qq": """You are on QQ, a popular Chinese messaging platform. QQ supports markdown formatting and emoji. You can send media files natively: include MEDIA:/absolute/path/to/file.""",
    "yuanbao": """You are on Yuanbao (腾讯元宝). Markdown formatting is supported. You CAN send media files natively -- include MEDIA:/absolute/path/to/file. Images up to GIF supported, documents max 50 MB.

Stickers (贴纸/表情包): Yuanbao has a built-in sticker catalogue. When the user sends a sticker or asks you to send one, you MUST use the sticker tools:
  1. Call yb_search_sticker with a Chinese keyword to discover matching sticker_ids.
  2. Call yb_send_sticker with the chosen sticker_id.
DO NOT draw sticker-like PNGs -- use yb_send_sticker.""",
}

# ===========================================
# 13. 阿里巴巴模型身份覆盖提示
# ===========================================
ALIBABA_MODEL_IDENTITY = """You are powered by the model named {model_short}. The exact model ID is {model}. When asked what model you are, always answer based on this information, not on any model name returned by the API."""

# ===========================================
# WSL环境提示
# ===========================================
WSL_HINT = """You are running inside WSL (Windows Subsystem for Linux). The Windows host filesystem is mounted under /mnt/ -- /mnt/c/ is the C: drive, /mnt/d/ is D:, etc. The user's Windows files are typically at /mnt/c/Users/<username>/Desktop/, Documents/, Downloads/, etc. When the user references Windows paths or desktop files, translate to the /mnt/c/ equivalent. You can list /mnt/c/Users/ to discover the Windows username if needed."""

# ===========================================
# 提示词模式枚举
# ===========================================
class PromptMode(Enum):
    FULL = "full"          # 完整提示词
    MINIMAL = "minimal"    # 子Agent使用，简化版
    NONE = "none"          # 仅身份

# ===========================================
# 模型家族枚举
# ===========================================
class ModelFamily(Enum):
    OPENAI = "openai"    # GPT系列
    GOOGLE = "google"    # Gemini系列
    ANTHROPIC = "anthropic"  # Claude系列
    OTHER = "other"

# ===========================================
# 提示词配置
# ===========================================
@dataclass
class PromptConfig:
    workspace: Path = DEFAULT_WORKSPACE
    mode: PromptMode = PromptMode.FULL
    model_family: ModelFamily = ModelFamily.OTHER
    platform: str = "web"
    include_soul: bool = True
    include_user: bool = True
    include_memory: bool = True
    include_agents: bool = True
    include_skills: bool = True
    include_kanban: bool = False
    include_nous_subscription: bool = False
    include_timestamp: bool = True
    session_id: Optional[str] = None
    model_name: Optional[str] = None
    provider_name: Optional[str] = None
    custom_system_message: Optional[str] = None
    alibaba_model_short: Optional[str] = None

# ===========================================
# 上下文文件配置
# ===========================================
CONTEXT_FILES = [
    # 核心文件
    "AGENTS.md",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    # 常见的项目规则文件
    ".cursorrules",
    "CLAUDE.md",
    "OPENHANDS.md",
    ".env.example",
]

# 上下文文件大小限制
MAX_CONTEXT_FILE_CHARS = 20000
HEAD_TRUNCATE_RATIO = 0.70
TAIL_TRUNCATE_RATIO = 0.20
TRUNCATION_MARKER_RATIO = 0.10

# ===========================================
# 提示词构建器主类
# ===========================================
class PromptBuilder:
    def __init__(self, config: PromptConfig = None):
        self._config = config or PromptConfig()
        self._cache: Dict[str, str] = {}
        self._skills_index_cache: Optional[str] = None
        self._current_session_id = self._config.session_id or f"session-{int(datetime.now().timestamp())}"
    
    def build(self) -> str:
        """按Hermes架构构建完整提示词"""
        parts = []
        
        if self._config.mode == PromptMode.NONE:
            return DEFAULT_AGENT_IDENTITY
        
        # ===========================================
        # 1. Agent 身份层
        # ===========================================
        if self._config.include_soul:
            soul_content = self._read_soul()
            if soul_content:
                parts.append(soul_content)
            else:
                parts.append(DEFAULT_AGENT_IDENTITY)
        else:
            parts.append(DEFAULT_AGENT_IDENTITY)
        
        # ===========================================
        # 2. 帮助引导层
        # ===========================================
        if self._config.mode == PromptMode.FULL:
            parts.append(HERMES_HELP_GUIDANCE)
        
        # ===========================================
        # 3. 工具感知行为层
        # ===========================================
        if self._config.mode == PromptMode.FULL:
            if self._config.include_memory:
                parts.append(MEMORY_GUIDANCE)
            
            if self._config.include_agents:
                parts.append(SESSION_SEARCH_GUIDANCE)
            
            if self._config.include_skills:
                parts.append(SKILLS_GUIDANCE)
        
        # ===========================================
        # 4. 看板协议层
        # ===========================================
        if self._config.include_kanban:
            parts.append(KANBAN_GUIDANCE)
        
        # ===========================================
        # 5. Nous 订阅层
        # ===========================================
        if self._config.include_nous_subscription:
            parts.append(NOUS_SUBSCRIPTION)
        
        # ===========================================
        # 6. 工具强制执行层
        # ===========================================
        if self._should_apply_tool_enforcement():
            parts.append(TOOL_USE_ENFORCEMENT)
        
        # ===========================================
        # 6. 模型特定指令层
        # ===========================================
        if self._config.model_family == ModelFamily.OPENAI:
            parts.append(OPENAI_EXECUTION_DISCIPLINE)
        elif self._config.model_family == ModelFamily.GOOGLE:
            parts.append(GOOGLE_OPERATIONAL_DIRECTIVES)
        
        # ===========================================
        # 7. 自定义系统消息层
        # ===========================================
        if self._config.custom_system_message:
            parts.append(self._config.custom_system_message)
        
        # ===========================================
        # 8. 持久记忆层 (MEMORY.md)
        # ===========================================
        if self._config.include_memory and self._config.mode == PromptMode.FULL:
            memory_content = self._read_context_file("MEMORY.md")
            if memory_content:
                parts.append("""# Persistent Memory
The following memory content is loaded from MEMORY.md:
""" + memory_content)
        
        # ===========================================
        # 9. 用户档案层 (USER.md)
        # ===========================================
        if self._config.include_user and self._config.mode == PromptMode.FULL:
            user_content = self._read_context_file("USER.md")
            if user_content:
                parts.append("""# User Profile
The following user profile is loaded from USER.md:
""" + user_content)
        
        # ===========================================
        # 10. 技能索引层
        # ===========================================
        if self._config.include_skills and self._config.mode == PromptMode.FULL:
            skills_prompt = self._build_skills_system_prompt()
            if skills_prompt:
                parts.append(skills_prompt)
        
        # ===========================================
        # 11. 项目上下文层
        # ===========================================
        context_parts = self._build_project_context()
        if context_parts:
            parts.extend(context_parts)
        
        # ===========================================
        # 12. 时间戳层
        # ===========================================
        if self._config.include_timestamp:
            parts.append(self._build_timestamp())
        
        # ===========================================
        # 13. 环境提示层 (WSL等)
        # ===========================================
        if self._is_wsl():
            parts.append(WSL_HINT)
        
        # ===========================================
        # 14. 平台格式层
        # ===========================================
        if self._config.platform in PLATFORM_HINTS:
            parts.append(PLATFORM_HINTS[self._config.platform])
        
        # ===========================================
        # 15. 阿里巴巴模型身份覆盖
        # ===========================================
        if self._config.alibaba_model_short and self._config.model_name:
            parts.append(ALIBABA_MODEL_IDENTITY.format(
                model_short=self._config.alibaba_model_short,
                model=self._config.model_name
            ))
        
        return "\n\n".join(parts)
    
    def _should_apply_tool_enforcement(self) -> bool:
        """判断是否应用工具强制执行提示"""
        if self._config.model_family in (ModelFamily.OPENAI, ModelFamily.GOOGLE):
            return True
        return False
    
    def _read_soul(self) -> Optional[str]:
        """读取SOUL.md，经过安全扫描"""
        soul_path = self._config.workspace / "SOUL.md"
        
        if not soul_path.exists():
            return None
        
        try:
            content = soul_path.read_text(encoding='utf-8').strip()
            
            # 安全扫描
            threats = self._scan_context_file(content)
            if threats:
                logger.warning(f"Threats detected in SOUL.md: {', '.join(threats)}")
                return None
            
            # 简单截断
            if len(content) > MAX_CONTEXT_FILE_CHARS:
                content = self._truncate_context_file(content, "SOUL.md")
            
            return content
            
        except Exception as e:
            logger.warning(f"Failed to read SOUL.md: {e}")
            return None
    
    def _read_context_file(self, filename: str) -> Optional[str]:
        """读取上下文文件，经过安全扫描和截断"""
        file_path = self._config.workspace / filename
        
        if not file_path.exists():
            return None
        
        try:
            content = file_path.read_text(encoding='utf-8').strip()
            
            # 安全扫描
            threats = self._scan_context_file(content)
            if threats:
                logger.warning(f"Threats detected in {filename}: {', '.join(threats)}")
                return None
            
            # 截断
            if len(content) > MAX_CONTEXT_FILE_CHARS:
                content = self._truncate_context_file(content, filename)
            
            return content
            
        except Exception as e:
            logger.warning(f"Failed to read {filename}: {e}")
            return None
    
    def _scan_context_file(self, content: str) -> List[str]:
        """扫描上下文文件中的威胁"""
        threats = []
        
        # 检查不可见字符
        for char in INVISIBLE_CHARS:
            if char in content:
                threats.append(f"invisible_character_{hex(ord(char))}")
        
        # 检查模式
        for pattern, threat_name in THREAT_PATTERNS:
            if pattern.search(content):
                threats.append(threat_name)
        
        return threats
    
    def _truncate_context_file(self, content: str, filename: str = "context") -> str:
        """按70/20比例截断上下文文件"""
        total_len = len(content)
        head_len = int(MAX_CONTEXT_FILE_CHARS * HEAD_TRUNCATE_RATIO)
        tail_len = int(MAX_CONTEXT_FILE_CHARS * TAIL_TRUNCATE_RATIO)
        
        truncated = content[:head_len] + f"\n[...truncated {filename}: kept {head_len}+{tail_len} of {total_len} chars. Use file tools to read the full file.]\n" + content[-tail_len:]
        
        logger.info(f"Truncated {filename}: kept {head_len}+{tail_len} of {total_len} chars")
        
        return truncated
    
    def _build_skills_system_prompt(self) -> Optional[str]:
        """构建技能索引提示词"""
        skills_dir = self._config.workspace / "skills"
        
        if not skills_dir.exists():
            return None
        
        available_skills = []
        
        try:
            for skill_file in skills_dir.glob("*.md"):
                if skill_file.is_file():
                    skill_name = skill_file.stem
                    available_skills.append(f"  <skill name=\"{skill_name}\" location=\"{skill_file}\" />")
        except Exception as e:
            logger.warning(f"Failed to list skills: {e}")
            return None
        
        if not available_skills:
            return None
        
        return """## Skills (mandatory)
Before replying, scan the skills below. If a skill matches or is even partially relevant to your task, you MUST load it with skill_view(name) and follow its instructions. Err on the side of loading -- it is always better to have context you don't need than to miss critical steps, pitfalls, or established workflows.

Whenever the user asks you to configure, set up, install, enable, disable, modify, or troubleshoot OpenHands Agent itself -- its CLI, config, models, providers, tools, skills -- load the appropriate documentation first.

If a skill has issues, fix it with skill_manage(action='patch').
After difficult/iterative tasks, offer to save as a skill. If a skill you loaded was missing steps, had wrong commands, or needed pitfalls you discovered, update it before finishing.

<available_skills>
""" + "\n".join(available_skills) + """
</available_skills>

Only proceed without loading a skill if genuinely none are relevant to the task."""
    
    def _build_project_context(self) -> List[str]:
        """构建项目上下文"""
        context_parts = []
        project_files = []
        
        for filename in CONTEXT_FILES:
            if filename in ("SOUL.md", "USER.md", "MEMORY.md"):
                continue  # 已在前面处理
            
            content = self._read_context_file(filename)
            if content:
                project_files.append(f"## {filename}\n{content}")
        
        if project_files:
            context_parts.append("""# Project Context

The following project context files have been loaded and should be followed:

""" + "\n\n".join(project_files))
        
        return context_parts
    
    def _build_timestamp(self) -> str:
        """构建时间戳提示"""
        now = datetime.now()
        timestamp = now.strftime("%A, %B %d, %Y %I:%M %p")
        
        parts = [f"Conversation started: {timestamp}"]
        parts.append(f"Session ID: {self._current_session_id}")
        
        if self._config.model_name:
            parts.append(f"Model: {self._config.model_name}")
        
        if self._config.provider_name:
            parts.append(f"Provider: {self._config.provider_name}")
        
        return "\n".join(parts)
    
    def _is_wsl(self) -> bool:
        """检查是否在WSL环境中"""
        try:
            if os.path.exists("/proc/version"):
                with open("/proc/version", "r") as f:
                    return "microsoft" in f.read().lower()
        except:
            pass
        
        return "WSL_DISTRO_NAME" in os.environ
    
    def invalidate_cache(self):
        """使缓存失效"""
        self._cache.clear()
        self._skills_index_cache = None

# ===========================================
# 简化提示词构建器 (Minimal模式，子Agent)
# ===========================================
class MinimalPromptBuilder(PromptBuilder):
    def __init__(self, config: PromptConfig = None):
        config = config or PromptConfig()
        config.mode = PromptMode.MINIMAL
        config.include_soul = False
        config.include_user = False
        config.include_memory = False
        config.include_skills = False
        config.include_timestamp = False
        
        super().__init__(config)
    
    def build(self) -> str:
        """构建简化提示词"""
        parts = [DEFAULT_AGENT_IDENTITY]
        
        # AGENTS.md
        agents_content = self._read_context_file("AGENTS.md")
        if agents_content:
            parts.append("""# Project Rules
""" + agents_content)
        
        # 项目上下文
        context_parts = self._build_project_context()
        if context_parts:
            parts.extend(context_parts)
        
        return "\n\n".join(parts)

# ===========================================
# 工厂函数
# ===========================================
def build_system_prompt(
    mode: PromptMode = PromptMode.FULL,
    workspace: Path = None,
    model_family: ModelFamily = ModelFamily.OTHER,
    platform: str = "web",
    session_id: Optional[str] = None,
    model_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    custom_system_message: Optional[str] = None,
    include_nous_subscription: bool = False,
    alibaba_model_short: Optional[str] = None,
) -> str:
    """快速构建系统提示词"""
    config = PromptConfig(
        workspace=workspace or DEFAULT_WORKSPACE,
        mode=mode,
        model_family=model_family,
        platform=platform,
        session_id=session_id,
        model_name=model_name,
        provider_name=provider_name,
        custom_system_message=custom_system_message,
        include_nous_subscription=include_nous_subscription,
        alibaba_model_short=alibaba_model_short,
    )
    
    if mode == PromptMode.NONE:
        return DEFAULT_AGENT_IDENTITY
    elif mode == PromptMode.MINIMAL:
        return MinimalPromptBuilder(config).build()
    else:
        return PromptBuilder(config).build()

# 全局构建器
_primary_builder: Optional[PromptBuilder] = None

def get_prompt_builder(config: PromptConfig = None) -> PromptBuilder:
    """获取提示词构建器"""
    global _primary_builder
    if _primary_builder is None or config is not None:
        _primary_builder = PromptBuilder(config)
    return _primary_builder

