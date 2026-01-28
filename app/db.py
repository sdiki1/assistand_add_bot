from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

engine = create_async_engine(settings.DB_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_response_columns)


def _ensure_response_columns(conn) -> None:
    result = conn.exec_driver_sql("PRAGMA table_info(responses)")
    existing = {row[1] for row in result.fetchall()}
    if "question_message_ids" not in existing:
        conn.exec_driver_sql("ALTER TABLE responses ADD COLUMN question_message_ids TEXT")
    if "user_message_ids" not in existing:
        conn.exec_driver_sql("ALTER TABLE responses ADD COLUMN user_message_ids TEXT")


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
