from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.models import Option, Question


def build_single_choice_keyboard(question_id: int, options: list[Option]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(text=opt.text, callback_data=f"q{question_id}:opt{opt.id}")
    builder.adjust(1)
    return builder.as_markup()


def build_multi_choice_keyboard(question_id: int, options: list[Option], selected: set[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for opt in options:
        prefix = "✅ " if opt.id in selected else "▫️ "
        builder.button(text=f"{prefix}{opt.text}", callback_data=f"q{question_id}:opt{opt.id}")
    builder.button(text="Далее", callback_data=f"q{question_id}:done")
    builder.adjust(1)
    return builder.as_markup()


def build_file_keyboard(question_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Завершить загрузку", callback_data=f"q{question_id}:done_files")
    builder.adjust(1)
    return builder.as_markup()


def build_contact_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="Поделиться контактом", request_contact=True))
    builder.add(KeyboardButton(text="Ввести вручную"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)


def format_question_text(question: Question) -> str:
    if question.help_text:
        return f"<b>{question.text}</b>\n\n{question.help_text}"
    return f"<b>{question.text}</b>"
