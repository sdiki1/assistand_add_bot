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
    ASSISTANT_TEST_BOT_TOKEN: str = ""
    WEBHOOK_URL: str = ""
    FILES_BASE_URL: str
    ADMIN_TOKEN: str = ""

    DB_URL: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'app.db').as_posix()}"

    # Survey codes per bot
    ASSISTANT_MAIN_SURVEY_CODE: str = "assistant_v1"
    ASSISTANT_TEST_SURVEY_CODE: str = "assistant_test_v1"

    # Assistant test PDFs
    ASSISTANT_TEST_PDF_DIR: str = str(DATA_DIR / "assistant_test_pdfs")

    # Google Sheets (optional)
    GOOGLE_SHEET_ID: str = ""
    GOOGLE_SHEET_TAB: str = "Sheet1"
    GOOGLE_SHEETS_CREDENTIALS_PATH: str = ""
    GOOGLE_SHEETS_CREDENTIALS_JSON: str = ""

    # Optional misc
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000


settings = Settings()
