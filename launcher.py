from pathlib import Path
import socket
import threading
import time
import webbrowser

from app.web_app import run
from utils.logging_setup import configure_logging, get_logger


def _free_port(start=8765, attempts=20):
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("没有找到可用端口")


def main():
    configure_logging(Path(__file__).resolve().parent / "logs")
    logger = get_logger(__name__)
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    logger.info("启动 EmbedPinDoctor: %s", url)
    thread = threading.Thread(target=lambda: run("127.0.0.1", port), daemon=True)
    thread.start()
    time.sleep(0.5)
    webbrowser.open(url)
    print(f"EmbedPinDoctor 已启动: {url}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("用户退出 EmbedPinDoctor")


if __name__ == "__main__":
    main()
