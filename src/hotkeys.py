"""
Global hotkey listener.

Registers Ctrl+Shift+<digit> combos from the active macro list and calls
the clipboard delivery function when one fires.

Hotkeys ALWAYS place text on the clipboard — press Ctrl+V to paste.
This approach works universally, including Windows security dialogs (UAC,
Windows Security, credential prompts) where SendInput is blocked by the OS
but the clipboard is shared with the Secure Desktop.

On Windows, hotkeys are registered via the Win32 RegisterHotKey API rather
than pynput's WH_KEYBOARD_LL hook.  RegisterHotKey is intercepted at the
Windows kernel message-routing level before any application (including
elevated security dialogs) can consume the key combo, so the hotkey fires
even when a credential prompt or Windows Security popup has focus.

Note: True UAC prompts run on the Windows Secure Desktop — a fully isolated
      session that no user-mode process can interact with.  Those are handled
      by copying to clipboard before the UAC prompt appears, or by using the
      normal desktop copy-then-paste flow.

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
import ctypes
import ctypes.wintypes
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
        self._listener = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Build hotkey map from current macros and start listening."""
        with self._lock:
            self._stop_listener()
            raw_mapping = self._build_raw_mapping()
            if not raw_mapping:
                return

            if platform.system() == "Windows":
                # RegisterHotKey fires even when elevated security dialogs
                # have focus — pynput's WH_KEYBOARD_LL hook may be blocked
                # by those windows, but Win32 RegisterHotKey is not.
                self._listener = _Win32HotkeyListener(raw_mapping)
            else:
                pynput_mapping = {
                    _to_pynput_hotkey(hk): handler
                    for hk, handler in raw_mapping.items()
                }
                self._listener = keyboard.GlobalHotKeys(pynput_mapping)

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

    def _build_raw_mapping(self) -> dict:
        """Return {hotkey_string: handler_callable} from the current macro list."""
        mapping = {}
        for macro in self._get_macros():
            hotkey_str = macro.get("hotkey", "").strip()
            if not hotkey_str:
                continue
            macro_text = macro.get("text", "")
            mapping[hotkey_str] = _make_handler(macro_text, self._get_settings)
        return mapping


# ---------------------------------------------------------------------------
# Win32 RegisterHotKey listener (Windows only)
# ---------------------------------------------------------------------------

