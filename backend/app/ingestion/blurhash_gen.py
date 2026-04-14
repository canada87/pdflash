"""
Generates a compact blur placeholder for a cover image.

We resize to a tiny JPEG (16×N pixels) and base64-encode it as a data URI.
The result is stored in the `blurhash` DB column and used by the frontend
as an instant <img src> before the real WebP loads (blur-up pattern).

Typical output size: ~300-500 characters — negligible in JSON responses.
"""
from __future__ import annotations
import base64
import io

from PIL import Image

# Tiny pixel width for the placeholder; height scales with aspect ratio
_PLACEHOLDER_WIDTH = 16


def compute_blurhash(image_path: str) -> str:
    """Return a base64 JPEG data URI for a blurred micro-thumbnail."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        # Preserve aspect ratio
        new_h = max(1, round(h * _PLACEHOLDER_WIDTH / w))
        img = img.resize((_PLACEHOLDER_WIDTH, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=20, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
