import signal
import sys

from agent.adb import ADBController
from agent.config import load_config
from agent.engine import Engine
from agent.logger import Logger
from agent.rules import load_rules


def main():
    cfg = load_config()
    logger = Logger()
    adb = ADBController(cfg.adb.path, cfg.adb.device_id)

    if not adb.check_device():
        logger.log("startup", "error", f"ADB 设备未连接: {cfg.adb.device_id}")
        print(f"[错误] ADB 设备未连接: {cfg.adb.device_id}")
        sys.exit(1)

    rules = load_rules()
    engine = Engine(adb=adb, config=cfg, logger=logger, handlers=rules)

    print(f"[信息] 脚本已启动, 模式: {cfg.agent.mode}, 设备: {cfg.adb.device_id}")
    logger.log("startup", "ok", f"模式={cfg.agent.mode} 设备={cfg.adb.device_id}")

    def handle_exit(sig, frame):
        print("\n[信息] 脚本已停止")
        logger.log("shutdown", "ok", "脚本已停止")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    engine.run_forever()


if __name__ == "__main__":
    main()
