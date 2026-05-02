import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from agent.blessing_task import BlessingTask, TaskStatus
from agent.config import (
    ADBConfig,
    AgentConfig,
    BlessingConfig,
    Config,
    GameConfig,
    LoopConfig,
    ServerConfig,
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
        screen = np.zeros((screen_size[1], screen_size[0], 3), dtype=np.uint8)
        screen[:] = (100, 100, 100)
        tx, ty, tw, th = template_region
        template = np.zeros((th, tw, 3), dtype=np.uint8)
        template[:] = (0, 255, 0)
        screen[ty : ty + th, tx : tx + tw] = template
        screen_path = self.tmpdir / "screen.png"
        cv2.imwrite(str(screen_path), screen)
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
        assert screenshot is None
        mock_adb.tap.assert_not_called()

    @patch("agent.blessing_task.time.sleep", return_value=None)
    def test_success_flow(self, _):
        screen_path, tmpl_path = self._make_screen_with_template((100, 200, 50, 50))
        success_path = self.tmpdir / "success_screen.png"
        shutil.copy2(screen_path, success_path)

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
        assert mock_adb.tap.call_count == 2
        mock_adb.tap.assert_any_call(200, 300)
        mock_adb.tap.assert_any_call(960, 810)
        assert _.call_args_list[-1].args[0] == 1

    @patch("agent.blessing_task.time.sleep", return_value=None)
    def test_failed_when_success_not_confirmed(self, _):
        screen_path, tmpl_path = self._make_screen_with_template((100, 200, 50, 50))
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
        assert mock_adb.tap.call_count == 1
