import json
import shutil
import tempfile
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
        fake_screenshot.write_text("fake image", encoding="utf-8")
        self.logger.log("blessing", "failed", "识别失败", fake_screenshot)
        pngs = list((Path(self.tmpdir) / "screenshots").glob("*.png"))
        assert len(pngs) == 1

    def test_multiple_logs_append(self):
        self.logger.log("blessing", "not_found", "第一次")
        self.logger.log("blessing", "success", "第二次")
        lines = (Path(self.tmpdir) / "agent.log").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
