from __future__ import annotations

import os
import re
from pathlib import Path
from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR, QUESTION_IMAGES_DIR, settings
from app.db import AsyncSessionLocal
from app.models import Option, Question
from app.services.survey import get_active_survey, get_survey_by_code, list_surveys, list_users

router = APIRouter(prefix="/admin")

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))


def _safe_filename(value: str) -> str:
    value = value.strip().replace(" ", "_")
    value = re.sub(r"[^a-zA-Z0-9_.-]", "", value)
    return value or "image"


def require_admin(request: Request) -> str:
    token = request.query_params.get("token") or request.headers.get("X-Admin-Token")
    if settings.ADMIN_TOKEN and token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return token or ""


@router.get("/")
async def admin_index(request: Request, token: str = Depends(require_admin)):
    return RedirectResponse(url=f"/admin/surveys?token={token}")


@router.get("/surveys")
async def list_surveys_page(request: Request, token: str = Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        surveys = await list_surveys(session)
    return templates.TemplateResponse(
        "surveys.html",
        {
            "request": request,
            "surveys": surveys,
            "token": token,
        },
    )


@router.get("/assistant-test-files")
async def assistant_test_files(request: Request, token: str = Depends(require_admin)):
    base_dir = Path(settings.ASSISTANT_TEST_PDF_DIR)
    files = {
        "OFFICE": base_dir / "office_assistant.pdf",
        "PERSONAL": base_dir / "personal_assistant.pdf",
        "BUSINESS": base_dir / "business_assistant.pdf",
        "MULTI": base_dir / "multi_assistant.pdf",
    }
    statuses = {key: path.exists() for key, path in files.items()}
    return templates.TemplateResponse(
        "assistant_test_files.html",
        {
            "request": request,
            "token": token,
            "files": files,
            "statuses": statuses,
        },
    )


@router.post("/assistant-test-files")
async def assistant_test_files_upload(request: Request, token: str = Depends(require_admin)):
    form = await request.form()
    base_dir = Path(settings.ASSISTANT_TEST_PDF_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)

    mapping = {
        "office": "office_assistant.pdf",
        "personal": "personal_assistant.pdf",
        "business": "business_assistant.pdf",
        "multi": "multi_assistant.pdf",
    }

    for field, filename in mapping.items():
        upload = form.get(field)
        if upload is None or not getattr(upload, "filename", None):
            continue
        if not str(upload.filename).lower().endswith(".pdf"):
            continue
        content = await upload.read()
        target_path = base_dir / filename
        with target_path.open("wb") as f:
            f.write(content)

    return RedirectResponse(url=f"/admin/assistant-test-files?token={token}", status_code=303)


@router.get("/questions")
async def list_questions(request: Request, token: str = Depends(require_admin)):
    survey_code = request.query_params.get("survey_code")
    async with AsyncSessionLocal() as session:
        if survey_code:
            survey = await get_survey_by_code(session, survey_code)
        else:
            survey = await get_active_survey(session)
        result = await session.execute(
            select(Question).where(Question.survey_id == survey.id).order_by(Question.order.asc())
        )
        questions = list(result.scalars().all())
        surveys = await list_surveys(session)
    return templates.TemplateResponse(
        "questions.html",
        {
            "request": request,
            "questions": questions,
            "token": token,
            "survey": survey,
            "surveys": surveys,
            "survey_code": survey_code or survey.code,
        },
    )


@router.get("/questions/{question_id}")
async def edit_question(request: Request, question_id: int, token: str = Depends(require_admin)):
    survey_code = request.query_params.get("survey_code")
    async with AsyncSessionLocal() as session:
        question = await session.get(Question, question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        await session.refresh(question)
    return templates.TemplateResponse(
        "question_edit.html",
        {
            "request": request,
            "question": question,
            "token": token,
            "survey_code": survey_code,
        },
    )


@router.post("/questions/{question_id}")
async def update_question(request: Request, question_id: int, token: str = Depends(require_admin)):
    form = await request.form()
    survey_code = request.query_params.get("survey_code")

    async with AsyncSessionLocal() as session:
        question = await session.get(Question, question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        question.text = str(form.get("text", question.text)).strip()
        question.code = str(form.get("code", question.code)).strip() or question.code
        question.type = str(form.get("type", question.type))
        question.required = "required" in form
        question.allow_multiple = "allow_multiple" in form
        question.order = int(form.get("order", question.order) or question.order)
        question.help_text = str(form.get("help_text", "")).strip() or None

        if "remove_image" in form:
            if question.image_path and os.path.exists(question.image_path):
                with suppress(Exception):
                    os.remove(question.image_path)
            question.image_path = None
            question.image_name = None
            question.image_mime = None

        upload = form.get("image")
        if upload is not None and getattr(upload, "filename", None):
            QUESTION_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = _safe_filename(upload.filename)
            target_path = QUESTION_IMAGES_DIR / f"q{question.id}_{safe_name}"
            content = await upload.read()
            with target_path.open("wb") as f:
                f.write(content)
            question.image_path = str(target_path)
            question.image_name = safe_name
            question.image_mime = getattr(upload, "content_type", None)

        for opt in question.options:
            text = form.get(f"opt_{opt.id}_text")
            value = form.get(f"opt_{opt.id}_value")
            order = form.get(f"opt_{opt.id}_order")
            if text is not None:
                opt.text = str(text).strip()
            if value is not None:
                opt.value = str(value).strip()
            if order is not None and str(order).strip().isdigit():
                opt.order = int(order)

        new_text = str(form.get("new_opt_text", "")).strip()
        new_value = str(form.get("new_opt_value", "")).strip()
        new_order = form.get("new_opt_order")
        if new_text:
            option = Option(
                question_id=question.id,
                text=new_text,
                value=new_value or new_text,
                order=int(new_order) if str(new_order).strip().isdigit() else 0,
            )
            session.add(option)

        await session.commit()

    redirect_url = f"/admin/questions/{question_id}?token={token}"
    if survey_code:
        redirect_url = f"{redirect_url}&survey_code={survey_code}"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/question-image/{question_id}")
async def question_image(question_id: int, token: str = Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        question = await session.get(Question, question_id)
        if not question or not question.image_path:
            raise HTTPException(status_code=404, detail="Image not found")
        if not os.path.exists(question.image_path):
            raise HTTPException(status_code=404, detail="Image missing")

    return FileResponse(
        path=question.image_path,
        media_type=question.image_mime,
        filename=question.image_name,
    )


@router.get("/users")
async def users_list(request: Request, token: str = Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        users = await list_users(session)
    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": users,
            "token": token,
        },
    )
