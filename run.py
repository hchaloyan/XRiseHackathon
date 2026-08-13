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


def _restore_window_styles(window) -> None:
    """Frameless costs the window more than its title bar. WinForms sets
    FormBorderStyle.None, which drops three style bits the shell reads, and the
    window stops behaving like an application window in ways that have nothing
    to do with how it is painted. All three go back on; none of them draws
    anything, because there is no caption for Windows to draw into.

    WS_THICKFRAME is the resize edges. Without it every edge hit-tests as client
    area and the window is stuck at its start size. Windows draws the resize
    zones, the sizing cursors and Aero Snap off this bit, none of which a CSS
    grip inside the page could offer, and the content still hit-tests as client
    so the drag strip and caption buttons are untouched.

    WS_MINIMIZEBOX is what the shell checks before it will minimize a window
    from its taskbar button. Without it, clicking the button of an app that is
    already up front just re-activates it instead of minimizing, which is the
    one taskbar gesture every other window on the machine honours.

    WS_MAXIMIZEBOX is the same story for the system menu — Alt+Space and the
    taskbar button's right-click menu grey out Maximize without it.

    The bit costs a sizing frame. Left, right and bottom fall outside the
    visible window and cost nothing, but the top edge is painted, and painted
    directly above the app bar: a 7px band the page cannot reach. Colouring it
    to match the bar hid it at rest and not in motion — the close button's red
    hover stopped 7px short of the window's corner, which is the one place a
    caption button is expected to run right into. `_install_frame_handler` below
    gives that band back to the page.
    """
    if sys.platform != "win32":
        return  # Win32 window styles; the other backends need their own fix

    import ctypes

    user32 = ctypes.windll.user32
    hwnd = window.native.Handle.ToInt32()
    GWL_STYLE = -16
    WS_MAXIMIZEBOX, WS_MINIMIZEBOX, WS_THICKFRAME = 0x00010000, 0x00020000, 0x00040000
    # NOSIZE | NOMOVE | NOZORDER | FRAMECHANGED: recalculate the frame in place.
    SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0020

    user32.SetWindowLongW(
        hwnd,
        GWL_STYLE,
        user32.GetWindowLongW(hwnd, GWL_STYLE)
        | WS_THICKFRAME
        | WS_MINIMIZEBOX
        | WS_MAXIMIZEBOX,
    )
    # Before the SetWindowPos below, so the frame recalculation it forces is
    # already running through our handler.
    _install_frame_handler(hwnd)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)

    # BORDER_COLOR is the 1px outline around the whole window. It takes the app
    # bar's own tone — #242424, what glass-bar's 62% #2E2E2E composites to over
    # the #121212 page — so the outline reads as the bar's own edge.
    # CAPTION_COLOR is set for the same reason and now covers only the instant
    # between the window appearing and the frame recalculation landing.
    #
    # A COLORREF is 0x00BBGGRR; grey needs no channel swap.
    DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR = 34, 35
    app_bar = ctypes.c_uint(0x242424)
    for attribute in (DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR):
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, attribute, ctypes.byref(app_bar), 4
        )


# The installed callback, held at module scope: ctypes collects a callback that
# nothing references, and the window would then call into freed memory.
_WNDPROC_REF = None


