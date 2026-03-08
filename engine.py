from __future__ import annotations

import secrets
from datetime import datetime, timezone

import aiosqlite

SQL_TABLES = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    client_email TEXT NOT NULL,
    file_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    token TEXT NOT NULL UNIQUE,
    feedback TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


async def init_db(path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.executescript(SQL_TABLES)
    await db.commit()
    return db


def _row(r: aiosqlite.Row) -> dict:
    return {k: r[k] for k in r.keys()}


async def create_review(db: aiosqlite.Connection, data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    token = secrets.token_urlsafe(16)
    cur = await db.execute(
        """INSERT INTO reviews (title, description, client_email, file_url, status, token, feedback, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'pending', ?, NULL, ?, ?)""",
        (data["title"], data.get("description"), data["client_email"],
         data.get("file_url"), token, now, now),
    )
    await db.commit()
    rows = await db.execute_fetchall("SELECT * FROM reviews WHERE id = ?", (cur.lastrowid,))
    return _row(rows[0])


async def list_reviews(db: aiosqlite.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = await db.execute_fetchall(
            "SELECT * FROM reviews WHERE status = ? ORDER BY created_at DESC", (status,)
        )
    else:
        rows = await db.execute_fetchall("SELECT * FROM reviews ORDER BY created_at DESC LIMIT 100")
    return [_row(r) for r in rows]


async def get_review_by_token(db: aiosqlite.Connection, token: str) -> dict | None:
    rows = await db.execute_fetchall("SELECT * FROM reviews WHERE token = ?", (token,))
    return _row(rows[0]) if rows else None


async def submit_feedback(db: aiosqlite.Connection, token: str, status: str, feedback: str | None) -> dict | None:
    valid = {"approved", "rejected", "changes_requested"}
    if status not in valid:
        raise ValueError(f"status must be one of {valid}")
    now = datetime.now(timezone.utc).isoformat()
    cur = await db.execute(
        "UPDATE reviews SET status = ?, feedback = ?, updated_at = ? WHERE token = ?",
        (status, feedback, now, token),
    )
    await db.commit()
    if cur.rowcount == 0:
        return None
    rows = await db.execute_fetchall("SELECT * FROM reviews WHERE token = ?", (token,))
    return _row(rows[0])


async def get_review(db: aiosqlite.Connection, review_id: int) -> dict | None:
    rows = await db.execute_fetchall("SELECT * FROM reviews WHERE id = ?", (review_id,))
    return _row(rows[0]) if rows else None


async def get_stats(db: aiosqlite.Connection) -> dict:
    rows = await db.execute_fetchall("SELECT status, COUNT(*) as cnt FROM reviews GROUP BY status")
    counts = {r["status"]: r["cnt"] for r in rows}
    total = sum(counts.values())
    approved = counts.get("approved", 0)
    rejected = counts.get("rejected", 0)
    changes = counts.get("changes_requested", 0)
    pending = counts.get("pending", 0)
    decided = approved + rejected + changes
    approval_rate = round(approved / decided * 100, 1) if decided else 0.0

    # Average turnaround for decided reviews (hours)
    decided_rows = await db.execute_fetchall(
        "SELECT created_at, updated_at FROM reviews WHERE status != 'pending'"
    )
    turnarounds = []
    for r in decided_rows:
        try:
            created = datetime.fromisoformat(r["created_at"])
            updated = datetime.fromisoformat(r["updated_at"])
            turnarounds.append((updated - created).total_seconds() / 3600)
        except Exception:
            pass
    avg_turnaround_hours = round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "changes_requested": changes,
        "approval_rate_pct": approval_rate,
        "avg_turnaround_hours": avg_turnaround_hours,
    }
