"""
Sprite sheet builder for the thumbnail strip.

Packs N thumbnails per sheet (default 50) in a grid, outputs one WebP per
sheet plus a single manifest.json with per-page coordinates.

Frontend uses the manifest to position each thumb via CSS background-position,
so the strip fires ≤ ceil(total_pages/50) HTTP requests total instead of one
per page.
"""
from __future__ import annotations
import json
import os

from PIL import Image

PAGES_PER_SHEET = 50
COLS = 10


def build_sprites(
    thumb_info: list[tuple[int, str, int, int]],
    sprites_dir: str,
    cell_px: int,
) -> None:
    """
    Build sprite sheets and write manifest.json.

    thumb_info: [(page_num, thumb_path, thumb_w, thumb_h), ...] sorted by page_num
    sprites_dir: output directory (created if needed)
    cell_px: square cell size in the grid; thumbs are centred inside the cell
    """
    os.makedirs(sprites_dir, exist_ok=True)

    batches = [
        thumb_info[i : i + PAGES_PER_SHEET]
        for i in range(0, len(thumb_info), PAGES_PER_SHEET)
    ]

    page_map: dict[str, dict] = {}  # str(page_num) → position info
    sheets_meta: list[dict] = []

    for sheet_idx, batch in enumerate(batches):
        rows = (len(batch) + COLS - 1) // COLS
        sheet_w = COLS * cell_px
        sheet_h = rows * cell_px

        sheet_img = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))

        for i, (page_num, thumb_path, thumb_w, thumb_h) in enumerate(batch):
            col = i % COLS
            row = i // COLS
            cell_x = col * cell_px
            cell_y = row * cell_px
            # Centre the thumb inside its cell
            offset_x = (cell_px - thumb_w) // 2
            offset_y = (cell_px - thumb_h) // 2

            with Image.open(thumb_path) as thumb_img:
                sheet_img.paste(thumb_img, (cell_x + offset_x, cell_y + offset_y))

            page_map[str(page_num)] = {
                "s": sheet_idx,               # sheet index
                "x": cell_x + offset_x,       # pixel x in sheet
                "y": cell_y + offset_y,        # pixel y in sheet
                "w": thumb_w,
                "h": thumb_h,
            }

        sheet_filename = f"strip_{sheet_idx:02d}.webp"
        sheet_img.save(
            os.path.join(sprites_dir, sheet_filename),
            "WEBP", quality=75, method=4,
        )
        sheets_meta.append({"file": sheet_filename, "w": sheet_w, "h": sheet_h})

    manifest = {
        "cell_px": cell_px,
        "cols": COLS,
        "sheets": sheets_meta,
        "pages": page_map,
    }
    with open(os.path.join(sprites_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"))
