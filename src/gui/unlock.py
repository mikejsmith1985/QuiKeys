"""Unlock / first-run dialog."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

import vault


def run_unlock_dialog(is_first_run: bool = False) -> Optional[tuple[dict, str]]:
    """
    Show the unlock (or first-run) dialog.

    Returns (vault_data, password) on success, or None if the user cancels.
    Blocks until the dialog closes.
    """
    root = tk.Tk()
    root.withdraw()

    dlg = _UnlockDialog(root, is_first_run=is_first_run)
    root.wait_window(dlg.top)
    root.destroy()

    return dlg.result


class _UnlockDialog:
    def __init__(self, parent: tk.Tk, is_first_run: bool) -> None:
        self.result: Optional[tuple[dict, str]] = None
        self._is_first_run = is_first_run

        self.top = tk.Toplevel(parent)
        self.top.title("QuiKeys — Set Up" if is_first_run else "QuiKeys — Unlock")
        self.top.resizable(False, False)
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._build_ui()
        self.top.update_idletasks()
        self._center(self.top)
        self.top.grab_set()
        self.top.focus_force()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}
        f = ttk.Frame(self.top, padding=16)
        f.grid(sticky="nsew")

        if self._is_first_run:
            ttk.Label(f, text="Welcome to QuiKeys!", font=("", 13, "bold")).grid(
                row=0, column=0, columnspan=2, pady=(0, 4)
            )
            ttk.Label(
                f,
                text="Create a master password to encrypt your macro vault.\n"
                     "You'll type this once per session (or after each reboot).",
                wraplength=320,
            ).grid(row=1, column=0, columnspan=2, pady=(0, 10))
        else:
            ttk.Label(f, text="QuiKeys", font=("", 13, "bold")).grid(
                row=0, column=0, columnspan=2, pady=(0, 4)
            )
            ttk.Label(f, text="Enter your master password to unlock your macros.").grid(
                row=1, column=0, columnspan=2, pady=(0, 10)
            )

        row = 2
        ttk.Label(f, text="Master password:").grid(row=row, column=0, sticky="e", **pad)
        self._pw_var = tk.StringVar()
        self._pw_entry = ttk.Entry(f, textvariable=self._pw_var, show="●", width=28)
        self._pw_entry.grid(row=row, column=1, **pad)
        self._pw_entry.focus_set()

        if self._is_first_run:
            row += 1
            ttk.Label(f, text="Confirm password:").grid(row=row, column=0, sticky="e", **pad)
            self._pw2_var = tk.StringVar()
            self._pw2_entry = ttk.Entry(f, textvariable=self._pw2_var, show="●", width=28)
            self._pw2_entry.grid(row=row, column=1, **pad)

        row += 1
        self._err_var = tk.StringVar()
        ttk.Label(f, textvariable=self._err_var, foreground="red", wraplength=320).grid(
            row=row, column=0, columnspan=2
        )

        row += 1
        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(8, 0))
        label = "Create Vault" if self._is_first_run else "Unlock"
        ttk.Button(btn_frame, text=label, command=self._on_submit).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="left", padx=4)

        self.top.bind("<Return>", lambda _: self._on_submit())
        self.top.bind("<Escape>", lambda _: self._on_cancel())

    def _on_submit(self) -> None:
        pw = self._pw_var.get()
        if not pw:
            self._err_var.set("Password cannot be empty.")
            return

        if self._is_first_run:
            pw2 = self._pw2_var.get()
            if pw != pw2:
                self._err_var.set("Passwords do not match.")
                return
            vault_data = vault.create_vault(pw)
            self.result = (vault_data, pw)
            self.top.destroy()
        else:
            try:
                vault_data = vault.load_vault(pw)
            except FileNotFoundError:
                self._err_var.set("Vault file not found.")
                return
            if vault_data is None:
                self._err_var.set("Wrong password. Please try again.")
                self._pw_entry.select_range(0, "end")
                return
            self.result = (vault_data, pw)
            self.top.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.top.destroy()

    @staticmethod
    def _center(win: tk.Toplevel) -> None:
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
