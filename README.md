# GJJB Agent

`gjjb` 是一个运行在 Windows 本机的游戏自动化 Agent 项目。它通过 ADB 控制 MuMu 模拟器截图和点击, 再用 OpenCV 模板匹配识别当前游戏界面, 按 `rules.yaml` 中定义的规则执行动作。

当前仓库主要实现本地独立模式, 目标场景是识别《时光大爆炸》的赐福点赞/领奖页面, 自动点击点赞并领取奖励。云控 WebSocket 客户端接口已预留, 但当前主流程仍以本地循环为主。

## 功能概览

- ADB 连接 MuMu 模拟器, 支持截图和点击。
- OpenCV 模板匹配, 支持多尺度匹配和纯色模板处理。
- YAML 规则驱动状态机, 支持按优先级选择最合适的状态。
- 支持固定坐标点击, 屏幕比例点击和等待动作。
- 本地 JSON 行日志, 并保存执行截图到 `logs/screenshots/`。
- 单元测试覆盖配置加载, ADB 封装, 模板匹配, 规则加载, 动作执行和引擎流程。

## 项目结构

```text
gjjb/
├── agent/
│   ├── main.py            # 启动入口
│   ├── engine.py          # 主循环和状态选择
│   ├── rules.py           # YAML 规则加载和执行
│   ├── actions.py         # tap, tap_ratio, wait 等动作
│   ├── matcher.py         # OpenCV 模板匹配
│   ├── adb.py             # ADB 截图和点击封装
│   ├── config.py          # config.yaml 加载
│   ├── logger.py          # 本地日志和截图保存
│   ├── ws_client.py       # 云控模式 WebSocket 客户端骨架
│   └── requirements.txt   # Python 依赖
├── config.yaml            # 本地运行配置
├── rules.yaml             # 状态识别与动作规则
├── templates/             # 模板匹配图片
├── logs/                  # 运行日志, 已被 git 忽略
├── tests/                 # 单元测试
└── docs/superpowers/      # 历史设计和实施文档
```

## 环境要求

- Windows
- Python 3.10+
- MuMu 模拟器
- 可用的 ADB, 默认配置指向 MuMu 自带 ADB

安装依赖:

```powershell
python -m pip install -r agent/requirements.txt
```

## 配置

核心配置在 `config.yaml`:

```yaml
adb:
  path: "D:/Program Files (x86)/MuMuPlayer/nx_main/adb.exe"
  device_id: "127.0.0.1:16384"

game:
  screen_width: 1080
  screen_height: 1920

loop:
  detect_interval: 2
  not_found_wait: 15
  success_cooldown: 5

agent:
  name: "pc-home"
  mode: "standalone"
```

运行前请确认:

1. `adb.path` 指向本机真实的 ADB 可执行文件。
2. `adb.device_id` 与 `adb devices` 输出中的设备 ID 一致。
3. `game.screen_width` 和 `game.screen_height` 与模拟器分辨率一致。
4. `templates/` 下的模板图片来自当前模拟器和游戏画面, 否则匹配率可能不稳定。

### 如何找到 adb.path

`adb.path` 是 ADB 可执行文件 `adb.exe` 的完整路径。MuMu 模拟器通常会自带 ADB, 常见位置包括:

```text
D:/Program Files (x86)/MuMuPlayer/nx_main/adb.exe
C:/Program Files (x86)/MuMuPlayer/nx_main/adb.exe
C:/Program Files/Netease/MuMu Player 12/shell/adb.exe
```

如果不确定安装在哪, 可以在 PowerShell 里搜索:

```powershell
Get-ChildItem -Path "C:/Program Files","C:/Program Files (x86)","D:/" -Recurse -Filter adb.exe -ErrorAction SilentlyContinue
```

找到结果后, 把完整路径写入 `config.yaml`:

```yaml
adb:
  path: "D:/Program Files (x86)/MuMuPlayer/nx_main/adb.exe"
```

如果系统环境变量里已经有可用的 ADB, 也可以检查:

```powershell
where.exe adb
```

### 如何找到 adb.device_id

先启动 MuMu 模拟器, 再用刚找到的 `adb.exe` 查看在线设备:

```powershell
& "D:/Program Files (x86)/MuMuPlayer/nx_main/adb.exe" devices
```

输出类似:

```text
List of devices attached
127.0.0.1:16384    device
```

其中 `device` 前面的值就是 `adb.device_id`, 写入 `config.yaml`:

```yaml
adb:
  device_id: "127.0.0.1:16384"
```

如果列表为空, 一般是模拟器还没完全启动, ADB 路径不对, 或设备端口变了。可以重启 MuMu 后再执行一次 `devices` 命令。

## 运行

先确认设备在线:

```powershell
& "D:/Program Files (x86)/MuMuPlayer/nx_main/adb.exe" devices
```

启动 Agent:

```powershell
python -m agent.main
```

程序启动后会持续执行:

1. 通过 ADB 截图。
2. 用 `rules.yaml` 中的模板识别当前状态。
3. 按优先级选择匹配状态。
4. 执行动作。
5. 写入日志并等待下一轮。

按 `Ctrl+C` 可停止程序。

## 规则说明

规则定义在 `rules.yaml`。当前已有两个状态:

- `blessing_reward_page`: 识别成功/领奖页面, 优先级 `110`, 先处理领奖。
- `blessing_like_page`: 识别点赞按钮页面, 优先级 `100`, 执行点赞。

规则示例:

```yaml
rules:
  blessing_like_page:
    priority: 100
    detect:
      template: "templates/like_button.png"
      threshold: 0.85
    actions:
      - tap: [978, 1529]
      - wait: 2
    waits:
      success: 2
      failed: 5
```

支持的动作:

- `tap: [x, y]`: 点击固定坐标。
- `tap_ratio: [rx, ry]`: 按屏幕宽高比例点击, 例如 `[0.5, 0.75]`。
- `wait: seconds`: 等待指定秒数。

如果多个规则同时匹配, 引擎会优先选择 `priority` 更高的规则; 优先级相同时选择匹配置信度更高的规则。

## 日志

运行日志写入:

```text
logs/agent.log
```

日志是 JSON Lines 格式, 每行一条记录。执行时的截图会复制到:

```text
logs/screenshots/
```

这些运行产物不建议提交到 git。

## 测试

运行全部测试:

```powershell
python -m pytest tests/ -v
```

运行单个测试文件:

```powershell
python -m pytest tests/test_rules.py -v
```

## 常见问题

### ADB 设备未连接

检查 MuMu 模拟器是否已启动, 并确认 `config.yaml` 中的 `adb.path` 和 `adb.device_id` 与本机环境一致。

### 识别不到页面

优先检查模板图片是否过期。游戏 UI, 分辨率, DPI, 缩放比例或活动皮肤变化都可能影响模板匹配。可以重新从模拟器截图中裁剪模板, 再调整 `rules.yaml` 中的 `threshold`。

### 点击位置不对

确认模拟器分辨率与 `config.yaml` 中的 `game.screen_width` 和 `game.screen_height` 一致。如果使用固定坐标点击, 需要重新测量当前分辨率下的坐标。

## 备注

当前项目只做本地自动化 Agent。`server` 配置和 `agent/ws_client.py` 是后续云控模式预留接口, 当前默认不需要配置真实服务端。
