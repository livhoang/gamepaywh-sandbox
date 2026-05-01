"""
main.py — GamePay Dev Sandbox
FastAPI application with all API routes.

Endpoints:
  POST /endpoints                  Register webhook endpoint
  GET  /endpoints                  List endpoints
  DELETE /endpoints/{id}           Deactivate endpoint
  POST /events/trigger             Fire a gaming event (async delivery)
  GET  /events                     List recent events
  GET  /events/{event_id}          Event detail + delivery history
  POST /test-receiver              Built-in webhook receiver
  GET  /test-receiver/log          View received payloads
  POST /assistant                  AI assistant message
  GET  /assistant/history          Conversation history
  GET  /                           Serve frontend
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from models import (
    init_db,
    get_all_endpoints,
    get_endpoint_by_id,
    get_all_events,
    get_event_by_id,
    get_deliveries_for_event,
    get_test_receiver_log,
    get_assistant_history,
    idempotency_key_exists,
    save_event,
    save_test_receiver_log,
    save_endpoint,
    deactivate_endpoint,
    VALID_EVENT_TYPES,
    build_payload,
    EndpointRegisterRequest,
    EventTriggerRequest,
    AssistantMessageRequest,
)
from webhook_sender import fire_event
from ai_assistant import chat


# ─── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="GamePay Dev Sandbox",
    description="Webhook simulation platform for in-game Bitcoin payment events.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ─── Root — serve frontend ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_frontend():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/endpoints", status_code=status.HTTP_201_CREATED)
async def register_endpoint(body: EndpointRegisterRequest):
    """
    Register a webhook endpoint URL.
    GamePay will POST events to this URL on trigger.
    """
    # Basic URL validation
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="URL must start with http:// or https://"
        )

    endpoint_id = str(uuid.uuid4())
    registered_at = datetime.utcnow().isoformat()

    await save_endpoint(endpoint_id, str(body.url), body.description, registered_at)

    return {
        "endpoint_id": endpoint_id,
        "url": str(body.url),
        "description": body.description,
        "registered_at": registered_at,
        "active": True,
    }


@app.get("/endpoints", status_code=status.HTTP_200_OK)
async def list_endpoints():
    """List all registered webhook endpoints."""
    endpoints = await get_all_endpoints()
    return {"endpoints": endpoints, "total": len(endpoints)}


@app.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_200_OK)
async def deactivate_endpoint_route(endpoint_id: str):
    """Deactivate a webhook endpoint. It will no longer receive events."""
    ep = await get_endpoint_by_id(endpoint_id)
    if not ep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {endpoint_id} not found."
        )

    await deactivate_endpoint(endpoint_id)

    return {"endpoint_id": endpoint_id, "active": False, "message": "Endpoint deactivated."}


# ─── Events ───────────────────────────────────────────────────────────────────

@app.post("/events/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_event(body: EventTriggerRequest, background_tasks: BackgroundTasks):
    """
    Fire a simulated in-game payment event.

    Returns 202 Accepted immediately. Delivery happens asynchronously.
    Use GET /events/{event_id} to check delivery status.

    Returns 409 Conflict if the idempotency_key was already used.
    """
    # Validate event type
    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "Invalid event_type.",
                "valid_event_types": VALID_EVENT_TYPES,
            }
        )

    # Resolve endpoints
    if body.endpoint_ids:
        # User selected specific endpoints
        endpoints = []
        for ep_id in body.endpoint_ids:
            ep = await get_endpoint_by_id(ep_id)
            if not ep:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Endpoint {ep_id} not found."
                )
            if not ep["active"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Endpoint {ep_id} is inactive."
                )
            endpoints.append(ep)
    else:
        # Fire to all active endpoints
        endpoints = await get_all_endpoints(active_only=True)
        if not endpoints:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No active endpoints registered. Register one first."
            )

    # Idempotency check
    idempotency_key = body.idempotency_key or str(uuid.uuid4())
    if body.idempotency_key and await idempotency_key_exists(idempotency_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Duplicate idempotency_key.",
                "idempotency_key": idempotency_key,
                "message": "This event was already triggered. No delivery will occur.",
            }
        )

    # Build event
    event_id = str(uuid.uuid4())
    payload = build_payload(
        event_type=body.event_type,
        event_id=event_id,
        player_id=body.player_id,
        game_id=body.game_id,
        amount=body.amount,
        idempotency_key=idempotency_key,
    )

    await save_event(event_id, body.event_type, payload, idempotency_key)

    # Fire in background — do not block the response
    background_tasks.add_task(fire_event, event_id, payload, endpoints, idempotency_key)

    return {
        "event_id": event_id,
        "event_type": body.event_type,
        "idempotency_key": idempotency_key,
        "status": "pending",
        "endpoints_targeted": len(endpoints),
        "message": "Event accepted. Delivery is in progress. Use GET /events/{event_id} to check status.",
        "payload_preview": payload,
    }


@app.get("/events", status_code=status.HTTP_200_OK)
async def list_events():
    """List the 50 most recent events with their delivery status."""
    events = await get_all_events(limit=50)
    return {"events": events, "total": len(events)}


@app.get("/events/{event_id}", status_code=status.HTTP_200_OK)
async def get_event(event_id: str):
    """
    Get full details for a single event including all delivery attempts.
    Use this to debug why a webhook was not received.
    """
    event = await get_event_by_id(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found."
        )

    deliveries = await get_deliveries_for_event(event_id)

    return {
        "event": event,
        "deliveries": deliveries,
        "delivery_count": len(deliveries),
    }


# ─── Built-in test receiver ───────────────────────────────────────────────────

@app.post("/test-receiver", status_code=status.HTTP_200_OK)
async def test_receiver(request: Request):
    """
    Built-in webhook receiver for testing.
    Register http://localhost:8000/test-receiver as your endpoint
    to see payloads without needing an external server.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": await request.body().decode()}

    headers = dict(request.headers)
    # Strip internal headers
    for key in ["host", "content-length", "connection"]:
        headers.pop(key, None)

    await save_test_receiver_log(payload, headers)

    return {
        "received": True,
        "event_id": payload.get("event_id"),
        "event_type": payload.get("event_type"),
        "idempotency_key": payload.get("idempotency_key"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/test-receiver/log", status_code=status.HTTP_200_OK)
async def get_test_receiver_logs():
    """View the last 20 payloads received by the built-in test receiver."""
    logs = await get_test_receiver_log(limit=20)
    return {"logs": logs, "total": len(logs)}


# ─── AI Assistant ─────────────────────────────────────────────────────────────

@app.post("/assistant", status_code=status.HTTP_200_OK)
async def assistant_chat(body: AssistantMessageRequest):
    """
    Ask the AI assistant a question about your webhook integration.

    Example questions:
    - "Why did my webhook fail?"
    - "Show me the payload for tournament_prize_disbursed"
    - "How do I verify the webhook signature in Node.js?"
    - "What events should I handle for a rewards system?"
    """
    if not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty."
        )

    reply = await chat(body.message.strip())
    return {
        "role": "assistant",
        "content": reply,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/assistant/history", status_code=status.HTTP_200_OK)
async def get_assistant_conversation():
    """Get the full conversation history with the AI assistant."""
    history = await get_assistant_history(limit=50)
    return {"history": history, "total": len(history)}
