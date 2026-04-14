from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass
class Config:
    pdf_dir: str = field(
        default_factory=lambda: os.environ.get("PDFLASH_PDF_DIR", "./pdfs")
    )
    data_dir: str = field(
        default_factory=lambda: os.environ.get("PDFLASH_DATA_DIR", "./data")
    )
    workers: int = field(
        default_factory=lambda: int(
            os.environ.get("PDFLASH_WORKERS", str(min(os.cpu_count() or 1, 4)))
        )
    )
    tier_thumb_px: int = field(
        default_factory=lambda: int(os.environ.get("PDFLASH_TIER_THUMB_PX", "200"))
    )
    tier_screen_px: int = field(
        default_factory=lambda: int(os.environ.get("PDFLASH_TIER_SCREEN_PX", "1400"))
    )
    tier_hi_px: int = field(
        default_factory=lambda: int(os.environ.get("PDFLASH_TIER_HI_PX", "2800"))
    )
    webp_quality_thumb: int = field(
        default_factory=lambda: int(os.environ.get("PDFLASH_WEBP_QUALITY_THUMB", "70"))
    )
    webp_quality_screen: int = field(
        default_factory=lambda: int(os.environ.get("PDFLASH_WEBP_QUALITY_SCREEN", "80"))
    )
    webp_quality_hi: int = field(
        default_factory=lambda: int(os.environ.get("PDFLASH_WEBP_QUALITY_HI", "82"))
    )

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "db", "app.db")

    @property
    def cache_dir(self) -> str:
        return os.path.join(self.data_dir, "cache")

    @property
    def covers_dir(self) -> str:
        return os.path.join(self.data_dir, "cache", "covers")

    def pages_dir(self, doc_hash: str) -> str:
        return os.path.join(self.data_dir, "cache", "pages", doc_hash)
