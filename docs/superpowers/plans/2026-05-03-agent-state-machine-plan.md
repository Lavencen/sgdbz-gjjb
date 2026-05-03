# Agent State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the local MuMu Agent from a single blessing script into a YAML-plus-Python-handler state machine while preserving the current blessing like and reward behavior.

**Architecture:** Add a small engine that captures a screenshot, detects matching states, chooses the highest-priority match, executes configured actions, logs the result, and returns the next wait interval. Simple states are defined in `rules.yaml`; complex future states can be implemented as Python handlers that share the same `detect(ctx)` and `handle(ctx, match)` interface.

**Tech Stack:** Python 3.10+, PyYAML, OpenCV, pytest, ADB via MuMu.

---

## File Structure

- Modify `agent/matcher.py`: keep `match_template()` compatibility, add confidence-returning `locate_template()`.
- Create `agent/state.py`: dataclasses for `StateMatch`, `ActionResult`, `AgentContext`, and `ResultStatus`.
- Create `agent/actions.py`: execute `tap`, `tap_ratio`, and `wait` actions against an `AgentContext`.
- Create `agent/rules.py`: load YAML rules, validate template paths, and expose `YAMLRule.detect()` / `YAMLRule.handle()`.
- Create `agent/engine.py`: one-shot and forever-running state-machine engine.
- Create `rules.yaml`: split blessing into `blessing_reward_page` and `blessing_like_page`.
- Modify `agent/main.py`: initialize `Engine` and `rules.yaml` instead of `BlessingTask`.
- Keep `agent/blessing_task.py`: leave it in place for compatibility during this phase.
- Add tests:
  - `tests/test_actions.py`
  - `tests/test_rules.py`
  - `tests/test_engine.py`
  - Extend `tests/test_matcher.py`

---

### Task 1: Add Confidence-Aware Template Matching

**Files:**
- Modify: `agent/matcher.py`
- Modify: `tests/test_matcher.py`

- [ ] **Step 1: Add failing matcher detail test**

Append this test to `tests/test_matcher.py`:

```python
def test_locate_template_returns_confidence_and_center(self):
    from agent.matcher import locate_template

    screen = np.zeros((600, 800, 3), dtype=np.uint8)
    screen[:] = (128, 128, 128)
    template = np.zeros((40, 40, 3), dtype=np.uint8)
    template[:] = (255, 0, 0)
    cv2.circle(template, (20, 20), 10, (0, 255, 0), -1)
    x, y = 320, 240
    screen[y : y + 40, x : x + 40] = template

    screen_path = Path(tempfile.gettempdir()) / "test_locate_screen.png"
    tmpl_path = Path(tempfile.gettempdir()) / "test_locate_tmpl.png"
    cv2.imwrite(str(screen_path), screen)
    cv2.imwrite(str(tmpl_path), template)
    try:
        result = locate_template(screen_path, tmpl_path, threshold=0.9)
        assert result.matched is True
        assert result.center is not None
        assert result.confidence >= 0.9
        assert abs(result.center[0] - (x + 20)) < 5
        assert abs(result.center[1] - (y + 20)) < 5
    finally:
        screen_path.unlink(missing_ok=True)
        tmpl_path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run matcher test and verify failure**

Run:

```bash
python -m pytest tests/test_matcher.py::TestMatchTemplate::test_locate_template_returns_confidence_and_center -v
```

Expected: FAIL with `ImportError` or `cannot import name 'locate_template'`.

- [ ] **Step 3: Replace `agent/matcher.py` with confidence-aware implementation**

Use this complete file content:

```python
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class TemplateMatch:
    matched: bool
    confidence: float
    center: tuple[int, int] | None
    scale: float | None


def match_template(
    screenshot_path: Path,
    template_path: Path,
    threshold: float = 0.85,
) -> tuple[bool, tuple[int, int] | None]:
    result = locate_template(screenshot_path, template_path, threshold)
    return result.matched, result.center


