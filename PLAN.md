# pdflash — Piano di progetto

Web app self-hosted per leggere PDF con velocità di navigazione estrema.
Single-user, container Docker, libreria su filesystem locale.

---

## 1. Principio guida

> **Non si renderizza mai a runtime.**
> Tutto il rendering avviene in fase di ingestion, una sola volta per file.
> A runtime l'app serve immagini statiche pre-calcolate, come una CDN di pagine.
> Scambiamo spazio disco per latenza: un PDF da 500 pagine occupa ~100–200 MB
> di cache, e in cambio ogni navigazione è istantanea.

Ogni decisione successiva discende da qui. Se una feature costringe a
renderizzare a runtime, la feature perde.

---

## 2. Scope v1

### IN
- Ingestion automatica dei PDF nella cartella montata
- Upload di PDF dall'interfaccia web
- Dashboard/gallery con cover, titolo, % letto, last opened
- Sezione "Continue reading"
- Reader con:
  - Singola pagina
  - Doppia pagina (opzione "prima pagina da sola")
  - Fullscreen
  - Zoom con pan
  - Strip di thumbnail laterale per navigazione rapida
  - Tastiera-first (shortcut per tutto)
- Ricerca testo globale e per-documento (FTS5)
- Memoria dell'ultima pagina per documento (resume)
- Outline/TOC estratto dal PDF nella sidebar
- Bookmark manuali
- Tag/collezioni con filtri in dashboard
- Trigger manuale di re-ingestion (singolo file o intera libreria)

### OUT (v1)
- Dark mode
- Deep linking condivisibile
- Rilevamento duplicati
- Autenticazione (demandata a reverse proxy se in futuro serve)
- OCR
- Annotazioni, highlights, editing PDF
- Multi-utente

---

## 3. Requisiti non funzionali (target di performance)

| Metrica | Target |
|---|---|
| Apertura documento (dalla gallery alla prima pagina visibile) | < 200 ms |
| Cambio pagina (next/prev) | < 50 ms percepiti |
| Scroll nella thumb strip | 60 fps costanti |
| Ricerca globale su ~100 documenti | < 100 ms |
| Cold start del container | < 3 s |
| Ingestion di un PDF da 500 pagine | non blocca la UI, in background |

Come li raggiungiamo → sezione "Trucchi di performance".

---

## 4. Stack tecnologico

- **Backend**: Python 3.12 + FastAPI + Uvicorn
- **Rendering**: PyMuPDF (fitz) — il motore PDF più veloce con API Python
- **File watcher**: watchdog
- **Ingestion async**: asyncio queue (no Celery/rq, overkill per single-user)
- **DB**: SQLite in WAL mode, estensione FTS5 per full-text search
- **Frontend**: Svelte + Vite (bundle minuscolo, runtime veloce, niente virtual DOM)
- **Reverse proxy / static**: Caddy (HTTPS auto, config una riga)
- **Orchestrazione**: docker-compose

Motivo della scelta PyMuPDF: rende più veloce di pdf2image/pdftoppm,
estrae testo con bounding box in un passaggio, gestisce outline e metadata.
Tutto in-process, niente processi shell.

---

## 5. Architettura

```
┌─────────────────────────────────────────────────┐
│                 Browser (Svelte)                │
└───────────────┬─────────────────────────────────┘
                │ HTTP/2
┌───────────────▼─────────────────────────────────┐
│                    Caddy                        │
│  - /assets/*   → static build frontend          │
│  - /cache/*    → WebP pre-renderizzate          │
│                  (Cache-Control immutable)      │
│  - /api/*      → proxy a FastAPI                │
└───────────────┬─────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────┐
│               FastAPI (app)                     │
│  - API leggere: metadata, search, progress      │
│  - Upload endpoint                              │
│  - Ingestion worker (asyncio task)              │
│  - Watchdog observer                            │
└───────┬───────────────────────────┬─────────────┘
        │                           │
 ┌──────▼──────┐              ┌─────▼──────┐
 │   SQLite    │              │ Filesystem │
 │  (WAL+FTS5) │              │  (volumi)  │
 └─────────────┘              └────────────┘
```

**FastAPI non serve mai i bytes delle pagine.** Quelle passano sempre
per Caddy come file statici con `Cache-Control: public, max-age=31536000, immutable`.
Gli hash nel path garantiscono invalidazione corretta.

---

## 6. Pipeline di ingestion

Trigger: watchdog rileva nuovo/modificato, upload API, o re-ingestion manuale.

