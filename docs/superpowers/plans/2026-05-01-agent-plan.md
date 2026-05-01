# Agent 端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Windows 本机实现赐福点赞 Agent，支持独立模式（本地轮询守护）和云控模式预留接口。

**Architecture:** 单进程 Python 脚本，ADB 控制 MuMu 模拟器截图+点击，OpenCV 模板匹配检测 UI 元素，本地 JSON 日志。通过配置切换独立/云控模式。

**Tech Stack:** Python 3.10+, OpenCV (cv2), PyYAML, websockets (Phase 2)

---

### Task 1: 项目脚手架

**Files:**
- Create: `agent/requirements.txt`
- Create: `agent/__init__.py` (empty)
- Create: `config.yaml`

- [ ] **Step 1: 创建目录结构**

```bash
cd D:\luosichen\workspace\gjjb
mkdir -p agent logs/screenshots templates
```

- [ ] **Step 2: 创建 requirements.txt**

```bash
cat > agent/requirements.txt << 'EOF'
opencv-python>=4.8.0
pyyaml>=6.0
websockets>=12.0
EOF
```

- [ ] **Step 3: 创建 config.yaml 骨架**

```yaml
# config.yaml
adb:
  path: "C:/MuMu/emulator/nemu/EmulatorShell/adb.exe"
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
  mode: "standalone"

server:
  url: "wss://your-domain.com/ws"
  token: "placeholder-token"
```

- [ ] **Step 4: 创建空的 __init__.py**

```bash
touch agent/__init__.py
```

- [ ] **Step 5: 安装依赖**

```bash
pip install -r agent/requirements.txt
```

Expected: opencv-python, pyyaml, websockets 安装成功

- [ ] **Step 6: Commit**

```bash
git add agent/requirements.txt agent/__init__.py config.yaml
git commit -m "feat: add agent project scaffold with config skeleton"
```

---

### Task 2: 配置模块 config.py

**Files:**
- Create: `agent/config.py`
- Create: `tests/test_config.py` (先建目录 `tests/`，创建空的 `tests/__init__.py`)

- [ ] **Step 1: 创建测试目录**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2: 编写测试文件 tests/test_config.py**

```python
import pytest
import tempfile
import os
from pathlib import Path
from agent.config import load_config, Config


VALID_CONFIG = """
adb:
  path: "C:/adb/adb.exe"
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
  mode: "standalone"

server:
  url: "wss://example.com/ws"
  token: "test-token"
"""


class TestLoadConfig:
    def test_loads_valid_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_CONFIG)
            path = f.name
        try:
            cfg = load_config(path)
            assert cfg.adb.path == "C:/adb/adb.exe"
            assert cfg.adb.device_id == "emulator-5554"
            assert cfg.game.screen_width == 1920
            assert cfg.game.screen_height == 1080
            assert cfg.blessing.like_button_x == 540
            assert cfg.blessing.like_button_y == 960
            assert cfg.blessing.success_template == "templates/success.png"
            assert cfg.blessing.blessing_template == "templates/blessing_icon.png"
            assert cfg.loop.detect_interval == 2
            assert cfg.loop.not_found_wait == 60
            assert cfg.loop.success_cooldown == 5
            assert cfg.agent.name == "pc-home"
            assert cfg.agent.mode == "standalone"
            assert cfg.server.url == "wss://example.com/ws"
            assert cfg.server.token == "test-token"
        finally:
            os.unlink(path)

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_server_section_optional(self):
        config_without_server = """
adb:
  path: "adb"
  device_id: "d1"
game:
  screen_width: 800
  screen_height: 600
blessing:
  like_button_x: 1
  like_button_y: 2
  success_template: "s.png"
  blessing_template: "b.png"
loop:
  detect_interval: 1
  not_found_wait: 10
  success_cooldown: 1
agent:
  name: "a"
  mode: "standalone"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_without_server)
            path = f.name
        try:
            cfg = load_config(path)
            assert cfg.server.url == ""
            assert cfg.server.token == ""
        finally:
            os.unlink(path)
```

