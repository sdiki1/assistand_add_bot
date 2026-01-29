from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    questions: Mapped[list[Question]] = relationship(
        "Question",
        back_populates="survey",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(32))  # text, contact, single_choice, multi_choice, file
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    allow_multiple: Mapped[bool] = mapped_column(Boolean, default=False)
    help_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    image_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_mime: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    survey: Mapped[Survey] = relationship("Survey", back_populates="questions")
    options: Mapped[list[Option]] = relationship(
        "Option",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="Option.order",
        lazy="selectin",
    )


class Option(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    text: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(String(255))
    order: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped[Question] = relationship("Question", back_populates="options")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    responses: Mapped[list[Response]] = relationship(
        "Response", back_populates="user", lazy="selectin"
    )


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_question_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    question_message_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    user_message_ids: Mapped[list[int]] = mapped_column(JSON, default=list)

    user: Mapped[User] = relationship("User", back_populates="responses")
    answers: Mapped[list[Answer]] = relationship(
        "Answer", back_populates="response", cascade="all, delete-orphan", lazy="selectin"
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    text_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    option_values: Mapped[list[int]] = mapped_column(JSON, default=list)
    file_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    response: Mapped[Response] = relationship("Response", back_populates="answers")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    tg_file_id: Mapped[str] = mapped_column(String(255))
    tg_unique_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    local_path: Mapped[str] = mapped_column(Text)
    public_url: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    response_id: Mapped[Optional[int]] = mapped_column(ForeignKey("responses.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    yk_payment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    confirmation_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    description: Mapped[str] = mapped_column(String(255))
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotence_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
