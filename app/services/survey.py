from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, Option, Question, Response, Survey, UploadedFile, User


async def get_active_survey(session: AsyncSession) -> Survey:
    result = await session.execute(
        select(Survey).where(Survey.is_active.is_(True)).order_by(Survey.id.desc())
    )
    survey = result.scalars().first()
    if not survey:
        raise RuntimeError("No active survey found")
    return survey


async def get_questions(session: AsyncSession, survey_id: int) -> list[Question]:
    result = await session.execute(
        select(Question)
        .where(Question.survey_id == survey_id)
        .order_by(Question.order.asc(), Question.id.asc())
    )
    return list(result.scalars().all())


async def get_question(session: AsyncSession, question_id: int) -> Question:
    result = await session.execute(select(Question).where(Question.id == question_id))
    question = result.scalars().first()
    if not question:
        raise RuntimeError("Question not found")
    return question


async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None, first_name: str | None, last_name: str | None) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalars().first()
    if user:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        await session.commit()
        return user

    user = User(
        tg_id=tg_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_active_response(session: AsyncSession, user_id: int, survey_id: int) -> Optional[Response]:
    result = await session.execute(
        select(Response)
        .where(Response.user_id == user_id, Response.survey_id == survey_id)
        .where(Response.status == "in_progress")
        .order_by(Response.started_at.desc())
    )
    return result.scalars().first()


async def abandon_active_responses(session: AsyncSession, user_id: int, survey_id: int) -> None:
    await session.execute(
        update(Response)
        .where(Response.user_id == user_id, Response.survey_id == survey_id)
        .where(Response.status == "in_progress")
        .values(status="abandoned")
    )
    await session.commit()


async def start_new_response(session: AsyncSession, user_id: int, survey_id: int, first_question_id: int) -> Response:
    response = Response(
        user_id=user_id,
        survey_id=survey_id,
        status="in_progress",
        started_at=datetime.utcnow(),
        current_question_id=first_question_id,
    )
    session.add(response)
    await session.commit()
    await session.refresh(response)
    return response


async def get_answer(session: AsyncSession, response_id: int, question_id: int) -> Optional[Answer]:
    result = await session.execute(
        select(Answer).where(Answer.response_id == response_id, Answer.question_id == question_id)
    )
    return result.scalars().first()


async def save_text_answer(session: AsyncSession, response_id: int, question_id: int, value: str) -> Answer:
    answer = await get_answer(session, response_id, question_id)
    if answer:
        answer.text_value = value
    else:
        answer = Answer(response_id=response_id, question_id=question_id, text_value=value)
        session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer


async def save_option_answer(session: AsyncSession, response_id: int, question_id: int, option_ids: list[int]) -> Answer:
    answer = await get_answer(session, response_id, question_id)
    if answer:
        answer.option_values = option_ids
    else:
        answer = Answer(response_id=response_id, question_id=question_id, option_values=option_ids)
        session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer


async def toggle_option_answer(session: AsyncSession, response_id: int, question_id: int, option_id: int) -> Answer:
    answer = await get_answer(session, response_id, question_id)
    if not answer:
        answer = Answer(response_id=response_id, question_id=question_id, option_values=[])
        session.add(answer)
        await session.commit()
        await session.refresh(answer)

    selected = set(answer.option_values or [])
    if option_id in selected:
        selected.remove(option_id)
    else:
        selected.add(option_id)
    answer.option_values = list(sorted(selected))
    await session.commit()
    await session.refresh(answer)
    return answer


async def append_file_answer(session: AsyncSession, response_id: int, question_id: int, file_id: int) -> Answer:
    answer = await get_answer(session, response_id, question_id)
    if not answer:
        answer = Answer(response_id=response_id, question_id=question_id, file_ids=[file_id])
        session.add(answer)
    else:
        current = list(answer.file_ids or [])
        current.append(file_id)
        answer.file_ids = current
    await session.commit()
    await session.refresh(answer)
    return answer


async def get_next_question(session: AsyncSession, survey_id: int, current_question_id: int | None) -> Optional[Question]:
    if current_question_id is None:
        result = await session.execute(
            select(Question).where(Question.survey_id == survey_id).order_by(Question.order.asc(), Question.id.asc())
        )
        return result.scalars().first()

    current = await get_question(session, current_question_id)
    result = await session.execute(
        select(Question)
        .where(Question.survey_id == survey_id, Question.order > current.order)
        .order_by(Question.order.asc(), Question.id.asc())
    )
    return result.scalars().first()


async def advance_response(session: AsyncSession, response: Response) -> Optional[Question]:
    next_question = await get_next_question(session, response.survey_id, response.current_question_id)
    if next_question:
        response.current_question_id = next_question.id
        await session.commit()
        return next_question

    response.status = "completed"
    response.completed_at = datetime.utcnow()
    response.current_question_id = None
    await session.commit()
    return None


async def update_user_phone(session: AsyncSession, user_id: int, phone: str) -> None:
    await session.execute(update(User).where(User.id == user_id).values(phone=phone))
    await session.commit()


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_options_map(session: AsyncSession, question_ids: Iterable[int]) -> dict[int, dict[int, str]]:
    if not question_ids:
        return {}
    result = await session.execute(select(Option).where(Option.question_id.in_(list(question_ids))))
    options = result.scalars().all()
    mapping: dict[int, dict[int, str]] = {}
    for opt in options:
        mapping.setdefault(opt.question_id, {})[opt.id] = opt.text
    return mapping


async def get_response_answers(session: AsyncSession, response_id: int) -> list[Answer]:
    result = await session.execute(select(Answer).where(Answer.response_id == response_id))
    return list(result.scalars().all())


async def count_users(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(User.id)))
    return int(result.scalar() or 0)


async def get_uploaded_files(session: AsyncSession, file_ids: list[int]) -> list[UploadedFile]:
    if not file_ids:
        return []
    result = await session.execute(select(UploadedFile).where(UploadedFile.id.in_(file_ids)))
    return list(result.scalars().all())


async def append_question_message_id(session: AsyncSession, response_id: int, message_id: int) -> None:
    response = await session.get(Response, response_id)
    if not response:
        return
    current = list(response.question_message_ids or [])
    current.append(message_id)
    response.question_message_ids = current
    await session.commit()


async def append_user_message_id(session: AsyncSession, response_id: int, message_id: int) -> None:
    response = await session.get(Response, response_id)
    if not response:
        return
    current = list(response.user_message_ids or [])
    current.append(message_id)
    response.user_message_ids = current
    await session.commit()
