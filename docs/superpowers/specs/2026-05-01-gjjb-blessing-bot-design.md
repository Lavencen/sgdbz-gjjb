# 时光大爆炸赐福点赞挂机脚本 — 设计文档

日期: 2026-05-01

## 1. 背景与目标

为手游《时光大爆炸》制作挂机脚本。第一阶段落地场景：每天 0 点后检测赐福弹窗并点赞领取奖励。

不做完整挂机系统，只实现赐福点赞这一明确场景。长期目标覆盖全玩法自动化（资源采集、征战、贸易等），支持多账号切换，支持本地+远程双模式运行。

## 2. 总体阶段规划

采用渐进演进路线，每阶段独立可验证：

| 阶段 | 目标 | 核心产出 |
|------|------|----------|
| **Phase 0** | 人工校准 | 确认弹窗模板、点赞坐标、成功提示特征，固化为配置 |
| **Phase 1** | 本地 MVP | 纯本地 Python 脚本，ADB 截图+OpenCV 模板匹配+点击，支持独立/云控双模式 |
| **Phase 2** | 云端接入 | 服务端上线（FastAPI + WebSocket + APScheduler + SQLite + Web 面板），Agent 切换到云控模式 |
| **Phase 3+** | 扩展 | 多任务（领奖、资源收取等）、多账号、云手机迁移 |

Phase 0 和 Phase 1 不依赖服务器，先跑通"检测赐福→点赞→记录"闭环。

## 3. 运行环境

- **本机 PC**：Windows，安装 MuMu 模拟器，ADB 可用
- **服务器**（Phase 2）：腾讯云 4C4G，已部署 Caddy（反代）+ 跳板机（SSH），有备案域名

## 4. 总体架构（Phase 2 完整形态）

采用**云控架构 — 服务端调度 + 本机执行（ADB + 图像识别）**：

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

## 5. Phase 1：Agent 设计

### 5.1 运行模式

Agent 支持两种模式，通过配置切换：

- **独立模式（Phase 1）**：不需要服务器，本地轮询守护。Agent 内置轻量调度器，按配置间隔截图检测。
- **云控模式（Phase 2）**：连上 WebSocket 后，任务由服务端下发，Agent 只执行和回传。

Phase 1 写代码时预留 WebSocket client 接口，避免 Phase 2 重写。

### 5.2 组件

```
agent/
├── main.py           # 入口，读配置，选模式，启动循环
├── config.py         # 配置文件读取
├── adb.py            # ADB 操作：screencap + tap
├── matcher.py        # OpenCV 模板匹配
├── blessing_task.py  # 赐福点赞流程
├── logger.py         # 本地日志 + 失败截图保存
├── ws_client.py      # WebSocket client 骨架（Phase 2 启用）
└── requirements.txt  # opencv-python, websockets, pyyaml
```

### 5.3 守护循环（独立模式）

```
启动 → 检查 ADB/设备 → 进入循环
  → 截图
  → 模板匹配"赐福"弹窗
    ├── 找到 (匹配度 > 0.85) → 执行点赞流程 → 冷却 5s → 继续
    └── 未找到 → 等待 60s → 继续
```

### 5.4 赐福点赞流程

```
截图 → 模板匹配"赐福"弹窗 (匹配度 > 0.85)
  ├── 找到
  │   ├── 直接点击点赞按钮坐标（弹窗内已有点赞按钮）
  │   ├── 等待 2s
  │   ├── 截图 → 匹配"成功提示"模板
  │   ├── 成功 → 记录日志 + 保存截图 → 点击屏幕收取奖励 → 冷却 5s
  │   └── 失败 → 记录失败 + 保存截图 → 冷却
  │
  └── 未找到 → 等待 60s → 继续下一轮
```

关键点：
- 找到赐福弹窗直接点击点赞坐标，不再二次识别点赞按钮
- 成功/失败都不重试，一次性判断
- 成功后需要额外点击一次屏幕收取奖励
- 两种冷却：成功冷却 5s，未找到弹窗等待 60s

