# 服务端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Linux 虚拟机上搭建赐福点赞云控服务端，通过 WebSocket 下发任务、收集结果、提供 Web 面板。

**Architecture:** FastAPI + asyncio 单进程，WebSocket Hub 管理 Agent 连接，APScheduler 定时触发任务，SQLite 持久化，Jinja2 渲染 Web 面板。

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, aiosqlite, APScheduler, websockets, Jinja2, PyYAML

---

### Task 1: 项目脚手架

**Files:**
- Create: `server/requirements.txt`
- Create: `server/__init__.py` (empty)
- Create: `config.yaml`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p server/templates data
```

- [ ] **Step 2: 创建 requirements.txt**

```bash
cat > server/requirements.txt << 'EOF'
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
aiosqlite>=0.20.0
apscheduler>=3.10.0
websockets>=12.0
pyyaml>=6.0
jinja2>=3.1.0
EOF
```

- [ ] **Step 3: 创建 config.yaml**

```yaml
# config.yaml
server:
  host: "127.0.0.1"
  port: 8088

auth:
  token: "change-me-to-a-random-string"

db:
  path: "data/gjjb.db"

scheduler:
  blessing_cron: "50 59 23 * * *"
```

- [ ] **Step 4: 创建空的 __init__.py**

```bash
touch server/__init__.py
```

- [ ] **Step 5: 安装依赖**

```bash
pip install -r server/requirements.txt
```

Expected: 全部依赖安装成功

- [ ] **Step 6: Commit**

```bash
git add server/requirements.txt server/__init__.py config.yaml
git commit -m "feat: add server project scaffold with config"
```

---

### Task 2: 数据模型 models.py

**Files:**
- Create: `server/models.py`
- Create: `tests/test_models.py` (先建 `tests/` 和 `tests/__init__.py`)

- [ ] **Step 1: 创建测试目录**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2: 编写测试 tests/test_models.py**

```python
import json
from server.models import (
    TaskCreate, TaskUpdate, TaskResult, TaskStatus,
    AgentMessage, ServerMessage, BlessingLogEntry,
)


class TestTaskCreate:
    def test_create_pending_task(self):
        task = TaskCreate(task_type="blessing_like")
        assert task.task_type == "blessing_like"
        assert task.id is not None
        assert len(task.id) == 36  # UUID4

    def test_task_serializable(self):
        task = TaskCreate(task_type="blessing_like")
        d = task.model_dump()
        assert d["task_type"] == "blessing_like"
        assert d["status"] == "pending"


class TestAgentMessage:
    def test_register_message(self):
        msg = AgentMessage(type="register", agent="pc-home")
        d = msg.model_dump()
        assert d["type"] == "register"
        assert d["agent"] == "pc-home"

    def test_heartbeat_message(self):
        msg = AgentMessage(type="heartbeat", agent="pc-home")
        assert msg.type == "heartbeat"

    def test_task_result_message(self):
        msg = AgentMessage(
            type="task_result",
            agent="pc-home",
            task_id="abc123",
            status="ok",
            detail={"matched": True},
        )
        assert msg.task_id == "abc123"
        assert msg.status == "ok"
        assert msg.detail == {"matched": True}

    def test_json_roundtrip(self):
        original = AgentMessage(type="register", agent="test-agent")
        json_str = original.model_dump_json()
        parsed = AgentMessage.model_validate_json(json_str)
        assert parsed.type == "register"
        assert parsed.agent == "test-agent"


class TestServerMessage:
    def test_task_message(self):
        msg = ServerMessage(type="task", task_id="t1", task_type="blessing_like")
        assert msg.task_type == "blessing_like"

    def test_ack_message(self):
        msg = ServerMessage(type="ack", msg="registered")
        assert msg.msg == "registered"

    def test_json_roundtrip(self):
        original = ServerMessage(type="task", task_id="t1", task_type="blessing_like")
        json_str = original.model_dump_json()
        parsed = ServerMessage.model_validate_json(json_str)
        assert parsed.task_id == "t1"


