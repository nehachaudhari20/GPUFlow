from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Optional
import json
import logging
from backend.app.events.event_manager import event_manager, SystemEvent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast_json(self, data: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to websocket client: {e}")
                self.disconnect(connection)

import asyncio

main_event_loop: Optional[asyncio.AbstractEventLoop] = None

def setup_event_broadcaster(loop: asyncio.AbstractEventLoop):
    global main_event_loop
    main_event_loop = loop

    def on_system_event(event: SystemEvent):
        if main_event_loop and main_event_loop.is_running():
            payload = {
                "type": "EVENT",
                "data": event.model_dump(mode="json")
            }
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast_json(payload), main_event_loop)

    event_manager.add_listener(on_system_event)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection open and listen for any incoming client messages (heartbeat/ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
