from __future__ import annotations

import uuid

import httpx

from app.config import settings

API_BASE = "https://api.yookassa.ru/v3"


def yookassa_enabled() -> bool:
    return bool(
        settings.YOOKASSA_SHOP_ID
        and settings.YOOKASSA_SECRET_KEY
        and settings.YOOKASSA_AMOUNT
        and settings.YOOKASSA_RETURN_URL
    )


def _build_receipt(email: str) -> dict:
    return {
        "tax_system_code": settings.YOOKASSA_TAX_SYSTEM_CODE,
        "customer": {
            "email": email,
        },
        "items": [
            {
                "description": settings.YOOKASSA_DESCRIPTION,
                "quantity": "1.00",
                "amount": {
                    "value": settings.YOOKASSA_AMOUNT,
                    "currency": settings.YOOKASSA_CURRENCY,
                },
                "vat_code": settings.YOOKASSA_VAT_CODE,
                "payment_mode": settings.YOOKASSA_PAYMENT_MODE,
                "payment_subject": settings.YOOKASSA_PAYMENT_SUBJECT,
            }
        ],
    }


async def create_payment(email: str, response_id: int | None, user_id: int) -> tuple[dict, str]:
    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {
            "value": settings.YOOKASSA_AMOUNT,
            "currency": settings.YOOKASSA_CURRENCY,
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": settings.YOOKASSA_RETURN_URL,
        },
        "description": settings.YOOKASSA_DESCRIPTION,
        "receipt": _build_receipt(email),
        "metadata": {
            "response_id": str(response_id or ""),
            "user_id": str(user_id),
        },
    }
    headers = {"Idempotence-Key": idempotence_key}

    async with httpx.AsyncClient(auth=(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)) as client:
        response = await client.post(f"{API_BASE}/payments", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    return data, idempotence_key


async def fetch_payment(payment_id: str) -> dict:
    async with httpx.AsyncClient(auth=(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)) as client:
        response = await client.get(f"{API_BASE}/payments/{payment_id}")
        response.raise_for_status()
        return response.json()