- [ ] **Step 3: 运行测试确认失败**

```bash
python -m pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.config'`

- [ ] **Step 4: 实现 agent/config.py**

```python
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class ADBConfig:
    path: str
    device_id: str


@dataclass
class GameConfig:
    screen_width: int
    screen_height: int


@dataclass
class BlessingConfig:
    like_button_x: int
    like_button_y: int
    success_template: str
    blessing_template: str


@dataclass
class LoopConfig:
    detect_interval: int
    not_found_wait: int
    success_cooldown: int


@dataclass
class AgentConfig:
    name: str
    mode: str


@dataclass
class ServerConfig:
    url: str
    token: str


@dataclass
class Config:
    adb: ADBConfig
    game: GameConfig
    blessing: BlessingConfig
    loop: LoopConfig
    agent: AgentConfig
    server: ServerConfig


def load_config(path: str = "config.yaml") -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    server_data = data.get("server") or {}
    return Config(
        adb=ADBConfig(**data["adb"]),
        game=GameConfig(**data["game"]),
        blessing=BlessingConfig(**data["blessing"]),
        loop=LoopConfig(**data["loop"]),
        agent=AgentConfig(**data["agent"]),
        server=ServerConfig(
            url=server_data.get("url", ""),
            token=server_data.get("token", ""),
        ),
    )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_config.py -v
```

Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add agent/config.py tests/test_config.py tests/__init__.py
git commit -m "feat: add config module with YAML loading"
```

---

### Task 3: 日志模块 logger.py

**Files:**
- Create: `agent/logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: 编写测试 tests/test_logger.py**

```python
import json
import tempfile
import shutil
from pathlib import Path
from agent.logger import Logger


class TestLogger:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.logger = Logger(log_dir=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_log_writes_json_line(self):
        self.logger.log("blessing", "success", "点赞成功")
        log_file = Path(self.tmpdir) / "agent.log"
        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["task"] == "blessing"
        assert entry["status"] == "success"
        assert entry["detail"] == "点赞成功"
        assert "timestamp" in entry

    def test_log_creates_screenshots_dir(self):
        screenshots_dir = Path(self.tmpdir) / "screenshots"
        assert screenshots_dir.exists()
        assert screenshots_dir.is_dir()

    def test_log_copies_screenshot(self):
        src_dir = Path(self.tmpdir) / "src"
        src_dir.mkdir()
        fake_screenshot = src_dir / "test.png"
        fake_screenshot.write_text("fake image")
        self.logger.log("blessing", "failed", "识别失败", fake_screenshot)
        pngs = list((Path(self.tmpdir) / "screenshots").glob("*.png"))
        assert len(pngs) == 1

    def test_multiple_logs_append(self):
        self.logger.log("blessing", "not_found", "第一次")
        self.logger.log("blessing", "success", "第二次")
        lines = (Path(self.tmpdir) / "agent.log").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_logger.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.logger'`

- [ ] **Step 3: 实现 agent/logger.py**

```python
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class Logger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir = self.log_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "agent.log"

    def log(self, task: str, status: str, detail: str, screenshot: Path | None = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "status": status,
            "detail": detail,
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if screenshot and screenshot.exists():
            ts = entry["timestamp"].replace(":", "-")
            dest = self.screenshot_dir / f"{ts}.png"
            shutil.copy2(screenshot, dest)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_logger.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/logger.py tests/test_logger.py
git commit -m "feat: add logger module with JSON logging and screenshot saving"
```

---

### Task 4: ADB 控制器 adb.py

**Files:**
- Create: `agent/adb.py`
- Create: `tests/test_adb.py`

- [ ] **Step 1: 编写测试 tests/test_adb.py**

