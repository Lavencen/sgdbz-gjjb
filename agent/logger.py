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
