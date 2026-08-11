"""Launch MFGX AI as a desktop app.

One process: uvicorn serves the API and the built UI on the same origin in a
background thread, and the main thread owns a native window pointed at it.
Requires Ollama to be running.

    python run.py              # desktop window
    python run.py --browser    # default browser instead, if the window misbehaves
"""

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST, PORT = "127.0.0.1", 8000
URL = f"http://{HOST}:{PORT}"


def _listening() -> bool:
    with socket.socket() as probe:
        return probe.connect_ex((HOST, PORT)) == 0


def _wait_until_ready(timeout: int = 180) -> None:
    """Uvicorn binds the port only after the lifespan pre-warm finishes, so a
    successful connect means the first paint won't sit waiting on Ollama.
    """
    for _ in range(timeout):
        if _listening():
            return
        time.sleep(1)
    sys.exit(f"backend did not come up on {URL} within {timeout}s — is Ollama running?")


class _Chrome:
    """Reaches the page as `window.pywebview.api`. The window is frameless, so
    the header draws its own controls and calls back into these.

    Method names are single words on purpose: pywebview exposes them verbatim,
    and these three read identically in Python and TypeScript.

    Underscore attributes are not exposed, which is why the window handle is
    `_window` — pywebview would otherwise try to hand it to the page.
    """

    _window = None
    _maximized = False

    def minimize(self) -> None:
        self._window.minimize()

    def maximize(self) -> None:
        """Toggle. Nothing outside this class can change the state — a frameless
        window has no title bar to double-click — so the flag can't drift."""
        self._maximized = not self._maximized
        if self._maximized:
            self._window.maximize()
        else:
            self._window.restore()

    def close(self) -> None:
        self._window.destroy()


def main() -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        sys.exit("frontend/dist is missing — run:  cd frontend && npm install && npm run build")
    if _listening():
        sys.exit(f"{URL} is already in use — the app may already be running.")

    # config.py reads ./.env and chroma/ lives here, both relative to backend/.
    os.chdir(ROOT / "backend")
    sys.path.insert(0, str(ROOT / "backend"))

    import uvicorn

    print(f"MFGX AI starting on {URL} (first launch pre-warms the model)")
    # Daemon: closing the window returns from the main thread and takes the
    # server down with it, so no uvicorn is left holding :8000 after a demo.
    threading.Thread(
        target=uvicorn.run,
        args=("app.main:app",),
        kwargs={"host": HOST, "port": PORT, "log_level": "warning"},
        daemon=True,
    ).start()
    _wait_until_ready()

    if "--browser" in sys.argv:
        webbrowser.open(URL)
        threading.Event().wait()  # nothing owns the main thread now; park it
        return

    # ponytail: pywebview picks the OS webview — WebView2 on Win11, WebKit on
    # macOS/Linux. If a machine somehow lacks WebView2 it falls back to MSHTML,
    # which will not render this app; `--browser` is the escape hatch.
    import webview

    # ponytail: frameless drops the OS resize border along with the title bar
    # (WinForms sets FormBorderStyle.None). The window is fixed at its start
    # size or maximized — add a CSS resize grip only if someone actually asks.
    chrome = _Chrome()
    chrome._window = webview.create_window(
        "MFGX AI",
        URL,
        width=1920,
        height=1080,
        # The page draws its own controls, so only the strip tagged
        # .pywebview-drag-region moves the window — dragging a chart does not.
        easy_drag=False,
        # Matches --color-surface, so the shell doesn't flash white before paint.
        background_color="#121212",
        js_api=chrome,
    )
    webview.start()


if __name__ == "__main__":
    main()
