"""Local browser UI and Windows executable entry point."""
import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import app

ROOT = Path(__file__).resolve().parent
app.mount("/assets", StaticFiles(directory=ROOT / "web" / "assets"), name="assets")


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/health")
def health():
    return {"app": "resume-materials", "status": "ok"}


def main():
    # Redirected Windows console streams may otherwise use a legacy encoding.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", args.port))
    except OSError as exc:
        sock.close()
        print(f"Port {args.port} unavailable: {exc}")
        print("Close the previous app, or run with --port 18766.")
        return 1
    config = uvicorn.Config(app, host="127.0.0.1", port=args.port,
                            loop="asyncio", http="h11", ws="none")
    server = uvicorn.Server(config)
    url = f"http://127.0.0.1:{args.port}"

    def open_browser():
        for _ in range(300):
            if server.started:
                webbrowser.open(url)
                return
            if server.should_exit:
                return
            time.sleep(0.1)

    if not args.no_browser:
        threading.Thread(target=open_browser, daemon=True).start()
    print(f"Open {url} in your browser. Keep this window open; Ctrl+C stops the app.")
    try:
        server.run(sockets=[sock])
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
