from __future__ import annotations
import os

import fitz  # PyMuPDF
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.db import get_doc_by_id
from app.state import state

router = APIRouter()

_MIME = {
    "jpeg": "image/jpeg",
    "jpg":  "image/jpeg",
    "png":  "image/png",
    "webp": "image/webp",
    "gif":  "image/gif",
    "tiff": "image/tiff",
    "bmp":  "image/bmp",
}


def _get_pdf(doc_id: int):
    doc_row = get_doc_by_id(state.conn, doc_id)
    if not doc_row:
        raise HTTPException(404, "Document not found")
    pdf_path = os.path.join(state.config.pdf_dir, doc_row["path"])
    if not os.path.isfile(pdf_path):
        raise HTTPException(404, "PDF file not found on disk")
    return doc_row, fitz.open(pdf_path)


@router.get("/docs/{doc_id:int}/page/{page_num:int}/images")
async def list_page_images(doc_id: int, page_num: int):
    """Return metadata for all embedded images on a given page (1-based)."""
    doc_row, pdf = _get_pdf(doc_id)
    try:
        if not (1 <= page_num <= doc_row["page_count"]):
            raise HTTPException(400, "Page out of range")
        raw = pdf[page_num - 1].get_images(full=True)
        result = []
        for idx, img in enumerate(raw):
            try:
                ex = pdf.extract_image(img[0])
                result.append({
                    "idx":    idx,
                    "width":  ex["width"],
                    "height": ex["height"],
                    "ext":    ex["ext"],
                })
            except Exception:
                pass  # skip unextractable entries
    finally:
        pdf.close()
    return result


@router.get("/docs/{doc_id:int}/page/{page_num:int}/images/{idx:int}")
async def get_page_image(doc_id: int, page_num: int, idx: int):
    """Serve the raw bytes of embedded image `idx` on the given page."""
    doc_row, pdf = _get_pdf(doc_id)
    try:
        if not (1 <= page_num <= doc_row["page_count"]):
            raise HTTPException(400, "Page out of range")
        raw = pdf[page_num - 1].get_images(full=True)
        if not (0 <= idx < len(raw)):
            raise HTTPException(404, "Image index out of range")
        ex = pdf.extract_image(raw[idx][0])
    finally:
        pdf.close()

    mime = _MIME.get(ex["ext"].lower(), "application/octet-stream")
    return Response(content=ex["image"], media_type=mime)
