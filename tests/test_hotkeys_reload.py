"""Tests that re-registering hotkeys after a macro edit never leaves a hotkey dead."""

import platform
from unittest.mock import Mock

import pytest

import hotkeys

# A combo nobody uses day-to-day, so the real-Windows test cannot collide with a running QuiKeys.
UNUSED_TEST_HOTKEY = "ctrl+alt+shift+f11"

# Enough back-to-back reloads to expose the stop/start race reliably when it exists.
RAPID_RELOAD_COUNT = 25


def test_stop_waits_for_message_loop_thread_to_exit(monkeypatch):
    listener = hotkeys._Win32HotkeyListener({})
    listener._win32_thread_id = 1234
    message_loop_thread = Mock()
    listener._thread = message_loop_thread
    monkeypatch.setattr(hotkeys.ctypes, "windll", Mock(), raising=False)

    listener.stop()

    message_loop_thread.join.assert_called_once()


def test_stop_before_start_is_harmless():
    listener = hotkeys._Win32HotkeyListener({})

    listener.stop()


@pytest.mark.skipif(platform.system() != "Windows", reason="RegisterHotKey is Windows-only")
def test_rapid_reload_keeps_hotkey_registered_on_windows():
    macros = [{"id": "pw", "text": "Password5", "hotkey": UNUSED_TEST_HOTKEY}]
    hotkey_manager = hotkeys.HotkeyManager(lambda: macros)
    hotkey_manager.start()
    try:
        for _ in range(RAPID_RELOAD_COUNT):
            hotkey_manager.reload()
            assert hotkey_manager._listener._registered_handlers, "hotkey failed to re-register after reload"
    finally:
        hotkey_manager.stop()
