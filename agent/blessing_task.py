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
            time.sleep(1)
            self.adb.tap(
                self.config.game.screen_width // 2,
                self.config.game.screen_height * 3 // 4,
            )
            return TaskStatus.SUCCESS, "点赞成功", screenshot2
        return TaskStatus.FAILED, "点赞后未检测到成功提示", screenshot2