def locate_template(
    screenshot_path: Path,
    template_path: Path,
    threshold: float = 0.85,
) -> TemplateMatch:
    screen = cv2.imread(str(screenshot_path))
    template = cv2.imread(str(template_path))

    if screen is None or template is None:
        return TemplateMatch(False, 0.0, None, None)

    if template.shape[0] <= screen.shape[0] and template.shape[1] <= screen.shape[1]:
        score, center = _score_template(screen, template)
        if score >= threshold:
            return TemplateMatch(True, score, center, 1.0)

    best = (float("-inf"), None, None)
    for scale in (0.75, 0.85, 0.95, 1.05, 1.15, 1.25, 1.3, 1.35, 1.4, 1.5):
        candidate = _resize_template(template, scale)
        if candidate.shape[0] > screen.shape[0] or candidate.shape[1] > screen.shape[1]:
            continue

        score, center = _score_template(screen, candidate)
        if score > best[0]:
            best = (score, center, scale)

    if best[0] >= threshold:
        return TemplateMatch(True, float(best[0]), best[1], best[2])
    confidence = 0.0 if best[0] == float("-inf") else float(best[0])
    return TemplateMatch(False, confidence, None, best[2])


def _resize_template(template, scale: float):
    if scale == 1.0:
        return template
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(template, None, fx=scale, fy=scale, interpolation=interpolation)


