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
