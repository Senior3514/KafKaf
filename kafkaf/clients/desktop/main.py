"""KafKaf desktop app: a native window wrapping the same local web GUI the
browser client uses. Built on pywebview (pure Python, no Node/Electron/Rust
toolchain) so it stays packageable into a single-file exe via PyInstaller on
every OS. See docs/SETUP.md for build instructions.
"""

import threading
import time

import httpx
import uvicorn
import webview

from kafkaf.core.api import app as backend_app
from kafkaf.core.config import settings

HOST = "127.0.0.1"  # desktop app only needs the loopback interface


def _is_backend_running(port: int) -> bool:
    try:
        response = httpx.get(f"http://{HOST}:{port}/health", timeout=1.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _run_backend(port: int) -> None:
    # Pass the app object directly rather than the "module:attr" string form —
    # uvicorn's string import doesn't reliably resolve inside a frozen
    # PyInstaller build, where the normal import machinery is patched.
    uvicorn.run(backend_app, host=HOST, port=port, log_level="warning")


def main() -> None:
    port = settings.port

    if not _is_backend_running(port):
        threading.Thread(target=_run_backend, args=(port,), daemon=True).start()
        for _ in range(50):  # ~10s max wait for the backend to come up
            if _is_backend_running(port):
                break
            time.sleep(0.2)

    webview.create_window("KafKaf", f"http://{HOST}:{port}", width=420, height=760)
    webview.start()


if __name__ == "__main__":
    main()
