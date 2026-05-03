
"""
Web GUI for OpenHands
FastAPI + HTML/JS frontend
"""

import asyncio
import logging
import base64
import json
import os
from pathlib import Path

# 显式加载.env文件
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[INFO] 已加载配置文件: {env_path}")
except ImportError:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from openhands import EmbeddedAgent, AgentConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenHands GUI")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = None
current_session = None
is_controlling = False
action_count = 0


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
    return {
        "connected": True,
        "model": str(agent.config.model) if agent else None,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket连接已建立")
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            logger.info(f"收到消息类型: {msg_type}")
            
            if msg_type == "message":
                user_message = data.get("content", "")
                logger.info(f"用户消息: {user_message}")
                
                await websocket.send_json({
                    "type": "status",
                    "content": "正在思考..."
                })
                
                global current_session
                
                if not agent:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Agent未初始化"
                    })
                    continue
                
                if not current_session:
                    current_session = await agent.create_session()
                    logger.info(f"创建新会话: {current_session}")
                
                try:
                    await agent.queue_message(current_session, user_message)
                    result = await agent.run(current_session)
                    
                    logger.info(f"Agent运行完成: success={result.success}, error={result.error}")
                    
                    if result.error:
                        await websocket.send_json({
                            "type": "error",
                            "content": f"错误: {result.error}"
                        })
                    else:
                        answer = result.final_answer or "已完成处理"
                        await websocket.send_json({
                            "type": "message",
                            "content": answer
                        })
                except Exception as e:
                    logger.error(f"Agent运行错误: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "content": f"错误: {str(e)}"
                    })
            
            elif msg_type == "clear":
                if agent:
                    agent.clear_history()
                await websocket.send_json({
                    "type": "status",
                    "content": "对话已清空"
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket连接断开")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}", exc_info=True)


def run_gui(host="0.0.0.0", port=8000):
    print(f"\n{'='*60}")
    print("OpenHands Web GUI")
    print(f"{'='*60}")
    print(f"访问地址: http://localhost:{port}")
    print("按 Ctrl+C 停止")
    print(f"{'='*60}\n")
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_gui()
