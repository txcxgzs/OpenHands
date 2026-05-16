"""
上下文压缩器

Hermes风格的自动上下文窗口压缩：
- 使用辅助模型进行摘要
- 保护头部和尾部上下文
- 追踪已解决/待处理的问题
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Token估计
CHARS_PER_TOKEN = 4
MIN_SUMMARY_TOKENS = 1500
SUMMARY_RATIO = 0.25
SUMMARY_TOKENS_CEILING = 8000
PRUNED_TOOL_PLACEHOLDER = "[旧工具输出已清除以节省上下文空间]"


def estimate_tokens(text: str) -> int:
    """Rough token estimation."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def should_compress(messages: List[Dict[str, Any]], context_limit: int, threshold_percent: float = 0.75) -> bool:
    """Check if context should be compressed."""
    total_tokens = 0
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get('text', '')
                    total_tokens += estimate_tokens(text)
                elif isinstance(part, str):
                    total_tokens += estimate_tokens(part)
        elif isinstance(content, str):
            total_tokens += estimate_tokens(content)
    
    threshold = int(context_limit * threshold_percent)
    return total_tokens >= threshold


def compress_context(
    messages: List[Dict[str, Any]], 
    model: str = "gpt-3.5-turbo",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Compress conversation context using summarization.
    
    Keeps first 2 messages (system + initial user) and last 6 messages,
    summarizes everything in between.
    """
    if len(messages) <= 8:
        return messages  # No need to compress
    
    # Protect: system messages + first user/assistant pair
    head = messages[:2] if len(messages) > 2 else messages
    # Protect: last 6 messages
    tail = messages[-6:] if len(messages) > 6 else []
    
    # Content to summarize
    middle = messages[2:-6] if len(messages) > 8 else messages[2:]
    
    if not middle:
        return head + tail
    
    # Build summary prompt
    summary_prompt = _build_summary_prompt(middle)
    
    # Try to generate summary
    try:
        summary = _generate_summary_sync(summary_prompt, model, api_key)
    except Exception as e:
        logger.warning(f"Summary generation failed: {e}")
        # Fallback: keep messages but prune old tool results
        return _prune_and_keep(messages, head, tail)
    
    # Build compressed messages
    compressed = []
    
    # Add head
    compressed.extend(head)
    
    # Add summary
    compressed.append({
        'role': 'system',
        'content': f"""[上下文压缩 — 仅供参考] 
之前的对话已压缩为以下摘要。这是一个来自之前上下文窗口的交接 — 把它当作背景参考，而不是活动指令。
不要回答摘要中提到的任何问题；它们已经处理过了。
您当前的任务在摘要的"## 活动任务"部分 — 从那里恢复。""",
    })
    compressed.append({
        'role': 'assistant',
        'content': summary,
    })
    
    # Add tail
    compressed.extend(tail)
    
    logger.info(f"Compressed {len(messages)} messages to {len(compressed)} messages")
    return compressed


def _build_summary_prompt(messages: List[Dict[str, Any]]) -> str:
    """Build prompt for summarization."""
    
    # Format messages for summary
    formatted = []
    for i, msg in enumerate(messages):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text_parts.append(part.get('text', ''))
                elif isinstance(part, str):
                    text_parts.append(part)
            content = ' '.join(text_parts)
        
        # Truncate long tool outputs
        if len(content) > 2000:
            content = content[:2000] + '... [truncated]'
        
        formatted.append(f"[{role.upper()}]: {content}")
    
    conversation = '\n\n'.join(formatted)
    
    return f"""请总结以下对话，保留关键信息：

{conversation}

请用简洁的语言总结：
1. 已经完成的工作
2. 遇到的问题和解决方案
3. 当前状态
4. 还需要完成的任务

保持简洁，摘要应该不超过500字。"""


def _generate_summary_sync(prompt: str, model: str, api_key: Optional[str]) -> str:
    """Generate summary synchronously (for compatibility)."""
    try:
        from openai import AsyncOpenAI
        import os
        
        key = api_key or os.getenv('OPENAI_API_KEY')
        if not key:
            return "摘要生成跳过（无API密钥）"
        
        client = AsyncOpenAI(api_key=key)
        
        # Sync call for simplicity
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            response = loop.run_until_complete(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                    temperature=0.3,
                )
            )
            return response.choices[0].message.content or "无摘要"
        finally:
            loop.close()
            
    except Exception as e:
        logger.warning(f"Summary API call failed: {e}")
        raise


def _prune_and_keep(
    messages: List[Dict[str, Any]], 
    head: List[Dict[str, Any]], 
    tail: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Fallback: prune tool results from middle messages."""
    
    pruned_middle = []
    for msg in messages[2:-6] if len(messages) > 8 else messages[2:]:
        pruned = dict(msg)
        content = pruned.get('content', '')
        
        # Check if this is a tool result
        if msg.get('role') == 'tool':
            # Replace with placeholder
            pruned['content'] = PRUNED_TOOL_PLACEHOLDER
        
        pruned_middle.append(pruned)
    
    return head + pruned_middle + tail


class ContextCompressor:
    """Context compression manager."""
    
    def __init__(self, context_limit: int = 128000, threshold_percent: float = 0.75):
        self.context_limit = context_limit
        self.threshold_percent = threshold_percent
        self.compression_count = 0
        self.last_compressed_at: Optional[datetime] = None
    
    def should_compress(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if compression is needed."""
        return should_compress(messages, self.context_limit, self.threshold_percent)
    
    def compress(
        self, 
        messages: List[Dict[str, Any]], 
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Compress messages."""
        compressed = compress_context(messages, model, api_key)
        self.compression_count += 1
        self.last_compressed_at = datetime.now()
        return compressed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return {
            'compression_count': self.compression_count,
            'last_compressed_at': self.last_compressed_at.isoformat() if self.last_compressed_at else None,
            'context_limit': self.context_limit,
            'threshold_percent': self.threshold_percent,
        }