```python
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.adb import ADBController


class TestADBController:
    def test_check_device_online(self):
        mock_result = MagicMock()
        mock_result.stdout = "List of devices attached\nemulator-5554\tdevice\n"
        with patch("subprocess.run", return_value=mock_result):
            adb = ADBController("adb", "emulator-5554")
            assert adb.check_device() is True

    def test_check_device_offline(self):
        mock_result = MagicMock()
        mock_result.stdout = "List of devices attached\nemulator-5554\toffline\n"
        with patch("subprocess.run", return_value=mock_result):
            adb = ADBController("adb", "emulator-5554")
            assert adb.check_device() is False

    def test_check_device_not_listed(self):
        mock_result = MagicMock()
        mock_result.stdout = "List of devices attached\n"
        with patch("subprocess.run", return_value=mock_result):
            adb = ADBController("adb", "emulator-5554")
            assert adb.check_device() is False

    def test_tap_sends_correct_command(self):
        with patch("subprocess.run") as mock_run:
            adb = ADBController("adb", "emulator-5554")
            adb.tap(100, 200)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "adb"
            assert args[1] == "-s"
            assert args[2] == "emulator-5554"
            assert args[3] == "shell"
            assert args[4] == "input"
            assert args[5] == "tap"
            assert args[6] == "100"
            assert args[7] == "200"

    def test_screencap_returns_path(self):
        with patch("subprocess.run") as mock_run:
            adb = ADBController("adb", "emulator-5554")
            result = adb.screencap()
            assert isinstance(result, Path)
            mock_run.assert_called_once()

    def test_screencap_command_uses_exec_out(self):
        with patch("subprocess.run") as mock_run:
            adb = ADBController("adb", "emulator-5554")
            adb.screencap()
            args = mock_run.call_args[0][0]
            assert "exec-out" in args
            assert "screencap" in args
            assert "-p" in args
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_adb.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.adb'`

- [ ] **Step 3: 实现 agent/adb.py**

```python
import subprocess
import tempfile
import time
from pathlib import Path


class ADBController:
    def __init__(self, adb_path: str, device_id: str):
        self.adb_path = adb_path
        self.device_id = device_id

    def _adb(self, *args) -> str:
        cmd = [self.adb_path, "-s", self.device_id] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()

    def check_device(self) -> bool:
        result = subprocess.run(
            [self.adb_path, "devices"], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if line.startswith(self.device_id) and "\tdevice" in line:
                return True
        return False

    def screencap(self) -> Path:
        tmp = Path(tempfile.gettempdir()) / f"gjjb_screencap_{int(time.time() * 1000)}.png"
        with open(tmp, "wb") as f:
            subprocess.run(
                [self.adb_path, "-s", self.device_id, "exec-out", "screencap", "-p"],
                stdout=f,
                check=True,
            )
        return tmp

    def tap(self, x: int, y: int):
        subprocess.run(
            [self.adb_path, "-s", self.device_id, "shell", "input", "tap", str(x), str(y)],
            check=True,
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_adb.py -v
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/adb.py tests/test_adb.py
git commit -m "feat: add ADB controller with screencap and tap"
```

---

### Task 5: 图像匹配 matcher.py

**Files:**
- Create: `agent/matcher.py`
- Create: `tests/test_matcher.py`

- [ ] **Step 1: 编写测试 tests/test_matcher.py**

