import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading


def configure_logging(log_dir):
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if getattr(root, "_embed_pin_doctor_configured", False):
        return log_dir / "app.log"
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler = RotatingFileHandler(log_dir / "app.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root._embed_pin_doctor_configured = True
    return log_dir / "app.log"


def install_exception_hooks(logger=None):
    logger = logger or logging.getLogger("crash")

    def system_hook(exc_type, exc_value, traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            return sys.__excepthook__(exc_type, exc_value, traceback)
        logger.critical("未捕获异常", exc_info=(exc_type, exc_value, traceback))

    def thread_hook(args):
        logger.critical("线程未捕获异常: %s", args.thread.name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = system_hook
    if hasattr(threading, "excepthook"):
        threading.excepthook = thread_hook


def get_logger(name):
    return logging.getLogger(name)
