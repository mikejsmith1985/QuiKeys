"""QuiKeys configuration — paths and constants."""
import sys
import os
import platform

APP_NAME = "QuiKeys"
APP_VERSION = "0.0.7"

PLATFORM = platform.system()  # "Windows", "Darwin", "Linux"

# Vault stored in user home, never in app dir
VAULT_DIR = os.path.join(os.path.expanduser("~"), ".quikeys")
VAULT_FILE = os.path.join(VAULT_DIR, "vault.qkv")

# PBKDF2 parameters
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_LENGTH = 32  # bytes

# Text expansion
EXPANSION_BUFFER_SIZE = 64  # max chars tracked in rolling buffer

# Inject delay between characters (ms) for slow target apps
INJECT_CHAR_DELAY = 0.012  # 12ms default

# Registry key for Windows run-at-startup
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_REG_VALUE = APP_NAME

# System tray icon size
ICON_SIZE = (64, 64)

# Hotkey prefix — Ctrl+Shift+<digit>
HOTKEY_DIGITS = list("123456789")


def ensure_vault_dir() -> None:
    os.makedirs(VAULT_DIR, exist_ok=True)