```python
import numpy as np
import cv2
import tempfile
from pathlib import Path
from agent.matcher import match_template


def _create_test_image(width: int, height: int, color: tuple = (255, 255, 255)) -> Path:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = color
    tmp = Path(tempfile.gettempdir()) / "test_img.png"
    cv2.imwrite(str(tmp), img)
    return tmp


class TestMatchTemplate:
    def test_exact_match_returns_true(self):
        screen = np.zeros((600, 800, 3), dtype=np.uint8)
        screen[:] = (128, 128, 128)
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:] = (255, 0, 0)
        x, y = 100, 200
        screen[y : y + 50, x : x + 50] = template

        screen_path = Path(tempfile.gettempdir()) / "test_screen.png"
        tmpl_path = Path(tempfile.gettempdir()) / "test_tmpl.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)
        try:
            matched, center = match_template(screen_path, tmpl_path, threshold=0.9)
            assert matched is True
            assert center is not None
            cx, cy = center
            assert abs(cx - (x + 25)) < 5
            assert abs(cy - (y + 25)) < 5
        finally:
            screen_path.unlink(missing_ok=True)
            tmpl_path.unlink(missing_ok=True)

    def test_no_match_returns_false(self):
        screen = np.zeros((600, 800, 3), dtype=np.uint8)
        screen[:] = (128, 128, 128)
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:] = (255, 0, 0)

        screen_path = Path(tempfile.gettempdir()) / "test_screen2.png"
        tmpl_path = Path(tempfile.gettempdir()) / "test_tmpl2.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)
        try:
            matched, center = match_template(screen_path, tmpl_path, threshold=0.9)
            assert matched is False
            assert center is None
        finally:
            screen_path.unlink(missing_ok=True)
            tmpl_path.unlink(missing_ok=True)

    def test_default_threshold_is_0_85(self):
        import inspect
        sig = inspect.signature(match_template)
        assert sig.parameters["threshold"].default == 0.85

    def test_nonexistent_screenshot_raises(self):
        import pytest
        with pytest.raises(cv2.error):
            match_template(
                Path("/nonexistent/screen.png"),
                Path("/nonexistent/tmpl.png"),
            )
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_matcher.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.matcher'`

- [ ] **Step 3: 实现 agent/matcher.py**

```python
from pathlib import Path
import cv2


def match_template(
    screenshot_path: Path,
    template_path: Path,
    threshold: float = 0.85,
) -> tuple[bool, tuple[int, int] | None]:
    screen = cv2.imread(str(screenshot_path))
    template = cv2.imread(str(template_path))

    if screen is None or template is None:
        return False, None

    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        return False, None

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        h, w = template.shape[:2]
        center = (max_loc[0] + w // 2, max_loc[1] + h // 2)
        return True, center
    return False, None
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_matcher.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/matcher.py tests/test_matcher.py
git commit -m "feat: add OpenCV template matching module"
```

---

### Task 6: 赐福任务 blessing_task.py

**Files:**
- Create: `agent/blessing_task.py`
- Create: `tests/test_blessing_task.py`

- [ ] **Step 1: 编写测试 tests/test_blessing_task.py**