Per ogni PDF:

1. **Hash SHA-256** del file → `doc_hash`, usato come chiave di cache.
2. **Skip** se hash già in DB con stato `ready` e mtime invariato.
3. Record DB in stato `pending`.
4. **Metadata** con PyMuPDF: titolo, autore, n. pagine, outline (TOC).
5. **Render cover** (prima pagina, ~400px lato lungo, WebP q80).
6. **Render pagine** in loop, per ciascuna a 3 tier:
   - `thumb` ~200px lato lungo, q70
   - `screen` ~1400px lato lungo, q80
   - `hi` ~2800px lato lungo, q82
   Salvate in `/data/cache/pages/{doc_hash}/{tier}/{page:04d}.webp`.
7. **Sprite sheet thumb**: pack di 50 thumbnail per sprite in un'unica WebP
   + JSON con coordinate → la strip carica 10 sprite invece di 500 immagini.
8. **Estrazione testo per pagina** con bounding box → due output:
   - Inserimento in FTS5: `(doc_id, page_num, text)`
   - JSON compatto per pagina con array di `{text, x, y, w, h}` per il text layer
     overlay (ricerca + selezione). Salvato in
     `/data/cache/pages/{doc_hash}/text/{page:04d}.json`.
9. **Blurhash / placeholder base64** da 10×14px della prima pagina e di ogni
   thumb, embeddato nei metadata JSON → blur-up istantaneo.
10. Record DB in stato `ready`, pubblica evento via SSE al frontend che
    eventualmente sta guardando la gallery.

Errori → stato `failed` con motivo, visibile in dashboard, pulsante retry.

Concorrenza: una coda singola, worker pool con N = `min(CPU, 4)`. PyMuPDF
non è thread-safe; usiamo process pool (`ProcessPoolExecutor`).

---

## 7. Schema database

SQLite. WAL abilitato all'avvio. FTS5 compilato in (standard in Python 3.12).

```sql
-- Documento
CREATE TABLE doc (
  id           INTEGER PRIMARY KEY,
  hash         TEXT UNIQUE NOT NULL,      -- sha256
  path         TEXT NOT NULL,             -- path relativo a /pdfs
  title        TEXT,
  author       TEXT,
  page_count   INTEGER NOT NULL,
  size_bytes   INTEGER NOT NULL,
  mtime        INTEGER NOT NULL,
  added_at     INTEGER NOT NULL,
  status       TEXT NOT NULL,             -- pending|indexing|ready|failed
  fail_reason  TEXT,
  blurhash     TEXT,
  outline_json TEXT                       -- TOC serializzato
);

CREATE INDEX idx_doc_status ON doc(status);
CREATE INDEX idx_doc_added  ON doc(added_at DESC);

-- Stato di lettura (single-user, quindi 1 riga per doc)
CREATE TABLE progress (
  doc_id       INTEGER PRIMARY KEY REFERENCES doc(id) ON DELETE CASCADE,
  last_page    INTEGER NOT NULL DEFAULT 1,
  last_opened  INTEGER NOT NULL,
  pages_seen   INTEGER NOT NULL DEFAULT 0   -- per % lettura
);

-- Bookmark manuali
CREATE TABLE bookmark (
  id        INTEGER PRIMARY KEY,
  doc_id    INTEGER NOT NULL REFERENCES doc(id) ON DELETE CASCADE,
  page      INTEGER NOT NULL,
  label     TEXT,
  created_at INTEGER NOT NULL
);

-- Tag
CREATE TABLE tag (
  id   INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE doc_tag (
  doc_id INTEGER NOT NULL REFERENCES doc(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (doc_id, tag_id)
);

-- Ricerca full-text per pagina
CREATE VIRTUAL TABLE page_fts USING fts5(
  doc_id UNINDEXED,
  page   UNINDEXED,
  text,
  tokenize = 'unicode61 remove_diacritics 2'
);
```

---

## 8. Layout filesystem / volumi Docker

```
/pdfs/                              # cartella PDF, montata dal host (read-write per upload)
  libro-tizio.pdf
  sottocartella/
    altro.pdf

/data/
  db/
    app.db                          # SQLite + WAL
  cache/
    covers/
      {doc_hash}.webp
    pages/
      {doc_hash}/
        thumb/0001.webp ... 0500.webp
        screen/0001.webp ... 0500.webp
        hi/0001.webp    ... 0500.webp
        text/0001.json  ... 0500.json
        sprites/strip_00.webp, strip_00.json, strip_01.webp, ...
  uploads_tmp/                      # staging upload prima del move in /pdfs
```

