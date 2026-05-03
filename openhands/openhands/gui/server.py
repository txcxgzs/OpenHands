
"""
Web GUI for OpenHands
FastAPI + HTML/JS frontend
实时屏幕预览和控制
"""

import asyncio
import logging
import base64
import json
import os
from pathlib import Path
from datetime import datetime

# 显式加载.env文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None

from openhands import EmbeddedAgent, AgentConfig

logger = logging.getLogger(__name__)

if FASTAPI_AVAILABLE:
    app = FastAPI(title="OpenHands GUI")
else:
    app = None


class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message, websocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")

    async def broadcast(self, message):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"广播失败: {e}")


manager = ConnectionManager()

agent = None
current_session = None
is_controlling = False
action_count = 0


def get_app():
    """获取FastAPI应用实例"""
    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI not installed. Install with: pip install fastapi uvicorn")
        return None
    return app


async def capture_screenshot():
    """捕获屏幕截图并返回 base64"""
    try:
        import pyautogui
        from io import BytesIO
        
        screenshot = pyautogui.screenshot()
        buffer = BytesIO()
        screenshot.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return None


async def execute_windows_action(action, params):
    """执行 Windows 控制操作"""
    global action_count
    
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        
        result = {"success": True, "action": action}
        
        if action == "click":
            x, y = params.get("x", 0), params.get("y", 0)
            button = params.get("button", "left")
            pyautogui.click(x, y, button=button)
            result["content"] = f"点击 ({x}, {y})"
            result["x"], result["y"] = x, y
            
        elif action == "double_click":
            x, y = params.get("x", 0), params.get("y", 0)
            pyautogui.doubleClick(x, y)
            result["content"] = f"双击 ({x}, {y})"
            result["x"], result["y"] = x, y
            
        elif action == "right_click":
            x, y = params.get("x", 0), params.get("y", 0)
            pyautogui.rightClick(x, y)
            result["content"] = f"右键点击 ({x}, {y})"
            result["x"], result["y"] = x, y
            
        elif action == "move":
            x, y = params.get("x", 0), params.get("y", 0)
            pyautogui.moveTo(x, y, duration=0.2)
            result["content"] = f"移动到 ({x}, {y})"
            result["x"], result["y"] = x, y
            
        elif action == "drag":
            x, y = params.get("x", 0), params.get("y", 0)
            pyautogui.dragTo(x, y, duration=0.5)
            result["content"] = f"拖拽到 ({x}, {y})"
            
        elif action == "type":
            text = params.get("text", "")
            interval = params.get("interval", 0.05)
            pyautogui.write(text, interval=interval)
            result["content"] = f"输入: {text[:50]}"
            
        elif action == "hotkey":
            keys = params.get("keys", "")
            key_list = keys.split("+")
            pyautogui.hotkey(*key_list)
            result["content"] = f"快捷键: {keys})"
            result["keys"] = keys
            
        elif action == "press":
            key = params.get("key", "")
            pyautogui.press(key)
            result["content"] = f"按键: {key}"
            
        elif action == "scroll":
            direction = params.get("direction", "down")
            clicks = params.get("clicks", 3)
            if direction == "down":
                pyautogui.scroll(-clicks)
            else:
                pyautogui.scroll(clicks)
            result["content"] = f"滚动: {direction}"
            
        elif action == "screenshot":
            screenshot_b64 = await capture_screenshot()
            if screenshot_b64:
                result["image"] = screenshot_b64
                result["content"] = "截图成功"
            else:
                result["success"] = False
                result["content"] = "截图失败"
        
        action_count += 1
        return result
        
    except Exception as e:
        logger.error(f"执行操作失败: {action}", exc_info=True)
        return {"success": False, "action": action, "error": str(e)}


class AgentProgressCallback:
    """Agent运行时的进度回调"""
    def __init__(self, websocket, manager):
        self.websocket = websocket
        self.manager = manager
        
    async def on_status(self, status):
        """状态更新"""
        logger.info(f"Agent状态: {status}")
        await self.manager.send_message({
            "type": "status",
            "content": status
        }, self.websocket)
        
    async def on_tool_call(self, tool_name, arguments):
        """工具调用开始"""
        logger.info(f"工具调用: {tool_name}")
        await self.manager.send_message({
            "type": "tool_call",
            "tool": tool_name,
            "arguments": arguments,
            "status": "calling"
        }, self.websocket)
        
    async def on_tool_result(self, tool_name, result, is_error=False):
        """工具调用完成"""
        logger.info(f"工具结果: {tool_name}")
        await self.manager.send_message({
            "type": "tool_result",
            "tool": tool_name,
            "result": str(result) if not isinstance(result, str) else result,
            "is_error": is_error
        }, self.websocket)
        
    async def on_message(self, content, role="assistant"):
        """消息更新"""
        await self.manager.send_message({
            "type": "message",
            "content": content,
            "role": role
        }, self.websocket)


