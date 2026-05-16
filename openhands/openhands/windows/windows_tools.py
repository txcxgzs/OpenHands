
"""
Windows Automation Tools
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def register_tools(registry):
    """Register Windows automation tools"""

    @registry.register_tool(
        name="mouse_click",
        description="Click at screen position",
        toolset="windows",
        parameters={
            "x": {"type": "number", "description": "X coordinate"},
            "y": {"type": "number", "description": "Y coordinate"},
            "button": {"type": "string", "description": "left, right, or middle"},
        },
    )
    async def mouse_click(x: int, y: int, button: str = "left") -> str:
        try:
            import pyautogui
            pyautogui.click(x, y, button=button)
            return f"Clicked at ({x}, {y}) with {button} button"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="mouse_move",
        description="Move mouse to position",
        toolset="windows",
        parameters={
            "x": {"type": "number", "description": "X coordinate"},
            "y": {"type": "number", "description": "Y coordinate"},
        },
    )
    async def mouse_move(x: int, y: int) -> str:
        try:
            import pyautogui
            pyautogui.moveTo(x, y)
            return f"Moved mouse to ({x}, {y})"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="key_press",
        description="Press keyboard keys",
        toolset="windows",
        parameters={
            "keys": {"type": "string", "description": "Keys to press (e.g., 'ctrl+c')"},
        },
    )
    async def key_press(keys: str) -> str:
        try:
            import pyautogui
            pyautogui.hotkey(*keys.split("+"))
            return f"Pressed: {keys}"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="type_text",
        description="Type text",
        toolset="windows",
        parameters={
            "text": {"type": "string", "description": "Text to type"},
            "interval": {"type": "number", "description": "Interval between keystrokes"},
        },
    )
    async def type_text(text: str, interval: float = 0.05) -> str:
        try:
            import pyautogui
            pyautogui.write(text, interval=interval)
            return f"Typed: {text[:50]}..."
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="screenshot",
        description="Capture screenshot",
        toolset="windows",
        parameters={},
    )
    async def screenshot() -> str:
        try:
            import pyautogui
            import base64
            from pathlib import Path
            from datetime import datetime

            Path("./data/screenshots").mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"./data/screenshots/screenshot_{timestamp}.png"
            pyautogui.screenshot(filepath)
            return f"Screenshot saved: {filepath}"
        except Exception as e:
            return f"Error: {e}"

    @registry.register_tool(
        name="get_screen_size",
        description="Get screen dimensions",
        toolset="windows",
        parameters={},
    )
    async def get_screen_size() -> str:
        try:
            import pyautogui
            size = pyautogui.size()
            return f"Screen size: {size.width}x{size.height}"
        except Exception as e:
            return f"Error: {e}"

    logger.debug("Windows tools registered")