class TestBlessingLogEntry:
    def test_entry_fields(self):
        entry = BlessingLogEntry(
            task_id="t1",
            detected_at="2026-05-01T00:00:05",
            like_result="ok",
            detail="点赞成功",
            screenshot="logs/screenshots/2026-05-01T00-00-05.png",
        )
        assert entry.like_result == "ok"
        assert entry.task_id == "t1"
```

- [ ] **Step 3: 运行测试确认失败**

```bash
python -m pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'server.models'`

- [ ] **Step 4: 实现 server/models.py**

```python
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str
    status: str = "pending"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TaskUpdate(BaseModel):
    status: str
    detail: Optional[str] = None
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgentMessage(BaseModel):
    type: str
    agent: str = ""
    task_id: Optional[str] = None
    status: Optional[str] = None
    detail: Optional[dict] = None


class ServerMessage(BaseModel):
    type: str
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    msg: Optional[str] = None


class BlessingLogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    detected_at: Optional[str] = None
    like_result: str = ""
    detail: str = ""
    screenshot: str = ""
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_models.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add server/models.py tests/test_models.py tests/__init__.py
git commit -m "feat: add server data models"
```

---

### Task 3: 配置模块 server/config.py

**Files:**
- Create: `server/config.py`
- Create: `tests/test_server_config.py`

- [ ] **Step 1: 编写测试 tests/test_server_config.py**

```python
import tempfile
import os
from server.config import load_server_config, ServerConfig


VALID_CONFIG = """
server:
  host: "127.0.0.1"
  port: 8088

auth:
  token: "test-token-123"

db:
  path: "data/gjjb.db"

scheduler:
  blessing_cron: "50 59 23 * * *"
"""


class TestServerConfig:
    def test_loads_valid_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_CONFIG)
            path = f.name
        try:
            cfg = load_server_config(path)
            assert cfg.server_host == "127.0.0.1"
            assert cfg.server_port == 8088
            assert cfg.auth_token == "test-token-123"
            assert cfg.db_path == "data/gjjb.db"
            assert cfg.blessing_cron == "50 59 23 * * *"
        finally:
            os.unlink(path)

    def test_file_not_found_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_server_config("nonexistent.yaml")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_server_config.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 server/config.py**

```python
from dataclasses import dataclass
import yaml


@dataclass
class ServerConfig:
    server_host: str
    server_port: int
    auth_token: str
    db_path: str
    blessing_cron: str


def load_server_config(path: str = "config.yaml") -> ServerConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ServerConfig(
        server_host=data["server"]["host"],
        server_port=data["server"]["port"],
        auth_token=data["auth"]["token"],
        db_path=data["db"]["path"],
        blessing_cron=data["scheduler"]["blessing_cron"],
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_server_config.py -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add server/config.py tests/test_server_config.py
git commit -m "feat: add server config module"
```

---

### Task 4: 数据库模块 db.py

**Files:**
- Create: `server/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: 编写测试 tests/test_db.py**

```python
import tempfile
import os
import pytest
from server.db import Database


