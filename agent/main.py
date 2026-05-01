import signal
import sys
import time

from agent.adb import ADBController
from agent.blessing_task import BlessingTask, TaskStatus
from agent.config import load_config
from agent.logger import Logger


def main():
    cfg = load_config()
    logger = Logger()
    adb = ADBController(cfg.adb.path, cfg.adb.device_id)

    if not adb.check_device():
        logger.log("startup", "error", f"ADB 设备未连接: {cfg.adb.device_id}")
        print(f"[ERROR] ADB 设备 {cfg.adb.device_id} 未连接, 请检查模拟器是否启动")
        sys.exit(1)

    print(f"[INFO] Agent 启动, 模式: {cfg.agent.mode}, 设备: {cfg.adb.device_id}")
    logger.log("startup", "ok", f"mode={cfg.agent.mode} device={cfg.adb.device_id}")

    task = BlessingTask(adb, cfg)

    def handle_exit(sig, frame):
        print("\n[INFO] 收到退出信号, Agent 停止")
        logger.log("shutdown", "ok", "agent stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while True:
        status, detail, screenshot = task.execute()
        logger.log("blessing", status.value, detail, screenshot)

        if status == TaskStatus.NOT_FOUND:
            wait = cfg.loop.not_found_wait
        else:
            wait = cfg.loop.success_cooldown

        print(f"[{status.value.upper()}] {detail}, wait {wait}s")
        time.sleep(wait)


if __name__ == "__main__":
    main()