Invalidazione cache: se cambia `doc_hash` il path cambia, vecchie cache
vengono eliminate in un job di cleanup.

---

## 9. API backend

Tutte sotto `/api`. JSON. Nessuna auth in v1 (rete locale).

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/api/docs` | Lista documenti per la gallery. Query: `?tag=&q=&sort=recent\|title\|progress&limit=&offset=` |
| GET | `/api/docs/{id}` | Metadata completi + outline + blurhash + sprite index |
| GET | `/api/docs/{id}/text/{page}` | JSON text layer della pagina (lazy, solo se serve selezione/ricerca) |
| POST | `/api/docs/upload` | Multipart upload, accoda ingestion |
| POST | `/api/docs/{id}/reindex` | Forza re-ingestion |
| DELETE | `/api/docs/{id}` | Rimuove doc + file + cache |
| GET | `/api/progress` | Lista "continue reading" (ultimi N non completati) |
| POST | `/api/progress/{id}` | Body: `{page}` — debounced da frontend, update `last_page`, `last_opened` |
| GET | `/api/search?q=...` | Global FTS5 — ritorna doc + pagina + snippet |
| GET | `/api/search?q=...&doc_id=X` | Search scoped a un doc |
| GET/POST/DELETE | `/api/bookmarks` | CRUD bookmark |
| GET/POST/DELETE | `/api/tags` | CRUD tag + associazione doc |
| GET | `/api/events` | Server-Sent Events per notifiche ingestion (stato ready/failed) |
| GET | `/api/health` | Healthcheck Docker |

Le pagine renderizzate **non** passano da qui. URL diretto:
`/cache/pages/{doc_hash}/{tier}/{page:04d}.webp` servito da Caddy.

---

## 10. Frontend — viste e trucchi di performance

### 10.1 Viste
1. **Dashboard / Gallery**
   - Grid di card: cover + titolo + % letto + barra progresso + tag
   - Filtri: tag, ricerca titolo/autore, sort (recent, title, progress)
   - Sezione top "Continue reading" (ultimi 6 aperti, non completati)
   - Bottone upload (drag & drop full-page opzionale)
   - Stato ingestion in live via SSE
2. **Reader**
   - Area centrale: pagina(e) correnti
   - Thumb strip (destra o bottom, toggle)
   - Sidebar sinistra collassabile: outline + bookmark + ricerca in-doc
   - Toolbar minima: page N/M, zoom, single/double, fullscreen, jump-to-page
3. **Search globale**
   - Overlay con risultati raggruppati per documento, snippet, click → reader alla pagina

### 10.2 Trucchi di performance

- **Preload vicini**: al display di pagina N, `new Image()` su N+1, N+2, N-1.
  Costo zero lato server (static cached).
- **Sprite sheets per la strip**: una sola richiesta per 50 thumb. Posizionamento
  via `background-position`. Scroll della strip = zero network traffic dopo il primo fetch.
- **Blur-up**: placeholder base64 (≤40 byte) dai metadata, mostrato subito,
  sostituito dalla WebP reale quando carica. Il browser non "lampeggia" mai.
- **Virtual scrolling** sulla gallery e sulla strip (only viewport items in DOM).
- **Service Worker** con strategia `CacheFirst` sui path `/cache/pages/*`.
  Documenti già letti = 0 ms alla riapertura, anche offline.
- **Zoom a swap**: tier `screen` di default, tier `hi` caricato al primo zoom
  (e cachato dal SW).
- **CSS transform** per pan/zoom (GPU), niente re-layout.
- **Debounce** del salvataggio progress (300 ms) per evitare storm su SQLite
  quando scrolli veloce.
- **Niente animazioni** sui cambi pagina — il cambio istantaneo *è* la feature.
  Solo un micro-fade (80 ms) sul blur-up se vogliamo essere gentili.
- **Svelte produce ~10 KB di runtime**: TTI minimale.
- **HTTP/2 via Caddy**: multiplexing per il burst di thumb/pagine.

### 10.3 Keyboard shortcuts

| Tasto | Azione |
|---|---|
| → / PgDn / Space | Next page (o next coppia in doppia pagina) |
| ← / PgUp | Prev page |
| Home / End | Prima / ultima pagina |
| F | Toggle fullscreen |
| D | Toggle doppia pagina |
| +, − | Zoom in/out |
| 0 | Fit |
| Ctrl+F | Search in-doc |
| Ctrl+K | Search globale |
| B | Toggle bookmark sulla pagina corrente |
| G | Vai a pagina (prompt numerico) |
| Esc | Exit fullscreen / chiudi overlay |

---

## 11. Docker setup

**Servizi** in `docker-compose.yml`:

- `app`: Python 3.12-slim, PyMuPDF, FastAPI, Uvicorn. Espone 8000 internamente.
- `caddy`: immagine ufficiale, espone 80/443 sulla rete host. Config:
  - `/assets/*` → file statici del build Svelte (copy-mount)
  - `/cache/*` → mount read-only della cache con header immutable
  - `/api/*` → reverse proxy a `app:8000`
  - `/*` → fallback all'index Svelte (SPA routing)

**Volumi**:
- `${PDF_DIR}:/pdfs` (host path configurabile via `.env`)
- `pdflash_data:/data` (named volume per DB + cache)

**Build**: multi-stage. Stage 1 = node alpine builda frontend. Stage 2 =
python slim copia i bundle + installa deps. Dockerfile finale < 300 MB.

**Healthcheck**: `GET /api/health` ogni 30 s.

**Env vars principali**:
```
PDFLASH_PDF_DIR=/pdfs
PDFLASH_DATA_DIR=/data
PDFLASH_WORKERS=4
PDFLASH_TIER_SCREEN_PX=1400
PDFLASH_TIER_HI_PX=2800
PDFLASH_WEBP_QUALITY_SCREEN=80
PDFLASH_WEBP_QUALITY_HI=82
```

---

## 12. Roadmap a milestone

**M1 — Ingestion funzionante a riga di comando**
- Setup progetto, PyMuPDF, SQLite schema, render dei 3 tier, estrazione testo,
  FTS5 popolata. Nessuna UI. Test su qualche PDF reale.

**M2 — Backend API + reader minimo**
- FastAPI con endpoint principali. Frontend Svelte con gallery e reader base
  (singola pagina, next/prev, thumb strip senza sprite).

**M3 — Performance pass**
- Sprite sheets, blur-up, preload vicini, service worker, virtual scroll.
  Benchmark contro i target della sezione 3.

**M4 — Feature di reading**
- Doppia pagina, zoom, fullscreen, ricerca in-doc con highlight, outline,
  bookmark, resume last page.

**M5 — Dashboard completa**
- Continue reading, tag, filtri, % letto, upload da web, SSE per stato ingestion.

**M6 — Packaging**
- Dockerfile multi-stage, docker-compose, .env, README di deploy, healthcheck,
  backup strategy (il DB è piccolo, cron di copia del file).

Ogni milestone produce qualcosa di usabile end-to-end. Niente big bang.

---

## 13. Rischi e decisioni aperte

| Rischio | Mitigazione |
|---|---|
| Ingestion lunga per libreria grande | Worker background, UI mostra progresso, l'uso non si blocca mai |
| Cache esplode in dimensione | Retention policy opzionale per tier `hi` (può essere rigenerato al volo se serve), report di uso spazio |
| PDF corrotti / password protected | Stato `failed` + motivo, nessun crash del worker (try/except per doc) |
| Filesystem case-sensitive vs Windows host | Usare solo hash come chiave di cache, path originale solo per display |
| Watchdog su volumi Docker su Windows/WSL inaffidabile | Fallback: polling ogni 30 s della cartella se watchdog non riceve eventi per tot tempo |
| SQLite e concorrenza worker | Worker in process pool scrivono via coda verso il main process; solo il main tocca SQLite. WAL mode per letture concorrenti. |

**Decisioni aperte da valutare durante M1/M2**:
- Strip thumb destra vs bottom come default (probabilmente toggle utente, salvato in localStorage)
- Dimensioni esatte dei tier (i valori attuali sono da testare su uno schermo 1440p)
- Se introdurre un tier `print` ~4000px per monitor 4K (decisione rimandata a post-M3 in base al benchmark)

---

## 14. Fuori scope v1, per memoria futura

Da valutare in un eventuale v2:
- Dark mode
- Deep linking condivisibile
- Rilevamento duplicati (by hash)
- Auth via reverse proxy (Authelia/Authentik)
- OCR (tesseract) per PDF scan-only
- Annotazioni e highlights persistenti
- Sync della posizione tra dispositivi
- Estrazione automatica di copertine migliori (prima pagina spesso è frontespizio bianco)
- App mobile / PWA install prompt