from __future__ import annotations
import os
from io import BytesIO

import fitz  # PyMuPDF
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image as PilImage

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
async def get_page_image(doc_id: int, page_num: int, idx: int, fmt: str = None):
    """Serve embedded image `idx` on the given page.
    Optional ?fmt=jpeg or ?fmt=png converts the image before serving.
    """
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

    data, ext = ex["image"], ex["ext"]

    if fmt == "jpeg":
        img = PilImage.open(BytesIO(data))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, "JPEG", quality=92)
        return Response(content=buf.getvalue(), media_type="image/jpeg")

    if fmt == "png":
        img = PilImage.open(BytesIO(data))
        buf = BytesIO()
        img.save(buf, "PNG")
        return Response(content=buf.getvalue(), media_type="image/png")

    mime = _MIME.get(ext.lower(), "application/octet-stream")
    return Response(content=data, media_type=mime)
