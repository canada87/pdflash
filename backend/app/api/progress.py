from __future__ import annotations
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.db import get_continue_reading, upsert_progress, get_doc_by_id
from app.state import state

router = APIRouter()


class ProgressUpdate(BaseModel):
    page: int


@router.get("/progress")
async def continue_reading(limit: int = 6):
    return get_continue_reading(state.conn, limit=limit)


@router.post("/progress/{doc_id:int}")
async def update_progress(doc_id: int, body: ProgressUpdate):
    doc = get_doc_by_id(state.conn, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    page = max(1, min(body.page, doc["page_count"]))
    upsert_progress(state.conn, doc_id, page)
    return {"ok": True}
