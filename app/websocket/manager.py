import json
import asyncio
from typing import Any
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections.
    Supports broadcast (all clients) and targeted sends.

    Frontend connects to WS /ws and receives JSON messages of the form:
        {
            "event": "risk_updated" | "unit_reassigned" | "incident_created" | "ping",
            "data": { ... }
        }
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WS client connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event: str, data: Any):
        """Send an event+data JSON to every connected client."""
        message = json.dumps({"event": event, "data": data})
        dead: list[WebSocket] = []
        for ws in list(self.active_connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def send_personal(self, websocket: WebSocket, event: str, data: Any):
        """Send to a single client."""
        message = json.dumps({"event": event, "data": data})
        try:
            await websocket.send_text(message)
        except Exception:
            await self.disconnect(websocket)


# Singleton — imported everywhere via `from app.websocket.manager import ws_manager`
ws_manager = ConnectionManager()
