"""Tests that editing a macro after Lock → Unlock updates what hotkeys and triggers deliver."""

from unittest.mock import Mock

import main


def _reset_app_state(monkeypatch, root_window) -> None:
    """Point main's module globals at fakes so no real windows or listeners start."""
    monkeypatch.setattr(main, "_root", root_window)
    monkeypatch.setattr(main, "_manager_win", None)
    monkeypatch.setattr(main, "_start_listeners", Mock())


def test_unlock_discards_manager_window_bound_to_old_vault(monkeypatch):
    _reset_app_state(monkeypatch, Mock())
    stale_manager = Mock()
    monkeypatch.setattr(main, "_manager_win", stale_manager)
    monkeypatch.setattr(main, "_do_unlock", lambda: True)

    main._unlock_and_resume()

    stale_manager.win.destroy.assert_called_once()
    assert main._manager_win is None


def test_manager_opened_after_unlock_edits_the_live_vault(monkeypatch):
    import gui.manager

    _reset_app_state(monkeypatch, Mock())
    stale_vault = {"macros": [{"id": "pw", "text": "Password4"}]}
    fresh_vault = {"macros": [{"id": "pw", "text": "Password4"}]}
    monkeypatch.setattr(main, "_manager_win", Mock(_vault=stale_vault))
    constructed_with_vaults = []
    monkeypatch.setattr(
        gui.manager,
        "ManagerWindow",
        lambda root, vault_data, password, on_macros_changed: constructed_with_vaults.append(vault_data) or Mock(),
    )

    def unlock_with_fresh_vault() -> bool:
        main.STATE.vault_data = fresh_vault
        return True

    monkeypatch.setattr(main, "_do_unlock", unlock_with_fresh_vault)

    main._unlock_and_resume()
    main._open_manager()

    assert constructed_with_vaults == [fresh_vault]
    assert constructed_with_vaults[0] is main.STATE.vault_data


def test_unlock_without_existing_manager_window_does_not_fail(monkeypatch):
    _reset_app_state(monkeypatch, Mock())
    monkeypatch.setattr(main, "_do_unlock", lambda: True)

    main._unlock_and_resume()

    assert main._manager_win is None
