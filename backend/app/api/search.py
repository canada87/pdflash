from __future__ import annotations
from fastapi import APIRouter, HTTPException

from app.db import search_fts
from app.state import state

router = APIRouter()


@router.get("/search")
async def search(q: str, doc_id: int = None, limit: int = 50):
    if not q or not q.strip():
        raise HTTPException(400, "Query cannot be empty")
    try:
        results = search_fts(state.conn, q.strip(), doc_id=doc_id, limit=limit)
    except Exception:
        # FTS5 syntax error (e.g. unmatched quotes) — return empty rather than 500
        results = []
    return results
