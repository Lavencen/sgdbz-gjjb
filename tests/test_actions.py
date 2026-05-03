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
