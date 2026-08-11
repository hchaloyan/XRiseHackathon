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
    and these four read identically in Python and TypeScript.

    Underscore attributes are not exposed, which is why the window handle is
    `_window` — pywebview would otherwise try to hand it to the page.
    """

    _window = None

    def minimize(self) -> None:
        self._window.minimize()

    def maximize(self) -> bool:
        """Toggle, returning the new state so the header can swap its icon."""
        maximized = not self.maximized()
        if maximized:
            self._window.maximize()
        else:
            self._window.restore()
        return maximized

    def maximized(self) -> bool:
        """Asked of the window, not remembered. Now that the window resizes,
        Aero Snap, Win+Up and a double-click on the drag strip can all maximize
        it without coming through here, and a cached flag would then answer for
        a state the window left some time ago."""
        return str(self._window.native.WindowState) == "Maximized"

    def close(self) -> None:
        self._window.destroy()


def _make_resizable(window) -> None:
    """Frameless costs the window its resize edges as well as its title bar:
    WinForms sets FormBorderStyle.None, which drops WS_THICKFRAME, and every
    edge then hit-tests as client area — the window is stuck at its start size.

    Putting that one style bit back is the whole fix. Windows draws the eight
    resize zones, the sizing cursors and Aero Snap off it, none of which a CSS
    grip inside the page could offer, and the content still hit-tests as client
    so the drag strip and caption buttons are untouched.

    The bit costs a 7px sizing frame. Left, right and bottom fall outside the
    visible window and cost nothing, but the top edge is painted, and it is
    painted directly above the app bar — so it is coloured to match the bar
    rather than left as the grey DWM picks.
    """
    if sys.platform != "win32":
        return  # Win32 window styles; the other backends need their own fix

    import ctypes

    user32 = ctypes.windll.user32
    hwnd = window.native.Handle.ToInt32()
    GWL_STYLE, WS_THICKFRAME = -16, 0x00040000
    # NOSIZE | NOMOVE | NOZORDER | FRAMECHANGED: recalculate the frame in place.
    SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0020

    user32.SetWindowLongW(
        hwnd, GWL_STYLE, user32.GetWindowLongW(hwnd, GWL_STYLE) | WS_THICKFRAME
    )
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)

    # The frame has two painted parts: BORDER_COLOR is the 1px outline around
    # the whole window, CAPTION_COLOR the 6px band inside it along the top.
    # Both take the app bar's own tone — #242424, what glass-bar's 62% #2E2E2E
    # composites to over the #121212 page — so the band reads as the bar
    # running out to the window's edge. --color-surface was the obvious value
    # here and the wrong one: a dark strip above a lighter bar is a gap.
    #
    # A COLORREF is 0x00BBGGRR; grey needs no channel swap.
    DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR = 34, 35
    app_bar = ctypes.c_uint(0x242424)
    for attribute in (DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR):
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, attribute, ctypes.byref(app_bar), 4
        )


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

    chrome = _Chrome()
    window = webview.create_window(
        "MFGX AI",
        URL,
        width=1920,
        height=1080,
        # The floor the layout is built to: below this the header runs out of
        # room for the wordmark, the tabs and the date picker on one line. The
        # sections themselves reflow from ~1024 down (four KPI cards to two,
        # the event table drops its Line column).
        min_size=(900, 640),
        # No OS title bar: the app header IS the title bar. It carries the
        # .pywebview-drag-region strip and the three caption buttons, which call
        # back into _Chrome above.
        frameless=True,
        # The page draws its own controls, so only the strip tagged
        # .pywebview-drag-region moves the window — dragging a chart does not.
        easy_drag=False,
        # Matches --color-surface, so the shell doesn't flash white before paint.
        background_color="#121212",
        js_api=chrome,
    )
    chrome._window = window

    def announce_state(*_) -> None:
        """Tell the header what the window just did. Aero Snap and Win+Up reach
        the window without touching _Chrome, so the caption icon has to be told
        rather than left to infer it from its last click.

        pywebview runs event handlers on a thread of their own, so evaluating JS
        from here cannot re-enter the message loop that raised the event.
        """
        state = "true" if chrome.maximized() else "false"
        window.evaluate_js(
            f"window.dispatchEvent(new CustomEvent('windowstate',{{detail:{state}}}))"
        )

    window.events.maximized += announce_state
    window.events.restored += announce_state
    # Not webview.start(_make_resizable, window): that runs the moment the GUI
    # loop starts, which is before the form exists and `window.native` is still
    # None. `shown` is the first point there is a handle to restyle. It hands
    # the window over because the parameter is named `window` — pywebview reads
    # the handler's signature to decide what to pass it.
    window.events.shown += _make_resizable

    webview.start()


if __name__ == "__main__":
    main()