```python
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import cv2
from agent.blessing_task import BlessingTask, TaskStatus
from agent.config import (
    Config, ADBConfig, GameConfig, BlessingConfig,
    LoopConfig, AgentConfig, ServerConfig,
)


def _make_config(like_x=540, like_y=960, screen_w=1920, screen_h=1080) -> Config:
    return Config(
        adb=ADBConfig(path="adb", device_id="emu"),
        game=GameConfig(screen_width=screen_w, screen_height=screen_h),
        blessing=BlessingConfig(
            like_button_x=like_x,
            like_button_y=like_y,
            success_template="templates/success.png",
            blessing_template="templates/blessing_icon.png",
        ),
        loop=LoopConfig(detect_interval=2, not_found_wait=60, success_cooldown=5),
        agent=AgentConfig(name="test", mode="standalone"),
        server=ServerConfig(url="", token=""),
    )


class TestBlessingTask:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_screen_with_template(self, template_region, screen_size=(800, 600)):
        """Create a screen image with a template embedded at template_region (x,y,w,h)."""
        screen = np.zeros((screen_size[1], screen_size[0], 3), dtype=np.uint8)
        screen[:] = (100, 100, 100)
        tx, ty, tw, th = template_region
        template = np.zeros((th, tw, 3), dtype=np.uint8)
        template[:] = (0, 255, 0)
        screen[ty : ty + th, tx : tx + tw] = template
        screen_path = self.tmpdir / "screen.png"
        cv2.imwrite(str(screen_path), screen)
        # Save just the template
        tmpl_path = self.tmpdir / "tmpl.png"
        cv2.imwrite(str(tmpl_path), template)
        return screen_path, tmpl_path

    def test_not_found_when_no_match(self):
        screen = np.zeros((600, 800, 3), dtype=np.uint8)
        screen[:] = (100, 100, 100)
        template = np.zeros((50, 50, 3), dtype=np.uint8)
        template[:] = (0, 255, 0)
        screen_path = self.tmpdir / "screen_nomatch.png"
        tmpl_path = self.tmpdir / "blessing_nomatch.png"
        cv2.imwrite(str(screen_path), screen)
        cv2.imwrite(str(tmpl_path), template)

        cfg = _make_config()
        cfg.blessing.blessing_template = str(tmpl_path)
        cfg.blessing.success_template = str(tmpl_path)

        mock_adb = MagicMock()
        mock_adb.screencap.return_value = screen_path

        task = BlessingTask(mock_adb, cfg)
        status, detail, screenshot = task.execute()

        assert status == TaskStatus.NOT_FOUND
        assert "未检测到" in detail
        mock_adb.tap.assert_not_called()

    def test_success_flow(self):
        screen_path, tmpl_path = self._make_screen_with_template((100, 200, 50, 50))
        success_path, _ = self._make_screen_with_template((300, 400, 50, 50))

        cfg = _make_config(like_x=200, like_y=300)
        cfg.blessing.blessing_template = str(tmpl_path)
        cfg.blessing.success_template = str(tmpl_path)

        mock_adb = MagicMock()
        mock_adb.screencap.side_effect = [screen_path, success_path]

        task = BlessingTask(mock_adb, cfg)
        status, detail, screenshot = task.execute()

        assert status == TaskStatus.SUCCESS
        assert detail == "点赞成功"
        assert screenshot == success_path
        # Should tap like button, then center of screen for reward
        assert mock_adb.tap.call_count == 2
        mock_adb.tap.assert_any_call(200, 300)
        mock_adb.tap.assert_any_call(960, 540)

    def test_failed_when_success_not_confirmed(self):
        screen_path, tmpl_path = self._make_screen_with_template((100, 200, 50, 50))
        # Second screenshot has no success template
        fail_screen = np.zeros((600, 800, 3), dtype=np.uint8)
        fail_screen[:] = (100, 100, 100)
        fail_path = self.tmpdir / "fail_screen.png"
        cv2.imwrite(str(fail_path), fail_screen)

        cfg = _make_config()
        cfg.blessing.blessing_template = str(tmpl_path)
        cfg.blessing.success_template = str(tmpl_path)

        mock_adb = MagicMock()
        mock_adb.screencap.side_effect = [screen_path, fail_path]

        task = BlessingTask(mock_adb, cfg)
        status, detail, screenshot = task.execute()

        assert status == TaskStatus.FAILED
        assert "未检测到成功提示" in detail
        assert screenshot == fail_path
        # Only taps like button, not reward
        assert mock_adb.tap.call_count == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_blessing_task.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'agent.blessing_task'`

- [ ] **Step 3: 实现 agent/blessing_task.py**

```python
import time
from enum import Enum
from pathlib import Path
from agent.adb import ADBController
from agent.config import Config
from agent.matcher import match_template


class TaskStatus(Enum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    FAILED = "failed"


class BlessingTask:
    def __init__(self, adb: ADBController, config: Config):
        self.adb = adb
        self.config = config

    def execute(self) -> tuple[TaskStatus, str, Path | None]:
        screenshot = self.adb.screencap()

        found, _ = match_template(
            screenshot,
            Path(self.config.blessing.blessing_template),
        )
        if not found:
            return TaskStatus.NOT_FOUND, "赐福弹窗未检测到", None

        self.adb.tap(self.config.blessing.like_button_x, self.config.blessing.like_button_y)
        time.sleep(2)

        screenshot2 = self.adb.screencap()
        success, _ = match_template(
            screenshot2,
            Path(self.config.blessing.success_template),
        )

        if success:
            self.adb.tap(
                self.config.game.screen_width // 2,
                self.config.game.screen_height // 2,
            )
            return TaskStatus.SUCCESS, "点赞成功", screenshot2
        else:
            return TaskStatus.FAILED, "点赞后未检测到成功提示", screenshot2
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_blessing_task.py -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/blessing_task.py tests/test_blessing_task.py
git commit -m "feat: add blessing task with detection, like, and reward collection"
```

