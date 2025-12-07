#!/usr/bin/env python3
"""Nagi - Web-based terminal for iOS/iPad with touch-friendly controls."""

import asyncio
import fcntl
import json
import os
import pty
import struct
import subprocess
import sys
import termios
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# Base directory for resolving paths (PyInstaller compatible)
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent.resolve()

# Load config
CONFIG_PATH = Path(os.environ.get("NAGI_CONFIG", "")) if os.environ.get("NAGI_CONFIG") else BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "startup_command": "tmux a || tmux new",
    "shell": "/bin/bash",
    "port": 8765
}

def load_config():
    """Load configuration from config.json."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        except Exception:
            pass
    return DEFAULT_CONFIG

config = load_config()

# Override port from environment variable
if os.environ.get("NAGI_PORT"):
    config["port"] = int(os.environ["NAGI_PORT"])

app = FastAPI(title="Nagi")

# Serve static files
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def set_winsize(fd: int, rows: int, cols: int) -> None:
    """Set terminal window size."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main terminal page."""
    html_path = BASE_DIR / "templates" / "index.html"
    return html_path.read_text()


@app.websocket("/ws")
async def websocket_terminal(websocket: WebSocket):
    """WebSocket endpoint for terminal communication."""
    await websocket.accept()

    # Create pseudo-terminal
    master_fd, slave_fd = pty.openpty()

    # Set initial terminal size
    set_winsize(master_fd, 24, 80)

    # Set environment variables
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["LANG"] = "ja_JP.UTF-8"
    env["LC_ALL"] = "ja_JP.UTF-8"

    # Get shell from config
    shell = config.get("shell", os.environ.get("SHELL", "/bin/bash"))

    # Start shell process
    process = subprocess.Popen(
        [shell, "-l"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        preexec_fn=os.setsid,
    )

    os.close(slave_fd)

    # Set master to non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    running = True
    startup_sent = False

    async def read_from_pty():
        """Read data from PTY and send to WebSocket."""
        nonlocal startup_sent
        while running:
            try:
                await asyncio.sleep(0.02)
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        await websocket.send_bytes(data)
                        # Send startup command after first output (shell is ready)
                        if not startup_sent:
                            startup_sent = True
                            startup_cmd = config.get("startup_command", "")
                            if startup_cmd:
                                await asyncio.sleep(0.1)
                                os.write(master_fd, (startup_cmd + "\n").encode())
                except BlockingIOError:
                    pass
                except OSError:
                    break
            except Exception:
                break

    # Start reading from PTY
    read_task = asyncio.create_task(read_from_pty())

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if "bytes" in message:
                data = message["bytes"]
            elif "text" in message:
                text = message["text"]
                # Handle resize command
                if text.startswith("resize:"):
                    _, size = text.split(":", 1)
                    cols, rows = map(int, size.split(","))
                    set_winsize(master_fd, rows, cols)
                    continue
                data = text.encode("utf-8")
            else:
                continue

            # Write to PTY
            try:
                os.write(master_fd, data)
            except OSError:
                break

    except WebSocketDisconnect:
        pass
    finally:
        running = False
        read_task.cancel()
        try:
            os.close(master_fd)
        except Exception:
            pass
        try:
            process.terminate()
            process.wait(timeout=1)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    port = config.get("port", 8765)
    uvicorn.run(app, host="0.0.0.0", port=port)
