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
