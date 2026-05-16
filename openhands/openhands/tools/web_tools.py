"""
Web Tools - References OpenClaw's web toolset
"""

import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register web tools"""

    @registry.register_tool(
        name="web_search",
        description="Search the web",
        toolset="web",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "number", "description": "Max results"},
        },
    )
    async def web_search(query: str, limit: int = 5) -> str:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json"},
                    timeout=10.0,
                )

            if response.status_code == 200:
                data = response.json()
                results = []

                if "RelatedTopics" in data:
                    for item in data["RelatedTopics"][:limit]:
                        if "Text" in item:
                            results.append(f"- {item['Text']}")

                if results:
                    return f"Search results for '{query}':\n\n" + "\n".join(results)
                return "No results found"

            return f"Search failed: HTTP {response.status_code}"
        except Exception as e:
            return f"Search error: {e}"

    @registry.register_tool(
        name="web_fetch",
        description="Fetch webpage content",
        toolset="web",
        parameters={
            "url": {"type": "string", "description": "URL to fetch"},
            "max_length": {"type": "number", "description": "Max content length"},
        },
    )
    async def web_fetch(url: str, max_length: int = 4000) -> str:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=15.0)

            if response.status_code == 200:
                content = response.text[:max_length]
                if len(response.text) > max_length:
                    content += f"\n\n[... truncated, total {len(response.text)} chars]"
                return content

            return f"Fetch failed: HTTP {response.status_code}"
        except Exception as e:
            return f"Fetch error: {e}"

    logger.debug("Web tools registered")
