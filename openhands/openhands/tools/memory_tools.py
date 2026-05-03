
"""
Memory Tools
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def register_tools(registry, memory_store):
    """Register memory tools to registry"""

    @registry.register_tool(
        name="memory_add",
        description="Add information to memory",
        toolset="memory",
        parameters={
            "key": {"type": "string", "description": "Key for memory entry"},
            "value": {"type": "string", "description": "Value/content to remember"},
        },
    )
    async def memory_add(key: str, value: str) -> str:
        """Add to memory"""
        content = f"{key}: {value}"
        item_id = await memory_store.add(content)
        return f"Added to memory (ID: {item_id}) - {key}: {value}"

    @registry.register_tool(
        name="memory_search",
        description="Search memory for information",
        toolset="memory",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "number", "description": "Max results"},
        },
    )
    async def memory_search(query: str, limit: int = 5) -> str:
        """Search memory"""
        results = await memory_store.search(query, limit=limit)
        if not results:
            return "No matching memories found"

        output = []
        for i, (item, score) in enumerate(results, 1):
            output.append(f"[{i}] (Score: {score:.2f})\n{item.content}")

        return "\n\n".join(output)

    @registry.register_tool(
        name="memory_list",
        description="List all memories",
        toolset="memory",
        parameters={},
    )
    async def memory_list(limit: int = 10) -> str:
        """List memories"""
        items = memory_store.list_all(limit=limit)
        if not items:
            return "No memories stored"

        output = []
        for i, item in enumerate(items, 1):
            snippet = item.content[:100]
            if len(item.content) > 100:
                snippet += "..."
            output.append(f"[{i}] {item.id} - {snippet}")

        return "\n".join(output)

    logger.debug("Memory tools registered")
