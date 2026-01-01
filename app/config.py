from __future__ import annotations

import pathlib
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    
    database_url: str = Field(
        default="sqlite:///./telegram_interview.db",
        description="SQLAlchemy database URL. Defaults to local SQLite file.",
    )
    admin_bot_token: str = Field(
        default="",
        description="Token for the admin bot (do not commit real tokens).",
    )
    telegram_api_id: int = Field(
        default=0,
        description="Telegram API ID for user clients (required for Telethon).",
    )
    telegram_api_hash: str = Field(
        default="",
        description="Telegram API Hash for user clients (required for Telethon).",
    )
    sessions_dir: pathlib.Path = Field(
        default=pathlib.Path("./sessions"),
        description="Directory where Telethon session files are stored.",
    )
    log_level: str = Field(default="INFO", description="Logging level.")
    timezone: str = Field(default="UTC", description="Timezone for schedulers.")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def get_settings() -> Settings:
    return Settings()
