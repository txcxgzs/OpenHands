"""
Windows 控制工具集
鼠标、键盘、窗口操作
"""

import asyncio
import logging
import sys
from typing import List, Optional, Tuple

from ..tools.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

# 延迟导入依赖
_pyautogui_available = None


def check_pyautogui() -> bool:
    """检查 pyautogui 是否可用"""
    global _pyautogui_available
    if _pyautogui_available is not None:
        return _pyautogui_available
    
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        _pyautogui_available = True
        return True
    except ImportError:
        _pyautogui_available = False
        return False


# === 鼠标工具 ===

async def mouse_position_impl() -> ToolResult:
    """获取当前鼠标位置"""
    try:
        import pyautogui
        x, y = pyautogui.position()
        return ToolResult(success=True, output=f"Mouse position: ({x}, {y})")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def mouse_move_impl(x: int, y: int, duration: float = 0.5) -> ToolResult:
    """移动鼠标到指定坐标"""
    try:
        import pyautogui
        await asyncio.to_thread(pyautogui.moveTo, x, y, duration)
        return ToolResult(success=True, output=f"Moved mouse to ({x}, {y})")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def mouse_click_impl(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    clicks: int = 1,
    interval: float = 0.1,
) -> ToolResult:
    """鼠标点击"""
    try:
        import pyautogui
        
        if x is not None and y is not None:
            await asyncio.to_thread(pyautogui.moveTo, x, y, 0.2)
        
        await asyncio.to_thread(
            pyautogui.click,
            x=x,
            y=y,
            button=button,
            clicks=clicks,
            interval=interval,
        )
        pos_str = f" at ({x}, {y})" if x is not None else ""
        return ToolResult(
            success=True,
            output=f"Clicked {button} button{pos_str} {clicks} times"
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def mouse_scroll_impl(clicks: int, direction: str = "down") -> ToolResult:
    """鼠标滚轮滚动"""
    try:
        import pyautogui
        if direction == "down":
            clicks = -abs(clicks)
        await asyncio.to_thread(pyautogui.scroll, clicks)
        return ToolResult(success=True, output=f"Scrolled {direction} {abs(clicks)} clicks")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def mouse_drag_impl(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 1.0,
    button: str = "left",
) -> ToolResult:
    """鼠标拖拽"""
    try:
        import pyautogui
        await asyncio.to_thread(pyautogui.moveTo, start_x, start_y, 0.2)
        await asyncio.to_thread(pyautogui.dragTo, end_x, end_y, duration, button=button)
        return ToolResult(
            success=True,
            output=f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))


# === 键盘工具 ===

async def key_press_impl(key: str, presses: int = 1, interval: float = 0.1) -> ToolResult:
    """按键"""
    try:
        import pyautogui
        await asyncio.to_thread(pyautogui.press, key, presses=presses, interval=interval)
        return ToolResult(success=True, output=f"Pressed '{key}' {presses} times")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def key_write_impl(text: str, interval: float = 0.05) -> ToolResult:
    """键盘输入文本"""
    try:
        import pyautogui
        await asyncio.to_thread(pyautogui.write, text, interval=interval)
        return ToolResult(success=True, output=f"Wrote: {text}")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def key_hotkey_impl(keys: str) -> ToolResult:
    """组合键"""
    try:
        import pyautogui
        key_list = keys.split("+")
        await asyncio.to_thread(pyautogui.hotkey, *key_list)
        return ToolResult(success=True, output=f"Pressed hotkey: {keys}")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


# === 屏幕工具 ===

async def screen_size_impl() -> ToolResult:
    """获取屏幕尺寸"""
    try:
        import pyautogui
        width, height = pyautogui.size()
        return ToolResult(success=True, output=f"Screen size: {width}x{height}")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


# === 窗口工具 (Windows 特定) ===

async def list_windows_impl() -> ToolResult:
    """列出所有窗口"""
    try:
        if sys.platform == "win32":
            import pygetwindow as gw
            windows = gw.getAllTitles()
            visible_windows = [w for w in windows if w.strip()]
            output = f"Windows ({len(visible_windows)}):\n"
            for i, title in enumerate(visible_windows[:50]):
                output += f"{i+1}. {title}\n"
            if len(visible_windows) > 50:
                output += f"... and {len(visible_windows)-50} more\n"
            return ToolResult(success=True, output=output)
        else:
            return ToolResult(success=False, error="Window listing only available on Windows")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def activate_window_impl(title: str) -> ToolResult:
    """激活窗口"""
    try:
        if sys.platform == "win32":
            import pygetwindow as gw
            win = gw.getWindowsWithTitle(title)
            if not win:
                return ToolResult(success=False, error=f"Window not found: {title}")
            win[0].activate()
            return ToolResult(success=True, output=f"Activated window: {title}")
        else:
            return ToolResult(success=False, error="Window activation only available on Windows")
    except Exception as e:
        return ToolResult(success=False, error=str(e))


# === 截图工具 (已移到 multimodal_tools) ===


def check_requirements() -> bool:
    """检查工具要求"""
    return check_pyautogui()


