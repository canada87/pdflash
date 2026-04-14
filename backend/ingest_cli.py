"""
M1 CLI — ingest one PDF or a whole directory.

Usage:
    python ingest_cli.py <path/to/file.pdf>
    python ingest_cli.py <path/to/folder/>
    python ingest_cli.py --reindex <path>    # force re-index even if hash matches
    python ingest_cli.py --search "query"    # quick FTS test
    python ingest_cli.py --list              # show all indexed docs

Run from the backend/ directory:
    cd backend
    python ingest_cli.py ../../my_pdfs/
"""
from __future__ import annotations
import argparse
import os
import sys
import time

# Make `app` importable without installing the package.
# ProcessPoolExecutor workers inherit this path on Windows (spawn).
sys.path.insert(0, os.path.dirname(__file__))

from app.config import Config
from app.db import init_db, get_docs, search_fts
from app.ingestion.pipeline import ingest_pdf


def _find_pdfs(path: str) -> list[str]:
    path = os.path.abspath(path)
    if os.path.isfile(path):
        return [path] if path.lower().endswith(".pdf") else []
    results = []
    for root, _, files in os.walk(path):
        for name in files:
            if name.lower().endswith(".pdf"):
                results.append(os.path.join(root, name))
    return sorted(results)


def cmd_ingest(paths: list[str], config: Config, force: bool) -> None:
    conn = init_db(config.db_path)
    pdfs: list[str] = []
    for p in paths:
        pdfs.extend(_find_pdfs(p))

    if not pdfs:
        print("No PDF files found.")
        return

    print(f"Found {len(pdfs)} PDF(s).")
    ok = failed = skipped = 0

    for pdf in pdfs:
        print(f"\n[{ok+failed+skipped+1}/{len(pdfs)}] {os.path.basename(pdf)}")
        t0 = time.perf_counter()
        try:
            doc_id = ingest_pdf(pdf, config, conn, force=force)
            elapsed = time.perf_counter() - t0
            print(f"  ✓  doc_id={doc_id}  ({elapsed:.1f}s)")
            ok += 1
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"  ✗  {exc}  ({elapsed:.1f}s)")
            failed += 1

    print(f"\nDone: {ok} ok, {failed} failed, {skipped} skipped.")


def cmd_list(config: Config) -> None:
    conn = init_db(config.db_path)
    docs = get_docs(conn, limit=200)
    if not docs:
        print("No indexed documents.")
        return
    print(f"{'ID':>4}  {'Pages':>5}  {'Status':<10}  Title")
    print("-" * 60)
    for d in docs:
        print(f"{d['id']:>4}  {d['page_count']:>5}  {d['status']:<10}  {d['title']}")


def cmd_search(query: str, config: Config) -> None:
    conn = init_db(config.db_path)
    results = search_fts(conn, query, limit=20)
    if not results:
        print("No results.")
        return
    print(f"{'doc_id':>6}  {'page':>5}  Snippet")
    print("-" * 70)
    for r in results:
        snippet = r["snippet"].replace("\n", " ")[:60]
        print(f"{r['doc_id']:>6}  {r['page']:>5}  {snippet}")


def main() -> None:
    parser = argparse.ArgumentParser(description="pdflash ingestion CLI (M1)")
    parser.add_argument("paths", nargs="*", help="PDF file(s) or director(ies) to ingest")
    parser.add_argument("--reindex", action="store_true", help="Force re-index even if already indexed")
    parser.add_argument("--list", action="store_true", help="List all indexed documents")
    parser.add_argument("--search", metavar="QUERY", help="Run a quick FTS search")
    parser.add_argument("--data-dir", default=None, help="Override PDFLASH_DATA_DIR")
    parser.add_argument("--pdf-dir",  default=None, help="Override PDFLASH_PDF_DIR")
    parser.add_argument("--workers",  type=int, default=None, help="Override PDFLASH_WORKERS")
    args = parser.parse_args()

    config = Config()
    if args.data_dir:
        config.data_dir = args.data_dir
    if args.pdf_dir:
        config.pdf_dir = args.pdf_dir
    if args.workers:
        config.workers = args.workers

    if args.list:
        cmd_list(config)
    elif args.search:
        cmd_search(args.search, config)
    elif args.paths:
        cmd_ingest(args.paths, config, force=args.reindex)
    else:
        parser.print_help()


# Required on Windows so ProcessPoolExecutor workers don't re-execute main()
if __name__ == "__main__":
    main()
