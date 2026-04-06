"""
Vault manager window — lists macros, allows add/edit/delete.
Also contains the Settings tab with run-at-startup toggle.
"""

import sys
import os
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import vault as vault_mod
from config import APP_NAME, STARTUP_REG_KEY, STARTUP_REG_VALUE, CLIPBOARD_CLEAR_DELAY

try:
    from gui.macro_edit import run_macro_dialog
except ImportError:
    from macro_edit import run_macro_dialog


class ManagerWindow:
    """
    Call ManagerWindow(root, vault_data, password, on_macros_changed).
    The window is a Toplevel; it does not block the caller.
    """

    def __init__(
        self,
        root: tk.Tk,
        vault_data: dict,
        password: str,
        on_macros_changed: Callable[[], None],
    ) -> None:
        self._root = root
        self._vault = vault_data
        self._password = password
        self._on_changed = on_macros_changed

        self.win = tk.Toplevel(root)
        self.win.title(f"{APP_NAME} — Macro Manager")
        self.win.geometry("640x420")
        self.win.protocol("WM_DELETE_WINDOW", self.win.withdraw)

        self._build_ui()
        self._refresh_list()

    def show(self) -> None:
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # --- Macros tab ---
        macro_frame = ttk.Frame(nb, padding=8)
        nb.add(macro_frame, text="Macros")

        # Treeview
        cols = ("name", "hotkey", "trigger", "category", "text")
        self._tree = ttk.Treeview(
            macro_frame,
            columns=cols,
            show="headings",
            selectmode="browse",
        )
        col_cfg = [
            ("name", "Name", 160),
            ("hotkey", "Hotkey", 110),
            ("trigger", "Trigger", 80),
            ("category", "Category", 80),
            ("text", "Text", 180),
        ]
        for cid, heading, width in col_cfg:
            self._tree.heading(cid, text=heading)
            self._tree.column(cid, width=width, anchor="w")

        vsb = ttk.Scrollbar(macro_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        macro_frame.columnconfigure(0, weight=1)
        macro_frame.rowconfigure(0, weight=1)

        self._tree.bind("<Double-1>", lambda _: self._on_edit())

        # Buttons
        btn_frame = ttk.Frame(macro_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(btn_frame, text="➕ Add", command=self._on_add).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="✏️ Edit", command=self._on_edit).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="🗑 Delete", command=self._on_delete).pack(side="left", padx=3)

        # --- Settings tab ---
        settings_frame = ttk.Frame(nb, padding=16)
        nb.add(settings_frame, text="Settings")

        row = 0
        if platform.system() == "Windows":
            self._startup_var = tk.BooleanVar(value=_get_startup_enabled())
            ttk.Checkbutton(
                settings_frame,
                text="Launch QuiKeys automatically when Windows starts",
                variable=self._startup_var,
                command=self._on_startup_toggle,
            ).grid(row=row, column=0, columnspan=2, sticky="w")
            row += 1
            ttk.Label(
                settings_frame,
                text="(Uses HKCU Run registry key — no admin required)",
                foreground="gray",
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=20)
            row += 1
        else:
            ttk.Label(
                settings_frame,
                text="Auto-startup is configured via your OS login items\n"
                     "or by adding QuiKeys to your shell profile.",
            ).grid(row=row, column=0, columnspan=2, sticky="w")
            row += 1

        ttk.Separator(settings_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=10
        )
        row += 1

        # Clipboard mode (applies to text-trigger expansions only)
        current = vault_mod.get_settings(self._vault)
        self._clipboard_var = tk.BooleanVar(value=current.get("clipboard_mode", True))
        cb = ttk.Checkbutton(
            settings_frame,
            text="Copy to clipboard for text triggers (instead of typing)",
            variable=self._clipboard_var,
            command=self._on_clipboard_toggle,
        )
        cb.grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Label(
            settings_frame,
            text="Hotkey shortcuts (Ctrl+Shift+1–9) always copy to clipboard — press\n"
                 "Ctrl+V to paste into any field, including Windows security dialogs.\n"
                 "This option extends clipboard delivery to text trigger expansions too.",
            foreground="gray",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=20)
        row += 1

        # Auto-clear delay
        clear_frame = ttk.Frame(settings_frame)
        clear_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=20, pady=(6, 0))
        row += 1

        ttk.Label(clear_frame, text="Auto-clear clipboard after").pack(side="left")
        self._clear_delay_var = tk.DoubleVar(
            value=current.get("clipboard_clear_delay", CLIPBOARD_CLEAR_DELAY)
        )
        self._clear_spin = ttk.Spinbox(
            clear_frame,
            from_=0,
            to=300,
            increment=5,
            width=5,
            textvariable=self._clear_delay_var,
            command=self._on_clear_delay_change,
        )
        self._clear_spin.pack(side="left", padx=4)
        ttk.Label(clear_frame, text="seconds  (0 = never)").pack(side="left")
        self._clear_spin.bind("<FocusOut>", lambda _: self._on_clear_delay_change())

        self._update_clear_delay_state()

    # ------------------------------------------------------------------
    def _refresh_list(self) -> None:
        self._tree.delete(*self._tree.get_children())
        for macro in self._vault.get("macros", []):
            text_display = "●●●●●●" if macro.get("masked") else macro.get("text", "")
            if len(text_display) > 30:
                text_display = text_display[:30] + "…"
            self._tree.insert(
                "",
                "end",
                iid=macro["id"],
                values=(
                    macro.get("name", ""),
                    macro.get("hotkey", "") or "—",
                    macro.get("trigger", "") or "—",
                    macro.get("category", ""),
                    text_display,
                ),
            )

    def _selected_macro(self) -> Optional[dict]:
        sel = self._tree.selection()
        if not sel:
            return None
        mid = sel[0]
        return next((m for m in self._vault["macros"] if m["id"] == mid), None)

    def _on_add(self) -> None:
        result = run_macro_dialog(self.win)
        if result:
            vault_mod.add_macro(self._vault, result)
            self._save_and_notify()

    def _on_edit(self) -> None:
        macro = self._selected_macro()
        if not macro:
            messagebox.showinfo("No selection", "Please select a macro to edit.", parent=self.win)
            return
        result = run_macro_dialog(self.win, macro)
        if result:
            vault_mod.update_macro(self._vault, result)
            self._save_and_notify()

    def _on_delete(self) -> None:
        macro = self._selected_macro()
        if not macro:
            return
        if not messagebox.askyesno(
            "Delete macro",
            f"Delete '{macro['name']}'?",
            parent=self.win,
        ):
            return
        vault_mod.delete_macro(self._vault, macro["id"])
        self._save_and_notify()

    def _save_and_notify(self) -> None:
        vault_mod.save_vault(self._vault, self._password)
        self._refresh_list()
        self._on_changed()

    def _on_startup_toggle(self) -> None:
        _set_startup_enabled(self._startup_var.get())

    def _on_clipboard_toggle(self) -> None:
        self._save_settings()
        self._update_clear_delay_state()

    def _on_clear_delay_change(self) -> None:
        self._save_settings()

    def _update_clear_delay_state(self) -> None:
        state = "normal" if self._clipboard_var.get() else "disabled"
        self._clear_spin.configure(state=state)

    def _save_settings(self) -> None:
        try:
            delay = float(self._clear_delay_var.get())
        except (ValueError, tk.TclError):
            delay = CLIPBOARD_CLEAR_DELAY
        settings = {
            "clipboard_mode": self._clipboard_var.get(),
            "clipboard_clear_delay": max(0.0, delay),
        }
        vault_mod.update_settings(self._vault, settings)
        vault_mod.save_vault(self._vault, self._password)


# ---------------------------------------------------------------------------
# Windows startup registry helpers
# ---------------------------------------------------------------------------

def _get_startup_enabled() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY) as key:
            winreg.QueryValueEx(key, STARTUP_REG_VALUE)
            return True
    except (FileNotFoundError, OSError):
        return False


def _set_startup_enabled(enabled: bool) -> None:
    if platform.system() != "Windows":
        return
    import winreg
    exe_path = sys.executable if not getattr(sys, "frozen", False) else sys.executable
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, STARTUP_REG_VALUE, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, STARTUP_REG_VALUE)
                except FileNotFoundError:
                    pass
    except OSError as e:
        messagebox.showerror("Registry error", str(e))
