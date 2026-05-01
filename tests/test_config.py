import os
import tempfile

import pytest

from agent.config import load_config


VALID_CONFIG = """
adb:
  path: "C:/adb/adb.exe"
  device_id: "emulator-5554"

game:
  screen_width: 1920
  screen_height: 1080

blessing:
  like_button_x: 540
  like_button_y: 960
  success_template: "templates/success.png"
  blessing_template: "templates/blessing_icon.png"

loop:
  detect_interval: 2
  not_found_wait: 60
  success_cooldown: 5

agent:
  name: "pc-home"
  mode: "standalone"

server:
  url: "wss://example.com/ws"
  token: "test-token"
"""


class TestLoadConfig:
    def test_loads_valid_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(VALID_CONFIG)
            path = f.name
        try:
            cfg = load_config(path)
            assert cfg.adb.path == "C:/adb/adb.exe"
            assert cfg.adb.device_id == "emulator-5554"
            assert cfg.game.screen_width == 1920
            assert cfg.game.screen_height == 1080
            assert cfg.blessing.like_button_x == 540
            assert cfg.blessing.like_button_y == 960
            assert cfg.blessing.success_template == "templates/success.png"
            assert cfg.blessing.blessing_template == "templates/blessing_icon.png"
            assert cfg.loop.detect_interval == 2
            assert cfg.loop.not_found_wait == 60
            assert cfg.loop.success_cooldown == 5
            assert cfg.agent.name == "pc-home"
            assert cfg.agent.mode == "standalone"
            assert cfg.server.url == "wss://example.com/ws"
            assert cfg.server.token == "test-token"
        finally:
            os.unlink(path)

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_server_section_optional(self):
        config_without_server = """
adb:
  path: "adb"
  device_id: "d1"
game:
  screen_width: 800
  screen_height: 600
blessing:
  like_button_x: 1
  like_button_y: 2
  success_template: "s.png"
  blessing_template: "b.png"
loop:
  detect_interval: 1
  not_found_wait: 10
  success_cooldown: 1
agent:
  name: "a"
  mode: "standalone"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_without_server)
            path = f.name
        try:
            cfg = load_config(path)
            assert cfg.server.url == ""
            assert cfg.server.token == ""
        finally:
            os.unlink(path)
