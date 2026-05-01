"""
models.py — Data models and database setup for GamePay Dev Sandbox.
Uses PostgreSQL (asyncpg) in production, SQLite (aiosqlite) for local dev.
Automatically detects which database to use based on DATABASE_URL env var.
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import asyncpg
    _pool: Optional[asyncpg.Pool] = None
else:
    import aiosqlite
    DB_PATH = "gamepaywh.db"


# ─── Pydantic request/response models ────────────────────────────────────────

class EndpointRegisterRequest(BaseModel):
    url: str
    description: Optional[str] = None


class EndpointResponse(BaseModel):
    endpoint_id: str
    url: str
    description: Optional[str]
    registered_at: str
    active: bool


class EventTriggerRequest(BaseModel):
    event_type: str
    player_id: str = "player_demo_001"
    game_id: str = "game_demo_001"
    amount: int = 1000
    endpoint_ids: Optional[list[str]] = None  # Changed from endpoint_id to endpoint_ids
    idempotency_key: Optional[str] = None


class EventResponse(BaseModel):
    event_id: str
    event_type: str
    payload: dict
    idempotency_key: str
    created_at: str
    status: str


class DeliveryResponse(BaseModel):
    delivery_id: str
    event_id: str
    endpoint_url: str
    status: str
    attempts: int
    last_response_code: Optional[int]
    last_attempt_at: Optional[str]
    next_retry_at: Optional[str]


class AssistantMessageRequest(BaseModel):
    message: str


class AssistantMessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str


# ─── Valid event types ────────────────────────────────────────────────────────

VALID_EVENT_TYPES = [
    "player_reward_earned",
    "tournament_prize_disbursed",
    "achievement_unlocked_payout",
    "in_game_purchase_completed",
    "referral_bonus_credited",
]


# ─── Payload builders ─────────────────────────────────────────────────────────

def build_payload(event_type: str, event_id: str, player_id: str,
                  game_id: str, amount: int, idempotency_key: str) -> dict:
    base = {
        "event_id": event_id,
        "event_type": event_type,
        "idempotency_key": idempotency_key,
        "game_id": game_id,
        "player_id": player_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "api_version": "2026-04",
    }

    if event_type == "player_reward_earned":
        base["reward"] = {
            "type": "bitcoin_satoshis",
            "amount": amount,
            "currency": "SAT",
            "reason": "level_completion",
            "level": 5,
        }

    elif event_type == "tournament_prize_disbursed":
        base["tournament_id"] = f"tournament_{uuid.uuid4().hex[:6]}"
        base["placement"] = 1
        base["prize"] = {"amount": amount, "currency": "SAT"}

    elif event_type == "achievement_unlocked_payout":
        base["achievement"] = {
            "id": "ach_speed_demon",
            "name": "Speed Demon",
            "description": "Complete level in under 60 seconds",
            "payout": {"amount": amount, "currency": "SAT"},
        }

    elif event_type == "in_game_purchase_completed":
        base["purchase"] = {
            "item_id": "item_powerup_001",
            "item_name": "Turbo Boost Pack",
            "quantity": 1,
            "amount": amount,
            "currency": "SAT",
        }

    elif event_type == "referral_bonus_credited":
        base["referral"] = {
            "referred_player_id": f"player_{uuid.uuid4().hex[:6]}",
            "bonus": {"amount": amount, "currency": "SAT"},
        }

    return base


# ─── Database setup and connection management ─────────────────────────────────

async def get_connection():
    """Get a database connection (PostgreSQL pool or SQLite)."""
    if USE_POSTGRES:
        global _pool
        if _pool is None:
            _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        return await _pool.acquire()
    else:
        return await aiosqlite.connect(DB_PATH)


async def release_connection(conn):
    """Release a database connection."""
    if USE_POSTGRES:
        await _pool.release(conn)
    else:
        await conn.close()


async def init_db():
    """Initialize database tables."""
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS endpoints (
                    endpoint_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    description TEXT,
                    registered_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    endpoint_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_response_code INTEGER,
                    last_attempt_at TEXT,
                    next_retry_at TEXT
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_receiver_log (
                    log_id TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL,
                    event_type TEXT,
                    event_id TEXT,
                    idempotency_key TEXT,
                    payload TEXT NOT NULL,
                    headers TEXT
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS assistant_history (
                    id SERIAL PRIMARY KEY,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS endpoints (
                    endpoint_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    description TEXT,
                    registered_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    endpoint_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_response_code INTEGER,
                    last_attempt_at TEXT,
                    next_retry_at TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS test_receiver_log (
                    log_id TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL,
                    event_type TEXT,
                    event_id TEXT,
                    idempotency_key TEXT,
                    payload TEXT NOT NULL,
                    headers TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS assistant_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            await db.commit()


# ─── Database helper functions ────────────────────────────────────────────────

async def get_all_endpoints(active_only: bool = False) -> list[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            query = "SELECT * FROM endpoints"
            if active_only:
                query += " WHERE active = 1"
            query += " ORDER BY registered_at DESC"
            rows = await conn.fetch(query)
            return [dict(r) for r in rows]
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if active_only:
                cursor = await db.execute(
                    "SELECT * FROM endpoints WHERE active = 1 ORDER BY registered_at DESC"
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM endpoints ORDER BY registered_at DESC"
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_endpoint_by_id(endpoint_id: str) -> Optional[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM endpoints WHERE endpoint_id = $1", endpoint_id
            )
            return dict(row) if row else None
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM endpoints WHERE endpoint_id = ?", (endpoint_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_events(limit: int = 50) -> list[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT $1", limit
            )
            result = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d["payload"])
                result.append(d)
            return result
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d["payload"])
                result.append(d)
            return result


async def get_event_by_id(event_id: str) -> Optional[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT * FROM events WHERE event_id = $1", event_id
            )
            if not row:
                return None
            d = dict(row)
            d["payload"] = json.loads(d["payload"])
            return d
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["payload"] = json.loads(d["payload"])
            return d


async def get_deliveries_for_event(event_id: str) -> list[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM deliveries WHERE event_id = $1 ORDER BY last_attempt_at DESC",
                event_id
            )
            return [dict(r) for r in rows]
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM deliveries WHERE event_id = ? ORDER BY last_attempt_at DESC",
                (event_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_deliveries(limit: int = 50) -> list[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM deliveries ORDER BY last_attempt_at DESC LIMIT $1", limit
            )
            return [dict(r) for r in rows]
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM deliveries ORDER BY last_attempt_at DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def idempotency_key_exists(key: str) -> bool:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            row = await conn.fetchrow(
                "SELECT event_id FROM events WHERE idempotency_key = $1", key
            )
            return row is not None
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT event_id FROM events WHERE idempotency_key = ?", (key,)
            )
            row = await cursor.fetchone()
            return row is not None


async def save_event(event_id: str, event_type: str, payload: dict,
                     idempotency_key: str) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO events (event_id, event_type, payload, idempotency_key,
                   created_at, status) VALUES ($1, $2, $3, $4, $5, $6)""",
                event_id, event_type, json.dumps(payload), idempotency_key,
                datetime.utcnow().isoformat(), "pending"
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO events (event_id, event_type, payload, idempotency_key,
                   created_at, status) VALUES (?, ?, ?, ?, ?, ?)""",
                (event_id, event_type, json.dumps(payload), idempotency_key,
                 datetime.utcnow().isoformat(), "pending")
            )
            await db.commit()


async def save_delivery(delivery_id: str, event_id: str, endpoint_id: str,
                        endpoint_url: str) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO deliveries (delivery_id, event_id, endpoint_id,
                   endpoint_url, status, attempts) VALUES ($1, $2, $3, $4, $5, $6)""",
                delivery_id, event_id, endpoint_id, endpoint_url, "pending", 0
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO deliveries (delivery_id, event_id, endpoint_id,
                   endpoint_url, status, attempts) VALUES (?, ?, ?, ?, ?, ?)""",
                (delivery_id, event_id, endpoint_id, endpoint_url, "pending", 0)
            )
            await db.commit()


async def update_delivery(delivery_id: str, status: str, attempts: int,
                          response_code: Optional[int],
                          next_retry_at: Optional[str] = None) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                """UPDATE deliveries SET status=$1, attempts=$2, last_response_code=$3,
                   last_attempt_at=$4, next_retry_at=$5 WHERE delivery_id=$6""",
                status, attempts, response_code, datetime.utcnow().isoformat(),
                next_retry_at, delivery_id
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE deliveries SET status=?, attempts=?, last_response_code=?,
                   last_attempt_at=?, next_retry_at=? WHERE delivery_id=?""",
                (status, attempts, response_code, datetime.utcnow().isoformat(),
                 next_retry_at, delivery_id)
            )
            await db.commit()


