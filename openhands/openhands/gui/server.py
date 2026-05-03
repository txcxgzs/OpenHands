"""
Web GUI for OpenHands
FastAPI + HTML/JS frontend
支持OpenClaw风格的流式输出
"""

import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] 已加载配置文件: {env_path}")
except ImportError:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from openhands import EmbeddedAgent, AgentConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenHands GUI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent: Optional[EmbeddedAgent] = None
current_session: Optional[str] = None


class StreamState:
    """流式状态管理"""
    def __init__(self):
        self.session_start = None
        self.message_count = 0
        self.tool_call_count = 0
        self.iteration_count = 0
        self.current_thinking = ""
        self.full_response = ""
        self.is_streaming = False

stream_state = StreamState()


@app.on_event("startup")
async def startup():
    global agent, current_session
    try:
        logger.info("正在初始化OpenHands Agent...")
        config = AgentConfig.load()
        logger.info(f"配置: provider={config.model.provider}, model={config.model.model}")
        
        agent = EmbeddedAgent(config)
        await agent.initialize()
        logger.info("Agent初始化成功")
        
        current_session = await agent.create_session()
        logger.info(f"会话创建成功: {current_session}")
        
        stream_state.session_start = asyncio.get_event_loop().time()
    except Exception as e:
        logger.error(f"启动失败: {e}", exc_info=True)


@app.get("/")
async def get_index():
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>OpenHands GUI</h1><p>index.html not found</p>")


@app.get("/api/status")
async def get_status():
    elapsed = 0
    if stream_state.session_start:
        elapsed = int(asyncio.get_event_loop().time() - stream_state.session_start)
    
    return {
        "connected": agent is not None,
        "model": str(agent.config.model) if agent else None,
        "session_id": current_session,
        "message_count": stream_state.message_count,
        "tool_call_count": stream_state.tool_call_count,
        "elapsed_seconds": elapsed,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket连接已建立")
    
    global current_session
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            logger.info(f"收到消息类型: {msg_type}")
            
            if msg_type == "message":
                user_message = data.get("content", "")
                logger.info(f"用户消息: {user_message}")
                
                if not agent:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Agent未初始化，请检查配置"
                    })
                    continue
                
                if not current_session:
                    current_session = await agent.create_session()
                    logger.info(f"创建新会话: {current_session}")
                
                stream_state.is_streaming = True
                stream_state.full_response = ""
                stream_state.message_count += 1
                
                await agent.queue_message(current_session, user_message)
                
                await websocket.send_json({
                    "type": "status",
                    "content": "开始处理..."
                })
                
                try:
                    async for chunk in agent.run_stream(current_session):
                        chunk_type = chunk.get("type")
                        
                        if chunk_type == "thinking":
                            thinking_content = chunk.get("content", "")
                            stream_state.current_thinking = thinking_content
                            await websocket.send_json({
                                "type": "thinking",
                                "content": thinking_content,
                                "iteration": stream_state.iteration_count
                            })
                            
                        elif chunk_type == "delta":
                            text = chunk.get("content", "")
                            stream_state.full_response += text
                            await websocket.send_json({
                                "type": "stream",
                                "delta": text,
                                "content": stream_state.full_response,
                                "is_thinking": stream_state.current_thinking
                            })
                            
                        elif chunk_type == "tool_call":
                            stream_state.tool_call_count += 1
                            stream_state.iteration_count += 1
                            await websocket.send_json({
                                "type": "tool_call",
                                "tool": chunk.get("tool"),
                                "arguments": chunk.get("arguments", {})
                            })
                            
                        elif chunk_type == "tool_result":
                            await websocket.send_json({
                                "type": "tool_result",
                                "tool": chunk.get("tool"),
                                "result": chunk.get("result", ""),
                                "is_error": chunk.get("is_error", False)
                            })
                            
                        elif chunk_type == "final":
                            await websocket.send_json({
                                "type": "message",
                                "content": chunk.get("content", "处理完成"),
                                "full_content": stream_state.full_response
                            })
                            
                        elif chunk_type == "error":
                            await websocket.send_json({
                                "type": "error",
                                "content": chunk.get("content", "未知错误")
                            })
                            
                except Exception as stream_err:
                    logger.error(f"流式处理错误: {stream_err}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "content": f"处理错误: {str(stream_err)}"
                    })
                finally:
                    stream_state.is_streaming = False
                    stream_state.current_thinking = ""
            
            elif msg_type == "clear":
                if agent and current_session:
                    agent._sessions[current_session].messages.clear()
                stream_state.message_count = 0
                stream_state.tool_call_count = 0
                stream_state.iteration_count = 0
                stream_state.full_response = ""
                await websocket.send_json({
                    "type": "status",
                    "content": "对话已清空"
                })
                
            elif msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "stats": {
                        "message_count": stream_state.message_count,
                        "tool_call_count": stream_state.tool_call_count,
                        "is_streaming": stream_state.is_streaming,
                        "current_thinking": stream_state.current_thinking
                    }
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket连接断开")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}", exc_info=True)


def run_gui(host="0.0.0.0", port=8000):
    print(f"\n{'='*60}")
    print("OpenHands Web GUI - OpenClaw风格")
    print(f"{'='*60}")
    print(f"访问地址: http://localhost:{port}")
    print("按 Ctrl+C 停止")
    print(f"{'='*60}\n")
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_gui()
