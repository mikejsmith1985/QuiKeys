"""
QuiKeys — main entry point.

Startup flow:
  1. Check vault exists → first-run wizard OR unlock dialog
  2. Derive key, decrypt vault, load macros into memory
  3. Register global hotkeys + start text expander
  4. Show system tray icon with menu
  5. Session stays unlocked until: Lock, Exit, or reboot
"""

import sys
import os
import threading
import platform

# Make src/ importable when running via PyInstaller or directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from PIL import Image

import vault as vault_mod
from config import APP_NAME, APP_VERSION, VAULT_FILE
from hotkeys import HotkeyManager
from expander import Expander

try:
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

class AppState:
    vault_data: dict = {}
    password: str = ""
    locked: bool = True


STATE = AppState()
_hotkey_mgr: HotkeyManager | None = None
_expander: Expander | None = None
_manager_win = None
_root: tk.Tk | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_macros() -> list:
    return STATE.vault_data.get("macros", [])


def _load_icon() -> Image.Image:
    """Load icon from assets, or generate on the fly if missing."""
    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets",
        "icon.png",
    )
    if not os.path.isfile(icon_path):
        from generate_icon import generate_icon
        return generate_icon()
    return Image.open(icon_path)


# ---------------------------------------------------------------------------
# Listener lifecycle
# ---------------------------------------------------------------------------

def _start_listeners() -> None:
    global _hotkey_mgr, _expander

    if _hotkey_mgr:
        _hotkey_mgr.stop()
    if _expander:
        _expander.stop()

    _hotkey_mgr = HotkeyManager(_get_macros)
    _hotkey_mgr.start()

    _expander = Expander(_get_macros)
    _expander.start()


def _stop_listeners() -> None:
    global _hotkey_mgr, _expander
    if _hotkey_mgr:
        _hotkey_mgr.stop()
        _hotkey_mgr = None
    if _expander:
        _expander.stop()
        _expander = None


# ---------------------------------------------------------------------------
# Unlock / lock
# ---------------------------------------------------------------------------

def _do_unlock() -> bool:
    """Show unlock dialog; return True if successful."""
    from gui.unlock import run_unlock_dialog

    is_first_run = not vault_mod.vault_exists()
    result = run_unlock_dialog(parent=_root, is_first_run=is_first_run)
    if result is None:
        return False

    vault_data, password = result
    STATE.vault_data = vault_data
    STATE.password = password
    STATE.locked = False
    return True


def _do_lock(icon=None, item=None) -> None:
    """Wipe in-memory secrets and stop listeners."""
    _stop_listeners()
    STATE.vault_data = {}
    STATE.password = ""
    STATE.locked = True
    # Re-show unlock dialog (run on main thread via root.after)
    if _root:
        _root.after(0, _unlock_and_resume)


def _unlock_and_resume() -> None:
    if not _do_unlock():
        # User cancelled — offer to quit
        if _root:
            import tkinter.messagebox as mb
            if mb.askyesno("QuiKeys", "Cancel unlock? QuiKeys will exit."):
                _quit_app()
            else:
                _unlock_and_resume()
        return
    _start_listeners()


# ---------------------------------------------------------------------------
# Manager window
# ---------------------------------------------------------------------------

def _open_manager(icon=None, item=None) -> None:
    global _manager_win
    if _root is None:
        return
    if _manager_win is None:
        from gui.manager import ManagerWindow
        _manager_win = ManagerWindow(
            _root,
            STATE.vault_data,
            STATE.password,
            on_macros_changed=_on_macros_changed,
        )
    _root.after(0, _manager_win.show)


def _on_macros_changed() -> None:
    if _hotkey_mgr:
        _hotkey_mgr.reload()


# ---------------------------------------------------------------------------
# Quit
# ---------------------------------------------------------------------------

def _quit_app(icon=None, item=None) -> None:
    _stop_listeners()
    if icon:
        icon.stop()
    if _root:
        _root.after(0, _root.destroy)


# ---------------------------------------------------------------------------
# System tray
# ---------------------------------------------------------------------------

def _build_tray_icon() -> "pystray.Icon":
    menu = pystray.Menu(
        pystray.MenuItem("Open Manager", _open_manager, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Lock", _do_lock),
        pystray.MenuItem("Exit", _quit_app),
    )
    icon = pystray.Icon(APP_NAME, _load_icon(), f"{APP_NAME} v{APP_VERSION}", menu)
    return icon


def _run_tray(icon: "pystray.Icon") -> None:
    icon.run()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    global _root

    # Generate icon asset if missing
    icon_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets",
        "icon.png",
    )
    if not os.path.isfile(icon_path):
        try:
            from generate_icon import save_icon
            save_icon(icon_path)
        except Exception:
            pass

    # Hidden Tk root — needed for dialogs and manager window
    _root = tk.Tk()
    _root.withdraw()
    _root.title(APP_NAME)

    # Unlock (blocks until dialog closes)
    if not _do_unlock():
        _root.destroy()
        sys.exit(0)

    _start_listeners()

    if HAS_TRAY:
        tray = _build_tray_icon()
        tray_thread = threading.Thread(target=_run_tray, args=(tray,), daemon=True)
        tray_thread.start()

    # Always open manager on startup so the user sees the UI immediately
    _open_manager()

    # Run Tk event loop (keeps dialogs and manager window alive)
    _root.mainloop()

    _stop_listeners()


if __name__ == "__main__":
    main()
