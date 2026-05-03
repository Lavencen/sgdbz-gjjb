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


def test_run_once_converts_capture_exception_to_failed_result():
    engine = _make_engine([])
    engine.adb.screencap.side_effect = RuntimeError("capture failed")

    result = engine.run_once()

    assert result.status == ResultStatus.FAILED
    assert result.state == "capture"
    assert "capture failed" in result.detail
    assert result.next_wait == 15
    engine.logger.log.assert_called_once()
