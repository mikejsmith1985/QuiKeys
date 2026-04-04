"""
Keystroke injector — types text character-by-character using pynput.
The clipboard is never touched.
"""

import time
import threading
import platform

from pynput.keyboard import Controller, Key

from config import INJECT_CHAR_DELAY

_keyboard = Controller()

# Set to True while any injection is in progress so the Expander's listener
# can suppress those synthetic keystrokes and avoid false trigger matches.
_injecting = False
_injecting_lock = threading.Lock()

# On Windows, WH_KEYBOARD_LL hooks are called asynchronously — the OS can
# deliver the final character's key event *after* _injecting is cleared.
# This grace-period timestamp keeps is_injecting() returning True for a short
# window after the last character is typed so those delayed events are still
# suppressed.
_inject_grace_until: float = 0.0
_INJECT_GRACE_S: float = 0.05  # 50 ms post-injection guard


def is_injecting() -> bool:
    """Return True while inject_text() is actively sending keystrokes,
    or within the short grace period after the last character was typed."""
    return _injecting or (time.monotonic() < _inject_grace_until)


def inject_text(text: str, char_delay: float = INJECT_CHAR_DELAY) -> None:
    """
    Type *text* into whatever window currently has focus.
    Uses pynput Controller.type() which handles unicode and dead keys.
    A small per-character delay is applied so slow apps (e.g. web SSO portals)
    can keep up.
    """
    global _injecting, _inject_grace_until
    with _injecting_lock:
        _injecting = True
    try:
        for char in text:
            _keyboard.type(char)
            if char_delay > 0:
                time.sleep(char_delay)
    finally:
        with _injecting_lock:
            # Set the grace deadline *before* clearing the flag so there is
            # no window where both guards are simultaneously False.
            _inject_grace_until = time.monotonic() + _INJECT_GRACE_S
            _injecting = False


def press_backspace(n: int) -> None:
    """Press Backspace *n* times (used by the text expander to erase a trigger)."""
    for _ in range(n):
        _keyboard.press(Key.backspace)
        _keyboard.release(Key.backspace)
        time.sleep(0.008)
