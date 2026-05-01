import asyncio
import json

import websockets


class WSClient:
    def __init__(self, server_url: str, agent_name: str, token: str):
        self.server_url = server_url
        self.agent_name = agent_name
        self.token = token
        self.websocket = None
        self._running = False

    async def connect(self) -> bool:
        try:
            self.websocket = await websockets.connect(
                self.server_url,
                additional_headers={"Authorization": f"Bearer {self.token}"},
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            )
            await self.websocket.send(json.dumps({
                "type": "register",
                "agent": self.agent_name,
            }))
            response = await self.websocket.recv()
            ack = json.loads(response)
            return ack.get("type") == "ack"
        except Exception:
            self.websocket = None
            return False

    async def send_result(self, task_id: str, status: str, detail: dict):
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "type": "task_result",
                    "task_id": task_id,
                    "status": status,
                    "detail": detail,
                }))
            except Exception:
                pass

    async def recv_task(self, timeout: float = 1.0) -> dict | None:
        if not self.websocket:
            return None
        try:
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            return json.loads(msg)
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def heartbeat_loop(self):
        self._running = True
        while self._running and self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "type": "heartbeat",
                    "agent": self.agent_name,
                }))
                await asyncio.sleep(30)
            except Exception:
                self._running = False
                break

    async def close(self):
        self._running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
