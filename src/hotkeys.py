"""
Global hotkey listener.

Registers Ctrl+Shift+<digit> combos from the active macro list and calls
the clipboard delivery function when one fires.

Hotkeys ALWAYS place text on the clipboard — press Ctrl+V to paste.
This approach works universally, including Windows security dialogs (UAC,
Windows Security, credential prompts) where SendInput is blocked by the OS
but the clipboard is shared with the Secure Desktop.

Usage:
    mgr = HotkeyManager(get_macros_fn)
    mgr.start()
    ...
    mgr.stop()

*get_macros_fn* is a callable that returns the current list of macro dicts,
allowing the manager to reload bindings when macros change without restarting
the listener.
"""

import threading
import platform
from typing import Callable

from pynput import keyboard


class HotkeyManager:
    def __init__(
        self,
        get_macros: Callable[[], list],
        get_settings: Callable[[], dict] | None = None,
    ) -> None:
        self._get_macros = get_macros
        self._get_settings = get_settings or (lambda: {})
        self._listener: keyboard.GlobalHotKeys | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Build hotkey map from current macros and start listening."""
        with self._lock:
            self._stop_listener()
            mapping = self._build_mapping()
            if mapping:
                self._listener = keyboard.GlobalHotKeys(mapping)
                self._listener.start()

    def stop(self) -> None:
        with self._lock:
            self._stop_listener()

    def reload(self) -> None:
        """Call this after macros are edited to re-register bindings."""
        self.start()

    # ------------------------------------------------------------------
    def _stop_listener(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _build_mapping(self) -> dict:
        mapping = {}
        for macro in self._get_macros():
            hk = macro.get("hotkey", "").strip()
            if not hk:
                continue
            text = macro.get("text", "")
            pynput_hk = _to_pynput_hotkey(hk)
            mapping[pynput_hk] = _make_handler(text, self._get_settings)
        return mapping


def _to_pynput_hotkey(hk: str) -> str:
    """
    Convert 'ctrl+shift+1' → '<ctrl>+<shift>+1'.
    Single characters (digits, letters) are left bare; modifier names get angle brackets.
    """
    MODIFIERS = {"ctrl", "shift", "alt", "cmd", "super"}
    parts = [p.strip().lower() for p in hk.split("+")]
    result = []
    for part in parts:
        if part in MODIFIERS:
            result.append(f"<{part}>")
        else:
            result.append(part)
    return "+".join(result)


def _make_handler(text: str, get_settings: Callable) -> Callable:
    """Return a closure that delivers *text* when called."""
    def handler():
        threading.Thread(target=_do_inject, args=(text, get_settings), daemon=True).start()
    return handler


def _do_inject(text: str, get_settings: Callable) -> None:
    """
    Copy *text* to the system clipboard.

    Hotkeys always use clipboard delivery — SendInput is blocked by the OS on
    the Windows Secure Desktop (UAC dialogs, Windows Security, credential
    prompts), but the clipboard IS shared across desktop sessions.  After this
    fires, press Ctrl+V in any field to paste.
    """
    from clipboard import copy_to_clipboard
    settings = get_settings()
    clear_delay = float(settings.get("clipboard_clear_delay", 0.0))
    copy_to_clipboard(text, clear_after=clear_delay)
