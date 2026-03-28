"""
Global hotkey listener.

Registers Ctrl+Shift+<digit> combos from the active macro list and calls
the injector when one fires.

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

import injector


class HotkeyManager:
    def __init__(self, get_macros: Callable[[], list]) -> None:
        self._get_macros = get_macros
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
            # pynput expects e.g. "<ctrl>+<shift>+1"
            pynput_hk = _to_pynput_hotkey(hk)
            mapping[pynput_hk] = _make_handler(text)
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


def _make_handler(text: str) -> Callable:
    """Return a closure that injects *text* when called."""
    def handler():
        from pynput.keyboard import Controller, Key
        import time
        kb = Controller()
        # Release all modifier keys before typing — they are still held
        # when the GlobalHotKeys callback fires, corrupting injected text.
        for mod in (Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                    Key.shift, Key.shift_l, Key.shift_r,
                    Key.alt, Key.alt_l, Key.alt_r):
            try:
                kb.release(mod)
            except Exception:
                pass
        time.sleep(0.05)  # let the OS process the releases
        injector.inject_text(text)
    return handler
