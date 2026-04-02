"""
Text expansion listener.

Maintains a rolling character buffer. When the buffer tail matches a macro's
:trigger: pattern, the expander:
  1. Presses Backspace × len(trigger) to erase the typed trigger
  2. Calls injector.inject_text(macro["text"]) to type the expansion

Buffer resets on Enter; individual Backspace presses trim the buffer.

Usage:
    exp = Expander(get_macros_fn)
    exp.start()
    ...
    exp.stop()
"""

import threading
from typing import Callable

from pynput import keyboard
from pynput.keyboard import Key

import injector
from config import EXPANSION_BUFFER_SIZE


class Expander:
    def __init__(
        self,
        get_macros: Callable[[], list],
        get_settings: Callable[[], dict] | None = None,
    ) -> None:
        self._get_macros = get_macros
        self._get_settings = get_settings or (lambda: {})
        self._buffer: list[str] = []
        self._listener: keyboard.Listener | None = None
        self._lock = threading.Lock()
        self._suppressing = False  # prevent re-entrant expansion

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=None,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    # ------------------------------------------------------------------
    def _on_press(self, key) -> None:
        if self._suppressing or injector.is_injecting():
            return

        with self._lock:
            char = _key_to_char(key)

            if char is None:
                # Special key — reset buffer for most (Enter, Esc, Tab…)
                if key in (Key.enter, Key.esc, Key.tab):
                    self._buffer.clear()
                elif key == Key.backspace:
                    if self._buffer:
                        self._buffer.pop()
                return

            self._buffer.append(char)
            if len(self._buffer) > EXPANSION_BUFFER_SIZE:
                self._buffer.pop(0)

            self._check_expansion()

    def _check_expansion(self) -> None:
        buf = "".join(self._buffer)
        for macro in self._get_macros():
            trigger = macro.get("trigger", "").strip()
            if not trigger:
                continue
            if buf.endswith(trigger):
                text = macro.get("text", "")
                n = len(trigger)
                self._buffer.clear()
                # Run injection in a daemon thread so we return from
                # the keyboard callback immediately (avoids deadlocks).
                t = threading.Thread(
                    target=self._do_expand,
                    args=(n, text),
                    daemon=True,
                )
                t.start()
                return

    def _do_expand(self, erase_count: int, text: str) -> None:
        self._suppressing = True
        try:
            settings = self._get_settings()
            if settings.get("clipboard_mode"):
                from clipboard import copy_to_clipboard
                clear_delay = float(settings.get("clipboard_clear_delay", 0.0))
                injector.press_backspace(erase_count)
                copy_to_clipboard(text, clear_after=clear_delay)
            else:
                injector.press_backspace(erase_count)
                injector.inject_text(text)
        finally:
            self._suppressing = False


def _key_to_char(key) -> str | None:
    """Return the printable character for *key*, or None for special keys."""
    try:
        return key.char
    except AttributeError:
        return None
