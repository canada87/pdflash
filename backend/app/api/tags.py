from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.db import get_all_tags, create_tag, update_tag, delete_tag, add_doc_tag, remove_doc_tag
from app.state import state

router = APIRouter()


class TagCreate(BaseModel):
    name: str
    color: str = "#6b7280"
    parent_id: Optional[int] = None


class TagUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    parent_id: Optional[int] = None  # send null to clear parent


@router.get("/tags")
async def list_tags():
    return get_all_tags(state.conn)


@router.post("/tags")
async def new_tag(body: TagCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Tag name cannot be empty")
    return create_tag(state.conn, name, color=body.color, parent_id=body.parent_id)


@router.patch("/tags/{tag_id:int}")
async def edit_tag(tag_id: int, body: TagUpdate):
    fs = body.model_fields_set
    kwargs = {}
    if "name" in fs:
        name = (body.name or "").strip()
        if not name:
            raise HTTPException(400, "Tag name cannot be empty")
        kwargs["name"] = name
    if "color" in fs:
        kwargs["color"] = body.color
    if "parent_id" in fs:
        kwargs["parent_id"] = body.parent_id
    result = update_tag(state.conn, tag_id, **kwargs)
    if result is None:
        raise HTTPException(404, "Tag not found")
    return result


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
