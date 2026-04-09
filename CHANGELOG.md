# Changelog — QuiKeys

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.11] — 2026-04-09

### Fixed
- **Hotkeys now fire when a Windows Security or credential dialog has keyboard focus.**
  Switched from pynput's `WH_KEYBOARD_LL` hook (blocked by elevated/protected windows)
  to the Win32 `RegisterHotKey` API, which is intercepted at the kernel
  message-routing level before any application can consume the combo.
- **Clipboard write no longer silently fails on security dialogs.**
  `OpenClipboard` now retries up to 10 times (500 ms total) to handle the brief
  period when a credential dialog holds the clipboard lock to block injection.
- **Text-trigger expansions now paste in-place automatically.**
  In `clipboard_mode`, the expander was erasing the trigger and writing the
  expansion to the clipboard but not pasting it, leaving the field empty.
  A Ctrl+V is now sent automatically after the clipboard write.

## [0.0.10] — 2026-04-06

### Added
- Enterprise workflow initialized with Forge Terminal Workflow Architect

### Changed
- Hotkeys now **always** deliver text via clipboard (never keystroke injection).
  Press Ctrl+V after a hotkey fires to paste into any field, including Windows
  security dialogs (UAC, Windows Security, credential prompts) where `SendInput`
  is blocked by the OS. The clipboard is shared with the Windows Secure Desktop.
- `clipboard_mode` setting default changed from `false` to `true` — text-trigger
  expansions also default to clipboard delivery for all new and existing vaults
  that have not explicitly overridden the setting.
- Settings UI label updated to clarify that the `clipboard_mode` toggle now
  applies to text-trigger expansions only (hotkeys are unconditionally clipboard).

### Fixed
- Hotkeys no longer attempt keystroke injection (`SendInput`) which silently
  fails on the Windows Secure Desktop and could corrupt input in other windows.
