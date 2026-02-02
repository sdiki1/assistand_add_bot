from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InputMediaPhoto, Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import build_single_choice_keyboard, format_question_text
from app.config import BASE_DIR, settings
from app.db import AsyncSessionLocal
from app.models import Option, Response
from app.services.survey import (
    abandon_active_responses,
    advance_response,
    append_question_message_id,
    get_active_response,
    get_or_create_user,
    get_question,
    get_questions,
    get_survey_by_code,
    get_response_answers,
    save_option_answer,
    start_new_response,
)


INTRO_MESSAGE_1 = (
    "<i>"
    "Привет, ассистентка! 👠\n"
    "это Олеся.\n\n"
    "У меня есть теория: существует 4 формата ассистентов, в которых люди развиваются быстрее всего, потому что "
    "работают в соответствии со своим типом личности.\n"
    "Я подготовила тест, который поможет определить, какой ты тип ассистента руководителя."
    "</i>"
)


INTRO_MESSAGE_2 = (
    "<i>"
    "И всё это - персонализировано под твой тип личности.\n"
    "Ну согласись, звучит как чит-код к карьерному росту?\n\n"
    "💔Время прохождения теста — всего 7 минут.\n"
    "Let’s choose your assistant superpower 💼⚡"
    "</i>"
)


RESULT_TEXTS = {
    "OFFICE": (
        "<b>офигеть… я в восторге от твоего результата!!</b>\n"
        "ты не просто ассистент — ты тот самый тип, на котором вообще всё держится.\n\n"
        "и ты… <tg-spoiler><b>OFFICE GIRL</b></tg-spoiler> 🖇️☕\n\n"
        "И без тебя тут, если честно… ничего нормально не работает.\n"
        "Ты в курсе процессов, людей, настроений, скрытых конфликтов и “что на самом деле происходит”, даже если "
        "формально это вообще не твоя зона ответственности.\n\n"
        "При этом ты как-то магически совмещаешь:\n"
        "✨ лёгкость в общении\n"
        "😏 иронию и живой ум\n"
        "🧠 системность\n"
        "🧱 и железную собранность, когда начинается реальная движуха\n\n"
        "<b>ААА, быстрее открывай файл с разбором</b> — там подробно про твоё ассистентское ядро, сильные стороны и как "
        "выстроить работу так, чтобы ты не выгорала, а росла в доходе и влиянии 🚀👇🏻\n"
        "И да… файл получился очень красивый и максимально прикладной... 💔\n\n"
        "<b>👀 А теперь самое интересное: а какого типа ассистентов больше всего?</b>\n"
        "Заходи в наш чат ассистентов и выбирай свой тип в опроснике — мне безумно интересно посмотреть на статистику 🔥"
    ),
    "BUSINESS": (
        "<b>офигеть… вот это уровень, конечно.</b>\n"
        "тут сразу понятно — перед нами не просто ассистент, а человек, который реально влияет на движение бизнеса.\n\n"
        "и ты… <tg-spoiler><b>BUSINESS GIRL</b></tg-spoiler> 📊⚡\n\n"
        "Ты не просто “помогаешь” — ты запускаешь и двигаешь процессы.\n"
        "Там, где у других просто список задач, у тебя — система, приоритеты и понимание, что действительно приведёт к "
        "результату.\n"
        "Ты мыслишь не поручениями, а итогами.\n\n"
        "Ты умеешь соединять:\n"
        "🧩 людей\n"
        "📅 договорённости\n"
        "⏳ сроки\n"
        "📌 ответственность\n\n"
        "<b>ААА, срочно открывай файл с разбором</b> — там подробно про твоё ассистентское ядро, сильные стороны и как "
        "выстроить работу так, чтобы расти не только в задачах, но и в деньгах, влиянии и роли в компании 🚀👇🏻\n"
        "И да… файл получился очень красивый и максимально прикладной 💔\n\n"
        "<b>👀 И теперь самое интересное: а какого типа бизнес-ассистентов больше всего?</b>\n"
        "Заходи в наш чат ассистентов и выбирай свой тип в опросе — мне безумно интересно посмотреть на общую картину 🔥"
    ),
    "PERSONAL": (
        "<b>офигеть, ну это прям отдельный уровень близости и доверия…</b>\n"
        "ты не просто ассистент — ты человек, который держит жизнь руководителя в порядке.\n\n"
        "и ты… <tg-spoiler><b>PERSONAL GIRL</b></tg-spoiler> 💄🗓️\n\n"
        "Ты та самая ассистентка, которая знает жизнь руководителя лучше, чем его собственный календарь. "
        "В твоей голове живут встречи, поездки, дни рождения, документы, билеты и все эти сообщения в стиле: «пишу, "
        "пока не забыл, это не срочно» — которые почему-то всегда становятся срочными 😅\n\n"
        "<b>ААА, скорее открывай файл с разбором</b> — там подробно про твоё ассистентское ядро, сильные стороны и как выстроить "
        "работу так, чтобы ты не растворялась в чужой жизни, а росла в доходе, статусе и влиянии 🚀👇🏻\n"
        "И да… файл получился очень красивый и супер практичный 💔\n\n"
        "<b>👀 И теперь самое любопытное: а какого типа ассистентов больше всего?</b>\n"
        "Залетай в наш чат ассистентов и выбирай свой тип в опросе — мне безумно интересно увидеть общую статистику 🔥"
    ),
    "MULTI": (
        "<b>вот это мощь, конечно…</b>\n"
        "ты не просто ассистент — ты универсальный человек, который вытаскивает всё и сразу.\n\n"
        "и ты… <tg-spoiler><b>MULTI GIRL</b></tg-spoiler> 🎧🗂️\n\n"
        "Ты не выбираешь один формат — ты умеешь всё.\n"
        "Сегодня ты заказываешь воду в офис, через час организуешь перелёт, а вечером уже собираешь данные для отчёта. "
        "И всё это — без паники и с ощущением, что так и было задумано.\n\n"
        "В твоей голове одновременно помещаются:\n"
        "🏠 личные вопросы руководителя\n"
        "⚙️ операционные процессы\n"
        "📊 бизнес-задачи\n\n"
        "<b>ААА, скорее открывай файл с разбором</b> — там подробно про твоё ассистентское ядро, сильные стороны и как выстроить"
        "работу так, чтобы твоя универсальность стала точкой роста, а не постоянной перегрузкой 🚀👇🏻\n"
        "И да… файл получился очень красивый и максимально прикладной 💔\n\n"
        "<b>👀 И теперь главный вопрос: а какого типа ассистентов больше всего?</b>\n"
        "Залетай в наш чат ассистентов и выбирай свой тип в опросе — мне безумно интересно посмотреть на общую картину 🔥"
    ),
}

