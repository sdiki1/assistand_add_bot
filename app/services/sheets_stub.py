from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DATA_DIR
from app.models import Answer, Question, Response, Survey, UploadedFile, User
from app.services.survey import get_options_map, get_response_answers, get_uploaded_files


async def send_to_google_sheets_stub(session: AsyncSession, response_id: int) -> None:
    response = await session.get(Response, response_id)
    if not response:
        return
    user = await session.get(User, response.user_id)
    survey = await session.get(Survey, response.survey_id)
    if not user or not survey:
        return

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

    payload = {
        "timestamp": (response.completed_at or datetime.utcnow()).isoformat(),
        "survey": survey.title,
        "telegram_id": user.tg_id,
        "username": user.username or "",
        "fio": fio,
        "contact": contact,
        "files": "; ".join(files_links),
        "answers": row_answers,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_path = Path(DATA_DIR) / "google_sheets_stub.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
