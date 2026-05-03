"""
Web GUI for OpenHands
FastAPI + HTML/JS frontend
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from openhands import EmbeddedAgent, AgentConfig

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenHands GUI")


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)


manager = ConnectionManager()

agent: Optional[EmbeddedAgent] = None
current_session: Optional[str] = None


@app.on_event("startup")
async def startup():
    global agent, current_session
    config = AgentConfig.load()
    agent = EmbeddedAgent(config)
    await agent.initialize()
    current_session = await agent.create_session(tool_profile="coding")
    logger.info("OpenHands GUI started")


@app.get("/")
async def get_index():
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse(DEFAULT_HTML)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "message":
                user_message = data["content"]
                await manager.send_message(
                    {"type": "status", "content": "Thinking..."},
                    websocket
                )

                await agent.queue_message(current_session, user_message)
                result = await agent.run(current_session)

                await manager.send_message(
                    {"type": "message", "content": result.final_answer or "No response"},
                    websocket
                )

            elif data["type"] == "clear":
                agent.clear_history()
                await manager.send_message(
                    {"type": "status", "content": "History cleared"},
                    websocket
                )

            elif data["type"] == "switch_profile":
                profile = data["profile"]
                agent.set_tool_profile(profile)
                await manager.send_message(
                    {"type": "status", "content": f"Profile switched to: {profile}"},
                    websocket
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)


DEFAULT_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenHands</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 20px;
        }
        h1 { font-size: 2.5em; color: #00d9ff; }
        .subtitle { color: #888; margin-top: 5px; }
        .chat-container {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            height: 60vh;
            overflow-y: auto;
            margin-bottom: 20px;
        }
        .message { margin-bottom: 15px; padding: 15px; border-radius: 10px; }
        .user { background: rgba(0,217,255,0.2); margin-left: 20%; }
        .assistant { background: rgba(255,255,255,0.1); margin-right: 20%; }
        .input-area {
            display: flex;
            gap: 10px;
        }
        input {
            flex: 1;
            padding: 15px;
            border: none;
            border-radius: 10px;
            background: rgba(255,255,255,0.1);
            color: #fff;
            font-size: 16px;
        }
        input:focus { outline: 2px solid #00d9ff; }
        button {
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            background: #00d9ff;
            color: #1a1a2e;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover { transform: scale(1.05); }
        .status {
            text-align: center;
            color: #888;
            padding: 10px;
            font-size: 14px;
        }
        .controls {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        .controls button {
            padding: 8px 15px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 OpenHands</h1>
            <p class="subtitle">AI Assistant with Windows Control</p>
        </header>

        <div class="controls">
            <button onclick="switchProfile('coding')">Coding</button>
            <button onclick="switchProfile('minimal')">Minimal</button>
            <button onclick="switchProfile('full')">Full</button>
            <button onclick="clearHistory()">Clear</button>
        </div>

        <div class="chat-container" id="chat"></div>

        <div class="input-area">
            <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="handleKey(event)">
            <button onclick="sendMessage()">Send</button>
        </div>

        <div class="status" id="status">Ready</div>
    </div>

    <script>
        let ws;
        const chat = document.getElementById('chat');
        const status = document.getElementById('status');

        function connect() {
            ws = new WebSocket(`ws://${location.host}/ws`);
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'message') {
                    addMessage(data.content, 'assistant');
                    status.textContent = 'Ready';
                } else if (data.type === 'status') {
                    status.textContent = data.content;
                }
            };
            ws.onclose = () => {
                setTimeout(connect, 1000);
            };
        }

        function addMessage(content, role) {
            const div = document.createElement('div');
            div.className = `message ${role}`;
            div.innerHTML = content.replace(/\\n/g, '<br>');
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            ws.send(JSON.stringify({ type: 'message', content: message }));
            input.value = '';
            status.textContent = 'Thinking...';
        }

        function handleKey(e) {
            if (e.key === 'Enter') sendMessage();
        }

        function clearHistory() {
            ws.send(JSON.stringify({ type: 'clear' }));
            chat.innerHTML = '';
        }

        function switchProfile(profile) {
            ws.send(JSON.stringify({ type: 'switch_profile', profile }));
        }

        connect();
    </script>
</body>
</html>
"""


def run_gui(host: str = "0.0.0.0", port: int = 8000):
    """Run the GUI server"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_gui()
