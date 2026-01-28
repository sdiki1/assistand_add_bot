from __future__ import annotations

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    build_contact_keyboard,
    build_file_keyboard,
    build_multi_choice_keyboard,
    build_single_choice_keyboard,
    format_question_text,
)
from app.db import AsyncSessionLocal
from app.models import Question
from app.services.files import download_telegram_file
from app.services.sheets_stub import send_to_google_sheets_stub
from app.services.survey import (
    abandon_active_responses,
    advance_response,
    append_file_answer,
    get_active_response,
    get_active_survey,
    get_answer,
    get_or_create_user,
    get_question,
    get_questions,
    save_option_answer,
    save_text_answer,
    toggle_option_answer,
    update_user_phone,
)


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

    await message.answer(
        "Привет! Это анкета ассистента. Ответьте на вопросы — так мы лучше поймём ваш опыт.",
        reply_markup=ReplyKeyboardRemove(),
    )
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
                await callback.message.edit_reply_markup(reply_markup=None)
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
            next_question = await advance_response(session, response)
            await callback.message.edit_reply_markup(reply_markup=None)
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
            next_question = await advance_response(session, response)
            await callback.message.edit_reply_markup(reply_markup=None)
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

        if question.type == "text":
            if not message.text:
                await message.answer("Пожалуйста, отправьте текстовый ответ.")
                return
            await save_text_answer(session, response.id, question.id, message.text.strip())
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
            next_question = await advance_response(session, response)
            if next_question:
                if next_question.type != "contact":
                    await message.answer("Спасибо!", reply_markup=ReplyKeyboardRemove())
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
            await message.answer("Файл получен. Можно отправить ещё или нажать 'Завершить загрузку'.")
            return

        await message.answer("Используйте кнопки под вопросом.")


async def send_question(
    bot: Bot, chat_id: int, question: Question, session: AsyncSession, response_id: int | None
) -> None:
    text = format_question_text(question)

    if question.type == "text":
        await bot.send_message(chat_id, text, reply_markup=ReplyKeyboardRemove())
        return

    if question.type == "contact":
        await bot.send_message(chat_id, text, reply_markup=build_contact_keyboard())
        return

    if question.type == "single_choice":
        await bot.send_message(chat_id, text, reply_markup=build_single_choice_keyboard(question.id, question.options))
        return

    if question.type == "multi_choice":
        answer = None
        if response_id is not None:
            answer = await get_answer(session, response_id, question.id)
        selected = set(answer.option_values or []) if answer else set()
        keyboard = build_multi_choice_keyboard(question.id, question.options, selected)
        await bot.send_message(chat_id, text, reply_markup=keyboard)
        return

    if question.type == "file":
        await bot.send_message(chat_id, text, reply_markup=build_file_keyboard(question.id))
        return


async def finish_response(message: Message, session: AsyncSession, response_id: int) -> None:
    await send_to_google_sheets_stub(session, response_id)
    await message.answer("Спасибо! Анкета завершена.", reply_markup=ReplyKeyboardRemove())


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
