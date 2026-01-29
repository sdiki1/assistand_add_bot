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

    # YooKassa
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str = ""
    YOOKASSA_AMOUNT: str = ""
    YOOKASSA_CURRENCY: str = "RUB"
    YOOKASSA_DESCRIPTION: str = "Оплата анкеты"
    YOOKASSA_VAT_CODE: int = 1
    YOOKASSA_PAYMENT_SUBJECT: str = "service"
    YOOKASSA_PAYMENT_MODE: str = "full_payment"
    YOOKASSA_TAX_SYSTEM_CODE: int = 6


settings = Settings()
