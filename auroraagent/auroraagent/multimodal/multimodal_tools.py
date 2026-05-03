"""
多模态工具集
屏幕捕获、图像处理
"""

import asyncio
import base64
import io
import logging
import os
from pathlib import Path
from typing import Optional

from ..tools.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

# 延迟导入依赖
_mss_available = None
_pil_available = None


def check_mss() -> bool:
    """检查 mss 依赖"""
    global _mss_available
    if _mss_available is not None:
        return _mss_available
    
    try:
        import mss
        _mss_available = True
        return True
    except ImportError:
        _mss_available = False
        return False


def check_pil() -> bool:
    """检查 PIL 依赖"""
    global _pil_available
    if _pil_available is not None:
        return _pil_available
    
    try:
        from PIL import Image
        _pil_available = True
        return True
    except ImportError:
        _pil_available = False
        return False


async def screenshot_impl(
    monitor: int = 0,
    save_path: Optional[str] = None,
    return_base64: bool = False,
) -> ToolResult:
    """屏幕截图"""
    try:
        import mss
        import mss.tools
        from PIL import Image
        
        sct = mss.mss()
        
        # 获取指定显示器或主显示器
        if monitor == 0:
            monitor_dict = sct.monitors[1]
        else:
            if monitor >= len(sct.monitors):
                monitor_dict = sct.monitors[1]
            else:
                monitor_dict = sct.monitors[monitor]
        
        # 捕获屏幕
        screenshot = sct.grab(monitor_dict)
        
        # 保存图片
        if save_path:
            save_p = Path(save_path)
            save_p.parent.mkdir(parents=True, exist_ok=True)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=save_p)
        
        # 转换为 PIL
        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb, "raw", "BGRX")
        
        result_parts = [f"Screenshot captured: {screenshot.size[0]}x{screenshot.size[1]}"]
        
        # 返回 base64 或保存路径
        if return_base64:
            # 调整大小以减少令牌消耗
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 转换为 base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            result_parts.append("\n[Image included in context (base64)]")
        else:
            if not save_path:
                # 默认保存到 temp
                import tempfile
                import uuid
                temp_file = Path(tempfile.gettempdir()) / f"screenshot_{uuid.uuid4()}.png"
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=temp_file)
                save_path = str(temp_file)
            result_parts.append(f"Saved to: {save_path}")
        
        return ToolResult(
            success=True,
            output="\n".join(result_parts),
            raw_data=img_base64 if return_base64 else save_path,
        )
    except Exception as e:
        logger.exception("Screenshot failed")
        return ToolResult(success=False, error=str(e))


async def screenshot_region_impl(
    left: int,
    top: int,
    right: int,
    bottom: int,
    save_path: Optional[str] = None,
) -> ToolResult:
    """区域截图"""
    try:
        import mss
        import mss.tools
        from PIL import Image
        
        sct = mss.mss()
        
        monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}
        
        screenshot = sct.grab(monitor)
        
        if save_path:
            save_p = Path(save_path)
            save_p.parent.mkdir(parents=True, exist_ok=True)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=save_p)
            output = f"Region screenshot saved to: {save_path}"
        else:
            import tempfile
            import uuid
            temp_file = Path(tempfile.gettempdir()) / f"screenshot_region_{uuid.uuid4()}.png"
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=temp_file)
            output = f"Region screenshot captured: {right-left}x{bottom-top}, saved to: {temp_file}"
        
        return ToolResult(success=True, output=output)
    except Exception as e:
        logger.exception("Region screenshot failed")
        return ToolResult(success=False, error=str(e))


async def list_monitors_impl() -> ToolResult:
    """列出显示器"""
    try:
        import mss
        sct = mss.mss()
        output = f"Available monitors ({len(sct.monitors)-1}):\n"
        
        for i, m in enumerate(sct.monitors[1:], 1):
            output += f"Monitor {i}: {m['width']}x{m['height']} at ({m['left']}, {m['top']})\n"
        
        return ToolResult(success=True, output=output)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


async def analyze_image_impl(
    image_path: str,
    description: Optional[str] = None,
) -> ToolResult:
    """分析图像（返回给 AI）"""
    try:
        from PIL import Image
        import base64
        import io
        
        img = Image.open(image_path)
        
        # 调整大小
        max_size = 1024
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        output_parts = [f"Image loaded: {img.size[0]}x{img.size[1]}"]
        if description:
            output_parts.append(f"Description: {description}")
        
        return ToolResult(
            success=True,
            output="\n".join(output_parts),
            raw_data=img_base64,
        )
    except Exception as e:
        logger.exception("Image analysis failed")
        return ToolResult(success=False, error=str(e))


def check_requirements() -> bool:
    """检查工具要求"""
    return check_mss() and check_pil()


def register_tools(registry: ToolRegistry):
    """注册多模态工具集"""
    registry.register(
        name="screenshot",
        toolset="multimodal",
        schema={
            "type": "function",
            "function": {
                "name": "screenshot",
                "description": "截取整个屏幕或指定显示器。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "monitor": {
                            "type": "integer",
                            "default": 0,
                            "description": "显示器编号 (0=主显示器, 1,2,...)",
                        },
                        "save_path": {
                            "type": "string",
                            "description": "可选保存路径",
                        },
                        "return_base64": {
                            "type": "boolean",
                            "default": True,
                            "description": "是否在上下文中包含图像 base64",
                        },
                    },
                    "required": [],
                },
            },
        },
        handler=screenshot_impl,
        check_fn=check_requirements,
        description="屏幕截图",
    )
    
    registry.register(
        name="screenshot_region",
        toolset="multimodal",
        schema={
            "type": "function",
            "function": {
                "name": "screenshot_region",
                "description": "截取屏幕指定区域。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "left": {"type": "integer", "description": "左边界 X"},
                        "top": {"type": "integer", "description": "上边界 Y"},
                        "right": {"type": "integer", "description": "右边界 X"},
                        "bottom": {"type": "integer", "description": "下边界 Y"},
                        "save_path": {"type": "string", "description": "可选保存路径"},
                    },
                    "required": ["left", "top", "right", "bottom"],
                },
            },
        },
        handler=screenshot_region_impl,
        check_fn=check_requirements,
        description="区域截图",
    )
    
    registry.register(
        name="list_monitors",
        toolset="multimodal",
        schema={
            "type": "function",
            "function": {
                "name": "list_monitors",
                "description": "列出所有可用显示器信息。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        handler=list_monitors_impl,
        check_fn=check_requirements,
        description="列出显示器",
    )
    
    registry.register(
        name="analyze_image",
        toolset="multimodal",
        schema={
            "type": "function",
            "function": {
                "name": "analyze_image",
                "description": "加载并分析图像（包含在上下文中给 AI）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string", "description": "图像文件路径"},
                        "description": {"type": "string", "description": "可选说明"},
                    },
                    "required": ["image_path"],
                },
            },
        },
        handler=analyze_image_impl,
        check_fn=check_requirements,
        description="分析图像",
    )