---

### Task 7: 主入口 main.py

**Files:**
- Create: `agent/main.py`

- [ ] **Step 1: 实现 agent/main.py**

```python
import time
import signal
import sys
from pathlib import Path
from agent.config import load_config
from agent.adb import ADBController
from agent.blessing_task import BlessingTask, TaskStatus
from agent.logger import Logger


def main():
    cfg = load_config()
    logger = Logger()
    adb = ADBController(cfg.adb.path, cfg.adb.device_id)

    if not adb.check_device():
        logger.log("startup", "error", f"ADB 设备未连接: {cfg.adb.device_id}")
        print(f"[ERROR] ADB 设备 {cfg.adb.device_id} 未连接，请检查模拟器是否启动")
        sys.exit(1)

    print(f"[INFO] Agent 启动，模式: {cfg.agent.mode}，设备: {cfg.adb.device_id}")
    logger.log("startup", "ok", f"mode={cfg.agent.mode} device={cfg.adb.device_id}")

    task = BlessingTask(adb, cfg)

    def handle_exit(sig, frame):
        print("\n[INFO] 收到退出信号，Agent 停止")
        logger.log("shutdown", "ok", "agent stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while True:
        status, detail, screenshot = task.execute()
        logger.log("blessing", status.value, detail, screenshot)

        if status == TaskStatus.NOT_FOUND:
            wait = cfg.loop.not_found_wait
        else:
            wait = cfg.loop.success_cooldown

        print(f"[{status.value.upper()}] {detail}，等待 {wait}s")
        time.sleep(wait)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证入口可导入**

```bash
python -c "from agent.main import main; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add agent/main.py
git commit -m "feat: add agent main entry with daemon loop"
```

---

### Task 8: WebSocket 客户端骨架（Phase 2 预留）

**Files:**
- Create: `agent/ws_client.py`

- [ ] **Step 1: 实现 agent/ws_client.py**

```python
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
                extra_headers={"Authorization": f"Bearer {self.token}"},
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
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from agent.ws_client import WSClient; print('import ok')"
```

Expected: `import ok`

- [ ] **Step 3: Commit**

```bash
git add agent/ws_client.py
git commit -m "feat: add WebSocket client skeleton for Phase 2 cloud mode"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: 确认所有模块导入正常**

```bash
python -c "
from agent.config import load_config, Config
from agent.logger import Logger
from agent.adb import ADBController
from agent.matcher import match_template
from agent.blessing_task import BlessingTask, TaskStatus
from agent.ws_client import WSClient
print('All modules imported successfully')
"
```

Expected: `All modules imported successfully`

- [ ] **Step 2: 运行全部测试**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS (config: 3, logger: 4, adb: 5, matcher: 4, blessing_task: 3 = 19 total)

- [ ] **Step 3: Phase 0 准备 — 放置模板图片**

确认以下文件就位（用户提供的截图）：
- `templates/blessing_icon.png`
- `templates/success.png`

```bash
ls -la templates/
```

- [ ] **Step 4: 更新 config.yaml 中的坐标**

根据实际截图测量点赞按钮坐标，修改 `config.yaml` 中 `blessing.like_button_x` 和 `blessing.like_button_y`。

- [ ] **Step 5: 启动 MuMu 模拟器，确认 ADB 连接**

```bash
adb devices
```

Expected: 列表中显示 `emulator-5554  device`

- [ ] **Step 6: 试运行 Agent**

```bash
python -m agent.main
```

观察输出：应显示 Agent 启动成功，开始检测循环。

- [ ] **Step 7: Commit**

```bash
git add templates/ config.yaml
git commit -m "feat: add template images and finalize config for Phase 0"
```
