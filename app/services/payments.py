from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Payment


async def get_latest_payment(
    session: AsyncSession, user_id: int, response_id: int | None
) -> Optional[Payment]:
    stmt = select(Payment).where(Payment.user_id == user_id)
    if response_id is not None:
        stmt = stmt.where(Payment.response_id == response_id)
    stmt = stmt.order_by(Payment.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_pending_email_payment(session: AsyncSession, user_id: int) -> Optional[Payment]:
    result = await session.execute(
        select(Payment)
        .where(Payment.user_id == user_id)
        .where(Payment.status == "awaiting_email")
        .order_by(Payment.created_at.desc())
    )
    return result.scalars().first()


async def create_payment_record(
    session: AsyncSession, user_id: int, response_id: int | None
) -> Payment:
    payment = Payment(
        user_id=user_id,
        response_id=response_id,
        status="awaiting_email",
        amount=settings.YOOKASSA_AMOUNT,
        currency=settings.YOOKASSA_CURRENCY,
        description=settings.YOOKASSA_DESCRIPTION,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def set_payment_email(session: AsyncSession, payment_id: int, email: str) -> Payment:
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise RuntimeError("Payment not found")
    payment.customer_email = email
    await session.commit()
    await session.refresh(payment)
    return payment


async def set_gateway_data(
    session: AsyncSession,
    payment_id: int,
    yk_payment_id: str,
    confirmation_url: str | None,
    idempotence_key: str | None,
    status: str,
) -> Payment:
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise RuntimeError("Payment not found")
    payment.yk_payment_id = yk_payment_id
    payment.confirmation_url = confirmation_url
    payment.idempotence_key = idempotence_key
    payment.status = status
    await session.commit()
    await session.refresh(payment)
    return payment


async def update_payment_status(session: AsyncSession, yk_payment_id: str, status: str) -> Optional[Payment]:
    result = await session.execute(select(Payment).where(Payment.yk_payment_id == yk_payment_id))
    payment = result.scalars().first()
    if not payment:
        return None
    payment.status = status
    if status == "succeeded":
        payment.paid_at = datetime.utcnow()
    await session.commit()
    await session.refresh(payment)
    return payment
