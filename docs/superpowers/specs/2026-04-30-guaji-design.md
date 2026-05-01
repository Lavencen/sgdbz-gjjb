# 时光大爆炸挂机脚本 — 设计文档

## 概述

为手游《时光大爆炸》实现挂机脚本。第一阶段落地场景：每晚 12 点自动检测赐福消息并点赞领奖励。长期目标：覆盖全玩法自动化（资源采集、征战、贸易等），支持多账号切换，支持本地+远程双模式运行。

## 运行环境

- **本机 PC**：Windows，安装 MuMu 模拟器，ADB 可用
- **服务器**：腾讯云 4C4G，已部署 Caddy（反代）+ 跳板机（SSH），有备案域名
- **游戏设备**：Android 真机（备用），主力跑在 MuMu 模拟器上

## 总体架构

方案：**云控架构 — 服务端调度 + 本机执行（ADB + 图像识别）**

```
┌── 腾讯云服务器 (4C4G) ────────────────────────────┐
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │ 定时调度   │  │ 任务队列   │  │  Web 面板        │  │
│  │(APScheduler)│ │(asyncio  │  │  (FastAPI +      │  │
│  │           │  │ Queue)   │  │   Jinja2 模板)   │  │
│  └─────┬─────┘  └────┬─────┘  └────────┬────────┘  │
│        │             │                │            │
│        └─────────────┼────────────────┘            │
│                      │                             │
│               ┌──────┴──────┐                      │
│               │  WebSocket   │                      │
│               │  Hub         │                      │
│               └──────┬──────┘                      │
└──────────────────────┼─────────────────────────────┘
                       │  WSS (TLS)，Agent 主动连接
┌──── 本机 PC ─────────┼─────────────────────────────┐
│                      │                             │
│               ┌──────┴──────┐                      │
│               │  Agent       │                      │
│               │  (WebSocket  │                      │
│               │   Client)    │                      │
│               └──────┬──────┘                      │
│                      │                             │
│          ┌───────────┼───────────┐                 │
│          │           │           │                 │
│     ┌────┴────┐ ┌───┴────┐ ┌───┴────┐            │
│     │ ADB 控制 │ │图像识别 │ │任务执行 │            │
│     │(screencap│ │(OpenCV │ │(状态机) │            │
│     │ + tap)   │ │模板匹配)│ │        │            │
│     └────┬────┘ └────────┘ └────────┘            │
│          │                                        │
│     ┌────┴────┐                                   │
│     │  MuMu    │                                   │
│     │ 模拟器    │                                   │
│     └─────────┘                                   │
└───────────────────────────────────────────────────┘
```

**核心原则**：
- 服务器是大脑：调度、状态管理、对外暴露
- Agent 是手：只执行，不存业务逻辑
- 单向连接：Agent 主动连服务器，无需公网 IP 或内网穿透
- 服务器和 Agent 通过 WSS（WebSocket over TLS）通信，走 Caddy 反代

## 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| 服务端框架 | FastAPI + asyncio | 原生 WebSocket，异步友好 |
| 定时调度 | APScheduler | cron 表达式，Python 生态标准 |
| 反向代理 | Caddy（已有） | 自动 HTTPS，WebSocket 透明代理 |
| 数据库 | SQLite（aiosqlite） | 零部署，够用 |
| Agent 通信 | websockets（Python） | 轻量异步 WebSocket 客户端 |
| 设备控制 | ADB（subprocess） | screencap 截图，input tap 点击 |
| 图像识别 | OpenCV（cv2.matchTemplate） | 模板匹配，阈值 0.85 |
| Web 面板 | FastAPI + Jinja2 + 原生 HTML/CSS | 极简，零前端构建 |

## 服务端组件

### 调度器（APScheduler）

- 每天 23:59:50 触发 `blessing_like` 任务，推入任务队列
- cron 表达式：`50 59 23 * * *`
- 可扩展：添加新 cron 任务即可增加挂机类型

### 任务队列

- `asyncio.Queue` 内存队列
- 任务入队后等待 Agent 认领
- 支持任务取消：`{"type": "cancel", "task_id": "xxx"}`

### WebSocket Hub

- 管理 Agent 连接生命周期
- 心跳检测：Agent 每 30s 发 heartbeat，超时 90s 标记离线
- 连接断线自动重连，Agent 侧实现指数退避（最大间隔 60s）
- 任务下发与结果回收

### Web 面板

路由规划：

| 路由 | 功能 |
|------|------|
| `GET /` | 仪表盘：Agent 状态、最近执行记录、心跳状态 |
| `POST /api/trigger/blessing` | 手动触发赐福检测 |
| `POST /api/cancel/{task_id}` | 停止当前任务 |
| `GET /api/tasks` | 任务执行历史 |