### 5.5 图像识别

- **赐福弹窗检测**：OpenCV `cv2.matchTemplate`，模板匹配，阈值 0.85
- **成功提示检测**：同上，匹配成功提示模板
- **点赞按钮**：使用固定坐标，不做模板匹配

模板图片（Phase 0 在 MuMu 中实际截图制作）：
- `templates/blessing_icon.png` — 赐福弹窗特征区域
- `templates/success.png` — 点赞成功提示

### 5.6 ADB 控制器

```python
# 截图：adb exec-out screencap -p > screenshot.png
# 点击：adb shell input tap x y
```

封装为 `screencap()` 和 `tap(x, y)` 两个函数。截图保存到临时目录，任务结束后清理。

## 6. Phase 2：服务端设计

### 6.1 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| 服务端框架 | FastAPI + asyncio | 原生 WebSocket，异步友好 |
| 定时调度 | APScheduler | cron 表达式 |
| 反向代理 | Caddy（已有） | 自动 HTTPS，WebSocket 透明代理 |
| 数据库 | SQLite（aiosqlite） | 零部署，够用 |
| Agent 通信 | websockets（Python） | 轻量异步 WebSocket 客户端 |

### 6.2 组件

```
server/
├── main.py              # FastAPI + WebSocket 入口
├── scheduler.py         # APScheduler 定时任务
├── ws_hub.py            # WebSocket 连接管理
├── db.py                # SQLite 初始化和访问
├── models.py            # 数据模型
├── templates/
│   └── dashboard.html   # Web 面板
└── requirements.txt
```

### 6.3 WebSocket 协议

Agent → 服务器：
```json
{"type": "register",    "agent": "pc-home"}
{"type": "heartbeat",   "agent": "pc-home"}
{"type": "task_result", "task_id": "xxx", "status": "ok", "detail": {}}
```

服务器 → Agent：
```json
{"type": "task", "task_id": "xxx", "task_type": "blessing_like"}
{"type": "ack",  "msg": "registered"}
```

### 6.4 心跳机制

- Agent 每 30s 发 heartbeat
- 服务端超时 90s 标记离线
- Agent 掉线自动重连（指数退避，最大间隔 60s）

### 6.5 定时调度

- 每天 23:59:50 触发 `blessing_like` 任务，推入任务队列
- cron 表达式：`50 59 23 * * *`

### 6.6 数据库

```sql
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,
    task_type   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    detail      TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE blessing_logs (
    id            TEXT PRIMARY KEY,
    task_id       TEXT NOT NULL,
    detected_at   TEXT,
    like_result   TEXT,
    detail        TEXT,
    screenshot    TEXT
);
```

### 6.7 Web 面板

| 路由 | 功能 |
|------|------|
| `GET /` | 仪表盘：Agent 状态、最近执行记录、心跳状态 |
| `POST /api/trigger/blessing` | 手动触发赐福检测 |
| `POST /api/cancel/{task_id}` | 停止当前任务 |
| `GET /api/tasks` | 任务执行历史 |

页面按钮：立即检测赐福、停止当前任务、重新连接。

### 6.8 部署

服务端（腾讯云）：
```bash
python server/main.py   # FastAPI，监听 127.0.0.1:8088
# Caddy 反代追加：
#   reverse_proxy /ws localhost:8088
#   reverse_proxy localhost:8088
```

Agent（本机 PC）：
```bash
python agent/main.py    # Windows 终端常驻运行
```

MuMu 模拟器设置：
- 关闭「后台省电/暂停」，避免最小化后截图定格
- 关闭「点 X 退出」，改为最小化到托盘

## 7. 配置

