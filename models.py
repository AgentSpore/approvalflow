from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class ReviewCreate(BaseModel):
    title: str
    description: str | None = None
    client_email: str
    file_url: str | None = None


class ReviewResponse(BaseModel):
    id: int
    title: str
    description: str | None
    client_email: str
    file_url: str | None
    status: str  # pending, approved, rejected, changes_requested
    token: str
    feedback: str | None
    created_at: str
    updated_at: str


class FeedbackSubmit(BaseModel):
    status: str  # approved | rejected | changes_requested
    feedback: str | None = None
