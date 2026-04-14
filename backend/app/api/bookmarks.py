from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.db import get_bookmarks, create_bookmark, delete_bookmark
from app.state import state

router = APIRouter()


class BookmarkCreate(BaseModel):
    doc_id: int
    page: int
    label: Optional[str] = None


@router.get("/bookmarks")
async def list_bookmarks(doc_id: int):
    return get_bookmarks(state.conn, doc_id)


@router.post("/bookmarks")
async def add_bookmark(body: BookmarkCreate):
    return create_bookmark(state.conn, body.doc_id, body.page, body.label)


@router.delete("/bookmarks/{bookmark_id:int}")
async def remove_bookmark(bookmark_id: int):
    delete_bookmark(state.conn, bookmark_id)
    return {"ok": True}