RESULT_PDFS = {
    "OFFICE": "office_assistant.pdf",
    "PERSONAL": "personal_assistant.pdf",
    "BUSINESS": "business_assistant.pdf",
    "MULTI": "multi_assistant.pdf",
}


def register_assistant_test_handlers(dp: Dispatcher) -> None:
    dp.message.register(start_command, CommandStart())
    dp.message.register(restart_command, Command("restart"))
    dp.callback_query.register(start_test_callback, F.data == "start_test")
    dp.callback_query.register(handle_callbacks, F.data.startswith("q"))
    dp.message.register(handle_messages)


async def start_command(message: Message) -> None:
    await message.answer(INTRO_MESSAGE_1, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        INTRO_MESSAGE_2,
        parse_mode="HTML",
        reply_markup=_build_start_keyboard(),
    )


async def restart_command(message: Message) -> None:
    await start_command(message)


async def start_test_callback(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        try:
            survey = await get_survey_by_code(session, settings.ASSISTANT_TEST_SURVEY_CODE)
        except Exception:
            await callback.answer("Тест пока не настроен.", show_alert=True)
            return
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        await abandon_active_responses(session, user.id, survey.id)
        questions = await get_questions(session, survey.id)
        if not questions:
            await callback.message.answer("Тест пока не настроен.")
            await callback.answer()
            return
        response = await start_new_response(session, user.id, survey.id, questions[0].id)
        await _send_test_question(callback.message.bot, callback.message.chat.id, questions[0], session, response.id)

    with suppress(Exception):
        await callback.message.delete()
    await callback.answer("Поехали!")


async def handle_callbacks(callback: CallbackQuery) -> None:
    if not callback.data:
        return
    question_id, action = _parse_callback(callback.data)
    if not question_id:
        await callback.answer()
        return

    async with AsyncSessionLocal() as session:
        try:
            survey = await get_survey_by_code(session, settings.ASSISTANT_TEST_SURVEY_CODE)
        except Exception:
            await callback.answer("Тест пока не настроен.", show_alert=True)
            return
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
            callback.from_user.last_name,
        )
        response = await get_active_response(session, user.id, survey.id)
        if not response or response.current_question_id != question_id:
            await callback.answer("Этот тест уже завершён или устарел.", show_alert=True)
            return
        question = await get_question(session, question_id)

        if action.startswith("opt"):
            option_id = int(action.replace("opt", ""))
            await save_option_answer(session, response.id, question.id, [option_id])
            with suppress(Exception):
                await callback.message.edit_reply_markup(reply_markup=None)
            next_question = await advance_response(session, response)
            await callback.answer("Принято")
            if next_question:
                await _send_test_question(callback.message.bot, callback.message.chat.id, next_question, session, response.id)
            else:
                await finish_response(callback.message, session, response.id)
            return

    await callback.answer()


