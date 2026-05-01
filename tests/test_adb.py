from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.adb import ADBController


class TestADBController:
    def test_check_device_online(self):
        mock_result = MagicMock()
        mock_result.stdout = "List of devices attached\nemulator-5554\tdevice\n"
        with patch("subprocess.run", return_value=mock_result):
            adb = ADBController("adb", "emulator-5554")
            assert adb.check_device() is True

    def test_check_device_offline(self):
        mock_result = MagicMock()
        mock_result.stdout = "List of devices attached\nemulator-5554\toffline\n"
        with patch("subprocess.run", return_value=mock_result):
            adb = ADBController("adb", "emulator-5554")
            assert adb.check_device() is False

    def test_check_device_not_listed(self):
        mock_result = MagicMock()
        mock_result.stdout = "List of devices attached\n"
        with patch("subprocess.run", return_value=mock_result):
            adb = ADBController("adb", "emulator-5554")
            assert adb.check_device() is False

    def test_check_device_returns_false_when_adb_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            adb = ADBController("missing-adb", "emulator-5554")
            assert adb.check_device() is False

    def test_tap_sends_correct_command(self):
        with patch("subprocess.run") as mock_run:
            adb = ADBController("adb", "emulator-5554")
            adb.tap(100, 200)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "adb"
            assert args[1] == "-s"
            assert args[2] == "emulator-5554"
            assert args[3] == "shell"
            assert args[4] == "input"
            assert args[5] == "tap"
            assert args[6] == "100"
            assert args[7] == "200"

    def test_screencap_returns_path(self):
        with patch("subprocess.run") as mock_run:
            adb = ADBController("adb", "emulator-5554")
            result = adb.screencap()
            assert isinstance(result, Path)
            mock_run.assert_called_once()

    def test_screencap_command_uses_exec_out(self):
        with patch("subprocess.run") as mock_run:
            adb = ADBController("adb", "emulator-5554")
            adb.screencap()
            args = mock_run.call_args[0][0]
            assert "exec-out" in args
            assert "screencap" in args
            assert "-p" in args
