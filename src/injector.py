"""
Keystroke injector — types text character-by-character using pynput.
The clipboard is never touched.
"""

import time
import platform

from pynput.keyboard import Controller, Key

from config import INJECT_CHAR_DELAY

_keyboard = Controller()


def inject_text(text: str, char_delay: float = INJECT_CHAR_DELAY) -> None:
    """
    Type *text* into whatever window currently has focus.
    Uses pynput Controller.type() which handles unicode and dead keys.
    A small per-character delay is applied so slow apps (e.g. web SSO portals)
    can keep up.
    """
    for char in text:
        _keyboard.type(char)
        if char_delay > 0:
            time.sleep(char_delay)


def press_backspace(n: int) -> None:
    """Press Backspace *n* times (used by the text expander to erase a trigger)."""
    for _ in range(n):
        _keyboard.press(Key.backspace)
        _keyboard.release(Key.backspace)
        time.sleep(0.008)
