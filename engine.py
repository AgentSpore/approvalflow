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
    # Migrate: add reminder tracking columns if not present
    for col_sql in [
        "ALTER TABLE reviews ADD COLUMN remind_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE reviews ADD COLUMN last_reminded_at TEXT",
        "ALTER TABLE reviews ADD COLUMN requester_email TEXT",
        "ALTER TABLE reviews ADD COLUMN deadline TEXT",
        "ALTER TABLE reviews ADD COLUMN asset_url TEXT",
    ]:
        try:
            await db.execute(col_sql)
        except Exception:
            pass  # column already exists
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

async def update_review(db: aiosqlite.Connection, review_id: int, updates: dict) -> dict | None:
    """Update review title/description/deadline if still pending."""
    rows = await db.execute_fetchall("SELECT * FROM reviews WHERE id = ?", (review_id,))
    if not rows:
        return None
    r = rows[0]
    if r["status"] \!= "pending":
        raise ValueError("Cannot edit a review that has already been decided")
    allowed = {"title", "description", "deadline", "asset_url"}
    fields = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not fields:
        return _row(r)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    await db.execute(
        f"UPDATE reviews SET {set_clause} WHERE id = ?",
        list(fields.values()) + [review_id],
    )
    await db.commit()
    updated = await db.execute_fetchall("SELECT * FROM reviews WHERE id = ?", (review_id,))
    return _row(updated[0]) if updated else None



async def list_overdue_reviews(db: aiosqlite.Connection) -> list[dict]:
    """Return pending reviews whose deadline has passed (overdue for client response)."""
    today = datetime.utcnow().date().isoformat()
    rows = await db.execute_fetchall(
        "SELECT * FROM reviews WHERE status = 'pending' AND deadline IS NOT NULL AND deadline < ? ORDER BY deadline ASC",
        (today,),
    )
    return [_row(r) for r in rows]


async def export_reviews_csv(db: aiosqlite.Connection, status: str | None = None) -> str:
    """Export reviews to CSV. Optionally filter by status."""
    import csv, io
    q = "SELECT * FROM reviews ORDER BY created_at DESC"
    params: list = []
    if status:
        q = "SELECT * FROM reviews WHERE status = ? ORDER BY created_at DESC"
        params = [status]
    rows = await db.execute_fetchall(q, params)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "title", "description", "requester_email", "client_email",
        "status", "deadline", "feedback", "asset_url", "token", "created_at", "updated_at"
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["title"], r["description"] or "",
            r["requester_email"] or "", r["client_email"] or "",
            r["status"], r["deadline"] or "", r["feedback"] or "",
            r["asset_url"] or "", r["token"] or "",
            r["created_at"], r.get("updated_at") or "",
        ])
    return buf.getvalue()


async def send_reminder(db: aiosqlite.Connection, review_id: int) -> dict | None:
    """
    Mock-send a reminder email to the client for a pending/overdue review.
    Increments remind_count and updates last_reminded_at.
    In production: wire to SendGrid/Resend with the review URL containing the token.
    """
    rows = await db.execute_fetchall("SELECT * FROM reviews WHERE id = ?", (review_id,))
    if not rows:
        return None
    review = rows[0]
    if review["status"] not in ("pending",):
        # Only remind on pending reviews
        return _row(review)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    # Mock: log reminder; in production send email here
    # e.g. send_email(to=review["client_email"], subject=f"Reminder: {review['title']} awaiting approval",
    #                 body=f"Please review: https://app.approvalflow.io/review/{review['token']}")
    await db.execute(
        """UPDATE reviews
           SET remind_count = COALESCE(remind_count, 0) + 1, last_reminded_at = ?, updated_at = ?
           WHERE id = ?""",
        (now, now, review_id),
    )
    await db.commit()
    rows2 = await db.execute_fetchall("SELECT * FROM reviews WHERE id = ?", (review_id,))
    return _row(rows2[0]) if rows2 else None
