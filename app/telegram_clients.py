from __future__ import annotations

import asyncio
import logging
import pathlib
from typing import Dict, Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ClientManager:
    """Manage Telethon clients for multiple accounts.

    Session files are stored on disk to avoid committing secrets. The manager supports
    creating and starting clients on demand.
    """

    def __init__(self, base_path: Optional[pathlib.Path] = None) -> None:
        self.base_path = base_path or settings.sessions_dir
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._clients: Dict[str, TelegramClient] = {}

    def _session_file(self, session_path: str) -> pathlib.Path:
        path = pathlib.Path(session_path)
        if not path.is_absolute():
            path = self.base_path / path
        return path

    def create_client(self, session_path: str) -> TelegramClient:
        path = self._session_file(session_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        client = TelegramClient(str(path), settings.telegram_api_id, settings.telegram_api_hash)
        self._clients[str(path)] = client
        return client

    def get_client(self, session_path: str) -> TelegramClient:
        path = str(self._session_file(session_path))
        if path in self._clients:
            return self._clients[path]
        return self.create_client(session_path)

    async def ensure_started(self, session_path: str) -> TelegramClient:
        client = self.get_client(session_path)
        if not client.is_connected():
            await client.connect()
        return client

    async def start_phone_login(self, session_path: str, phone: str, code: str, password: Optional[str] = None) -> TelegramClient:
        """Complete login for a phone-based account using a code provided by the admin user."""
        client = self.get_client(session_path)
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            try:
                await client.sign_in(phone=phone, code=code)
            except SessionPasswordNeededError:
                if not password:
                    raise
                await client.sign_in(password=password)
        return client

    async def stop_all(self) -> None:
        await asyncio.gather(*(client.disconnect() for client in self._clients.values()))
        self._clients.clear()
