from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from models import ReviewCreate, ReviewResponse, FeedbackSubmit
from engine import init_db, create_review, list_reviews, get_review, get_review_by_token, submit_feedback, get_stats, update_review, list_overdue_reviews

DB_PATH = "approvalflow.db"


class ReviewUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[str] = None
    asset_url: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await init_db(DB_PATH)
    yield
    await app.state.db.close()


app = FastAPI(
    title="ApprovalFlow",
    description=(
        "Client approval workflow for agencies. "
        "Create a review request, share a unique link with the client. "
        "Client approves, rejects, or requests changes — all in one place."
    ),
    version="0.4.0",
    lifespan=lifespan,
)


@app.post("/reviews", response_model=ReviewResponse, status_code=201)
async def create(body: ReviewCreate):
    """Create a new review request with a unique client token."""
    return await create_review(app.state.db, body.model_dump())




@app.get("/reviews/overdue", response_model=list[ReviewResponse])
async def overdue_reviews():
    """
    List pending reviews whose deadline has already passed.
    Use this to trigger follow-up emails or escalation workflows.
    """
    return await list_overdue_reviews(app.state.db)

@app.get("/reviews", response_model=list[ReviewResponse])
async def index(
    status: str | None = Query(None, description="Filter: pending, approved, rejected, changes_requested"),
):
    """List all review requests for the agency dashboard."""
    return await list_reviews(app.state.db, status)


@app.get("/reviews/{review_id}", response_model=ReviewResponse)
async def detail(review_id: int):
    """Get a single review request by ID."""
    r = await get_review(app.state.db, review_id)
    if not r:
        raise HTTPException(404, "Review not found")
    return r


@app.patch("/reviews/{review_id}", response_model=ReviewResponse)
async def patch_review(review_id: int, body: ReviewUpdate):
    """Update a pending review (title, description, deadline, asset_url). Blocked once client responds."""
    try:
        r = await update_review(app.state.db, review_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not r:
        raise HTTPException(404, "Review not found")
    return r


@app.get("/review/{token}", response_model=ReviewResponse)
async def client_view(token: str):
    """Public — client opens their unique approval link (no auth required)."""
    r = await get_review_by_token(app.state.db, token)
    if not r:
        raise HTTPException(404, "Review link not found or expired")
    return r


@app.post("/review/{token}/feedback", response_model=ReviewResponse)
async def client_feedback(token: str, body: FeedbackSubmit):
    """Client submits decision: approved / rejected / changes_requested."""
    try:
        r = await submit_feedback(app.state.db, token, body.status, body.feedback)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not r:
        raise HTTPException(404, "Review link not found")
    return r


@app.get("/stats")
async def stats():
    """Agency stats: total reviews, approval rate %, avg turnaround hours."""
    return await get_stats(app.state.db)
