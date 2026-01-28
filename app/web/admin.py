from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BASE_DIR, settings
from app.db import AsyncSessionLocal
from app.models import Option, Question
from app.services.survey import get_active_survey, list_users

router = APIRouter(prefix="/admin")

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))


def require_admin(request: Request) -> str:
    token = request.query_params.get("token") or request.headers.get("X-Admin-Token")
    if settings.ADMIN_TOKEN and token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return token or ""


@router.get("/")
async def admin_index(request: Request, token: str = Depends(require_admin)):
    return RedirectResponse(url=f"/admin/questions?token={token}")


@router.get("/questions")
async def list_questions(request: Request, token: str = Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        survey = await get_active_survey(session)
        result = await session.execute(
            select(Question).where(Question.survey_id == survey.id).order_by(Question.order.asc())
        )
        questions = list(result.scalars().all())
    return templates.TemplateResponse(
        "questions.html",
        {
            "request": request,
            "questions": questions,
            "token": token,
            "survey": survey,
        },
    )


@router.get("/questions/{question_id}")
async def edit_question(request: Request, question_id: int, token: str = Depends(require_admin)):
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
        },
    )


@router.post("/questions/{question_id}")
async def update_question(request: Request, question_id: int, token: str = Depends(require_admin)):
    form = await request.form()

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

    return RedirectResponse(url=f"/admin/questions/{question_id}?token={token}", status_code=303)


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
