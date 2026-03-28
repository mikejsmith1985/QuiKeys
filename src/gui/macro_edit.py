"""Add / Edit macro dialog."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import vault as vault_mod
from config import HOTKEY_DIGITS

CATEGORIES = ["password", "greeting", "snippet", "other"]


def run_macro_dialog(parent: tk.Tk, macro: Optional[dict] = None) -> Optional[dict]:
    """
    Show add (macro=None) or edit (macro=existing dict) dialog.
    Returns updated/new macro dict on save, or None on cancel.
    """
    dlg = _MacroDialog(parent, macro)
    parent.wait_window(dlg.top)
    return dlg.result


class _MacroDialog:
    def __init__(self, parent: tk.Tk, macro: Optional[dict]) -> None:
        self.result: Optional[dict] = None
        self._existing = macro

        self.top = tk.Toplevel(parent)
        self.top.title("Edit Macro" if macro else "Add Macro")
        self.top.resizable(False, False)
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.top.transient(parent)

        self._build_ui(macro or {})
        self.top.update_idletasks()
        _center(self.top)
        self.top.grab_set()
        self.top.focus_force()

    # ------------------------------------------------------------------
    def _build_ui(self, m: dict) -> None:
        pad = {"padx": 10, "pady": 5}
        f = ttk.Frame(self.top, padding=16)
        f.grid(sticky="nsew")

        # Name
        ttk.Label(f, text="Name:").grid(row=0, column=0, sticky="e", **pad)
        self._name_var = tk.StringVar(value=m.get("name", ""))
        ttk.Entry(f, textvariable=self._name_var, width=32).grid(row=0, column=1, columnspan=2, **pad)

        # Text / secret
        ttk.Label(f, text="Text / secret:").grid(row=1, column=0, sticky="e", **pad)
        self._text_var = tk.StringVar(value=m.get("text", ""))
        self._text_entry = ttk.Entry(f, textvariable=self._text_var, width=32, show="●")
        self._text_entry.grid(row=1, column=1, **pad)
        self._show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Show", variable=self._show_var, command=self._toggle_show
        ).grid(row=1, column=2, sticky="w")

        # Hotkey
        ttk.Label(f, text="Hotkey:").grid(row=2, column=0, sticky="e", **pad)
        hotkey_options = ["(none)"] + [f"Ctrl+Shift+{d}" for d in HOTKEY_DIGITS]
        self._hotkey_var = tk.StringVar()
        current_hk = m.get("hotkey", "")
        self._hotkey_var.set(self._hk_to_display(current_hk))
        ttk.Combobox(
            f,
            textvariable=self._hotkey_var,
            values=hotkey_options,
            state="readonly",
            width=18,
        ).grid(row=2, column=1, columnspan=2, sticky="w", **pad)

        # Trigger
        ttk.Label(f, text="Text trigger:").grid(row=3, column=0, sticky="e", **pad)
        self._trigger_var = tk.StringVar(value=m.get("trigger", ""))
        ttk.Entry(f, textvariable=self._trigger_var, width=20).grid(
            row=3, column=1, columnspan=2, sticky="w", **pad
        )
        ttk.Label(f, text="e.g.  :pw1:", foreground="gray").grid(
            row=4, column=1, columnspan=2, sticky="w", padx=10
        )

        # Category
        ttk.Label(f, text="Category:").grid(row=5, column=0, sticky="e", **pad)
        self._cat_var = tk.StringVar(value=m.get("category", "other"))
        ttk.Combobox(
            f,
            textvariable=self._cat_var,
            values=CATEGORIES,
            state="readonly",
            width=14,
        ).grid(row=5, column=1, columnspan=2, sticky="w", **pad)

        # Masked in manager list
        self._masked_var = tk.BooleanVar(value=m.get("masked", False))
        ttk.Checkbutton(f, text="Mask text in manager list", variable=self._masked_var).grid(
            row=6, column=1, columnspan=2, sticky="w", padx=10, pady=(0, 8)
        )

        # Error label
        self._err_var = tk.StringVar()
        ttk.Label(f, textvariable=self._err_var, foreground="red", wraplength=320).grid(
            row=7, column=0, columnspan=3
        )

        # Buttons
        btn_f = ttk.Frame(f)
        btn_f.grid(row=8, column=0, columnspan=3, pady=(4, 0))
        ttk.Button(btn_f, text="Save", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(btn_f, text="Cancel", command=self._on_cancel).pack(side="left", padx=4)

        self.top.bind("<Return>", lambda _: self._on_save())
        self.top.bind("<Escape>", lambda _: self._on_cancel())

    def _toggle_show(self) -> None:
        self._text_entry.config(show="" if self._show_var.get() else "●")

    def _on_save(self) -> None:
        name = self._name_var.get().strip()
        text = self._text_var.get()
        if not name:
            self._err_var.set("Name is required.")
            return
        if not text:
            self._err_var.set("Text/secret cannot be empty.")
            return

        hk_display = self._hotkey_var.get()
        hotkey = "" if hk_display == "(none)" else self._display_to_hk(hk_display)

        trigger = self._trigger_var.get().strip()
        if trigger and not (trigger.startswith(":") and trigger.endswith(":") and len(trigger) > 2):
            self._err_var.set("Trigger must be in :name: format (e.g. :pw1:)")
            return

        if self._existing:
            macro = dict(self._existing)
        else:
            macro = vault_mod.new_macro("", "")

        macro.update(
            name=name,
            text=text,
            hotkey=hotkey,
            trigger=trigger,
            category=self._cat_var.get(),
            masked=self._masked_var.get(),
        )
        self.result = macro
        self.top.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.top.destroy()

    @staticmethod
    def _hk_to_display(hk: str) -> str:
        if not hk:
            return "(none)"
        # "ctrl+shift+1" → "Ctrl+Shift+1"
        return "+".join(p.capitalize() for p in hk.split("+"))

    @staticmethod
    def _display_to_hk(display: str) -> str:
        return display.lower()


def _center(win: tk.Toplevel) -> None:
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w = win.winfo_reqwidth()
    h = win.winfo_reqheight()
    win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