def register_tools(registry: ToolRegistry):
    """注册 Windows 控制工具集"""
    # === 鼠标工具 ===
    registry.register(
        name="mouse_position",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "mouse_position",
                "description": "获取当前鼠标位置。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        handler=mouse_position_impl,
        check_fn=check_requirements,
        description="获取鼠标位置",
    )
    
    registry.register(
        name="mouse_move",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "mouse_move",
                "description": "移动鼠标到指定坐标 (0,0 为左上角)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X 坐标"},
                        "y": {"type": "integer", "description": "Y 坐标"},
                        "duration": {
                            "type": "number",
                            "description": "移动持续时间（秒）",
                            "default": 0.5,
                        },
                    },
                    "required": ["x", "y"],
                },
            },
        },
        handler=mouse_move_impl,
        check_fn=check_requirements,
        description="移动鼠标",
    )
    
    registry.register(
        name="mouse_click",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "mouse_click",
                "description": "鼠标点击。可选指定坐标位置。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "X 坐标 (可选)"},
                        "y": {"type": "integer", "description": "Y 坐标 (可选)"},
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "default": "left",
                            "description": "按键",
                        },
                        "clicks": {
                            "type": "integer",
                            "default": 1,
                            "description": "点击次数",
                        },
                        "interval": {
                            "type": "number",
                            "default": 0.1,
                            "description": "点击间隔（秒）",
                        },
                    },
                    "required": [],
                },
            },
        },
        handler=mouse_click_impl,
        check_fn=check_requirements,
        description="鼠标点击",
    )
    
    registry.register(
        name="mouse_scroll",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "mouse_scroll",
                "description": "鼠标滚轮滚动。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "clicks": {"type": "integer", "default": 3, "description": "滚动次数"},
                        "direction": {
                            "type": "string",
                            "enum": ["up", "down"],
                            "default": "down",
                            "description": "滚动方向",
                        },
                    },
                    "required": ["clicks"],
                },
            },
        },
        handler=mouse_scroll_impl,
        check_fn=check_requirements,
        description="鼠标滚动",
    )
    
    registry.register(
        name="mouse_drag",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "mouse_drag",
                "description": "鼠标拖拽。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_x": {"type": "integer", "description": "起始 X 坐标"},
                        "start_y": {"type": "integer", "description": "起始 Y 坐标"},
                        "end_x": {"type": "integer", "description": "结束 X 坐标"},
                        "end_y": {"type": "integer", "description": "结束 Y 坐标"},
                        "duration": {"type": "number", "default": 1.0, "description": "拖拽耗时（秒）"},
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "default": "left",
                        },
                    },
                    "required": ["start_x", "start_y", "end_x", "end_y"],
                },
            },
        },
        handler=mouse_drag_impl,
        check_fn=check_requirements,
        description="鼠标拖拽",
    )
    
    # === 键盘工具 ===
    registry.register(
        name="key_press",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "key_press",
                "description": "按一个键。例如: 'a', 'enter', 'tab', 'space' 等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "按键名称"},
                        "presses": {"type": "integer", "default": 1, "description": "按压次数"},
                        "interval": {"type": "number", "default": 0.1, "description": "间隔时间（秒）"},
                    },
                    "required": ["key"],
                },
            },
        },
        handler=key_press_impl,
        check_fn=check_requirements,
        description="按键",
    )
    
    registry.register(
        name="key_write",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "key_write",
                "description": "键盘输入文本字符串。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "要输入的文本"},
                        "interval": {"type": "number", "default": 0.05, "description": "字符间间隔（秒）"},
                    },
                    "required": ["text"],
                },
            },
        },
        handler=key_write_impl,
        check_fn=check_requirements,
        description="键盘输入",
    )
    
    registry.register(
        name="key_hotkey",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "key_hotkey",
                "description": "组合键。例如: 'ctrl+c', 'ctrl+v', 'ctrl+z', 'win+d' 等。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keys": {"type": "string", "description": "组合键字符串，用 + 分隔"},
                    },
                    "required": ["keys"],
                },
            },
        },
        handler=key_hotkey_impl,
        check_fn=check_requirements,
        description="组合键",
    )
    
    registry.register(
        name="screen_size",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "screen_size",
                "description": "获取屏幕尺寸。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handler=screen_size_impl,
        check_fn=check_requirements,
        description="屏幕尺寸",
    )
    
    # === 窗口工具 ===
    registry.register(
        name="list_windows",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "list_windows",
                "description": "列出所有可见窗口 (仅 Windows)。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handler=list_windows_impl,
        check_fn=check_requirements,
        description="列出窗口",
    )
    
    registry.register(
        name="activate_window",
        toolset="windows",
        schema={
            "type": "function",
            "function": {
                "name": "activate_window",
                "description": "激活指定窗口 (仅 Windows)。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "窗口标题或标题的一部分"},
                    },
                    "required": ["title"],
                },
            },
        },
        handler=activate_window_impl,
        check_fn=check_requirements,
        description="激活窗口",
    )