async def update_event_status(event_id: str, status: str) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                "UPDATE events SET status=$1 WHERE event_id=$2", status, event_id
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE events SET status=? WHERE event_id=?", (status, event_id)
            )
            await db.commit()


async def save_test_receiver_log(payload: dict, headers: dict) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO test_receiver_log (log_id, received_at, event_type,
                   event_id, idempotency_key, payload, headers)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                str(uuid.uuid4()), datetime.utcnow().isoformat(),
                payload.get("event_type"), payload.get("event_id"),
                payload.get("idempotency_key"), json.dumps(payload), json.dumps(headers)
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO test_receiver_log (log_id, received_at, event_type,
                   event_id, idempotency_key, payload, headers)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    datetime.utcnow().isoformat(),
                    payload.get("event_type"),
                    payload.get("event_id"),
                    payload.get("idempotency_key"),
                    json.dumps(payload),
                    json.dumps(headers),
                )
            )
            await db.commit()


async def get_test_receiver_log(limit: int = 20) -> list[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM test_receiver_log ORDER BY received_at DESC LIMIT $1",
                limit
            )
            result = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d["payload"])
                d["headers"] = json.loads(d["headers"])
                result.append(d)
            return result
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM test_receiver_log ORDER BY received_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d["payload"])
                d["headers"] = json.loads(d["headers"])
                result.append(d)
            return result


