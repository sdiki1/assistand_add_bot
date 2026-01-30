from __future__ import annotations

import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove
from html import escape as html_escape
from jinja2 import pass_environment
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    build_contact_keyboard,
    build_file_keyboard,
    build_multi_choice_keyboard,
    build_single_choice_keyboard,
    format_question_text,
)
from app.db import AsyncSessionLocal
from app.models import Question, Response, Survey
from app.services.files import download_telegram_file
from app.services.sheets_stub import send_to_google_sheets_stub
from app.services.survey import (
    abandon_active_responses,
    advance_response,
    append_file_answer,
    append_question_message_id,
    append_user_message_id,
    get_active_response,
    get_active_survey,
    get_answer,
    get_options_map,
    get_or_create_user,
    get_question,
    get_questions,
    get_response_answers,
    get_uploaded_files,
    save_option_answer,
    save_text_answer,
    toggle_option_answer,
    update_user_phone,
)
from app.config import BASE_DIR


def register_handlers(dp: Dispatcher) -> None:
    dp.message.register(start_command, CommandStart())
    dp.message.register(restart_command, Command("restart"))
    dp.callback_query.register(handle_callbacks, F.data.startswith("q"))
    dp.message.register(handle_messages)


async def start_command(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        survey = await get_active_survey(session)
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await abandon_active_responses(session, user.id, survey.id)
        questions = await get_questions(session, survey.id)
        if not questions:
            await message.answer("Анкета пока не настроена.")
            return
        response = await start_response_flow(session, user.id, survey.id, questions[0].id)
    text = ("Если Вы смотрели фильм <b>\"Дьявол носит Прада\"</b> и помните успевающую во всем ассистенку?  "
        "Приятно познакомиться - это Я!\n\n"
        "Занимая разные роли в компании, я узнала, как <b>«крутится каждый винтик»</b> их организационного процесса "
        "и успела накопить обширный опыт <b>fashion-retail</b>, <b>продажах</b>, <b>IT</b> и <b>управлении процессами</b>.\n\n"
        "<b>7</b> лет <b>опыта</b>, и теперь я хочу помочь тебе занять место той самой <b>right hand</b> 👠\n"
        "Заполни небольшую анкету кандидата — так я смогу лучше понять твой опыт, сильные стороны и то, "
        "какой формат работы тебе подойдёт больше всего.")
    sent = await message.bot.send_photo(
            message.from_user.id,
            FSInputFile(BASE_DIR / "bot_intro.jpg"),
            caption=text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
    # await message.answer(
        
    #     reply_markup=ReplyKeyboardRemove(),
    # )
    async with AsyncSessionLocal() as session:
        question = await get_question(session, response.current_question_id)
        await send_question(message.bot, message.chat.id, question, session, response.id)


async def restart_command(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        survey = await get_active_survey(session)
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await abandon_active_responses(session, user.id, survey.id)
        questions = await get_questions(session, survey.id)
        if not questions:
            await message.answer("Анкета пока не настроена.")
            return
        response = await start_response_flow(session, user.id, survey.id, questions[0].id)

    await message.answer("Начнём сначала.", reply_markup=ReplyKeyboardRemove())
    async with AsyncSessionLocal() as session:
        question = await get_question(session, response.current_question_id)
        await send_question(message.bot, message.chat.id, question, session, response.id)


async def start_response_flow(session: AsyncSession, user_id: int, survey_id: int, first_question_id: int):
    from app.services.survey import start_new_response

    return await start_new_response(session, user_id, survey_id, first_question_id)


async def handle_callbacks(callback: CallbackQuery) -> None:
    if not callback.data:
        return

    question_id, action = _parse_callback(callback.data)
    if not question_id:
        await callback.answer()
        return

    async with AsyncSessionLocal() as session:
        survey = await get_active_survey(session)
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        response = await get_active_response(session, user.id, survey.id)
        if not response or response.current_question_id != question_id:
            await callback.answer("Эта анкета уже завершена или устарела.", show_alert=True)
            return
        question = await get_question(session, question_id)

        if action.startswith("opt"):
            option_id = int(action.replace("opt", ""))
            if question.type == "single_choice":
                await save_option_answer(session, response.id, question.id, [option_id])
                answer_text = _format_option_values(question, [option_id])
                await _edit_callback_message(callback, question, answer_text)
                next_question = await advance_response(session, response)
                await callback.answer("Принято")
                if next_question:
                    await send_question(callback.message.bot, callback.message.chat.id, next_question, session, response.id)
                else:
                    await finish_response(callback.message, session, response.id)
                return

            if question.type == "multi_choice":
                answer = await toggle_option_answer(session, response.id, question.id, option_id)
                selected = set(answer.option_values or [])
                keyboard = build_multi_choice_keyboard(question.id, question.options, selected)
                await callback.message.edit_reply_markup(reply_markup=keyboard)
                await callback.answer()
                return

        if action == "done" and question.type == "multi_choice":
            answer = await get_answer(session, response.id, question.id)
            answer_text = _format_option_values(question, answer.option_values if answer else [])
            await _edit_callback_message(callback, question, answer_text)
            next_question = await advance_response(session, response)
            await callback.answer("Дальше")
            if next_question:
                await send_question(callback.message.bot, callback.message.chat.id, next_question, session, response.id)
            else:
                await finish_response(callback.message, session, response.id)
            return

        if action == "done_files" and question.type == "file":
            answer = await get_answer(session, response.id, question.id)
            if not answer or not answer.file_ids:
                await callback.answer("Сначала отправьте файл.", show_alert=True)
                return
            files = await get_uploaded_files(session, answer.file_ids)
            answer_text = _format_file_list(files)
            await _edit_callback_message(callback, question, answer_text)
            next_question = await advance_response(session, response)
            await callback.answer("Файлы приняты")
            if next_question:
                await send_question(callback.message.bot, callback.message.chat.id, next_question, session, response.id)
            else:
                await finish_response(callback.message, session, response.id)
            return

    await callback.answer()


async def handle_messages(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        return

    async with AsyncSessionLocal() as session:
        survey = await get_active_survey(session)
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        response = await get_active_response(session, user.id, survey.id)
        if not response or response.current_question_id is None:
            await message.answer("Нажмите /start чтобы начать анкету.")
            return
        question = await get_question(session, response.current_question_id)
        await append_user_message_id(session, response.id, message.message_id)

        if question.type == "text":
            if not message.text:
                await message.answer("Пожалуйста, отправьте текстовый ответ.")
                return
            await save_text_answer(session, response.id, question.id, message.text.strip())
            await _edit_last_question_message(
                message.bot,
                message.chat.id,
                response,
                question,
                message.text.strip(),
            )
            next_question = await advance_response(session, response)
            if next_question:
                await send_question(message.bot, message.chat.id, next_question, session, response.id)
            else:
                await finish_response(message, session, response.id)
            return

        if question.type == "contact":
            if message.contact:
                phone = message.contact.phone_number
            elif message.text:
                if message.text.strip().lower() == "ввести вручную":
                    await message.answer(
                        "Введите номер телефона или ссылку на соцсеть.",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    return
                phone = message.text.strip()
            else:
                await message.answer("Пожалуйста, отправьте контакт или текст.")
                return

            await update_user_phone(session, user.id, phone)
            await save_text_answer(session, response.id, question.id, phone)
            await _edit_last_question_message(message.bot, message.chat.id, response, question, phone)
            next_question = await advance_response(session, response)
            if next_question:
                await send_question(message.bot, message.chat.id, next_question, session, response.id)
            else:
                await finish_response(message, session, response.id)
            return

        if question.type == "file":
            if not _is_file_message(message):
                await message.answer("Отправьте файл или нажмите 'Завершить загрузку'.")
                return
            uploaded = await download_telegram_file(message.bot, session, response.id, question.id, message)
            await append_file_answer(session, response.id, question.id, uploaded.id)
            answer = await get_answer(session, response.id, question.id)
            files = await get_uploaded_files(session, answer.file_ids if answer else [])
            await _edit_last_question_message(
                message.bot,
                message.chat.id,
                response,
                question,
                _format_file_list(files),
                keep_file_keyboard=True,
            )
            return

        await message.answer("Используйте кнопки под вопросом.")


async def send_question(
    bot: Bot, chat_id: int, question: Question, session: AsyncSession, response_id: int | None
) -> Message | None:
    if question.code == "consent":
        await _send_consent_files(bot, chat_id)
    text = format_question_text(question)
    has_image = _has_question_image(question)

    if question.type == "text":
        if has_image:
            sent = await bot.send_photo(
                chat_id,
                FSInputFile(question.image_path),
                caption=text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        else:
            sent = await bot.send_message(chat_id, text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
        if response_id is not None:
            await append_question_message_id(session, response_id, sent.message_id)
        return sent

    if question.type == "contact":
        if has_image:
            sent = await bot.send_photo(
                chat_id,
                FSInputFile(question.image_path),
                caption=text,
                reply_markup=build_contact_keyboard(),
                parse_mode="HTML",
            )
        else:
            sent = await bot.send_message(chat_id, text, reply_markup=build_contact_keyboard(), parse_mode="HTML")
        if response_id is not None:
            await append_question_message_id(session, response_id, sent.message_id)
        return sent

    if question.type == "single_choice":
        if has_image:
            sent = await bot.send_photo(
                chat_id,
                FSInputFile(question.image_path),
                caption=text,
                reply_markup=build_single_choice_keyboard(question.id, question.options),
                parse_mode="HTML",
            )
        else:
            sent = await bot.send_message(
                chat_id,
                text,
                reply_markup=build_single_choice_keyboard(question.id, question.options),
                parse_mode="HTML",
            )
        if response_id is not None:
            await append_question_message_id(session, response_id, sent.message_id)
        return sent

    if question.type == "multi_choice":
        answer = None
        if response_id is not None:
            answer = await get_answer(session, response_id, question.id)
        selected = set(answer.option_values or []) if answer else set()
        keyboard = build_multi_choice_keyboard(question.id, question.options, selected)
        if has_image:
            sent = await bot.send_photo(
                chat_id,
                FSInputFile(question.image_path),
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            sent = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")
        if response_id is not None:
            await append_question_message_id(session, response_id, sent.message_id)
        return sent

    if question.type == "file":
        if has_image:
            sent = await bot.send_photo(
                chat_id,
                FSInputFile(question.image_path),
                caption=text,
                reply_markup=build_file_keyboard(question.id),
                parse_mode="HTML",
            )
        else:
            sent = await bot.send_message(chat_id, text, reply_markup=build_file_keyboard(question.id), parse_mode="HTML")
        if response_id is not None:
            await append_question_message_id(session, response_id, sent.message_id)
        return sent


async def finish_response(message: Message, session: AsyncSession, response_id: int) -> None:
    await send_to_google_sheets_stub(session, response_id)
    summary = await _build_summary(session, response_id)
    response = await session.get(Response, response_id)
    if response:
        await _delete_messages(
            message.bot,
            message.chat.id,
            list(response.question_message_ids or []) + list(response.user_message_ids or []),
        )
    await message.answer(summary, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")


def _render_answered_question(question: Question, answer_text: str) -> str:
    return f"<b>{question.text}</b>\n\n{answer_text}"


def _format_option_values(question: Question, option_ids: list[int]) -> str:
    if not option_ids:
        return "—"
    option_map = {opt.id: opt.text for opt in question.options}
    values = [option_map.get(opt_id, str(opt_id)) for opt_id in option_ids]
    return "\n".join([f"• {value}" for value in values if value])


def _format_file_list(files: list) -> str:
    if not files:
        return "Файлы не получены."
    lines = []
    for file in files:
        lines.append(file.public_url or file.file_name)
    return "\n".join(lines)


async def _edit_callback_message(callback: CallbackQuery, question: Question, answer_text: str) -> None:
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=_render_answered_question(question, answer_text), reply_markup=None, parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                _render_answered_question(question, answer_text), reply_markup=None, parse_mode="HTML"
            )
    except Exception:
        return


async def _edit_last_question_message(
    bot: Bot,
    chat_id: int,
    response: Response,
    question: Question,
    answer_text: str,
    keep_file_keyboard: bool = False,
) -> None:
    message_ids = list(response.question_message_ids or [])
    if not message_ids:
        return
    message_id = message_ids[-1]
    reply_markup = build_file_keyboard(question.id) if keep_file_keyboard else None
    try:
        if _has_question_image(question):
            await bot.edit_message_caption(
                caption=_render_answered_question(question, answer_text),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            await bot.edit_message_text(
                _render_answered_question(question, answer_text),
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
    except Exception:
        return


def _has_question_image(question: Question) -> bool:
    return bool(question.image_path and os.path.exists(question.image_path))


async def _send_consent_files(bot: Bot, chat_id: int) -> None:
    files = [
        BASE_DIR / "ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ.pdf",
        BASE_DIR / "СОГЛАСИЕ_НА_ОБРАБОТКУ_ПЕРСОНАЛЬНЫХ_ДАННЫХ.pdf",
    ]
    for path in files:
        if not path.exists():
            continue
        try:
            await bot.send_document(chat_id, FSInputFile(path))
        except Exception:
            continue


async def _build_summary(session: AsyncSession, response_id: int) -> str:
    response = await session.get(Response, response_id)
    if not response:
        return "Спасибо! Анкета завершена."
    survey = await session.get(Survey, response.survey_id)
    questions = await get_questions(session, response.survey_id)
    answers = await get_response_answers(session, response.id)
    answers_map = {answer.question_id: answer for answer in answers}
    options_map = await get_options_map(session, [q.id for q in questions])

    title_raw = f"Сводка анкеты: {survey.title}" if survey else "Сводка анкеты"
    lines = [html_escape(title_raw)]
    for question in questions:
        if question.code == 0:
            continue
        answer = answers_map.get(question.id)
        value = await _format_answer_value(session, question, answer, options_map)
        q_text = html_escape(question.text)
        a_text = html_escape(value)
        lines.append(f"<b>{q_text}</b>\n{a_text}")

    return "\n\n".join(lines)


async def _format_answer_value(
    session: AsyncSession,
    question: Question,
    answer,
    options_map: dict[int, dict[int, str]],
) -> str:
    if not answer:
        return "—"
    if answer.text_value:
        return answer.text_value
    if answer.option_values:
        texts = [options_map.get(question.id, {}).get(opt_id, str(opt_id)) for opt_id in answer.option_values]
        values = [t for t in texts if t]
        return "\n".join([f"• {value}" for value in values]) or "—"
    if answer.file_ids:
        files = await get_uploaded_files(session, answer.file_ids)
        return _format_file_list(files)
    return "—"


async def _delete_messages(bot: Bot, chat_id: int, message_ids: list[int]) -> None:
    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            continue


def _parse_callback(data: str) -> tuple[int | None, str]:
    if ":" not in data:
        return None, ""
    head, action = data.split(":", 1)
    if not head.startswith("q"):
        return None, ""
    try:
        return int(head[1:]), action
    except ValueError:
        return None, ""


def _is_file_message(message: Message) -> bool:
    return any(
        [
            message.document,
            message.photo,
            message.video,
            message.video_note,
            message.voice,
            message.audio,
        ]
    )
