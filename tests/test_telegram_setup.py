"""Local Telegram setup tests; no real secrets or network calls."""
from types import SimpleNamespace

import pytest
import requests
from streamlit.testing.v1 import AppTest

import app
from vcp_scanner.telegram_setup import credentials, discover_chats, save_credentials


@pytest.fixture
def private_settings(tmp_path, monkeypatch):
    path = tmp_path / "telegram.json"
    monkeypatch.setenv("VCP_TELEGRAM_CONFIG", str(path))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    return path


def reply(payload, ok=True):
    return SimpleNamespace(ok=ok, json=lambda: payload)


def test_private_save_survives_reload_and_env_pair_overrides(private_settings, monkeypatch):
    save_credentials("fake-test-token", "1234", "VCP_SACNNER_bot")
    assert private_settings.stat().st_mode & 0o777 == 0o600
    assert credentials() == ("fake-test-token", "1234")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "different-fake-token")
    assert credentials() == ("different-fake-token", None)


def test_world_readable_config_is_not_loaded(private_settings):
    save_credentials("fake-test-token", "1234", "VCP_SACNNER_bot")
    private_settings.chmod(0o644)
    assert credentials() == (None, None)


def test_discovery_only_reads_correct_bot_and_private_start_messages():
    calls = []
    def get(url, **kwargs):
        calls.append(url.rsplit("/", 1)[1])
        if url.endswith("getMe"):
            return reply({"ok": True, "result": {"username": "VCP_SACNNER_bot"}})
        assert "offset" not in kwargs.get("params", {})
        return reply({"ok": True, "result": [
            {"message": {"text": "/start", "chat": {"type": "private", "id": 1234, "first_name": "Test"}}},
            {"message": {"text": "/start", "chat": {"type": "group", "id": -2345}}},
            {"message": {"text": "hello", "chat": {"type": "private", "id": 3456}}},
        ]})
    username, chats, error = discover_chats("fake-test-token", "@VCP_SACNNER_bot", get)
    assert not error and username == "VCP_SACNNER_bot"
    assert chats == [{"id": "1234", "name": "Test"}]
    assert calls == ["getMe", "getUpdates"]


def test_wrong_bot_and_network_error_are_safe():
    get = lambda *a, **k: reply({"ok": True, "result": {"username": "wrong_bot"}})
    assert "different bot" in discover_chats("fake-test-token", "VCP_SACNNER_bot", get)[2]
    def failed(*a, **k):
        raise requests.Timeout("fake-test-token must not leak")
    error = discover_chats("fake-test-token", "VCP_SACNNER_bot", failed)[2]
    assert "fake-test-token" not in error


def test_setup_ui_password_save_and_explicit_send(private_settings, monkeypatch):
    from vcp_scanner import telegram_setup, workflow
    monkeypatch.setattr(telegram_setup, "discover_chats", lambda *a: ("VCP_SACNNER_bot", [{"id": "1234", "name": "Test"}], None))
    sent = []
    monkeypatch.setattr(workflow, "send_telegram", lambda *a: (sent.append(1) or "SENT", None))
    def render():
        from vcp_scanner.telegram_setup import render_telegram_setup
        render_telegram_setup()
    ui = AppTest.from_function(render).run()
    ui.text_input[1].set_value("fake-test-token")
    ui.button[0].click().run()
    assert not ui.exception
    assert not private_settings.exists() and not sent
    ui.button(key="telegram_save_local").click().run()
    assert not ui.exception
    assert credentials() == ("fake-test-token", "1234")
    assert not sent
    assert all("fake-test-token" not in element.value for element in ui.markdown)
    ui.button(key="telegram_send_test").click().run()
    assert not ui.exception and sent == [1]
