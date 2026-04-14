from __future__ import annotations
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.db import get_all_tags, create_tag, delete_tag, add_doc_tag, remove_doc_tag
from app.state import state

router = APIRouter()


class TagCreate(BaseModel):
    name: str


@router.get("/tags")
async def list_tags():
    return get_all_tags(state.conn)


@router.post("/tags")
async def new_tag(body: TagCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Tag name cannot be empty")
    return create_tag(state.conn, name)


@router.delete("/tags/{tag_id:int}")
async def remove_tag(tag_id: int):
    delete_tag(state.conn, tag_id)
    return {"ok": True}


@router.post("/docs/{doc_id:int}/tags/{tag_id:int}")
async def attach_tag(doc_id: int, tag_id: int):
    add_doc_tag(state.conn, doc_id, tag_id)
    return {"ok": True}


@router.delete("/docs/{doc_id:int}/tags/{tag_id:int}")
async def detach_tag(doc_id: int, tag_id: int):
    remove_doc_tag(state.conn, doc_id, tag_id)
    return {"ok": True}