@pytest.mark.asyncio
class TestDatabase:
    async def test_init_creates_tables(self):
        db_path = os.path.join(tempfile.mkdtemp(), "test.db")
        db = Database(db_path)
        await db.init()
        try:
            async with db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ) as cursor:
                tables = [row[0] async for row in cursor]
            assert "tasks" in tables
            assert "blessing_logs" in tables
        finally:
            await db.close()

    async def test_insert_and_get_task(self):
        db_path = os.path.join(tempfile.mkdtemp(), "test.db")
        db = Database(db_path)
        await db.init()
        try:
            task_id = await db.create_task("blessing_like")
            assert task_id is not None
            task = await db.get_task(task_id)
            assert task is not None
            assert task["task_type"] == "blessing_like"
            assert task["status"] == "pending"
        finally:
            await db.close()

    async def test_update_task_status(self):
        db_path = os.path.join(tempfile.mkdtemp(), "test.db")
        db = Database(db_path)
        await db.init()
        try:
            task_id = await db.create_task("blessing_like")
            await db.update_task(task_id, "ok", '{"matched": true}')
            task = await db.get_task(task_id)
            assert task["status"] == "ok"
            assert task["detail"] == '{"matched": true}'
        finally:
            await db.close()

    async def test_insert_blessing_log(self):
        db_path = os.path.join(tempfile.mkdtemp(), "test.db")
        db = Database(db_path)
        await db.init()
        try:
            task_id = await db.create_task("blessing_like")
            log_id = await db.insert_blessing_log(
                task_id=task_id,
                like_result="ok",
                detail="点赞成功",
                screenshot="path/to/screenshot.png",
            )
            assert log_id is not None
            logs = await db.get_recent_blessing_logs(limit=10)
            assert len(logs) == 1
            assert logs[0]["like_result"] == "ok"
        finally:
            await db.close()

    async def test_get_recent_tasks(self):
        db_path = os.path.join(tempfile.mkdtemp(), "test.db")
        db = Database(db_path)
        await db.init()
        try:
            await db.create_task("blessing_like")
            await db.create_task("blessing_like")
            tasks = await db.get_recent_tasks(limit=10)
            assert len(tasks) == 2
        finally:
            await db.close()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_db.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 server/db.py**

```python
import uuid
import aiosqlite
from datetime import datetime, timezone


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          TEXT PRIMARY KEY,
                task_type   TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                detail      TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS blessing_logs (
                id            TEXT PRIMARY KEY,
                task_id       TEXT NOT NULL,
                detected_at   TEXT,
                like_result   TEXT,
                detail        TEXT,
                screenshot    TEXT
            );
        """)
        await self._conn.commit()

    async def create_task(self, task_type: str) -> str:
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "INSERT INTO tasks (id, task_type, status, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
            (task_id, task_type, now, now),
        )
        await self._conn.commit()
        return task_id

    async def get_task(self, task_id: str) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_task(self, task_id: str, status: str, detail: str = ""):
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "UPDATE tasks SET status = ?, detail = ?, updated_at = ? WHERE id = ?",
            (status, detail, now, task_id),
        )
        await self._conn.commit()

    async def get_recent_tasks(self, limit: int = 50) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def insert_blessing_log(
        self,
        task_id: str,
        like_result: str = "",
        detail: str = "",
        screenshot: str = "",
    ) -> str:
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "INSERT INTO blessing_logs (id, task_id, detected_at, like_result, detail, screenshot) VALUES (?, ?, ?, ?, ?, ?)",
            (log_id, task_id, now, like_result, detail, screenshot),
        )
        await self._conn.commit()
        return log_id

    async def get_recent_blessing_logs(self, limit: int = 50) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM blessing_logs ORDER BY detected_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def close(self):
        if self._conn:
            await self._conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_db.py -v
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add server/db.py tests/test_db.py
git commit -m "feat: add SQLite database module"
```

---

### Task 5: WebSocket Hub ws_hub.py

**Files:**
- Create: `server/ws_hub.py`

- [ ] **Step 1: 实现 server/ws_hub.py**

