
"""
Multimodal Tools
"""

import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register multimodal tools"""

    @registry.register_tool(
        name="capture_region",
        description="Capture a region of the screen",
        toolset="multimodal",
        parameters={
            "x": {"type": "number", "description": "X coordinate"},
            "y": {"type": "number", "description": "Y coordinate"},
            "width": {"type": "number", "description": "Width"},
            "height": {"type": "number", "description": "Height"},
        },
    )
    async def capture_region(x: int, y: int, width: int, height: int) -> str:
        try:
            import mss
            from pathlib import Path
            from datetime import datetime

            Path("./data/screenshots").mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"./data/screenshots/region_{timestamp}.png"

            with mss.mss() as sct:
                region = {"top": y, "left": x, "width": width, "height": height}
                sct.shot(output=filepath, region=region)

            return f"Region captured: {filepath}"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="list_monitors",
        description="List available monitors",
        toolset="multimodal",
        parameters={},
    )
    async def list_monitors() -> str:
        try:
            import mss

            with mss.mss() as sct:
                monitors = sct.monitors
                result = []
                for i, mon in enumerate(monitors):
                    result.append(f"Monitor {i}: {mon['width']}x{mon['height']}")
                return "\n".join(result)
        except Exception as e:
            return f"Error: {e}"

    logger.debug("Multimodal tools registered")