def _score_template(screen, template) -> tuple[float, tuple[int, int]]:
    channel_std = np.std(template.reshape(-1, template.shape[2]), axis=0)
    if bool(np.all(channel_std == 0.0)):
        return _score_flat_template(screen, template)

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    h, w = template.shape[:2]
    center = (max_loc[0] + w // 2, max_loc[1] + h // 2)
    return float(max_val), center


def _score_flat_template(screen, template) -> tuple[float, tuple[int, int]]:
    result = cv2.matchTemplate(screen, template, cv2.TM_SQDIFF_NORMED)
    min_val, _, min_loc, _ = cv2.minMaxLoc(result)
    score = 1.0 - min_val
    h, w = template.shape[:2]
    center = (min_loc[0] + w // 2, min_loc[1] + h // 2)
    return float(score), center
```

- [ ] **Step 4: Run matcher tests**

Run:

```bash
python -m pytest tests/test_matcher.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/matcher.py tests/test_matcher.py
git commit -m "feat: expose template match confidence"
```

---

### Task 2: Add State Models and Generic Actions

**Files:**
- Create: `agent/state.py`
- Create: `agent/actions.py`
- Create: `tests/test_actions.py`

- [ ] **Step 1: Write failing action tests**

Create `tests/test_actions.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from agent.actions import execute_action, execute_actions
from agent.config import (
    ADBConfig,
    AgentConfig,
    BlessingConfig,
    Config,
    GameConfig,
    LoopConfig,
    ServerConfig,
)
from agent.state import AgentContext


def _make_config() -> Config:
    return Config(
        adb=ADBConfig(path="adb", device_id="emu"),
        game=GameConfig(screen_width=1920, screen_height=1080),
        blessing=BlessingConfig(
            like_button_x=978,
            like_button_y=1529,
            success_template="templates/success.png",
            blessing_template="templates/like_button.png",
        ),
        loop=LoopConfig(detect_interval=2, not_found_wait=15, success_cooldown=5),
        agent=AgentConfig(name="test", mode="standalone"),
        server=ServerConfig(url="", token=""),
    )


def _make_context():
    return AgentContext(
        adb=MagicMock(),
        config=_make_config(),
        logger=MagicMock(),
        screenshot=Path("screen.png"),
        sleeper=MagicMock(),
    )


def test_execute_tap_action():
    ctx = _make_context()
    execute_action({"tap": [100, 200]}, ctx)
    ctx.adb.tap.assert_called_once_with(100, 200)


def test_execute_tap_ratio_action():
    ctx = _make_context()
    execute_action({"tap_ratio": [0.5, 0.75]}, ctx)
    ctx.adb.tap.assert_called_once_with(960, 810)


def test_execute_wait_action():
    ctx = _make_context()
    execute_action({"wait": 1}, ctx)
    ctx.sleeper.assert_called_once_with(1)


def test_execute_actions_runs_in_order():
    ctx = _make_context()
    execute_actions(
        [
            {"tap": [1, 2]},
            {"wait": 3},
            {"tap_ratio": [0.5, 0.75]},
        ],
        ctx,
    )
    assert ctx.adb.tap.call_args_list[0].args == (1, 2)
    assert ctx.sleeper.call_args_list[0].args == (3,)
    assert ctx.adb.tap.call_args_list[1].args == (960, 810)


def test_unknown_action_raises_value_error():
    ctx = _make_context()
    try:
        execute_action({"swipe": [1, 2, 3, 4]}, ctx)
    except ValueError as exc:
        assert "Unsupported action" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run action tests and verify failure**

Run:

```bash
python -m pytest tests/test_actions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.actions'`.

- [ ] **Step 3: Create `agent/state.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from agent.adb import ADBController
from agent.config import Config
from agent.logger import Logger
from agent.matcher import TemplateMatch, locate_template


class ResultStatus(str, Enum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class StateMatch:
    name: str
    confidence: float
    priority: int
    screenshot: Path
    center: tuple[int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    status: ResultStatus
    detail: str
    screenshot: Path | None = None
    next_wait: float | None = None
    state: str = ""
    confidence: float = 0.0


@dataclass
class AgentContext:
    adb: ADBController
    config: Config
    logger: Logger
    screenshot: Path
    sleeper: Callable[[float], None]

    @property
    def screen_width(self) -> int:
        return self.config.game.screen_width

    @property
    def screen_height(self) -> int:
        return self.config.game.screen_height

    def sleep(self, seconds: float):
        self.sleeper(seconds)

    def match_template(self, template_path: Path, threshold: float) -> TemplateMatch:
        return locate_template(self.screenshot, template_path, threshold)
```

- [ ] **Step 4: Create `agent/actions.py`**

```python
from agent.state import AgentContext


def execute_actions(actions: list[dict], ctx: AgentContext):
    for action in actions:
        execute_action(action, ctx)


def execute_action(action: dict, ctx: AgentContext):
    if "tap" in action:
        x, y = action["tap"]
        ctx.adb.tap(int(x), int(y))
        return

    if "tap_ratio" in action:
        rx, ry = action["tap_ratio"]
        x = round(ctx.screen_width * float(rx))
        y = round(ctx.screen_height * float(ry))
        ctx.adb.tap(x, y)
        return

    if "wait" in action:
        ctx.sleep(float(action["wait"]))
        return

    raise ValueError(f"Unsupported action: {action}")
```

- [ ] **Step 5: Run action tests**

Run:

```bash
python -m pytest tests/test_actions.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/state.py agent/actions.py tests/test_actions.py
git commit -m "feat: add state models and generic actions"
```

---

### Task 3: Add YAML Rules and Rule Loader

**Files:**
- Create: `agent/rules.py`
- Create: `rules.yaml`
- Create: `tests/test_rules.py`

- [ ] **Step 1: Write failing rule tests**

Create `tests/test_rules.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from agent.rules import YAMLRule, load_rules
from agent.state import AgentContext, ResultStatus


def test_load_rules_sorts_by_priority(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "like.png").write_bytes(b"fake")
    (templates / "success.png").write_bytes(b"fake")
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        """
rules:
  like:
    priority: 100
    detect:
      template: "templates/like.png"
      threshold: 0.85
    actions:
      - tap: [1, 2]
    waits:
      success: 2
  reward:
    priority: 110
    detect:
      template: "templates/success.png"
      threshold: 0.85
    actions:
      - tap_ratio: [0.5, 0.75]
    waits:
      success: 5
""",
        encoding="utf-8",
    )

    rules = load_rules(rules_file)

    assert [rule.name for rule in rules] == ["reward", "like"]
    assert rules[0].priority == 110
    assert rules[1].actions == [{"tap": [1, 2]}]


def test_load_rules_rejects_missing_template(tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        """
rules:
  missing:
    priority: 1
    detect:
      template: "templates/missing.png"
      threshold: 0.85
    actions:
      - wait: 1
""",
        encoding="utf-8",
    )

    try:
        load_rules(rules_file)
    except FileNotFoundError as exc:
        assert "templates/missing.png" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_yaml_rule_detect_returns_state_match():
    match_result = MagicMock()
    match_result.matched = True
    match_result.confidence = 0.91
    match_result.center = (10, 20)
    match_result.scale = 1.0
    ctx = MagicMock(spec=AgentContext)
    ctx.screenshot = Path("screen.png")
    ctx.match_template.return_value = match_result
    rule = YAMLRule(
        name="like",
        priority=100,
        template=Path("templates/like.png"),
        threshold=0.85,
        actions=[{"tap": [1, 2]}],
        waits={"success": 2},
    )

    state_match = rule.detect(ctx)

    assert state_match is not None
    assert state_match.name == "like"
    assert state_match.confidence == 0.91
    assert state_match.center == (10, 20)
    assert state_match.metadata["template"] == "templates/like.png"


def test_yaml_rule_handle_executes_actions_and_returns_wait(monkeypatch):
    calls = []
    monkeypatch.setattr("agent.rules.execute_actions", lambda actions, ctx: calls.append(actions))
    ctx = MagicMock(spec=AgentContext)
    rule = YAMLRule(
        name="reward",
        priority=110,
        template=Path("templates/success.png"),
        threshold=0.85,
        actions=[{"wait": 1}, {"tap_ratio": [0.5, 0.75]}],
        waits={"success": 5},
    )
    match = MagicMock()
    match.screenshot = Path("screen.png")
    match.confidence = 0.92

    result = rule.handle(ctx, match)

    assert calls == [[{"wait": 1}, {"tap_ratio": [0.5, 0.75]}]]
    assert result.status == ResultStatus.SUCCESS
    assert result.state == "reward"
    assert result.next_wait == 5
```

- [ ] **Step 2: Run rule tests and verify failure**

Run:

```bash
python -m pytest tests/test_rules.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.rules'`.

- [ ] **Step 3: Create `agent/rules.py`**

```python
from dataclasses import dataclass
from pathlib import Path

import yaml

from agent.actions import execute_actions
from agent.state import ActionResult, AgentContext, ResultStatus, StateMatch


@dataclass
class YAMLRule:
    name: str
    priority: int
    template: Path
    threshold: float
    actions: list[dict]
    waits: dict[str, float]

    def detect(self, ctx: AgentContext) -> StateMatch | None:
        result = ctx.match_template(self.template, self.threshold)
        if not result.matched:
            return None
        return StateMatch(
            name=self.name,
            confidence=result.confidence,
            priority=self.priority,
            screenshot=ctx.screenshot,
            center=result.center,
            metadata={
                "template": str(self.template),
                "scale": result.scale,
            },
        )

    def handle(self, ctx: AgentContext, match: StateMatch) -> ActionResult:
        execute_actions(self.actions, ctx)
        return ActionResult(
            status=ResultStatus.SUCCESS,
            detail=f"{self.name} actions executed",
            screenshot=match.screenshot,
            next_wait=self.waits.get("success"),
            state=self.name,
            confidence=match.confidence,
        )


def load_rules(path: str | Path = "rules.yaml") -> list[YAMLRule]:
    rules_path = Path(path)
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_rules = data.get("rules")
    if not isinstance(raw_rules, dict):
        raise ValueError("rules.yaml must contain a 'rules' mapping")

    loaded = []
    for name, raw in raw_rules.items():
        detect = raw.get("detect") or {}
        template = _resolve_template(rules_path.parent, detect.get("template", ""))
        if not template.exists():
            raise FileNotFoundError(f"Template not found for rule {name}: {template}")

        loaded.append(
            YAMLRule(
                name=name,
                priority=int(raw.get("priority", 0)),
                template=template,
                threshold=float(detect.get("threshold", 0.85)),
                actions=list(raw.get("actions") or []),
                waits={key: float(value) for key, value in (raw.get("waits") or {}).items()},
            )
        )

    return sorted(loaded, key=lambda rule: rule.priority, reverse=True)


def _resolve_template(base_dir: Path, value: str) -> Path:
    template = Path(value)
    if template.is_absolute():
        return template
    return base_dir / template
```

- [ ] **Step 4: Create `rules.yaml`**

```yaml
rules:
  blessing_reward_page:
    priority: 110
    detect:
      template: "templates/success.png"
      threshold: 0.85
    actions:
      - wait: 1
      - tap_ratio: [0.5, 0.75]
    waits:
      success: 5
      failed: 5

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

- [ ] **Step 5: Run rule tests**

Run:

```bash
python -m pytest tests/test_rules.py -v
```

Expected: PASS.

- [ ] **Step 6: Verify default rules load**

Run:

```bash
python -c "from agent.rules import load_rules; print([r.name for r in load_rules()])"
```

Expected:

```text
['blessing_reward_page', 'blessing_like_page']
```

- [ ] **Step 7: Commit**

```bash
git add agent/rules.py rules.yaml tests/test_rules.py
git commit -m "feat: add YAML state rules"
```

---

### Task 4: Add State Machine Engine

**Files:**
- Create: `agent/engine.py`
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write failing engine tests**

Create `tests/test_engine.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from agent.config import (
    ADBConfig,
    AgentConfig,
    BlessingConfig,
    Config,
    GameConfig,
    LoopConfig,
    ServerConfig,
)
from agent.engine import Engine
from agent.state import ActionResult, ResultStatus, StateMatch


def _make_config() -> Config:
    return Config(
        adb=ADBConfig(path="adb", device_id="emu"),
        game=GameConfig(screen_width=1920, screen_height=1080),
        blessing=BlessingConfig(
            like_button_x=978,
            like_button_y=1529,
            success_template="templates/success.png",
            blessing_template="templates/like_button.png",
        ),
        loop=LoopConfig(detect_interval=2, not_found_wait=15, success_cooldown=5),
        agent=AgentConfig(name="test", mode="standalone"),
        server=ServerConfig(url="", token=""),
    )


class FakeHandler:
    def __init__(self, name, priority, confidence=None, next_wait=5):
        self.name = name
        self.priority = priority
        self.confidence = confidence
        self.next_wait = next_wait
        self.handled = False

    def detect(self, ctx):
        if self.confidence is None:
            return None
        return StateMatch(
            name=self.name,
            confidence=self.confidence,
            priority=self.priority,
            screenshot=ctx.screenshot,
        )

    def handle(self, ctx, match):
        self.handled = True
        return ActionResult(
            status=ResultStatus.SUCCESS,
            detail=f"{self.name} handled",
            screenshot=match.screenshot,
            next_wait=self.next_wait,
            state=self.name,
            confidence=match.confidence,
        )


def _make_engine(handlers):
    adb = MagicMock()
    adb.screencap.return_value = Path("screen.png")
    logger = MagicMock()
    return Engine(
        adb=adb,
        config=_make_config(),
        logger=logger,
        handlers=handlers,
        sleeper=MagicMock(),
    )


def test_run_once_returns_not_found_when_no_handler_matches():
    engine = _make_engine([FakeHandler("like", 100, None)])

    result = engine.run_once()

    assert result.status == ResultStatus.NOT_FOUND
    assert result.next_wait == 15
    engine.logger.log.assert_called_once()


def test_run_once_chooses_higher_priority_match():
    low = FakeHandler("like", 100, 0.99, next_wait=2)
    high = FakeHandler("reward", 110, 0.90, next_wait=5)
    engine = _make_engine([low, high])

    result = engine.run_once()

    assert result.state == "reward"
    assert result.next_wait == 5
    assert high.handled is True
    assert low.handled is False


def test_run_once_chooses_higher_confidence_when_priority_ties():
    first = FakeHandler("first", 100, 0.90, next_wait=1)
    second = FakeHandler("second", 100, 0.95, next_wait=2)
    engine = _make_engine([first, second])

    result = engine.run_once()

    assert result.state == "second"
    assert second.handled is True
    assert first.handled is False


def test_run_once_converts_handler_exception_to_failed_result():
    class BrokenHandler(FakeHandler):
        def handle(self, ctx, match):
            raise RuntimeError("tap failed")

    engine = _make_engine([BrokenHandler("broken", 100, 0.9)])

    result = engine.run_once()

    assert result.status == ResultStatus.FAILED
    assert result.state == "broken"
    assert "tap failed" in result.detail
```

- [ ] **Step 2: Run engine tests and verify failure**

Run:

```bash
python -m pytest tests/test_engine.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.engine'`.

- [ ] **Step 3: Create `agent/engine.py`**

```python
import time
from typing import Iterable

from agent.adb import ADBController
from agent.config import Config
from agent.logger import Logger
from agent.state import ActionResult, AgentContext, ResultStatus, StateMatch


class Engine:
    def __init__(
        self,
        adb: ADBController,
        config: Config,
        logger: Logger,
        handlers: Iterable,
        sleeper=time.sleep,
    ):
        self.adb = adb
        self.config = config
        self.logger = logger
        self.handlers = list(handlers)
        self.sleeper = sleeper

    def run_once(self) -> ActionResult:
        screenshot = self.adb.screencap()
        ctx = AgentContext(
            adb=self.adb,
            config=self.config,
            logger=self.logger,
            screenshot=screenshot,
            sleeper=self.sleeper,
        )

        selected = self._select_handler(ctx)
        if selected is None:
            result = ActionResult(
                status=ResultStatus.NOT_FOUND,
                detail="no state matched",
                screenshot=screenshot,
                next_wait=self.config.loop.not_found_wait,
                state="unknown",
                confidence=0.0,
            )
            self._log(result)
            return result

        handler, match = selected
        try:
            result = handler.handle(ctx, match)
        except Exception as exc:
            result = ActionResult(
                status=ResultStatus.FAILED,
                detail=str(exc),
                screenshot=screenshot,
                next_wait=self.config.loop.success_cooldown,
                state=match.name,
                confidence=match.confidence,
            )

        if result.next_wait is None:
            result.next_wait = self.config.loop.success_cooldown
        self._log(result)
        return result

    def run_forever(self):
        while True:
            result = self.run_once()
            print(f"[{result.status.value.upper()}] {result.state}: {result.detail}, wait {result.next_wait}s")
            self.sleeper(result.next_wait)

    def _select_handler(self, ctx: AgentContext):
        matches: list[tuple[object, StateMatch]] = []
        for handler in self.handlers:
            match = handler.detect(ctx)
            if match is not None:
                matches.append((handler, match))

        if not matches:
            return None
        return max(matches, key=lambda item: (item[1].priority, item[1].confidence))

    def _log(self, result: ActionResult):
        detail = f"{result.detail}; confidence={result.confidence:.3f}"
        self.logger.log(result.state, result.status.value, detail, result.screenshot)
```

- [ ] **Step 4: Run engine tests**

Run:

```bash
python -m pytest tests/test_engine.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/engine.py tests/test_engine.py
git commit -m "feat: add state machine engine"
```

---

### Task 5: Switch Main Loop to the Engine

**Files:**
- Modify: `agent/main.py`

- [ ] **Step 1: Verify current full test baseline**

Run:

```bash
python -m pytest tests/ -q
```

Expected: all tests PASS.

- [ ] **Step 2: Replace `agent/main.py`**

Use this complete file content:

```python
import signal
import sys

from agent.adb import ADBController
from agent.config import load_config
from agent.engine import Engine
from agent.logger import Logger
from agent.rules import load_rules


def main():
    cfg = load_config()
    logger = Logger()
    adb = ADBController(cfg.adb.path, cfg.adb.device_id)

    if not adb.check_device():
        logger.log("startup", "error", f"ADB device not connected: {cfg.adb.device_id}")
        print(f"[ERROR] ADB device {cfg.adb.device_id} not connected")
        sys.exit(1)

    rules = load_rules()
    engine = Engine(adb=adb, config=cfg, logger=logger, handlers=rules)

    print(f"[INFO] Agent started, mode: {cfg.agent.mode}, device: {cfg.adb.device_id}")
    logger.log("startup", "ok", f"mode={cfg.agent.mode} device={cfg.adb.device_id}")

    def handle_exit(sig, frame):
        print("\n[INFO] Agent stopped")
        logger.log("shutdown", "ok", "agent stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    engine.run_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify import**

Run:

```bash
python -c "from agent.main import main; print('import ok')"
```

Expected:

```text
import ok
```

- [ ] **Step 4: Run full tests**

Run:

```bash
python -m pytest tests/ -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/main.py
git commit -m "feat: run agent through state machine engine"
```

---

### Task 6: End-to-End Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Verify modules import**

Run:

```bash
python -c "from agent.engine import Engine; from agent.rules import load_rules; from agent.actions import execute_action; print('state machine import ok')"
```

Expected:

```text
state machine import ok
```

- [ ] **Step 2: Verify rules load**

Run:

```bash
python -c "from agent.rules import load_rules; print([r.name for r in load_rules()])"
```

Expected:

```text
['blessing_reward_page', 'blessing_like_page']
```

- [ ] **Step 3: Run full automated tests**

Run:

```bash
python -m pytest tests/ -q
```

Expected: all tests PASS.

- [ ] **Step 4: Verify ADB is connected**

Run:

```powershell
& "D:\Program Files (x86)\MuMuPlayer\nx_main\adb.exe" devices -l
```

Expected: output contains:

```text
127.0.0.1:16384 device
```

- [ ] **Step 5: Run a controlled live smoke test**

Run:

```powershell
python -u -m agent.main
```

Expected while on blessing like page:

```text
[SUCCESS] blessing_like_page: blessing_like_page actions executed, wait 2.0s
```

Expected while on reward page:

```text
[SUCCESS] blessing_reward_page: blessing_reward_page actions executed, wait 5.0s
```

Stop with `Ctrl+C` after one or two cycles.

- [ ] **Step 6: Check log lines**

Run:

```bash
@'
from pathlib import Path
for line in Path("logs/agent.log").read_text(encoding="utf-8").splitlines()[-10:]:
    print(line)
'@ | python -
```

Expected: recent lines include `blessing_like_page` or `blessing_reward_page`.

- [ ] **Step 7: Commit if live verification caused intentional config or rule changes**

Only run this if you changed tracked files during live calibration:

```bash
git add config.yaml rules.yaml templates
git commit -m "chore: calibrate state machine rules"
```

---

### Task 7: Cleanup and Compatibility Decision

**Files:**
- Optional modify: `agent/blessing_task.py`
- Optional modify: `tests/test_blessing_task.py`

- [ ] **Step 1: Keep `BlessingTask` for one release**

Do not delete `agent/blessing_task.py` in this plan. It remains as a compatibility fallback until the engine has run reliably for several live sessions.

- [ ] **Step 2: Add module-level deprecation note**

At the top of `agent/blessing_task.py`, after imports, add:

```python
# Compatibility fallback for the pre-state-machine blessing flow.
# New automation states should be implemented through rules.yaml or handlers.
```

- [ ] **Step 3: Run legacy task tests**

Run:

```bash
python -m pytest tests/test_blessing_task.py -v
```

Expected: PASS.

- [ ] **Step 4: Run full tests**

Run:

```bash
python -m pytest tests/ -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/blessing_task.py
git commit -m "docs: mark legacy blessing task fallback"
```

---

## Self-Review Checklist

- Spec coverage:
  - YAML simple states are implemented by `rules.yaml` and `agent/rules.py`.
  - Python handler shape is supported by the shared `detect(ctx)` / `handle(ctx, match)` protocol used by `Engine`.
  - Blessing is split into `blessing_like_page` and `blessing_reward_page`.
  - Reward state priority is higher than like state.
  - `tap`, `tap_ratio`, and `wait` are supported.
  - Existing launch command remains `python -m agent.main`.
- Placeholder scan: no `TBD`, `TODO`, or undefined function names are intentionally left in the plan.
- Type consistency:
  - `StateMatch`, `ActionResult`, `ResultStatus`, and `AgentContext` are defined before being used.
  - `YAMLRule.detect()` returns `StateMatch | None`.
  - `YAMLRule.handle()` returns `ActionResult`.
  - `Engine.run_once()` returns `ActionResult`.