```python
import asyncio
import json
import time
from typing import Optional
from fastapi import WebSocket
from server.models import AgentMessage, ServerMessage
from server.db import Database


class AgentConnection:
    def __init__(self, websocket: WebSocket, name: str):
        self.websocket = websocket
        self.name = name
        self.last_heartbeat = time.time()
        self._connected = True

    async def send(self, msg: ServerMessage):
        try:
            await self.websocket.send_text(msg.model_dump_json())
        except Exception:
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.last_heartbeat) < 90


class WSHub:
    def __init__(self, db: Database, auth_token: str):
        self.db = db
        self.auth_token = auth_token
        self._agents: dict[str, AgentConnection] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()

    def _verify_token(self, headers) -> bool:
        auth = headers.get("authorization", "")
        return auth == f"Bearer {self.auth_token}"

    async def handle_connection(self, websocket: WebSocket):
        # Verify token during WebSocket handshake
        headers = dict(websocket.headers)
        if not self._verify_token(headers):
            await websocket.close(code=4001, reason="Unauthorized")
            return

        await websocket.accept()
        agent: Optional[AgentConnection] = None

        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            msg = AgentMessage.model_validate_json(raw)
            if msg.type != "register":
                await websocket.close(code=4002, reason="Expected register")
                return

            agent = AgentConnection(websocket, msg.agent)
            self._agents[msg.agent] = agent
            await agent.send(ServerMessage(type="ack", msg="registered"))
            print(f"[WS] Agent '{msg.agent}' connected")

            # Start heartbeat monitor and task dispatcher
            heartbeat_task = asyncio.create_task(self._heartbeat_check(agent))
            dispatch_task = asyncio.create_task(self._dispatch_loop(agent))

            while agent.is_connected:
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=5)
                    msg = AgentMessage.model_validate_json(raw)

                    if msg.type == "heartbeat":
                        agent.last_heartbeat = time.time()
                    elif msg.type == "task_result":
                        task_id = msg.task_id or ""
                        status = msg.status or "error"
                        detail = json.dumps(msg.detail) if msg.detail else ""
                        await self.db.update_task(task_id, status, detail)
                        if msg.detail and msg.detail.get("like_result"):
                            await self.db.insert_blessing_log(
                                task_id=task_id,
                                like_result=msg.detail.get("like_result", ""),
                                detail=msg.detail.get("detail", ""),
                                screenshot=msg.detail.get("screenshot", ""),
                            )
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"[WS] Error: {e}")
        finally:
            if agent:
                self._agents.pop(agent.name, None)
                print(f"[WS] Agent '{agent.name}' disconnected")

    async def _heartbeat_check(self, agent: AgentConnection):
        while agent.is_connected:
            await asyncio.sleep(15)
            if not agent.is_alive:
                agent._connected = False
                break

    async def _dispatch_loop(self, agent: AgentConnection):
        while agent.is_connected:
            try:
                task_data = await asyncio.wait_for(self._task_queue.get(), timeout=3)
                if task_data["agent"] == agent.name or task_data["agent"] == "*":
                    msg = ServerMessage(
                        type="task",
                        task_id=task_data["task_id"],
                        task_type=task_data["task_type"],
                    )
                    await agent.send(msg)
            except asyncio.TimeoutError:
                continue

    async def enqueue_task(self, task_type: str, agent_name: str = "*") -> str:
        task_id = await self.db.create_task(task_type)
        await self.db.update_task(task_id, "running")
        await self._task_queue.put({
            "task_id": task_id,
            "task_type": task_type,
            "agent": agent_name,
        })
        return task_id

    def get_agent_status(self) -> dict:
        return {
            name: {
                "connected": agent.is_connected,
                "alive": agent.is_alive,
                "last_heartbeat": agent.last_heartbeat,
            }
            for name, agent in self._agents.items()
        }

    def any_agent_alive(self) -> bool:
        return any(a.is_connected and a.is_alive for a in self._agents.values())
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from server.ws_hub import WSHub, AgentConnection; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add server/ws_hub.py
git commit -m "feat: add WebSocket hub with agent management and task dispatch"
```

---

### Task 6: 定时调度 scheduler.py

**Files:**
- Create: `server/scheduler.py`

- [ ] **Step 1: 实现 server/scheduler.py**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from server.ws_hub import WSHub


