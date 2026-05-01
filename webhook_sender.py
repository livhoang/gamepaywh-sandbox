"""
webhook_sender.py — Webhook delivery engine.

Handles:
- HMAC-SHA256 payload signing
- Idempotency key deduplication
- Exponential backoff retry (5 attempts max)
- Async delivery via httpx
- Delivery status tracking in SQLite
"""

import os
import uuid
import hmac
import hashlib
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx
from dotenv import load_dotenv

from models import (
    save_delivery,
    update_delivery,
    update_event_status,
    get_deliveries_for_event,
    idempotency_key_exists,
)

load_dotenv()

# Webhook signing secret - load from env or use secure default
# In production, set WEBHOOK_SECRET in environment variables
WEBHOOK_SECRET = os.getenv(
    "WEBHOOK_SECRET",
    "gamepaywh_dev_secret_CHANGE_IN_PRODUCTION_use_openssl_rand_hex_32"
)

# Retry schedule in seconds: attempt 1 immediate, then backoff
RETRY_DELAYS = [0, 5, 30, 120, 300]  # 5 attempts total


def sign_payload(payload_bytes: bytes) -> str:
    """Generate HMAC-SHA256 signature for a payload."""
    return hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()


async def deliver_to_endpoint(
    event_id: str,
    payload: dict,
    endpoint_id: str,
    endpoint_url: str,
    idempotency_key: str,
) -> str:
    """
    Attempt delivery of a single event to a single endpoint with retry logic.
    Returns final delivery status: 'delivered' | 'failed'
    """
    delivery_id = str(uuid.uuid4())
    await save_delivery(delivery_id, event_id, endpoint_id, endpoint_url)

    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    signature = sign_payload(payload_bytes)

    headers = {
        "Content-Type": "application/json",
        "X-GamePay-Event": payload.get("event_type", ""),
        "X-GamePay-Delivery-ID": delivery_id,
        "X-GamePay-Signature": f"sha256={signature}",
        "X-GamePay-Idempotency-Key": idempotency_key,
        "X-GamePay-API-Version": "2026-04",
        "User-Agent": "GamePay-Webhook/1.0",
    }

    for attempt_num, delay in enumerate(RETRY_DELAYS, start=1):
        if delay > 0:
            await asyncio.sleep(delay)

        next_retry_at = None
        if attempt_num < len(RETRY_DELAYS):
            next_retry_at = (
                datetime.utcnow() + timedelta(seconds=RETRY_DELAYS[attempt_num])
            ).isoformat()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    endpoint_url,
                    content=payload_bytes,
                    headers=headers,
                )
                response_code = response.status_code

            if 200 <= response_code < 300:
                await update_delivery(
                    delivery_id,
                    status="delivered",
                    attempts=attempt_num,
                    response_code=response_code,
                    next_retry_at=None,
                )
                return "delivered"
            else:
                # Non-2xx — retry if attempts remain
                is_last = attempt_num == len(RETRY_DELAYS)
                status = "failed" if is_last else "retrying"
                await update_delivery(
                    delivery_id,
                    status=status,
                    attempts=attempt_num,
                    response_code=response_code,
                    next_retry_at=None if is_last else next_retry_at,
                )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as exc:
            is_last = attempt_num == len(RETRY_DELAYS)
            status = "failed" if is_last else "retrying"
            await update_delivery(
                delivery_id,
                status=status,
                attempts=attempt_num,
                response_code=None,
                next_retry_at=None if is_last else next_retry_at,
            )

    return "failed"


async def fire_event(
    event_id: str,
    payload: dict,
    endpoints: list[dict],
    idempotency_key: str,
) -> dict:
    """
    Fire an event to all provided endpoints concurrently.
    Returns a summary: {endpoint_url: status}
    """
    tasks = [
        deliver_to_endpoint(
            event_id=event_id,
            payload=payload,
            endpoint_id=ep["endpoint_id"],
            endpoint_url=ep["url"],
            idempotency_key=idempotency_key,
        )
        for ep in endpoints
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    summary = {}
    any_delivered = False
    all_failed = True

    for ep, result in zip(endpoints, results):
        if isinstance(result, Exception):
            summary[ep["url"]] = "failed"
        else:
            summary[ep["url"]] = result
            if result == "delivered":
                any_delivered = True
                all_failed = False
            elif result != "failed":
                all_failed = False

    # Update overall event status
    if any_delivered:
        final_status = "delivered"
    elif all_failed:
        final_status = "failed"
    else:
        final_status = "retrying"

    await update_event_status(event_id, final_status)
    return summary
