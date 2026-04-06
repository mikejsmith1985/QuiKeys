"""
Vault encryption/decryption for QuiKeys.

Security model:
  - Master password → PBKDF2-HMAC-SHA256 (600k iters, 32-byte salt) → 32-byte key
  - Key → base64url encode → Fernet key (AES-128-CBC + HMAC-SHA256)
  - Vault file layout: [32-byte salt][Fernet ciphertext]
  - Salt is stored plaintext (non-secret); the derived key never touches disk.
"""

import json
import os
import uuid
import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

import config

# Current vault schema version
SCHEMA_VERSION = 1


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from *password* and *salt* using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=config.PBKDF2_ITERATIONS,
    )
    raw = kdf.derive(password.encode("utf-8"))
    # Fernet requires URL-safe base64-encoded 32-byte key
    return base64.urlsafe_b64encode(raw)


def vault_exists() -> bool:
    return os.path.isfile(config.VAULT_FILE)


def create_vault(password: str) -> dict:
    """Create a new empty vault encrypted with *password*. Returns the empty vault dict."""
    config.ensure_vault_dir()
    salt = os.urandom(config.PBKDF2_SALT_LENGTH)
    vault_data = {"version": SCHEMA_VERSION, "macros": []}
    _write_vault(vault_data, password, salt)
    return vault_data


def load_vault(password: str) -> Optional[dict]:
    """
    Decrypt and return the vault dict, or None if the password is wrong.
    Raises FileNotFoundError if vault does not exist.
    """
    with open(config.VAULT_FILE, "rb") as f:
        salt = f.read(config.PBKDF2_SALT_LENGTH)
        ciphertext = f.read()

    key = _derive_key(password, salt)
    fernet = Fernet(key)
    try:
        plaintext = fernet.decrypt(ciphertext)
    except InvalidToken:
        return None

    return json.loads(plaintext.decode("utf-8"))


def save_vault(vault_data: dict, password: str) -> None:
    """Re-encrypt and save *vault_data* using *password*."""
    # Read existing salt to keep key stable for the session
    with open(config.VAULT_FILE, "rb") as f:
        salt = f.read(config.PBKDF2_SALT_LENGTH)
    _write_vault(vault_data, password, salt)


def _write_vault(vault_data: dict, password: str, salt: bytes) -> None:
    config.ensure_vault_dir()
    key = _derive_key(password, salt)
    fernet = Fernet(key)
    plaintext = json.dumps(vault_data, ensure_ascii=False).encode("utf-8")
    ciphertext = fernet.encrypt(plaintext)
    with open(config.VAULT_FILE, "wb") as f:
        f.write(salt)
        f.write(ciphertext)


# ---------------------------------------------------------------------------
# Macro helpers
# ---------------------------------------------------------------------------

def new_macro(
    name: str,
    text: str,
    hotkey: str = "",
    trigger: str = "",
    category: str = "other",
    masked: bool = False,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "text": text,
        "hotkey": hotkey,   # e.g. "ctrl+shift+1" or ""
        "trigger": trigger, # e.g. ":wp:" or ""
        "category": category,
        "masked": masked,
    }


def add_macro(vault_data: dict, macro: dict) -> None:
    vault_data["macros"].append(macro)


def update_macro(vault_data: dict, macro: dict) -> None:
    for i, m in enumerate(vault_data["macros"]):
        if m["id"] == macro["id"]:
            vault_data["macros"][i] = macro
            return


def delete_macro(vault_data: dict, macro_id: str) -> None:
    vault_data["macros"] = [m for m in vault_data["macros"] if m["id"] != macro_id]


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS: dict = {
    # True = copy to clipboard; False = inject keystrokes (text triggers only —
    # hotkeys always use clipboard regardless of this setting).
    "clipboard_mode": True,
    "clipboard_clear_delay": 30.0,
}


def get_settings(vault_data: dict) -> dict:
    """Return current settings merged with defaults (safe for older vaults)."""
    return {**DEFAULT_SETTINGS, **vault_data.get("settings", {})}


def update_settings(vault_data: dict, settings: dict) -> None:
    """Write *settings* into *vault_data* (call save_vault afterwards)."""
    vault_data["settings"] = settings