class _Win32HotkeyListener:
    """
    Registers hotkeys via the Win32 RegisterHotKey API.

    Unlike pynput's WH_KEYBOARD_LL hook, RegisterHotKey messages are
    posted to our hidden window's queue by the Windows kernel before any
    foreground application (including elevated, protected, or credential
    dialogs) can consume the key combo.  This means hotkeys work even when
    a Windows Security popup or credential dialog has keyboard focus.

    Limitation: the Windows Secure Desktop (UAC elevation prompt, CTRL+ALT+DEL
    screen) is a fully isolated desktop session — no user-mode code can
    intercept input there.  That case is handled separately by the clipboard-
    based paste flow.
    """

    _WM_HOTKEY = 0x0312
    _WM_QUIT = 0x0012

    # Win32 modifier flag bitmasks for RegisterHotKey
    _MODIFIER_FLAGS: dict[str, int] = {
        "ctrl":    0x0002,  # MOD_CONTROL
        "control": 0x0002,
        "shift":   0x0004,  # MOD_SHIFT
        "alt":     0x0001,  # MOD_ALT
        "win":     0x0008,  # MOD_WIN
        "super":   0x0008,
        "cmd":     0x0008,
    }

    # Named key → Windows Virtual Key code
    _VK_NAMED_KEYS: dict[str, int] = {
        "f1": 0x70, "f2": 0x71, "f3": 0x72,  "f4": 0x73,
        "f5": 0x74, "f6": 0x75, "f7": 0x76,  "f8": 0x77,
        "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
        "space": 0x20, "tab": 0x09, "enter": 0x0D,
        "esc": 0x1B, "escape": 0x1B,
        "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
        "home": 0x24, "end": 0x23,
        "pgup": 0x21, "pgdn": 0x22, "pageup": 0x21, "pagedown": 0x22,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    }

    def __init__(self, hotkey_map: dict) -> None:
        """
        hotkey_map: {hotkey_string: callable}
          e.g. {"ctrl+shift+1": handler_fn, "ctrl+shift+2": handler_fn2}
        """
        self._hotkey_map = hotkey_map
        self._registered_handlers: dict[int, Callable] = {}  # {hotkey_id: handler}
        self._win32_thread_id: int = 0
        self._thread: threading.Thread | None = None
        self._ready_event = threading.Event()

    def start(self) -> None:
        """Start the background message-loop thread and wait for it to register hotkeys."""
        self._ready_event.clear()
        self._thread = threading.Thread(
            target=self._run_message_loop,
            daemon=True,
            name="QuiKeys-Win32Hotkeys",
        )
        self._thread.start()
        # Block briefly so hotkeys are registered before returning to caller
        self._ready_event.wait(timeout=2.0)

    def stop(self) -> None:
        """Post WM_QUIT to the listener thread so it unregisters and exits cleanly."""
        if self._win32_thread_id:
            ctypes.windll.user32.PostThreadMessageW(
                self._win32_thread_id, self._WM_QUIT, 0, 0
            )

    # ------------------------------------------------------------------
    def _run_message_loop(self) -> None:
        """
        Background thread: creates a message-only window, registers all
        hotkeys, then pumps the Windows message queue until WM_QUIT arrives.
        """
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Store the Win32 thread ID so stop() can post WM_QUIT to this thread.
        self._win32_thread_id = kernel32.GetCurrentThreadId()

        # Create a message-only window (HWND_MESSAGE parent = -3).
        # Message-only windows have no visual presence and exist solely to
        # receive messages — perfect for WM_HOTKEY delivery.
        hwnd = user32.CreateWindowExW(
            0,                                    # dwExStyle
            "STATIC",                             # lpClassName (predefined, always available)
            "QuiKeysHotkeyReceiver",              # lpWindowName (informational only)
            0,                                    # dwStyle
            0, 0, 0, 0,                           # x, y, width, height
            ctypes.wintypes.HWND(-3),             # hWndParent = HWND_MESSAGE
            None,                                 # hMenu
            kernel32.GetModuleHandleW(None),      # hInstance
            None,                                 # lpParam
        )

        if not hwnd:
            self._ready_event.set()
            return

        # Register each hotkey; assign a sequential integer ID so we can
        # look up the right handler when WM_HOTKEY fires.
        for hotkey_id, (hotkey_str, handler) in enumerate(self._hotkey_map.items()):
            modifier_flags, vk_code = self._parse_hotkey(hotkey_str)
            if vk_code == 0:
                continue  # Unrecognized key — skip silently
            if user32.RegisterHotKey(hwnd, hotkey_id, modifier_flags, vk_code):
                self._registered_handlers[hotkey_id] = handler

        self._ready_event.set()

        # Pump the Windows message queue.  GetMessageW blocks until a message
        # arrives; it returns 0 on WM_QUIT (which stop() posts via PostThreadMessageW).
        msg = ctypes.wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break
            if msg.message == self._WM_HOTKEY:
                handler = self._registered_handlers.get(msg.wParam)
                if handler:
                    # Fire the handler on a separate thread so the message
                    # loop stays responsive during the clipboard write.
                    threading.Thread(target=handler, daemon=True).start()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Clean up: unregister all hotkeys then destroy the window.
        for hotkey_id in self._registered_handlers:
            user32.UnregisterHotKey(hwnd, hotkey_id)
        user32.DestroyWindow(hwnd)
        self._win32_thread_id = 0

    def _parse_hotkey(self, hotkey_str: str) -> tuple[int, int]:
        """
        Convert a hotkey string like 'ctrl+shift+1' into the pair
        (win32_modifier_flags, virtual_key_code) that RegisterHotKey expects.

        Returns (MOD_NOREPEAT, 0) if the non-modifier key part is unrecognized
        so the caller can skip registration.
        """
        # MOD_NOREPEAT (0x4000) prevents the hotkey from firing repeatedly
        # while the key is held down, matching pynput's one-shot behaviour.
        MOD_NOREPEAT = 0x4000
        modifier_flags = MOD_NOREPEAT
        vk_code = 0

        for part in hotkey_str.lower().split("+"):
            part = part.strip()
            if part in self._MODIFIER_FLAGS:
                modifier_flags |= self._MODIFIER_FLAGS[part]
            elif part in self._VK_NAMED_KEYS:
                vk_code = self._VK_NAMED_KEYS[part]
            elif len(part) == 1:
                # Single character: digits 0–9 → VK 0x30–0x39,
                # letters a–z → VK 0x41–0x5A (uppercase ASCII).
                vk_code = ord(part.upper())

        return modifier_flags, vk_code


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _to_pynput_hotkey(hotkey_str: str) -> str:
    """
    Convert 'ctrl+shift+1' → '<ctrl>+<shift>+1'.
    Single characters (digits, letters) are left bare; modifier names get angle brackets.
    Used for the non-Windows pynput path only.
    """
    MODIFIER_NAMES = {"ctrl", "shift", "alt", "cmd", "super"}
    parts = [part.strip().lower() for part in hotkey_str.split("+")]
    formatted_parts = []
    for part in parts:
        if part in MODIFIER_NAMES:
            formatted_parts.append(f"<{part}>")
        else:
            formatted_parts.append(part)
    return "+".join(formatted_parts)


def _make_handler(text: str, get_settings: Callable) -> Callable:
    """Return a closure that delivers *text* to the clipboard when called."""
    def handler():
        threading.Thread(target=_do_deliver, args=(text, get_settings), daemon=True).start()
    return handler


def _do_deliver(text: str, get_settings: Callable) -> None:
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
