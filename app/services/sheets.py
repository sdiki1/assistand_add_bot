from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Answer, Question, Response, Survey, User
from app.services.survey import get_options_map, get_response_answers, get_uploaded_files

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def sheets_enabled() -> bool:
    return bool(settings.GOOGLE_SHEET_ID and (settings.GOOGLE_SHEETS_CREDENTIALS_PATH or settings.GOOGLE_SHEETS_CREDENTIALS_JSON))


def _load_credentials() -> Credentials:
    if settings.GOOGLE_SHEETS_CREDENTIALS_JSON:
        info = json.loads(settings.GOOGLE_SHEETS_CREDENTIALS_JSON)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    return Credentials.from_service_account_file(settings.GOOGLE_SHEETS_CREDENTIALS_PATH, scopes=SCOPES)


def _prepare_payload(raw: dict[str, Any]) -> tuple[list[str], list[str]]:
    base_headers = [
        "timestamp",
        "survey",
        "telegram_id",
        "username",
        "fio",
        "contact",
        "files",
    ]
    answer_headers = list(raw["answers"].keys())
    headers = base_headers + answer_headers

    row = [
        raw["timestamp"],
        raw["survey"],
        str(raw["telegram_id"]),
        raw["username"],
        raw["fio"],
        raw["contact"],
        raw["files"],
    ]
    row.extend([raw["answers"].get(key, "") for key in answer_headers])
    return headers, row


def _send_sync(raw: dict[str, Any]) -> None:
    credentials = _load_credentials()
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(settings.GOOGLE_SHEET_ID)
    worksheet = spreadsheet.worksheet(settings.GOOGLE_SHEET_TAB)

    headers, row = _prepare_payload(raw)
    existing_headers = worksheet.row_values(1)
    if not existing_headers:
        worksheet.update([headers], "A1")
    worksheet.append_row(row, value_input_option="USER_ENTERED")


async def send_to_google_sheets(session: AsyncSession, response_id: int) -> None:
    raw = await build_payload(session, response_id)
    if not raw:
        return
    await asyncio.to_thread(_send_sync, raw)


async def build_payload(session: AsyncSession, response_id: int) -> dict[str, Any] | None:
    response = await session.get(Response, response_id)
    if not response:
        return None
    user = await session.get(User, response.user_id)
    survey = await session.get(Survey, response.survey_id)
    if not user or not survey:
        return None

    questions_result = await session.execute(
        select(Question).where(Question.survey_id == survey.id).order_by(Question.order.asc())
    )
    questions = list(questions_result.scalars().all())
    answers = await get_response_answers(session, response.id)
    answers_map = {answer.question_id: answer for answer in answers}
    option_map = await get_options_map(session, [q.id for q in questions])

    fio = ""
    contact = ""
    files_links: list[str] = []
    row_answers: dict[str, str] = {}

    for question in questions:
        answer = answers_map.get(question.id)
        value = ""
        if answer:
            if answer.text_value:
                value = answer.text_value
            if answer.option_values:
                texts = [option_map.get(question.id, {}).get(opt_id, str(opt_id)) for opt_id in answer.option_values]
                value = "; ".join([t for t in texts if t])
            if answer.file_ids:
                files = await get_uploaded_files(session, answer.file_ids)
                file_urls = [f.public_url for f in files]
                value = "; ".join(file_urls)
                files_links.extend(file_urls)

        row_answers[question.text] = value
        if question.code == "fio":
            fio = value
        if question.code == "contact":
            contact = value

    return {
        "timestamp": (response.completed_at or datetime.utcnow()).isoformat(),
        "survey": survey.title,
        "telegram_id": user.tg_id,
        "username": user.username or "",
        "fio": fio,
        "contact": contact,
        "files": "; ".join(files_links),
        "answers": row_answers,
    }
