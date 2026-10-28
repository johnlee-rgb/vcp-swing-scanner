"""Local private Telegram setup; tokens never appear in rendered output."""
import json
import os
from pathlib import Path
import tempfile

import requests


def config_path():
    configured = os.environ.get("VCP_TELEGRAM_CONFIG")
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / "data" / "telegram.json"


def credentials():
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token or chat:
        return token, chat  # Never mix credentials for different bots.
    try:
        path = config_path()
        if path.is_symlink() or path.stat().st_mode & 0o077:
            return None, None
        saved = json.loads(path.read_text())
        return saved.get("token"), saved.get("chat_id")
    except (OSError, ValueError, AttributeError):
        return None, None


def save_credentials(token, chat_id, username):
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".telegram-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump({"token": token, "chat_id": str(chat_id), "username": username}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def discover_chats(token, expected_username, get=None):
    get = get or requests.get
    try:
        if not token or not expected_username:
            return None, [], "Enter the bot token and username."
        base = f"https://api.telegram.org/bot{token}"
        response = get(base + "/getMe", timeout=(5, 10))
        identity = response.json()
        if not response.ok or not identity.get("ok"):
            return None, [], "Bot verification failed. Check the BotFather token."
        username = identity.get("result", {}).get("username", "")
        if username.casefold() != expected_username.strip().lstrip("@").casefold():
            return None, [], "This token belongs to a different bot. Check the username and token."
        response = get(base + "/getUpdates", params={"timeout": 0}, timeout=(5, 10))
        updates = response.json()
        if not response.ok or not updates.get("ok"):
            return username, [], "Cannot read updates. An existing webhook or bot consumer may be using this bot."
        chats = {}
        for update in updates.get("result", []):
            message = update.get("message", {})
            chat = message.get("chat", {})
            if chat.get("type") == "private" and str(message.get("text", "")).split(" ")[0] == "/start":
                chats[str(chat["id"])] = {"id": str(chat["id"]), "name": chat.get("first_name", "Private chat")}
        return username, list(chats.values()), None
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        return None, [], "Telegram could not be reached or verified. No credentials were saved. Try again."


def render_telegram_setup():
    import streamlit as st
    from vcp_scanner.workflow import send_telegram

    token, chat = credentials()
    configured = bool(token and chat)
    st.caption("Telegram: configured" if configured else "Telegram: not connected")
    with st.expander("Telegram Setup", expanded=not configured):
        with st.form("telegram_private_setup", clear_on_submit=True):
            username = st.text_input("Bot Username", value="VCP_SACNNER_bot")
            entered_token = st.text_input("Bot Token", type="password", autocomplete="off")
            verify = st.form_submit_button("Verify Bot and Find My Chat")
        if verify:
            st.session_state.pop("telegram_setup_pending", None)
            with st.spinner("Verifying Telegram bot..."):
                verified, chats, error = discover_chats(entered_token.strip(), username)
            if error:
                st.warning(error)
            elif not chats:
                st.warning("No private /start message found. Send /start to your bot again, then verify again.")
            else:
                st.session_state["telegram_setup_pending"] = {"token": entered_token.strip(), "username": verified, "chats": chats}
        pending = st.session_state.get("telegram_setup_pending")
        if pending:
            st.write("Verified bot: @" + pending["username"])
            selected = st.selectbox("Confirm Your Telegram Chat", pending["chats"], format_func=lambda c: f"{c['name']} | Chat ID {c['id']}")
            if st.button("Save Telegram on This Mac", key="telegram_save_local"):
                try:
                    save_credentials(pending["token"], selected["id"], pending["username"])
                    st.session_state.pop("telegram_setup_pending", None)
                    st.session_state["telegram_setup_saved"] = True
                    st.rerun()
                except OSError:
                    st.warning("Private settings could not be saved. Check local disk permissions.")
        if st.session_state.get("telegram_setup_saved"):
            st.success("Telegram settings saved locally. The daily schedule is not activated by this step.")
        if configured:
            if os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_CHAT_ID"):
                st.caption("Server environment settings take priority over local settings.")
            if st.button("Send Test Notification", key="telegram_send_test"):
                state, error = send_telegram(token, chat, "VCP Scanner connected. Test notification only; no trade or order placed.")
                if state == "SENT":
                    st.success("Test notification sent. Check Telegram.")
                else:
                    st.warning(error or "Test notification failed.")
