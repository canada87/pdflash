from __future__ import annotations
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.db import (
    get_doc_by_id,
    get_docs_gallery,
    delete_doc_from_db,
)
from app.state import state

router = APIRouter()


@router.get("/docs")
async def list_docs(
    tag: str = None,
    q: str = None,
    sort: str = "recent",
    limit: int = 50,
    offset: int = 0,
):
    return get_docs_gallery(
        state.conn, tag=tag, q=q, sort=sort, limit=limit, offset=offset
    )


@router.get("/docs/{doc_id:int}")
async def get_doc(doc_id: int):
    doc = get_doc_by_id(state.conn, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("/docs/upload")
async def upload_doc(file: UploadFile = File(...)):
    safe_name = Path(file.filename).name
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    tmp_dir = os.path.join(state.config.data_dir, "uploads_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(state.config.pdf_dir, exist_ok=True)

    tmp_path = os.path.join(tmp_dir, safe_name)
    with open(tmp_path, "wb") as f:
        while chunk := await file.read(1 << 20):  # 1 MB chunks
            f.write(chunk)

    dest = os.path.join(state.config.pdf_dir, safe_name)
    shutil.move(tmp_path, dest)

    await state.queue.enqueue(dest)
    return {"status": "queued", "filename": safe_name}


@router.post("/docs/{doc_id:int}/reindex")
async def reindex_doc(doc_id: int):
    doc = get_doc_by_id(state.conn, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    pdf_path = os.path.join(state.config.pdf_dir, doc["path"])
    if not os.path.isfile(pdf_path):
        raise HTTPException(404, f"PDF file not found on disk: {doc['path']}")
    await state.queue.enqueue(pdf_path, force=True)
    return {"status": "queued"}


@router.delete("/docs/{doc_id:int}")
async def delete_doc(doc_id: int):
    doc = get_doc_by_id(state.conn, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    cache_dir = state.config.pages_dir(doc["hash"])
    cover_path = os.path.join(state.config.covers_dir, f"{doc['hash']}.webp")

    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir, ignore_errors=True)
    if os.path.exists(cover_path):
        os.remove(cover_path)

    delete_doc_from_db(state.conn, doc_id)
    return {"status": "deleted"}
