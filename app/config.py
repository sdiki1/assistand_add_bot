from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
QUESTION_IMAGES_DIR = DATA_DIR / "question_images"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    WEBHOOK_URL: str = ""
    FILES_BASE_URL: str
    ADMIN_TOKEN: str = ""

    DB_URL: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'app.db').as_posix()}"

    # Optional misc
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000


settings = Settings()