页面按钮：
- **立即检测赐福** — 手动下发任务
- **停止当前任务** — 中断正在执行的重试循环
- **重新连接** — Agent 离线时提示并触发重连

### 数据库

SQLite，两张表：

```sql
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,
    task_type   TEXT NOT NULL,         -- 'blessing_like' 等
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending/running/ok/error/cancelled
    detail      TEXT,                  -- 结果详情 JSON
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE blessing_logs (
    id            TEXT PRIMARY KEY,
    task_id       TEXT NOT NULL,
    detected_at   TEXT,
    like_result   TEXT,                -- 'ok'/'not_found'/'error'
    detail        TEXT,                -- 截图坐标、匹配度等
    screenshot    TEXT                 -- 截图保存路径（可选）
);
```

## Agent 端组件

### WebSocket Client

- 启动即连服务器 WSS 地址
- 心跳 30s 间隔，掉线自动重连（指数退避，最大 60s）
- 注册消息：`{"type": "register", "agent": "pc-home"}`

### 任务执行器

- 收到 `task` 消息 → 路由到对应 handler 函数
- 当前 handler：`blessing_like`
- 执行完毕 → 回传 `task_result` 消息

### ADB 控制器

```python
# 截图：adb exec-out screencap -p > screenshot.png
# 点击：adb shell input tap x y
```

- 封装为 `screencap()` 和 `tap(x, y)` 两个函数
- 截图保存到临时目录，任务结束后清理

### 图像识别（赐福点赞流程）

```
收到 blessing_like 任务
    │
    ▼
截图 → 模板匹配查找"赐福"图标
    │
    ├── 找到了 (匹配度 > 0.85)
    │     ├── 点击赐福坐标
    │     ├── 截图确认 → 查找"点赞"按钮
    │     ├── 点击点赞
    │     ├── 截图保存（证据）
    │     └── 回传 "ok"
    │
    └── 没找到
          ├── 等待 2s
          ├── 重试（最多 30 次，覆盖约 1 分钟）
          │
          ├── 期间找到 → 正常处理
          └── 全部超时 → 回传 "not_found"
```

模板图片存放在 `templates/` 目录：
- `blessing_icon.png` — 赐福按钮/图标截图
- `like_button.png` — 点赞按钮截图

## 部署方案

### 服务端（腾讯云）

```bash
# FastAPI 进程，监听 127.0.0.1:8088
python server/main.py

# Caddy 反代（追加到 Caddyfile）
# your-domain.com {
#     reverse_proxy /ws localhost:8088
#     reverse_proxy localhost:8088
# }
```

### Agent（本机 PC）

```bash
# Windows 终端常驻运行
python agent/main.py

# 或注册为 Windows 服务 / 计划任务开机自启
```

MuMu 模拟器注意事项：
- 设置中关闭「后台省电/暂停」，否则最小化后截图画布定格
- 设置中关闭「点 X 退出」，改为最小化到托盘，避免误关

启动参数通过配置文件或环境变量：
- `SERVER_URL=wss://your-domain.com/ws`
- `AGENT_NAME=pc-home`

## 项目结构

```
gjjb/
├── server/
│   ├── main.py              # FastAPI + WebSocket 入口
│   ├── scheduler.py         # APScheduler 定时任务
│   ├── ws_hub.py            # WebSocket 连接管理
│   ├── db.py                # SQLite 初始化和访问
│   ├── models.py            # 数据模型
│   ├── templates/
│   │   └── dashboard.html   # Web 面板
│   └── requirements.txt
│
├── agent/
│   ├── main.py              # Agent 入口，WebSocket 连接
│   ├── adb_controller.py    # ADB 截图 + 点击
│   ├── image_matcher.py     # OpenCV 模板匹配
│   ├── executor.py          # 任务路由和执行
│   └── requirements.txt
│
└── templates/               # 图像识别模板
    ├── blessing_icon.png
    └── like_button.png
```

## 扩展预留

当前架构的扩展点：
- **新任务类型**：加 action + handler + 模板图，不改骨架
- **多 Agent**：不同 Agent 注册不同名字，HUB 区分管理
- **复杂流程**（征战等需要多步决策的）：未来在 executor 中引入简单状态机/步骤链
- **账号切换**：MuMu 多开实例 或 ADB 切账号，待后续设计

## 待定项

- 赐福图标模板需在 MuMu 中实际截图后制作
- Web 面板 UI 细节实现时确定，不做提前设计
