"""
Clipboard helper — copies text to the system clipboard without pynput.

Used as an alternative to keystroke injection when the target window runs
on the Windows Secure Desktop (UAC dialogs, Windows Security, credential
prompts, etc.) where SendInput is blocked by the OS.

The Windows clipboard IS shared with the Secure Desktop, so the user can
press Ctrl+V to paste after this function copies the macro text.

Why OpenClipboard can fail on security dialogs:
  Windows credential and security dialogs sometimes hold the clipboard open
  to block clipboard injection attacks.  A retry loop lets us succeed once
  the dialog momentarily releases the lock (typically within a few hundred ms).
"""

import platform
import threading
import time

_clear_timer: threading.Timer | None = None
_clear_lock = threading.Lock()


def copy_to_clipboard(text: str, clear_after: float = 0.0) -> None:
    """
    Copy *text* to the system clipboard.
    If *clear_after* > 0, clear the clipboard after that many seconds.
    """
    _platform_copy(text)
    if clear_after > 0:
        _schedule_clear(clear_after)


def _platform_copy(text: str) -> None:
    system = platform.system()
    if system == "Windows":
        _copy_windows(text)
    elif system == "Darwin":
        _copy_macos(text)
    else:
        _copy_linux(text)


def _copy_windows(text: str) -> None:
    """Write to the Win32 clipboard via ctypes — works from any thread."""
    import ctypes
    import ctypes.wintypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    # Declare pointer-returning functions with correct types for 64-bit Windows
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    # How long to keep retrying when a security dialog holds the clipboard lock.
    # 10 attempts × 50 ms = 500 ms maximum wait before giving up.
    CLIPBOARD_OPEN_RETRY_COUNT = 10
    CLIPBOARD_OPEN_RETRY_DELAY_S = 0.05

    # Null-terminated UTF-16-LE (native Windows wide string)
    encoded = (text + "\x00").encode("utf-16-le")

    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not h_mem:
        return

    p_mem = kernel32.GlobalLock(h_mem)
    if not p_mem:
        kernel32.GlobalFree(h_mem)
        return
    ctypes.memmove(p_mem, encoded, len(encoded))
    kernel32.GlobalUnlock(h_mem)

    # Windows security and credential dialogs may hold the clipboard open to
    # block injection.  Retry until they release it or the timeout expires.
    clipboard_opened = False
    for _ in range(CLIPBOARD_OPEN_RETRY_COUNT):
        if user32.OpenClipboard(None):
            clipboard_opened = True
            break
        time.sleep(CLIPBOARD_OPEN_RETRY_DELAY_S)

    if not clipboard_opened:
        kernel32.GlobalFree(h_mem)
        return

    user32.EmptyClipboard()
    result = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    user32.CloseClipboard()

    if not result:
        # SetClipboardData failed; OS did not take ownership
        kernel32.GlobalFree(h_mem)


def _copy_macos(text: str) -> None:
    import subprocess
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)


def _copy_linux(text: str) -> None:
    import subprocess
    for cmd in (
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ):
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass


def _schedule_clear(delay: float) -> None:
    """Cancel any pending clear and schedule a new one."""
    global _clear_timer
    with _clear_lock:
        if _clear_timer is not None:
            _clear_timer.cancel()
        _clear_timer = threading.Timer(delay, lambda: _platform_copy(""))
        _clear_timer.daemon = True
        _clear_timer.start()