def setup_scheduler(hub: WSHub, blessing_cron: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    async def trigger_blessing():
        if hub.any_agent_alive():
            task_id = await hub.enqueue_task("blessing_like")
            print(f"[Scheduler] Blessing task enqueued: {task_id}")
        else:
            print("[Scheduler] No agent alive, blessing task skipped")

    scheduler.add_job(
        trigger_blessing,
        trigger="cron",
        hour=23,
        minute=59,
        second=50,
        id="blessing_like",
        name="每日赐福点赞检测",
    )

    return scheduler
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from server.scheduler import setup_scheduler; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add server/scheduler.py
git commit -m "feat: add APScheduler for daily blessing task trigger"
```

---

### Task 7: Web 面板 dashboard.html

**Files:**
- Create: `server/templates/dashboard.html`

- [ ] **Step 1: 实现 server/templates/dashboard.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>时光大爆炸 — 挂机面板</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
        .container { max-width: 800px; margin: 0 auto; padding: 24px; }
        h1 { font-size: 1.5rem; margin-bottom: 24px; color: #38bdf8; }
        .card { background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
        .card h2 { font-size: 1rem; margin-bottom: 12px; color: #94a3b8; }
        .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
        .status-dot.online { background: #22c55e; }
        .status-dot.offline { background: #ef4444; }
        .btn { padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; margin-right: 8px; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-danger { background: #ef4444; color: white; }
        .btn:hover { opacity: 0.85; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #334155; font-size: 14px; }
        th { color: #94a3b8; }
        .badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
        .badge-ok { background: #166534; color: #22c55e; }
        .badge-error { background: #7f1d1d; color: #ef4444; }
        .badge-pending { background: #334155; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>时光大爆炸 — 挂机控制面板</h1>

        <div class="card">
            <h2>Agent 状态</h2>
            {% if agents %}
                {% for name, info in agents.items() %}
                <div>
                    <span class="status-dot {{ 'online' if info.alive else 'offline' }}"></span>
                    <strong>{{ name }}</strong>
                    {% if info.alive %}
                    <span style="color:#22c55e">在线</span>
                    {% else %}
                    <span style="color:#ef4444">离线</span>
                    {% endif %}
                    <span style="color:#64748b; margin-left: 12px">
                        最后心跳: {{ info.last_heartbeat | default('N/A') }}
                    </span>
                </div>
                {% endfor %}
            {% else %}
                <p style="color:#94a3b8">暂无 Agent 连接</p>
            {% endif %}
        </div>

        <div class="card">
            <h2>操作</h2>
            <button class="btn btn-primary" onclick="triggerBlessing()">立即检测赐福</button>
            <p id="trigger-status" style="margin-top:8px;color:#38bdf8"></p>
        </div>

        <div class="card">
            <h2>最近赐福记录</h2>
            <table>
                <thead>
                    <tr><th>时间</th><th>任务 ID</th><th>结果</th><th>详情</th></tr>
                </thead>
                <tbody>
                    {% for log in blessing_logs %}
                    <tr>
                        <td>{{ log.detected_at or 'N/A' }}</td>
                        <td style="font-size:12px;color:#64748b">{{ log.task_id[:8] }}...</td>
                        <td>
                            <span class="badge {{ 'badge-ok' if log.like_result == 'ok' else 'badge-error' }}">
                                {{ log.like_result }}
                            </span>
                        </td>
                        <td>{{ log.detail or '' }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="4" style="color:#64748b">暂无记录</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>最近任务</h2>
            <table>
                <thead>
                    <tr><th>创建时间</th><th>类型</th><th>状态</th></tr>
                </thead>
                <tbody>
                    {% for task in tasks %}
                    <tr>
                        <td>{{ task.created_at }}</td>
                        <td>{{ task.task_type }}</td>
                        <td>
                            <span class="badge {{ 'badge-ok' if task.status == 'ok' else 'badge-error' if task.status == 'error' else 'badge-pending' }}">
                                {{ task.status }}
                            </span>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="3" style="color:#64748b">暂无任务</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function triggerBlessing() {
            const status = document.getElementById('trigger-status');
            status.textContent = '发送中...';
            try {
                const resp = await fetch('/api/trigger/blessing', { method: 'POST' });
                const data = await resp.json();
                status.textContent = '任务已下发: ' + data.task_id;
                setTimeout(() => location.reload(), 2000);
            } catch (e) {
                status.textContent = '请求失败: ' + e.message;
            }
        }
    </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add server/templates/dashboard.html
git commit -m "feat: add web dashboard for agent status and task control"
```

---

### Task 8: FastAPI 入口 main.py

**Files:**
- Create: `server/main.py`

- [ ] **Step 1: 实现 server/main.py**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from server.config import load_server_config
from server.db import Database
from server.ws_hub import WSHub
from server.scheduler import setup_scheduler


cfg = load_server_config()
db = Database(cfg.db_path)
hub = WSHub(db, cfg.auth_token)
templates = Jinja2Templates(directory="server/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    scheduler = setup_scheduler(hub, cfg.blessing_cron)
    scheduler.start()
    print(f"[Server] Started on {cfg.server_host}:{cfg.server_port}")
    yield
    scheduler.shutdown(wait=False)
    await db.close()


app = FastAPI(lifespan=lifespan, title="GJJB Server")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    agents = hub.get_agent_status()
    tasks = await db.get_recent_tasks(limit=20)
    blessing_logs = await db.get_recent_blessing_logs(limit=20)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "agents": agents, "tasks": tasks, "blessing_logs": blessing_logs},
    )


