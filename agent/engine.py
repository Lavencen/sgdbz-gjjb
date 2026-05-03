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
