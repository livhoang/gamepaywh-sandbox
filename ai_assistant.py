"""
ai_assistant.py — AI integration assistant powered by GLM-4.5 Air via OpenRouter.

The assistant has access to:
- Live event log (last 10 events)
- Live delivery log (last 10 deliveries)
- Registered endpoints
- Full API schema summary
- Conversation history

It helps developers debug webhook integrations in plain language.
"""

import os
import json
from datetime import datetime

import httpx
from dotenv import load_dotenv

from models import (
    get_all_events,
    get_all_deliveries,
    get_all_endpoints,
    get_assistant_history,
    save_assistant_message,
)

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "z-ai/glm-4.5-air:free"

API_SCHEMA_SUMMARY = """
GamePay Dev Sandbox API — Schema Summary
=========================================

ENDPOINTS
POST /endpoints                 Register a new webhook endpoint URL
GET  /endpoints                 List all registered endpoints
DELETE /endpoints/{endpoint_id} Deactivate an endpoint

EVENTS
POST /events/trigger            Fire a simulated gaming event
  Body: { event_type, player_id, game_id, amount, endpoint_id (optional), idempotency_key (optional) }
  Valid event_types:
    - player_reward_earned          Player earns SAT reward for in-game achievement
    - tournament_prize_disbursed    Tournament placement prize payout
    - achievement_unlocked_payout   Achievement badge with SAT reward
    - in_game_purchase_completed    In-game item purchase settled
    - referral_bonus_credited       Referral program bonus credited
  Returns: 202 Accepted — delivery is async

GET  /events                    List recent events with status
GET  /events/{event_id}         Inspect event + full delivery history

DELIVERY STATUS VALUES
  pending     Not yet attempted
  retrying    Previous attempt failed, retry scheduled
  delivered   At least one successful 2xx response received
  failed      All 5 retry attempts exhausted with no 2xx

RETRY SCHEDULE (exponential backoff)
  Attempt 1: immediate
  Attempt 2: 5 seconds
  Attempt 3: 30 seconds
  Attempt 4: 2 minutes
  Attempt 5: 5 minutes → final, marked failed if no 2xx

WEBHOOK REQUEST HEADERS (sent on every delivery attempt)
  Content-Type:                    application/json
  X-GamePay-Event:                 <event_type>
  X-GamePay-Delivery-ID:          <uuid>
  X-GamePay-Signature:            sha256=<hmac_sha256_hex>
  X-GamePay-Idempotency-Key:      <key>
  X-GamePay-API-Version:          2026-04

IDEMPOTENCY
  If you trigger an event with the same idempotency_key twice,
  the second request returns 409 Conflict — no duplicate delivery.
  Auto-generated if not provided.

SIGNATURE VERIFICATION (Python example)
  import hmac, hashlib, json

  def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
      secret = "your_webhook_secret"
      expected = "sha256=" + hmac.new(
          secret.encode(), payload_bytes, hashlib.sha256
      ).hexdigest()
      return hmac.compare_digest(expected, signature_header)

BUILT-IN TEST RECEIVER
POST /test-receiver             Receives and logs any webhook POST
GET  /test-receiver/log         View last 20 received payloads

ASSISTANT
POST /assistant                 Send a message: { "message": "..." }
GET  /assistant/history         Get conversation history
"""


async def build_system_prompt() -> str:
    """Build a dynamic system prompt with live context from the database."""
    events = await get_all_events(limit=10)
    deliveries = await get_all_deliveries(limit=10)
    endpoints = await get_all_endpoints()

    events_summary = json.dumps(
        [{
            "event_id": e["event_id"][:8] + "...",
            "event_type": e["event_type"],
            "status": e["status"],
            "created_at": e["created_at"],
            "idempotency_key": e["idempotency_key"][:12] + "...",
        } for e in events],
        indent=2
    ) if events else "No events yet."

    deliveries_summary = json.dumps(
        [{
            "delivery_id": d["delivery_id"][:8] + "...",
            "event_id": d["event_id"][:8] + "...",
            "endpoint_url": d["endpoint_url"],
            "status": d["status"],
            "attempts": d["attempts"],
            "last_response_code": d["last_response_code"],
            "last_attempt_at": d["last_attempt_at"],
        } for d in deliveries],
        indent=2
    ) if deliveries else "No deliveries yet."

    endpoints_summary = json.dumps(
        [{
            "endpoint_id": ep["endpoint_id"][:8] + "...",
            "url": ep["url"],
            "active": bool(ep["active"]),
        } for ep in endpoints],
        indent=2
    ) if endpoints else "No endpoints registered yet."

    return f"""You are a developer integration assistant for GamePay Dev Sandbox, \
a webhook simulation platform for in-game Bitcoin (SAT) payment events.

You help game developers integrate webhooks into their games by:
- Debugging delivery failures based on actual event and delivery logs
- Explaining payload schemas for each event type
- Explaining how idempotency keys prevent duplicate processing
- Showing how to verify HMAC-SHA256 signatures
- Recommending which event types to handle for different use cases

Be concise, specific, and developer-friendly. Reference actual data from the \
logs when relevant. Format code examples in markdown code blocks.

--- CURRENT REGISTERED ENDPOINTS ---
{endpoints_summary}

--- RECENT EVENT LOG (last 10) ---
{events_summary}

--- RECENT DELIVERY LOG (last 10) ---
{deliveries_summary}

--- API SCHEMA ---
{API_SCHEMA_SUMMARY}

Current time (UTC): {datetime.utcnow().isoformat()}Z
"""


async def chat(user_message: str) -> str:
    """
    Send a message to the assistant and return the response.
    Maintains conversation history in SQLite.
    """
    if not OPENROUTER_API_KEY:
        return (
            "OPENROUTER_API_KEY is not set. Add it to your .env file to use "
            "the AI assistant. See .env.example for instructions."
        )

    # Save user message
    await save_assistant_message("user", user_message)

    # Build conversation payload
    history = await get_assistant_history(limit=20)
    system_prompt = await build_system_prompt()

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://gamepaywh-sandbox.onrender.com",
                    "X-Title": "GamePay Dev Sandbox",
                },
                json={
                    "model": MODEL,
                    "messages": messages,
                    "max_tokens": 600,
                    "temperature": 0.3,
                    "reasoning": {"enabled": False},  # non-thinking mode for speed
                },
            )
            response.raise_for_status()
            data = response.json()
            assistant_reply = data["choices"][0]["message"]["content"]

    except httpx.HTTPStatusError as e:
        assistant_reply = (
            f"OpenRouter API error {e.response.status_code}: "
            f"{e.response.text[:200]}"
        )
    except Exception as e:
        assistant_reply = f"Assistant error: {str(e)}"

    # Save assistant reply
    await save_assistant_message("assistant", assistant_reply)
    return assistant_reply