```yaml
# config.yaml
adb:
  path: "C:/MuMu/..."
  device_id: "emulator-5554"

game:
  screen_width: 1920
  screen_height: 1080

blessing:
  like_button_x: 540
  like_button_y: 960
  success_template: "templates/success.png"
  blessing_template: "templates/blessing_icon.png"

loop:
  detect_interval: 2
  not_found_wait: 60
  success_cooldown: 5

agent:
  name: "pc-home"
  mode: "standalone"        # "standalone" 或 "cloud"

server:                     # Phase 2 启用
  url: "wss://your-domain.com/ws"
  token: "xxx"
```

## 8. 日志

本地日志每行 JSON，写入 `logs/agent.log`：

```json
{"timestamp":"2026-05-01T00:00:05","task":"blessing","status":"success","detail":"..."}
{"timestamp":"2026-05-01T00:01:10","task":"blessing","status":"not_found","detail":"..."}
{"timestamp":"2026-05-01T00:02:15","task":"blessing","status":"failed","detail":"..."}
```

失败截图存 `logs/screenshots/`，按时间戳命名。

## 9. 工作区拆分

Agent 和服务端分属两个独立 workspace，各自开发、各自 git 管理：

| 工作区 | 环境 | 内容 | 依赖 |
|--------|------|------|------|
| `gjjb` | Windows 本机 | Agent 客户端（ADB/OpenCV/本地循环） | MuMu 模拟器、ADB |
| `gjjb-server` | Linux 虚拟机 | 服务端（FastAPI/WebSocket/APScheduler/SQLite） | Python 3.10+ |

Agent 端先以独立模式跑通，服务端开发时两边通过 WSS 联调。

### 9.1 Agent 端项目结构（`gjjb`）

```
gjjb/
├── config.yaml
├── agent/
│   ├── main.py
│   ├── config.py
│   ├── adb.py
│   ├── matcher.py
│   ├── blessing_task.py
│   ├── logger.py
│   ├── ws_client.py
│   └── requirements.txt
├── templates/                 # 图像识别模板
│   ├── blessing_icon.png
│   └── success.png
└── logs/
    ├── agent.log
    └── screenshots/
```

### 9.2 服务端项目结构（`gjjb-server`）

```
gjjb-server/
├── config.yaml
├── server/
│   ├── main.py
│   ├── scheduler.py
│   ├── ws_hub.py
│   ├── db.py
│   ├── models.py
│   ├── templates/
│   │   └── dashboard.html
│   └── requirements.txt
└── data/                      # SQLite 数据库文件
```

## 10. 风险与应对

### 模拟器兼容风险

游戏可能对模拟器环境、分辨率或性能敏感。

应对：固定 MuMu 模拟器，固定分辨率和 DPI，不在多环境之间过早适配。

### 识别误判风险

模板匹配可能受动画、亮度、活动皮肤变化影响。

应对：固定匹配区域减少干扰；使用成功提示做二次验证；失败时保留截图用于复盘；必要时准备多张模板。

### 重复点击或漏检风险

弹窗持续存在时可能重复点击，弹窗一闪而过时可能漏检。

应对：成功后进入冷却；每次检测结果用成功提示验证；失败不重试；截图间隔可配置。

### 长期运行稳定性

模拟器卡死、游戏掉线、网络波动、ADB 断开。

应对：Phase 1 先记录并告警；Phase 2 增加心跳监控；后续考虑自动重连和游戏前台恢复。

### 云端安全

接口裸奔可能被滥用。

应对：接口校验 Token；限制截图上传大小；日志避免记录账号敏感信息。

## 11. 暂不做范围

- 不抓包
- 不修改协议
- 不读写游戏内存
- 不修改客户端
- 不做支付、登录、账号切换相关自动化
- 不做高频点击
- 不做复杂全游戏挂机（Phase 1 只做赐福点赞）

## 12. 下一步

1. 生成两份实施计划：Agent 端（`gjjb`）+ 服务端（`gjjb-server`）
2. 在两台机器上分头执行

---

*本方案融合了 Claude 方案的云控架构设计（WebSocket、数据库、Web 面板）和 Codex 方案的渐进路线与风险分析。*
