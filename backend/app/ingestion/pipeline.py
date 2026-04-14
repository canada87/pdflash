"""
Full ingestion pipeline for a single PDF.

Steps (matches PLAN.md §6):
  1. SHA-256 hash → doc_hash (cache key)
  2. Skip if already ready with same mtime
  3. DB record → status=indexing
  4. Extract metadata + outline via PyMuPDF (main process)
  5. Render cover at 400 px (main process, fast)
  6. Render all pages concurrently in ProcessPoolExecutor
       → 3 WebP tiers (thumb/screen/hi) + per-word text
  7. Build sprite sheets
  8. Save per-page text JSON + insert into FTS5
  9. Compute blur placeholder from cover
 10. DB → status=ready

Only the main process touches SQLite (WAL + no cross-process writes).
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz  # PyMuPDF — only used in main process here for metadata + cover
from PIL import Image

from app.config import Config
from app.db import insert_page_fts, upsert_doc, update_doc_status, get_doc_by_hash
from app.ingestion.blurhash_gen import compute_blurhash
from app.ingestion.render import render_page
from app.ingestion.sprites import build_sprites


def ingest_pdf(
    pdf_path: str,
    config: Config,
    conn: sqlite3.Connection,
    *,
    force: bool = False,
) -> int:
    """
    Ingest a single PDF.  Returns doc_id.
    Raises on unrecoverable errors (corrupt PDF, disk full, …).
    Sets status=failed in DB on render errors without re-raising.
    """
    pdf_path = os.path.abspath(pdf_path)

    # ── 1. Hash ──────────────────────────────────────────────────────────────
    doc_hash = _sha256_file(pdf_path)

    # ── 2. Skip if already indexed with the same content ─────────────────────
    if not force:
        existing = get_doc_by_hash(conn, doc_hash)
        if existing and existing["status"] == "ready":
            mtime = int(os.path.getmtime(pdf_path))
            if existing["mtime"] == mtime:
                return existing["id"]

    # ── 3-4. Open PDF, extract metadata ──────────────────────────────────────
    try:
        pdf = fitz.open(pdf_path)
    except Exception as e:
        raise RuntimeError(f"Cannot open PDF: {e}") from e

    try:
        meta = pdf.metadata or {}
        page_count = pdf.page_count
        toc = pdf.get_toc()  # [[level, title, page_1indexed], ...]
    finally:
        pdf.close()

    mtime = int(os.path.getmtime(pdf_path))
    size_bytes = os.path.getsize(pdf_path)
    title = (meta.get("title") or "").strip() or Path(pdf_path).stem

    doc_id = upsert_doc(
        conn,
        {
            "hash": doc_hash,
            "path": _rel(pdf_path, config.pdf_dir),
            "title": title,
            "author": (meta.get("author") or "").strip() or None,
            "page_count": page_count,
            "size_bytes": size_bytes,
            "mtime": mtime,
            "added_at": int(time.time()),
            "status": "indexing",
            "outline_json": json.dumps(toc) if toc else None,
        },
    )

    # ── 5. Render cover (400 px, main process) ────────────────────────────────
    output_base = config.pages_dir(doc_hash)
    for sub in ("thumb", "screen", "hi", "text", "sprites"):
        os.makedirs(os.path.join(output_base, sub), exist_ok=True)
    os.makedirs(config.covers_dir, exist_ok=True)

    cover_path = os.path.join(config.covers_dir, f"{doc_hash}.webp")
    _render_cover(pdf_path, cover_path, max_px=400)

    # ── 6. Render all pages concurrently ──────────────────────────────────────
    args_list = [
        (
            pdf_path, page_idx, output_base,
            config.tier_thumb_px, config.tier_screen_px, config.tier_hi_px,
            config.webp_quality_thumb, config.webp_quality_screen, config.webp_quality_hi,
        )
        for page_idx in range(page_count)
    ]

    page_results: list[dict | None] = [None] * page_count
    try:
        with ProcessPoolExecutor(max_workers=config.workers) as pool:
            futures = {pool.submit(render_page, args): args[1] for args in args_list}
            done = 0
            for fut in as_completed(futures):
                page_idx = futures[fut]
                page_results[page_idx] = fut.result()  # propagates worker exceptions
                done += 1
                if done % 20 == 0 or done == page_count:
                    print(f"    rendered {done}/{page_count} pages …", flush=True)
    except Exception as exc:
        update_doc_status(conn, doc_id, "failed", fail_reason=str(exc))
        raise

    # ── 7. Sprite sheets ──────────────────────────────────────────────────────
    thumb_info = [
        (r["page_num"], r["thumb_path"], r["thumb_w"], r["thumb_h"])
        for r in page_results  # type: ignore[union-attr]
    ]
    build_sprites(thumb_info, os.path.join(output_base, "sprites"), config.tier_thumb_px)

    # ── 8. Text JSON + FTS5 ───────────────────────────────────────────────────
    text_dir = os.path.join(output_base, "text")
    fts_rows: list[tuple[int, int, str]] = []

    for r in page_results:  # type: ignore[union-attr]
        text_path = os.path.join(text_dir, f"{r['page_num']:04d}.json")
        with open(text_path, "w", encoding="utf-8") as f:
            json.dump(r["text_data"], f, ensure_ascii=False, separators=(",", ":"))

        full_text = " ".join(w["t"] for w in r["text_data"])
        fts_rows.append((doc_id, r["page_num"], full_text))

    insert_page_fts(conn, fts_rows)

    # ── 9. Blur placeholder ───────────────────────────────────────────────────
    blur = compute_blurhash(cover_path)

    # ── 10. Mark ready ────────────────────────────────────────────────────────
    update_doc_status(conn, doc_id, "ready", blurhash=blur)

    return doc_id


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _render_cover(pdf_path: str, cover_path: str, max_px: int) -> None:
    doc = fitz.open(pdf_path)
    page = doc[0]
    rect = page.rect
    long_side = max(rect.width, rect.height) or 1.0
    scale = max_px / long_side
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    doc.close()
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img.save(cover_path, "WEBP", quality=80, method=4)


def _rel(path: str, base: str) -> str:
    try:
        return os.path.relpath(path, base)
    except ValueError:
        # Different drives on Windows
        return path