async def handle_messages(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        return
    await message.answer("Нажмите /start чтобы начать тест.")


async def finish_response(message: Message, session: AsyncSession, response_id: int) -> None:
    loading = await message.answer("loading....")
    result_type = await _compute_result(session, response_id)
    with suppress(Exception):
        await message.bot.delete_message(chat_id=loading.chat.id, message_id=loading.message_id)

    response = await session.get(Response, response_id)
    if response:
        await _delete_messages(message.bot, message.chat.id, list(response.question_message_ids or []))

    text = RESULT_TEXTS.get(result_type, RESULT_TEXTS["MULTI"])
    await message.answer(text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await _send_result_pdf(message.bot, message.chat.id, result_type)


def _build_start_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="пройти тест 👠", callback_data="start_test")
    builder.adjust(1)
    return builder.as_markup()


def _get_question_images(question) -> list[Path]:
    settings_data = question.settings or {}
    image_dir = settings_data.get("image_dir")
    if not image_dir:
        code = (question.code or "").lower()
        if code.startswith("q") and code[1:].isdigit():
            image_dir = str(Path("assistant_images_questions") / f"question{int(code[1:])}")
        else:
            return []
    path = Path(str(image_dir))
    if not path.is_absolute():
        path = Path(BASE_DIR) / path
    if not path.exists() or not path.is_dir():
        return []
    allowed = {".jpg", ".jpeg", ".png", ".webp"}
    files = [p for p in sorted(path.iterdir()) if p.is_file() and p.suffix.lower() in allowed]
    return files


async def _send_test_question(
    bot: Bot,
    chat_id: int,
    question,
    session: AsyncSession,
    response_id: int | None,
) -> None:
    images = _get_question_images(question)
    if images:
        media = [InputMediaPhoto(media=FSInputFile(path)) for path in images]
        try:
            messages = await bot.send_media_group(chat_id, media)
            if response_id is not None:
                for msg in messages:
                    await append_question_message_id(session, response_id, msg.message_id)
        except Exception:
            pass

    keyboard = build_single_choice_keyboard(question.id, question.options)
    text = format_question_text(question)
    sent = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")
    if response_id is not None:
        await append_question_message_id(session, response_id, sent.message_id)


async def _compute_result(session: AsyncSession, response_id: int) -> str:
    response = await session.get(Response, response_id)
    if not response:
        return "MULTI"
    answers = await get_response_answers(session, response_id)
    option_ids = [opt_id for answer in answers for opt_id in (answer.option_values or [])]
    if not option_ids:
        return "MULTI"
    options_result = await session.execute(select(Option).where(Option.id.in_(option_ids)))
    option_value_map = {opt.id: (opt.value or "").strip().upper() for opt in options_result.scalars().all()}

    office = 0
    personal = 0
    business = 0
    for answer in answers:
        for opt_id in answer.option_values or []:
            value = option_value_map.get(opt_id, "")
            if value == "A":
                office += 1
            elif value == "B":
                personal += 1
            elif value == "C":
                business += 1

    scores = {"OFFICE": office, "PERSONAL": personal, "BUSINESS": business}
    ordered = sorted(scores.values(), reverse=True)
    top = ordered[0] if ordered else 0
    second = ordered[1] if len(ordered) > 1 else 0

    if top >= 5 and (top - second) >= 2:
        for key, value in scores.items():
            if value == top:
                return key
    return "MULTI"


async def _send_result_pdf(bot: Bot, chat_id: int, result_type: str) -> None:
    filename = RESULT_PDFS.get(result_type, RESULT_PDFS["MULTI"])
    base_dir = Path(settings.ASSISTANT_TEST_PDF_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / filename
    if not path.exists():
        await bot.send_message(chat_id, "Файл пока не загружен. Напишите администратору.")
        return
    await bot.send_document(chat_id, FSInputFile(path))


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
