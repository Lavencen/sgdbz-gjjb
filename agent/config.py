from dataclasses import dataclass

import yaml


@dataclass
class ADBConfig:
    path: str
    device_id: str


@dataclass
class GameConfig:
    screen_width: int
    screen_height: int


@dataclass
class BlessingConfig:
    like_button_x: int
    like_button_y: int
    success_template: str
    blessing_template: str


@dataclass
class LoopConfig:
    detect_interval: int
    not_found_wait: int
    success_cooldown: int


@dataclass
class AgentConfig:
    name: str
    mode: str


@dataclass
class ServerConfig:
    url: str
    token: str


@dataclass
class Config:
    adb: ADBConfig
    game: GameConfig
    blessing: BlessingConfig
    loop: LoopConfig
    agent: AgentConfig
    server: ServerConfig


def load_config(path: str = "config.yaml") -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    server_data = data.get("server") or {}
    return Config(
        adb=ADBConfig(**data["adb"]),
        game=GameConfig(**data["game"]),
        blessing=BlessingConfig(**data["blessing"]),
        loop=LoopConfig(**data["loop"]),
        agent=AgentConfig(**data["agent"]),
        server=ServerConfig(
            url=server_data.get("url", ""),
            token=server_data.get("token", ""),
        ),
    )
