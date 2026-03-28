# QuiKeys 🗝️

**Secure macro & hotkey manager** — type your password (or any repeated text) once, then
trigger it with a hotkey or text shortcut anywhere on your system.

> Vault encrypted with AES-128-CBC. Your master password never touches disk.
> Text is injected via **keystroke simulation** — the clipboard is never used.

---

## Features

| Feature | Detail |
|---------|--------|
| 🔐 Encrypted vault | PBKDF2-HMAC-SHA256 (600k iterations) + Fernet AES |
| ⌨️ Global hotkeys | Ctrl+Shift+1 … Ctrl+Shift+9 (configurable per macro) |
| 📝 Text expansion | Type `:trigger:` anywhere → trigger erased → macro typed |
| 🖱️ System tray | Runs silently in background; unlock once per session / boot |
| 🔒 Auto-lock | Lock from tray menu clears all secrets from RAM |
| 🚀 Run at startup | Optional Windows registry entry (no admin required) |
| 📦 Portable | Single `.exe` (Windows) or `.app` (macOS) — no installer |

---

## Quick Start

### Windows
1. Download `QuiKeys-windows-vX.Y.Z.zip` from Releases
2. Extract → double-click `QuiKeys.exe`
3. Set a master password on first launch
4. Add your first macro: tray icon → **Open Manager** → **➕ Add**

### macOS
1. Download `QuiKeys-macos-vX.Y.Z.zip` from Releases
2. Extract → right-click `QuiKeys.app` → **Open** → **Open Anyway** *(first launch only)*
3. Grant **Accessibility** permission when prompted *(System Preferences → Privacy & Security → Accessibility)*
4. Set a master password and add macros as above

---

## Adding Macros

Open Manager via the tray icon, then click **➕ Add**.

| Field | Example | Notes |
|-------|---------|-------|
| **Name** | Work Password | Label shown in the manager |
| **Text / secret** | `MyP@ss!` | The text that will be typed |
| **Hotkey** | `Ctrl+Shift+1` | Optional global hotkey |
| **Text trigger** | `:wp:` | Optional text expansion trigger |
| **Category** | password | For your own organization |
| **Mask in list** | ☑ | Shows `●●●●●●` in the manager table |

**Trigger format:** must start and end with `:` and be at least 3 chars total (e.g. `:pw1:`, `:hi:`).

---

## Security Model

```
Master password
     │
     ▼ PBKDF2-HMAC-SHA256 (600,000 iterations, 32-byte random salt)
32-byte key (RAM only — never written to disk)
     │
     ▼ Fernet (AES-128-CBC + HMAC-SHA256)
~/.quikeys/vault.qkv   ← [32-byte salt][ciphertext]
```

- **Salt** is stored in plaintext at the start of the vault file (this is expected and safe)
- **Derived key** exists only in process memory; cleared on Lock or Exit
- **Keystroke simulation** (`pynput`) types characters directly — clipboard is never touched
- **Run-at-startup** uses `HKCU\...\Run` registry key (Windows) — no admin required

---

## Keyboard Shortcuts

| Action | Key |
|--------|-----|
| Trigger macro | Ctrl+Shift+1 … Ctrl+Shift+9 |
| Text expansion | Type your `:trigger:` in any text field |

---

## macOS: Gatekeeper Note

QuiKeys is **not code-signed** with an Apple Developer certificate. On first launch:

1. Right-click `QuiKeys.app` → **Open**
2. Click **Open Anyway** in the dialog

This is a **one-time** step. After that, macOS remembers your choice.

If you see "Apple cannot check it for malicious software" — this is expected for
unsigned apps distributed outside the App Store.

---

## Building from Source

### Prerequisites
- Python 3.10+
- Windows: PowerShell 5+
- macOS: Xcode command-line tools (for `sips` / `iconutil`)

### Windows
```powershell
cd C:\ProjectsWin\QuiKeys
.\build.ps1
# Output: dist\QuiKeys-windows-vX.Y.Z.zip
```

### macOS
```bash
cd /path/to/QuiKeys
chmod +x build-mac.sh
./build-mac.sh
# Output: dist/QuiKeys-macos-vX.Y.Z.zip
```

### Run from source (dev)
```bash
python -m venv .venv
# Windows:
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python src\main.py
# macOS:
.venv/bin/pip install -r requirements.txt -r requirements-mac.txt
.venv/bin/python src/main.py
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `cryptography` | PBKDF2 key derivation + Fernet AES encryption |
| `pynput` | Global keyboard hooks (hotkeys + expander) + keystroke injection |
| `pystray` | System tray icon + menu |
| `Pillow` | Icon generation |
| `rumps` | macOS tray backend *(macOS only)* |
| `pyinstaller` | Build portable executable *(build-time only)* |

---

## Vault Location

| Platform | Path |
|----------|------|
| Windows | `%USERPROFILE%\.quikeys\vault.qkv` |
| macOS / Linux | `~/.quikeys/vault.qkv` |

---

## License

MIT
