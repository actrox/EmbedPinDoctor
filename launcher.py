from pathlib import Path
import os
import socket
import sys
import threading
import time
from urllib.request import urlopen
import webbrowser

from app.web_app import run
from utils.logging_setup import configure_logging, get_logger, install_exception_hooks


def _free_port(start=8765, attempts=20):
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("没有找到可用端口")


def _wait_until_ready(url, timeout=10):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{url}/api/version", timeout=0.5) as response:
                if response.status == 200:
                    return
        except OSError as exc:
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"本地服务启动超时: {last_error}")


def main():
    app_root = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EmbedPinDoctor") if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    log_path = configure_logging(app_root / "logs")
    logger = get_logger(__name__)
    install_exception_hooks(logger)
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    logger.info("启动 EmbedPinDoctor: %s (log=%s)", url, log_path)
    thread = threading.Thread(target=lambda: run("127.0.0.1", port), daemon=True, name="web-server")
    thread.start()
    _wait_until_ready(url)
    webbrowser.open(url)
    print(f"EmbedPinDoctor 已启动: {url}")
    try:
        while thread.is_alive():
            thread.join(timeout=1)
    except KeyboardInterrupt:
        logger.info("用户退出 EmbedPinDoctor")


if __name__ == "__main__":
    main()
