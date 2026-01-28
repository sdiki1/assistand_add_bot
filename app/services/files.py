from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import FILES_DIR, settings
from app.models import UploadedFile


def _safe_filename(value: str) -> str:
    value = value.strip().replace(" ", "_")
    value = re.sub(r"[^a-zA-Z0-9_.-]", "", value)
    return value or "file"


async def extract_telegram_file(message: Message) -> tuple[str, str, Optional[str], Optional[int], str]:
    if message.document:
        doc = message.document
        return doc.file_id, doc.file_name or "document.pdf", doc.mime_type, doc.file_size, "document"
    if message.photo:
        photo = message.photo[-1]
        return photo.file_id, f"photo_{photo.file_unique_id}.jpg", "image/jpeg", photo.file_size, "photo"
    if message.video:
        video = message.video
        return video.file_id, video.file_name or f"video_{video.file_unique_id}.mp4", video.mime_type, video.file_size, "video"
    if message.video_note:
        note = message.video_note
        return note.file_id, f"video_note_{note.file_unique_id}.mp4", "video/mp4", note.file_size, "video_note"
    if message.voice:
        voice = message.voice
        return voice.file_id, f"voice_{voice.file_unique_id}.ogg", voice.mime_type, voice.file_size, "voice"
    if message.audio:
        audio = message.audio
        return audio.file_id, audio.file_name or f"audio_{audio.file_unique_id}.mp3", audio.mime_type, audio.file_size, "audio"
    raise ValueError("Unsupported file type")


async def download_telegram_file(
    bot: Bot,
    session: AsyncSession,
    response_id: int,
    question_id: int,
    message: Message,
) -> UploadedFile:
    file_id, file_name, mime_type, size, file_type = await extract_telegram_file(message)
    tg_file = await bot.get_file(file_id)

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(file_name)
    local_path = FILES_DIR / f"{tg_file.file_unique_id}_{safe_name}"

    await bot.download(tg_file, destination=local_path)

    uploaded = UploadedFile(
        response_id=response_id,
        question_id=question_id,
        tg_file_id=file_id,
        tg_unique_id=tg_file.file_unique_id,
        file_name=safe_name,
        mime_type=mime_type,
        size=size,
        local_path=str(local_path),
        public_url="",
        file_type=file_type,
    )
    session.add(uploaded)
    await session.commit()
    await session.refresh(uploaded)

    base_url = settings.FILES_BASE_URL.rstrip("/")
    uploaded.public_url = f"{base_url}/files/{uploaded.id}"
    await session.commit()
    await session.refresh(uploaded)
    return uploaded
