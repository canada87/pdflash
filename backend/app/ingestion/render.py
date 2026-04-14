"""
Page rendering worker — runs inside a subprocess (ProcessPoolExecutor).

Rules:
- No imports from the rest of the app at module level (pickling / spawn safety).
- All arguments and return values must be picklable.
- PyMuPDF is NOT thread-safe; using one process per task is safe.
"""
from __future__ import annotations
import os

import fitz  # PyMuPDF
from PIL import Image


def render_page(args: tuple) -> dict:
    """
    Render one PDF page to three WebP tiers and extract per-word text.

    args:
        pdf_path    - absolute path to the PDF
        page_idx    - 0-based page index
        output_base - base dir for this doc: .../cache/pages/{doc_hash}
        thumb_px    - long-side pixels for thumb tier (~200)
        screen_px   - long-side pixels for screen tier (~1400)
        hi_px       - long-side pixels for hi tier (~2800)
        q_thumb     - WebP quality for thumb
        q_screen    - WebP quality for screen
        q_hi        - WebP quality for hi

    returns dict:
        page_num, thumb_path, thumb_w, thumb_h,
        screen_path, hi_path, text_data
    """
    (
        pdf_path, page_idx, output_base,
        thumb_px, screen_px, hi_px,
        q_thumb, q_screen, q_hi,
    ) = args

    page_num = page_idx + 1
    page_str = f"{page_num:04d}"

    doc = fitz.open(pdf_path)
    page = doc[page_idx]
    rect = page.rect
    page_w = rect.width or 1.0
    page_h = rect.height or 1.0
    long_side = max(page_w, page_h)

    def _render_tier(max_px: int, quality: int, tier: str) -> tuple[str, int, int]:
        scale = max_px / long_side
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        out_dir = os.path.join(output_base, tier)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{page_str}.webp")
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(out_path, "WEBP", quality=quality, method=4)
        return out_path, pix.width, pix.height

    thumb_path, thumb_w, thumb_h = _render_tier(thumb_px, q_thumb, "thumb")
    screen_path, _, _ = _render_tier(screen_px, q_screen, "screen")
    hi_path, _, _ = _render_tier(hi_px, q_hi, "hi")

    # Per-word bounding boxes, coordinates normalised to 0..1
    words = page.get_text("words")  # (x0,y0,x1,y1, word, block, line, word_no)
    text_data = [
        {
            "t": w[4],
            "x": round(w[0] / page_w, 4),
            "y": round(w[1] / page_h, 4),
            "w": round((w[2] - w[0]) / page_w, 4),
            "h": round((w[3] - w[1]) / page_h, 4),
        }
        for w in words
    ]

    doc.close()

    return {
        "page_num": page_num,
        "thumb_path": thumb_path,
        "thumb_w": thumb_w,
        "thumb_h": thumb_h,
        "screen_path": screen_path,
        "hi_path": hi_path,
        "text_data": text_data,
    }
