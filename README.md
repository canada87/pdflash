# pdflash

A self-hosted, single-user PDF reader built for speed. Every page is pre-rendered to WebP at ingest time — navigating a document is serving a static file, nothing more.

## How it works

When you add a PDF, the ingestion pipeline:
1. Renders every page to three WebP tiers (thumb / screen / hi-res) using PyMuPDF
2. Extracts full text and indexes it in SQLite FTS5
3. Builds sprite sheets for the thumbnail strip
4. Computes a blur-up placeholder for cover images

From that point on, every page load is a static file request — no runtime rendering, no layout engine, no surprises.

## Requirements

- Docker + Docker Compose (recommended)
- Or: Python 3.11+ and Node 20+ for local development

## Quick start (Docker)

```bash
git clone <repo>
cd pdflash
cp .env.example .env          # adjust if needed
docker compose up -d
```

Open [http://localhost:8000](http://localhost:8000), then drop PDFs into `./pdfs/` or use the Upload button in the UI.

## Configuration

Copy `.env.example` to `.env` and edit as needed. Docker Compose reads it automatically.

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Host port |
| `PDF_DIR` | `./pdfs` | Local folder watched for new PDFs |
| `PDFLASH_WORKERS` | `4` | Parallel rendering workers (≤ CPU count) |
| `PDFLASH_TIER_THUMB_PX` | `200` | Thumbnail long edge (px) |
| `PDFLASH_TIER_SCREEN_PX` | `1400` | Default view long edge (px) |
| `PDFLASH_TIER_HI_PX` | `2800` | Hi-res long edge (px) |
| `PDFLASH_WEBP_QUALITY_THUMB` | `70` | WebP quality — thumbnails |
| `PDFLASH_WEBP_QUALITY_SCREEN` | `80` | WebP quality — default view |
| `PDFLASH_WEBP_QUALITY_HI` | `82` | WebP quality — hi-res |

## Features

**Gallery**
- Cover grid with blur-up placeholders and reading progress bars
- Continue Reading shelf (recently opened, not finished)
- Sort by: recent / A–Z / progress
- Tag-based filtering — assign tags per document, filter by tag
- Drag-and-drop or button upload
- Live ingestion progress bar via Server-Sent Events

**Reader**
- Single and double-page mode (`D`)
- Zoom + pan with mouse wheel and drag (`+` / `-` / `0`)
- Click top half of page → previous page, bottom half → next page
- Fullscreen (`F`)
- Thumbnail strip with virtual scroll
- Table of Contents sidebar (from PDF outline)
- In-document full-text search with highlighted snippets
- Embedded image viewer — browse and download images embedded in the PDF as JPG or PNG
- Bookmarks (`B` to toggle)
- Page position saved automatically

**Keyboard shortcuts**

| Key | Action |
|---|---|
| `→` `Space` `PgDn` | Next page |
| `←` `PgUp` | Previous page |
| `Home` / `End` | First / last page |
| `D` | Toggle double-page mode |
| `+` / `-` / `0` | Zoom in / out / reset |
| `B` | Toggle bookmark |
| `O` | Toggle outline + bookmarks panel |
| `T` | Toggle thumbnail strip |
| `/` | Toggle search |
| `G` | Go to page |
| `F` | Toggle fullscreen |
| `Esc` | Close overlay / exit fullscreen |

## Local development

**Backend**

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev       # Vite dev server at http://localhost:5173
```

The Vite dev server proxies `/api` and `/cache` to the backend on port 8000.

## Production with Caddy (optional)

The included `Caddyfile` puts Caddy in front for automatic HTTPS and optimal static file serving. Caddy intercepts `/cache/*` and `/assets/*` with `Cache-Control: immutable` headers and forwards `/api/*` to the app container.

```yaml
# docker-compose.yml addition
services:
  caddy:
    image: caddy:2
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - pdflash_data:/data
      - ./frontend/dist:/static
    ports:
      - "80:80"
      - "443:443"
```

Replace `:80` in `Caddyfile` with your domain name for automatic HTTPS.

## Data layout

All persistent data lives in the `pdflash_data` Docker volume (or `./data/` in dev):

```
/data/
├── db/app.db               SQLite database
├── pdfs/                   Source PDF files
├── cache/
│   ├── covers/             Cover images ({hash}.webp)
│   └── pages/{hash}/
│       ├── thumb/          Thumbnail tier
│       ├── screen/         Default view tier
│       ├── hi/             Hi-res tier
│       ├── text/           Per-page word data (JSON)
│       └── sprites/        Thumbnail sprite sheets
└── uploads_tmp/            Staging area for uploads
```

Cache paths are content-addressed (SHA-256 of the PDF). Identical files share the same cache regardless of filename. Deleting a document from the UI removes the PDF, its cache, and its database record.

## API

All endpoints are under `/api`. No authentication (single-user, designed for private networks).

| Method | Path | Description |
|---|---|---|
| `GET` | `/docs` | List documents (`?tag=&sort=recent\|title\|progress`) |
| `GET` | `/docs/indexing` | Documents currently being ingested |
| `GET` | `/docs/{id}` | Single document metadata |
| `POST` | `/docs/upload` | Upload a PDF |
| `DELETE` | `/docs/{id}` | Delete document and all associated data |
| `GET` | `/progress` | Continue-reading list |
| `POST` | `/progress/{id}` | Update reading position |
| `GET` | `/search` | Full-text search (`?q=&doc_id=`) |
| `GET` | `/bookmarks` | List bookmarks (`?doc_id=`) |
| `POST` | `/bookmarks` | Create bookmark |
| `DELETE` | `/bookmarks/{id}` | Delete bookmark |
| `GET` | `/tags` | List all tags |
| `POST` | `/tags` | Create tag |
| `DELETE` | `/tags/{id}` | Delete tag globally |
| `POST` | `/docs/{id}/tags/{tag_id}` | Attach tag to document |
| `DELETE` | `/docs/{id}/tags/{tag_id}` | Detach tag from document |
| `GET` | `/docs/{id}/page/{n}/images` | List embedded images on a page |
| `GET` | `/docs/{id}/page/{n}/images/{idx}` | Download embedded image (`?fmt=jpeg\|png`) |
| `GET` | `/events` | Server-Sent Events stream |

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn |
| PDF engine | PyMuPDF (bundled MuPDF wheels — no system deps) |
| Image processing | Pillow |
| Database | SQLite 3 (WAL mode, FTS5) |
| File watching | Watchdog |
| Frontend | Svelte 4, Vite 5 |
| Caching | Service Worker (CacheFirst for `/cache/*`) |
| Reverse proxy | Caddy 2 (optional) |
| Container | Docker, single-container by default |