async def get_assistant_history(limit: int = 20) -> list[dict]:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            rows = await conn.fetch(
                "SELECT role, content, timestamp FROM assistant_history ORDER BY id DESC LIMIT $1",
                limit
            )
            return list(reversed([dict(r) for r in rows]))
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT role, content, timestamp FROM assistant_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return list(reversed([dict(r) for r in rows]))


async def save_assistant_message(role: str, content: str) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                "INSERT INTO assistant_history (role, content, timestamp) VALUES ($1, $2, $3)",
                role, content, datetime.utcnow().isoformat()
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO assistant_history (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, datetime.utcnow().isoformat())
            )
            await db.commit()


async def save_endpoint(endpoint_id: str, url: str, description: Optional[str],
                        registered_at: str) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                """INSERT INTO endpoints (endpoint_id, url, description,
                   registered_at, active) VALUES ($1, $2, $3, $4, 1)""",
                endpoint_id, url, description, registered_at
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO endpoints (endpoint_id, url, description,
                   registered_at, active) VALUES (?, ?, ?, ?, 1)""",
                (endpoint_id, url, description, registered_at)
            )
            await db.commit()


async def deactivate_endpoint(endpoint_id: str) -> None:
    if USE_POSTGRES:
        conn = await get_connection()
        try:
            await conn.execute(
                "UPDATE endpoints SET active=0 WHERE endpoint_id=$1", endpoint_id
            )
        finally:
            await release_connection(conn)
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE endpoints SET active=0 WHERE endpoint_id=?", (endpoint_id,)
            )
            await db.commit()
