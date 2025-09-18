#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, Dict, Any, List, Optional

SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
    id UNINDEXED,
    title,
    authors,
    type,
    tags,
    summary,
    body,
    path UNINDEXED,
    tokenize='porter'
);
"""
PRAGMAS = ["PRAGMA journal_mode=WAL;", "PRAGMA synchronous=NORMAL;"]

def connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    for p in PRAGMAS:
        conn.execute(p)
    conn.execute(SCHEMA)
    return conn

def _as_list(x):
    if x is None: return []
    if isinstance(x, list): return x
    return [x]

def normalize(rec: Dict[str, Any]) -> Dict[str, str]:
    title = rec.get("title") or rec.get("name") or Path(rec.get("path", "")).stem
    authors = rec.get("authors") or rec.get("author") or []
    authors = ", ".join(_as_list(authors))
    rtype = rec.get("type") or rec.get("media_type") or Path(rec.get("path", "")).suffix
    tags = rec.get("tags") or rec.get("keywords") or []
    tags = ", ".join(sorted(set(t.strip() for t in _as_list(tags) if t)))
    summary = rec.get("summary") or rec.get("description") or ""
    body = rec.get("notes") or rec.get("content") or ""
    path = rec.get("path") or rec.get("file") or rec.get("url") or ""
    _id = rec.get("id") or rec.get("doc_id") or f"{title}|{path}"
    return dict(id=str(_id), title=str(title), authors=str(authors), type=str(rtype),
                tags=str(tags), summary=str(summary), body=str(body), path=str(path))

def ingest_jsonl(conn: sqlite3.Connection, jsonl_paths: List[Path], ignore_ids: set[str] | None = None) -> int:
    cur = conn.cursor()
    n = 0
    all_ids = set()
    
    for jsonl in jsonl_paths:
        if not jsonl.exists():
            print(f"Warning: Ingest file not found: {jsonl}", file=sys.stderr)
            continue
        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    rec = normalize(json.loads(line))
                    if (ignore_ids and rec["id"] in ignore_ids) or rec["id"] in all_ids:
                        continue
                    
                    all_ids.add(rec["id"])
                    cur.execute("DELETE FROM docs WHERE id = ?", (rec["id"],))
                    cur.execute(
                        "INSERT INTO docs (id,title,authors,type,tags,summary,body,path) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (rec["id"], rec["title"], rec["authors"], rec["type"], rec["tags"],
                         rec["summary"], rec["body"], rec["path"])
                    )
                    n += 1
                except json.JSONDecodeError:
                    print(f"Warning: Skipping malformed JSON line in {jsonl}", file=sys.stderr)
                    continue
    conn.commit()
    return n

def ingest_chunks(conn: sqlite3.Connection, chunk_path: Path) -> int:
    """Aggregate chunk texts per doc and populate/append into body field.
    Returns number of documents whose body was updated."""
    if not chunk_path or not chunk_path.exists():
        print(f"Warning: chunks file not found: {chunk_path}", file=sys.stderr)
        return 0
    doc_parts: Dict[str, List[str]] = {}
    ln = 0
    with open(chunk_path, 'r', encoding='utf-8') as f:
        for line in f:
            ln += 1
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                if ln < 10:
                    print(f"Warning: malformed JSON in chunks line {ln}", file=sys.stderr)
                continue
            doc_id = rec.get('doc_id') or rec.get('source_doc_id')
            text = rec.get('text') or ''
            if not doc_id or not text:
                continue
            # Light normalization: collapse Windows newlines already handled by universal newlines
            doc_parts.setdefault(str(doc_id), []).append(text.strip())
    cur = conn.cursor()
    updated = 0
    for doc_id, parts in doc_parts.items():
        body_text = '\n'.join(parts)
        # Fetch existing body (if any) and append only if different length (avoid repeated ingestion duplication)
        row = cur.execute("SELECT body FROM docs WHERE id = ?", (doc_id,)).fetchone()
        if row:
            existing = row[0] or ''
            if len(existing) >= len(body_text) * 0.9:  # heuristic: skip if we already have comparable size
                continue
            cur.execute("UPDATE docs SET body = ? WHERE id = ?", (body_text, doc_id))
            updated += 1
        else:
            # Minimal insert (unknown other fields)
            cur.execute("INSERT INTO docs (id,title,authors,type,tags,summary,body,path) VALUES (?,?,?,?,?,?,?,?)",
                        (doc_id, doc_id, '', '', '', '', body_text, ''))
            updated += 1
    conn.commit()
    return updated

def ingest_doc_metadata(conn: sqlite3.Connection, metadata_paths: List[Path]) -> int:
    """Merge metadata-derived tags into existing doc rows. Returns number of docs updated."""
    if not metadata_paths:
        return 0
    cur = conn.cursor()
    updated = 0
    for mp in metadata_paths:
        if not mp.exists():
            print(f"Warning: metadata file not found: {mp}", file=sys.stderr)
            continue
        with open(mp, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                doc_id = rec.get('doc_id')
                meta = rec.get('metadata') or {}
                if not doc_id or not isinstance(meta, dict):
                    continue
                # Collect candidate tag values
                meta_values: List[str] = []
                for k, v in meta.items():
                    if isinstance(v, str) and v.strip():
                        meta_values.append(v.strip())
                    elif isinstance(v, list):
                        meta_values.extend(str(x).strip() for x in v if str(x).strip())
                if not meta_values:
                    continue
                row = cur.execute("SELECT tags FROM docs WHERE id = ?", (doc_id,)).fetchone()
                existing_tags = []
                if row:
                    existing_tags = [t.strip() for t in (row[0] or '').split(',') if t.strip()]
                merged = sorted(set(existing_tags + meta_values))
                if not row:
                    # Insert skeleton row if missing
                    cur.execute("INSERT INTO docs (id,title,authors,type,tags,summary,body,path) VALUES (?,?,?,?,?,?,?,?)",
                                (doc_id, doc_id, '', '', ', '.join(merged), '', '', ''))
                    updated += 1
                else:
                    if set(existing_tags) != set(merged):
                        cur.execute("UPDATE docs SET tags = ? WHERE id = ?", (', '.join(merged), doc_id))
                        updated += 1
    conn.commit()
    return updated

def read_ignore_set(paths: List[Path]) -> set[str]:
    ignore = set()
    for p in paths:
        if not p.exists(): continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    rec = json.loads(line)
                    _id = rec.get("id") or rec.get("doc_id")
                    if _id: ignore.add(str(_id))
                except json.JSONDecodeError:
                    continue
    return ignore

def search(conn: sqlite3.Connection, q: str, limit: int = 10,
           rtype: Optional[str]=None, tags: Optional[List[str]]=None) -> List[Dict[str, Any]]:
    clauses = ["docs MATCH ?"]
    params: List[Any] = [q]
    if rtype:
        clauses.append("type = ?")
        params.append(rtype)
    if tags:
        for t in tags:
            clauses.append("tags LIKE ?")
            params.append(f"%{t}%")

    where = " AND ".join(clauses)
    
    # Attempt to include snippet from body and bm25 score
    # body column index in schema: id(0) title(1) authors(2) type(3) tags(4) summary(5) body(6) path(7)
    snippet_expr = "snippet(docs, 6, '[', ']', ' … ', 18) AS snippet"
    try:
        conn.execute("SELECT bm25(docs) FROM docs LIMIT 1")
        order_by = "bm25(docs)"
        cols = f"id,title,authors,type,tags,summary,path,{snippet_expr},bm25(docs) AS score"
        keys = ["id","title","authors","type","tags","summary","path","snippet","score"]
    except sqlite3.OperationalError:
        order_by = "rank"
        cols = f"id,title,authors,type,tags,summary,path,{snippet_expr},rank AS score"
        keys = ["id","title","authors","type","tags","summary","path","snippet","score"]

    sql = f"SELECT {cols} FROM docs WHERE {where} ORDER BY {order_by} LIMIT ?"
    rows = conn.execute(sql, (*params, limit)).fetchall()
    
    out: List[Dict[str, Any]] = []
    for r in rows:
        rec = dict(zip(keys, r))
        # Basic cleanup: if snippet empty, skip field
        if not rec.get('snippet'):
            rec.pop('snippet', None)
        out.append(rec)
    return out

def resolve_file_path(raw_path: str) -> Path:
    """Attempt to resolve a stored manifest path to an existing file.
    Tries (in order): absolute path, CWD/raw_path, CWD/Library/raw_path.
    Returns the first existing Path or the last candidate if none exist."""
    if not raw_path:
        return Path(raw_path)
    p = Path(raw_path)
    if p.is_absolute() and p.exists():
        return p
    cwd = Path.cwd()
    cand1 = cwd / raw_path
    if cand1.exists():
        return cand1
    if not raw_path.startswith('Library'):
        cand2 = cwd / 'Library' / raw_path
        if cand2.exists():
            return cand2
    # fall back to original (could be non-existent)
    return p if p.is_absolute() else (cwd / raw_path)

TEXT_EXT = {'.txt', '.md', '.markdown', '.json', '.yaml', '.yml', '.csv', '.tsv'}

def is_small_text_file(path: Path, max_bytes: int = 500_000) -> bool:
    try:
        return path.suffix.lower() in TEXT_EXT and path.is_file() and path.stat().st_size <= max_bytes
    except OSError:
        return False

def main():
    ap = argparse.ArgumentParser(description="Minimal library search (SQLite FTS5).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_ing = sub.add_parser("ingest", help="Ingest JSONL files into the index.")
    ap_ing.add_argument("jsonl", type=Path, nargs='+', help="One or more library JSONL files (e.g., manifest.jsonl).")
    ap_ing.add_argument("--db", type=Path, default=Path("library.db"))
    ap_ing.add_argument("--ignore", type=Path, nargs="*", default=[],
                        help="JSONL files with ids to skip (e.g., quarantine.jsonl).")
    ap_ing.add_argument("--chunks", type=Path, default=None, help="Optional chunks.jsonl to populate full-text body.")
    ap_ing.add_argument("--doc-metadata", dest="doc_metadata", type=Path, nargs='*', default=[],
                        help="Optional doc_metadata.jsonl files to augment tags.")

    ap_q = sub.add_parser("search", help="Query the index.")
    ap_q.add_argument("q", type=str)
    ap_q.add_argument("--db", type=Path, default=Path("library.db"))
    ap_q.add_argument("--limit", type=int, default=10)
    ap_q.add_argument("--type", dest="rtype", type=str, default=None)
    ap_q.add_argument("--tag", dest="tags", action="append", default=[],
                      help="Filter by tag (repeatable).")

    ap_srv = sub.add_parser("serve", help="Run a tiny HTTP API (requires fastapi & uvicorn).")
    ap_srv.add_argument("--db", type=Path, default=Path("library.db"))
    ap_srv.add_argument("--host", default="127.0.0.1")
    ap_srv.add_argument("--port", default=8765, type=int)

    ap_read = sub.add_parser("read", help="Read a document by id (prints text or path).")
    ap_read.add_argument("doc_id", type=str, help="Document id as returned in search results.")
    ap_read.add_argument("--db", type=Path, default=Path("library.db"))
    ap_read.add_argument("--show-path", action="store_true", help="Always show resolved absolute path header before content.")

    args = ap.parse_args()
    db_path = args.db.resolve()

    if args.cmd == "ingest":
        conn = connect(db_path)
        ignore = read_ignore_set(args.ignore)
        n = ingest_jsonl(conn, args.jsonl, ignore_ids=ignore)
        added_chunks = 0
        added_meta = 0
        if getattr(args, 'chunks', None):
            print(f"Integrating chunks from {args.chunks} ...")
            added_chunks = ingest_chunks(conn, args.chunks)
        if getattr(args, 'doc_metadata', None):
            for p in args.doc_metadata:
                print(f"Integrating metadata from {p} ...")
            added_meta = ingest_doc_metadata(conn, args.doc_metadata)
        print(f"Ingested {n} docs; updated {added_chunks} bodies; updated {added_meta} metadata tags into {db_path}")
    elif args.cmd == "search":
        if not db_path.exists():
            print(f"Error: Database file not found at {db_path}. Please run 'ingest' first.", file=sys.stderr)
            sys.exit(1)
        conn = connect(db_path)
        results = search(conn, args.q, limit=args.limit, rtype=args.rtype, tags=args.tags)
        for r in results:
            print(json.dumps(r, ensure_ascii=False))
    elif args.cmd == "serve":
        if not db_path.exists():
            print(f"Error: Database file not found at {db_path}. Please run 'ingest' first.", file=sys.stderr)
            sys.exit(1)
        try:
            from fastapi import FastAPI
            from fastapi.responses import JSONResponse
            import uvicorn
        except ImportError:
            print("Install FastAPI & uvicorn to use the server: pip install 'fastapi>=0.115' 'uvicorn[standard]>=0.30'", file=sys.stderr)
            sys.exit(2)
        
        app = FastAPI(title="Library Search MVP")
        
        @app.get("/search")
        def _search(q: str, limit: int = 10, rtype: Optional[str] = None, tags: Optional[str] = None):
            conn = connect(db_path)
            tag_list = [t.strip() for t in tags.split(",")] if tags else []
            results = search(conn, q, limit=limit, rtype=rtype, tags=tag_list)
            conn.close()
            return JSONResponse(content=results)
            
        print(f"Starting API server on http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.cmd == "read":
        if not db_path.exists():
            print(f"Error: Database file not found at {db_path}. Please run 'ingest' first.", file=sys.stderr)
            sys.exit(1)
        conn = connect(db_path)
        row = conn.execute("SELECT id,title,type,path FROM docs WHERE id = ? LIMIT 1", (args.doc_id,)).fetchone()
        if not row:
            print(f"Error: Document id not found: {args.doc_id}", file=sys.stderr)
            sys.exit(3)
        _id, title, rtype, raw_path = row
        fpath = resolve_file_path(raw_path)
        if args.show_path or True:
            print(f"[id={_id}] [title={title}] [type={rtype}]\nPATH: {fpath}")
        # If it's a small textual file, print its content
        if is_small_text_file(fpath):
            try:
                print("\n----- BEGIN CONTENT -----\n")
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    for line in fh:
                        print(line.rstrip('\n'))
                print("\n----- END CONTENT -----")
            except Exception as e:
                print(f"Warning: Failed to read file content: {e}", file=sys.stderr)
        else:
            print("(Non-text or large file; open with an external viewer.)")
        conn.close()
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
