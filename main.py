from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from aiogram import Bot, Dispatcher
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.bot.assistant_test_handlers import register_assistant_test_handlers
from app.bot.handlers import register_handlers
from app.config import FILES_DIR, QUESTION_IMAGES_DIR, settings
from app.db import AsyncSessionLocal, init_db
from app.models import UploadedFile
from app.seed import seed_if_empty
from app.web.admin import router as admin_router

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
register_handlers(dp)

assistant_test_bot = None
assistant_test_dp = None
if settings.ASSISTANT_TEST_BOT_TOKEN:
    assistant_test_bot = Bot(token=settings.ASSISTANT_TEST_BOT_TOKEN)
    assistant_test_dp = Dispatcher()
    register_assistant_test_handlers(assistant_test_dp)

@asynccontextmanager
async def lifespan(app: FastAPI):
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    QUESTION_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    Path(settings.ASSISTANT_TEST_PDF_DIR).mkdir(parents=True, exist_ok=True)
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_if_empty(session)

    await bot.delete_webhook(drop_pending_updates=True)
    tasks = [
        asyncio.create_task(dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()))
    ]
    if assistant_test_bot and assistant_test_dp:
        await assistant_test_bot.delete_webhook(drop_pending_updates=True)
        tasks.append(
            asyncio.create_task(
                assistant_test_dp.start_polling(
                    assistant_test_bot,
                    allowed_updates=assistant_test_dp.resolve_used_update_types(),
                )
            )
        )
    app.state.bot_tasks = tasks
    try:
        yield
    finally:
        tasks = getattr(app.state, "bot_tasks", [])
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        await bot.session.close()
        if assistant_test_bot:
            await assistant_test_bot.session.close()


app = FastAPI(lifespan=lifespan)
app.include_router(admin_router)


@app.get("/files/{file_id}")
async def download_file(file_id: int):
    async with AsyncSessionLocal() as session:
        file = await session.get(UploadedFile, file_id)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        if not os.path.exists(file.local_path):
            raise HTTPException(status_code=404, detail="File missing")

    return FileResponse(path=file.local_path, media_type=file.mime_type, filename=file.file_name)
