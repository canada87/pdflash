# ── Stage 1: build the Svelte frontend ──────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# vite.config.js has outDir: '../backend/static'
# With WORKDIR=/build that resolves to /backend/static (Vite creates it)
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app/backend

# System deps: none needed — pymupdf ships bundled mupdf wheels
RUN pip install --no-cache-dir --upgrade pip

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Pull in the compiled frontend from stage 1
COPY --from=frontend /backend/static/ ./static/

# Default data directories (override via env vars or volume mounts)
RUN mkdir -p /data/pdfs /data/cache /data/db

ENV PDFLASH_PDF_DIR=/data/pdfs \
    PDFLASH_DATA_DIR=/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
