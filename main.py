from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from aiogram import Bot, Dispatcher
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.bot.handlers import register_handlers
from app.config import FILES_DIR, settings
from app.db import AsyncSessionLocal, init_db
from app.models import UploadedFile
from app.seed import seed_if_empty
from app.web.admin import router as admin_router

bot = Bot(token=settings.BOT_TOKEN)

dp = Dispatcher()
register_handlers(dp)

@asynccontextmanager
async def lifespan(app: FastAPI):
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_if_empty(session)

    await bot.delete_webhook(drop_pending_updates=True)
    bot_task = asyncio.create_task(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    )
    app.state.bot_task = bot_task
    try:
        yield
    finally:
        task = getattr(app.state, "bot_task", None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await bot.session.close()


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
