"""Start the built EXE (or --source), check HTTP boundaries, and stop it."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    command = ([sys.executable, str(root / "launcher.py")] if sys.argv[1] == "--source"
               else [str(Path(sys.argv[1]).resolve())])
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command += ["--no-browser", "--port", str(port)]
    base = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def read(path):
        with opener.open(base + path, timeout=3) as response:
            return response.read()

    with tempfile.TemporaryFile(mode="w+b") as log:
        process = subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 45
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Application exited early: {process.returncode}")
                try:
                    assert json.loads(read("/health"))["status"] == "ok"
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() > deadline:
                        raise RuntimeError("Application did not become healthy")
                    time.sleep(0.25)
            html = read("/").decode("utf-8")
            assert "采用浮动图片和四周型文字环绕" in html
            assert "fetch('/api/scrape'" in html
            for asset in ("tailwind.js", "docx.js", "FileSaver.min.js"):
                assert len(read("/assets/" + asset)) > 1000
            paths = json.loads(read("/openapi.json"))["paths"]
            assert "/api/scrape" in paths and "/api/doubao" not in paths
            request = urllib.request.Request(base + "/api/scrape", data=b'{"targets":""}',
                                             headers={"Content-Type": "application/json"})
            with opener.open(request, timeout=3) as response:
                assert json.load(response)["success"] is False
            print("PASS: startup, health, page, bundled assets, local API, no LLM endpoint")
        except Exception:
            log.seek(0)
            print(log.read().decode("utf-8", errors="replace"))
            raise
        finally:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