@app.post("/api/trigger/blessing")
async def trigger_blessing():
    if hub.any_agent_alive():
        task_id = await hub.enqueue_task("blessing_like")
        return {"ok": True, "task_id": task_id}
    return {"ok": False, "error": "No agent alive"}


@app.get("/api/tasks")
async def get_tasks(limit: int = 50):
    tasks = await db.get_recent_tasks(limit=limit)
    return {"tasks": tasks}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await hub.handle_connection(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=cfg.server_host, port=cfg.server_port)
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from server.main import app; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat: add FastAPI entry with WebSocket, dashboard, and API routes"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: 启动服务端**

```bash
python server/main.py
```

Expected: 输出 `[Server] Started on 127.0.0.1:8088`

- [ ] **Step 2: 验证 Web 面板可访问**

```bash
curl -s http://127.0.0.1:8088/ | head -5
```

Expected: 返回 HTML 内容

- [ ] **Step 3: 验证手动触发 API（无 Agent 时应返回错误）**

```bash
curl -s -X POST http://127.0.0.1:8088/api/trigger/blessing
```

Expected: `{"ok":false,"error":"No agent alive"}`

- [ ] **Step 4: 验证 WebSocket 连接需要 Token**

用 Python 脚本测试（另开终端）：

```python
import asyncio
import websockets
import json

async def test():
    # 无 Token 应被拒绝
    try:
        async with websockets.connect("ws://127.0.0.1:8088/ws") as ws:
            print("Connected (unexpected)")
    except websockets.exceptions.InvalidStatus as e:
        print(f"Rejected as expected: {e.response.status_code}")

    # 正确 Token 应连接成功
    headers = {"Authorization": "Bearer change-me-to-a-random-string"}
    async with websockets.connect("ws://127.0.0.1:8088/ws", extra_headers=headers) as ws:
        await ws.send(json.dumps({"type": "register", "agent": "test-agent"}))
        resp = await ws.recv()
        print(f"Registered: {resp}")

asyncio.run(test())
```

Expected:
```
Rejected as expected: 4001
Registered: {"type":"ack","task_id":null,"task_type":null,"msg":"registered"}
```

- [ ] **Step 5: 配置 Caddy 反代（生产环境）**

```bash
# 追加到 Caddyfile
# your-domain.com {
#     reverse_proxy /ws localhost:8088
#     reverse_proxy localhost:8088
# }
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: end-to-end verification, server ready for integration test"
```