if FASTAPI_AVAILABLE:
    @app.on_event("startup")
    async def startup():
        global agent, current_session
        try:
            logger.info("正在初始化OpenHands Agent...")
            config = AgentConfig.load()
            logger.info(f"配置加载成功: model={config.model.provider}")
            
            agent = EmbeddedAgent(config)
            await agent.initialize()
            logger.info("Agent初始化成功")
            
            current_session = await agent.create_session()
            logger.info(f"会话创建成功: {current_session}")
            
            logger.info("OpenHands GUI started")
        except Exception as e:
            logger.error(f"Startup failed: {e}", exc_info=True)

    @app.get("/")
    async def get_index():
        html_path = Path(__file__).parent / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("&lt;h1&gt;OpenHands GUI&lt;/h1&gt;&lt;p&gt;index.html not found&lt;/p&gt;")

    @app.get("/api/status")
    async def get_status():
        return {
            "connected": True,
            "controlling": is_controlling,
            "action_count": action_count,
            "model": str(agent.config.model) if agent else None,
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket):
        global is_controlling, action_count
        
        await manager.connect(websocket)
        logger.info("WebSocket连接已建立")
        
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                logger.info(f"收到消息: {msg_type}")
                
                if msg_type == "message":
                    user_message = data.get("content", "")
                    logger.info(f"用户消息: {user_message}")
                    
                    callback = AgentProgressCallback(websocket, manager)
                    await callback.on_status("正在思考...")
                    
                    if not agent:
                        await callback.on_status("Agent未初始化")
                        await callback.on_message("Agent未初始化，请检查配置", "error")
                        continue
                        
                    if not current_session:
                        await callback.on_status("会话未创建")
                        current_session = await agent.create_session()
                    
                    try:
                        await callback.on_status("正在处理消息...")
                        await agent.queue_message(current_session, user_message)
                        
                        await callback.on_status("正在运行Agent...")
                        
                        # 运行Agent
                        result = await agent.run(current_session)
                        
                        logger.info(f"Agent运行完成: success={result.success}, final_answer={result.final_answer}")
                        
                        if result.error:
                            await callback.on_status(f"错误: {result.error}")
                            await callback.on_message(f"发生错误: {result.error}", "error")
                        else:
                            await callback.on_status("完成")
                            if result.final_answer:
                                await callback.on_message(result.final_answer)
                            else:
                                await callback.on_message("Agent已处理您的请求")
                                
                    except Exception as e:
                        logger.error(f"Agent运行错误: {e}", exc_info=True)
                        await callback.on_status(f"错误: {str(e)}")
                        await callback.on_message(f"抱歉，发生了错误: {str(e)}", "error")
                
                elif msg_type == "take_control":
                    is_controlling = True
                    await manager.send_message({
                        "type": "status",
                        "content": "控制权已接管"
                    }, websocket)
                    
                    # 发送初始截图
                    screenshot_b64 = await capture_screenshot()
                    if screenshot_b64:
                        await manager.send_message({
                            "type": "screenshot",
                            "image": screenshot_b64
                        }, websocket)
                
                elif msg_type == "release_control":
                    is_controlling = False
                    await manager.send_message({
                        "type": "status",
                        "content": "控制权已释放"
                    }, websocket)
                
                elif msg_type == "screenshot":
                    screenshot_b64 = await capture_screenshot()
                    if screenshot_b64:
                        await manager.send_message({
                            "type": "screenshot",
                            "image": screenshot_b64
                        }, websocket)
                
                elif msg_type == "execute_action":
                    if not is_controlling:
                        await manager.send_message({
                            "type": "error",
                            "content": "请先接管控制"
                        }, websocket)
                        continue
                    
                    action = data.get("action")
                    params = data.get("params", {})
                    
                    result = await execute_windows_action(action, params)
                    
                    if result.get("success"):
                        await manager.send_message({
                            "type": "action",
                            "content": result.get("content", ""),
                            "action": action,
                            **{k: v for k, v in result.items() if k not in ["success", "content"]}
                        }, websocket)
                        
                        # 操作后更新截图
                        if action in ["click", "double_click", "right_click", "type", "hotkey", "press", "scroll"]:
                            await asyncio.sleep(0.3)
                            screenshot_b64 = await capture_screenshot()
                            if screenshot_b64:
                                await manager.send_message({
                                    "type": "screenshot",
                                    "image": screenshot_b64
                                }, websocket)
                    else:
                        await manager.send_message({
                            "type": "error",
                            "content": result.get("error", "操作失败")
                        }, websocket)
                
                elif msg_type == "clear":
                    if agent:
                        agent.clear_history()
                    await manager.send_message({
                        "type": "status",
                        "content": "对话历史已清除"
                    }, websocket)
                
                elif msg_type == "get_stats":
                    await manager.send_message({
                        "type": "stats",
                        "action_count": action_count,
                        "is_controlling": is_controlling
                    }, websocket)
                    
        except WebSocketDisconnect:
            logger.info("WebSocket连接断开")
            manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            manager.disconnect(websocket)


def run_gui(host="0.0.0.0", port=8000):
    """Run the GUI server"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI not installed. Install with: pip install fastapi uvicorn")
    
    print(f"\n{'='*60}")
    print("OpenHands Web GUI")
    print(f"{'='*60}")
    print(f"访问地址: http://localhost:{port}")
    print("按 Ctrl+C 停止")
    print(f"{'='*60}\n")
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_gui()