def _install_frame_handler(hwnd: int) -> None:
    """Answer the two frame messages WinForms gets wrong for a frameless window.

    WM_GETMINMAXINFO — where a window states how large it may maximize. The
    default for a borderless window is the whole monitor, taskbar included,
    which is fullscreen behaviour on a button that only says maximize. Answered
    with the monitor's work area instead, read fresh each time so the window
    still does the right thing after being dragged to a second screen.

    WM_NCCALCSIZE — extend the client area over the top sizing frame, so the
    page reaches the window's real top edge.

    WM_NCCALCSIZE is where a window is asked how much of itself is frame. Let
    the stock handler answer, then push the top back to where it started: the
    other three edges keep their frame — and with it the resize cursors and
    Aero Snap — while the top 7px become client area that the webview paints.
    The app bar then IS the top of the window, which is what the caption
    buttons' hover has to fill.

    Only while restored. Maximized, a thick-framed window's rect extends past
    the work area by the frame width, and reclaiming the top there would push
    the app bar off the top of the screen.

    ponytail: the top edge and the two top corners stop hit-testing as resize
    zones, since they are client now. The other five zones still work. Fixing
    that means answering WM_NCHITTEST too, which then has to carve out the
    caption buttons or make them unclickable — a lot of surface for an edge
    nobody drags when three others resize the same window.
    """
    global _WNDPROC_REF

    import ctypes

    user32 = ctypes.windll.user32
    GWLP_WNDPROC, WM_NCCALCSIZE, WM_GETMINMAXINFO = -4, 0x0083, 0x0024
    MONITOR_DEFAULTTONEAREST = 2
    SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CXPADDEDBORDER = 32, 33, 92

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [("rgrc", RECT * 3), ("lppos", ctypes.c_void_p)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class MINMAXINFO(ctypes.Structure):
        _fields_ = [
            ("ptReserved", POINT),
            ("ptMaxSize", POINT),
            ("ptMaxPosition", POINT),
            ("ptMinTrackSize", POINT),
            ("ptMaxTrackSize", POINT),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", ctypes.c_ulong),
        ]

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(
        LRESULT, ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t
    )

    # Spelled out because ctypes defaults every pointer it does not know about
    # to a 32-bit int, which silently truncates a 64-bit window proc address —
    # the chained call then jumps into nothing.
    for fn, argtypes, restype in (
        (user32.GetWindowLongPtrW, [ctypes.c_void_p, ctypes.c_int], ctypes.c_void_p),
        (
            user32.SetWindowLongPtrW,
            [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p],
            ctypes.c_void_p,
        ),
        (
            user32.CallWindowProcW,
            [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            ],
            LRESULT,
        ),
        (user32.IsZoomed, [ctypes.c_void_p], ctypes.c_bool),
        (
            user32.MonitorFromWindow,
            [ctypes.c_void_p, ctypes.c_ulong],
            ctypes.c_void_p,
        ),
        (user32.GetMonitorInfoW, [ctypes.c_void_p, ctypes.c_void_p], ctypes.c_bool),
        (user32.GetSystemMetrics, [ctypes.c_int], ctypes.c_int),
    ):
        fn.argtypes, fn.restype = argtypes, restype

    # Read before ours is installed, never after: a message arriving between the
    # swap and the assignment would otherwise chain to a null pointer.
    stock = user32.GetWindowLongPtrW(hwnd, GWLP_WNDPROC)

    def proc(window_handle, message, wparam, lparam):
        try:
            if message == WM_GETMINMAXINFO:
                monitor = user32.MonitorFromWindow(window_handle, MONITOR_DEFAULTTONEAREST)
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    work, screen = info.rcWork, info.rcMonitor
                    # Reproduce what Windows does for a normal thick-framed
                    # window: overhang the target by the frame on every side so
                    # the CLIENT lands flush on it, borders off-screen. Without
                    # this the frame is inset instead and a few pixels of
                    # desktop show through down each edge.
                    pad_x = user32.GetSystemMetrics(SM_CXSIZEFRAME) + user32.GetSystemMetrics(
                        SM_CXPADDEDBORDER
                    )
                    pad_y = user32.GetSystemMetrics(SM_CYSIZEFRAME) + user32.GetSystemMetrics(
                        SM_CXPADDEDBORDER
                    )
                    mmi = MINMAXINFO.from_address(lparam)
                    # ptMaxPosition is relative to the monitor, not the desktop.
                    mmi.ptMaxPosition.x = work.left - screen.left - pad_x
                    mmi.ptMaxPosition.y = work.top - screen.top - pad_y
                    mmi.ptMaxSize.x = (work.right - work.left) + pad_x * 2
                    mmi.ptMaxSize.y = (work.bottom - work.top) + pad_y * 2
                    return 0

            if message == WM_NCCALCSIZE and wparam and not user32.IsZoomed(window_handle):
                params = NCCALCSIZE_PARAMS.from_address(lparam)
                top = params.rgrc[0].top
                result = user32.CallWindowProcW(
                    stock, window_handle, message, wparam, lparam
                )
                params.rgrc[0].top = top
                return result
        except Exception as exc:  # a dead window proc is a dead app
            print(f"[chrome] frame handler failed, falling back: {exc}")
        return user32.CallWindowProcW(stock, window_handle, message, wparam, lparam)

    _WNDPROC_REF = WNDPROC(proc)
    user32.SetWindowLongPtrW(
        hwnd, GWLP_WNDPROC, ctypes.cast(_WNDPROC_REF, ctypes.c_void_p)
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

    # The taskbar groups buttons by AppUserModelID, and a process hosted by
    # python.exe inherits Python's — so the button shows the Python icon no
    # matter what the window's own icon is set to. Claiming an ID of our own
    # detaches the button and lets it use the window icon. Has to happen before
    # the window exists; after, the button is already grouped.
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mfgx.ai.app")

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
    # Not webview.start(_restore_window_styles, window): that runs the moment
    # the GUI loop starts, which is before the form exists and `window.native`
    # is still None. `shown` is the first point there is a handle to restyle. It
    # hands the window over because the parameter is named `window` — pywebview
    # reads the handler's signature to decide what to pass it.
    window.events.shown += _restore_window_styles

    # Taskbar icon. Without this the winforms backend falls back to extracting
    # one from sys.executable, i.e. the app shows up as the Python logo. The
    # window is frameless so this never appears in a title bar — taskbar and
    # Alt-Tab are the whole point. Absolute, because main() already chdir'd
    # into backend/. Regenerate with `python make_icon.py`.
    webview.start(icon=str(ROOT / "frontend" / "public" / "favicon.ico"))


if __name__ == "__main__":
    main()
