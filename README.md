# onyx-pipeline

[![ci](https://github.com/parryio/onyx-pipeline-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/parryio/onyx-pipeline-demo/actions/workflows/ci.yml)

Deterministic, manifest‑first document ingestion & indexing pipeline (“safe mode”) focused on reproducibility, atomic writes, and observable runs.

## Features
* Manifest builder (stable JSONL schema) with deterministic file hashing & doc IDs.
* PDF harvest (metadata + optional image stub dir) & text extraction (PyMuPDF) with OCR gate + engine (pytesseract) – graceful fallback.
* Deterministic chunking rules (`chunks@v2`) and metas index (`metas@v3`).
* Search primitives: BM25 placeholder + deterministic pseudo‑embeddings (8192‑d) for repeatable tests.
* Quarantine recording (`quarantine.jsonl`) for exception / no‑text documents with reasons & stage.
* Structured event log (`reports/events.jsonl`) + consolidated run summary (`reports/run_summary.json`) including timings, counts, schema versions, warnings.
* Idempotent reruns (already‑produced immutable artifacts reused, no duplication).
* Strict validation (counts, orphan detection) and atomic write helpers.
* Inspect CLI for quick introspection of a single document’s manifest row, meta, and first chunk(s).

## Overview Diagram
```mermaid
flowchart LR
  A[Library files] --> B[Manifest build\nmanifest.jsonl (stable IDs)]
  B --> C[Harvest & Text]
  C -->|no text| D[OCR gate -> pytesseract]
  C -->|has text| E[Text pass]
  D --> F[Chunks @v2]
  E --> F
  F --> G[Metas @v3]
  F --> H[BM25]
  F --> I[Deterministic embeddings]
  subgraph Reports
    J[events.jsonl]:::rep --> K[run_summary.json]:::rep
  end
  F --> J
  classDef rep fill:#eef,stroke:#99f
```

## Quick Start (PowerShell)
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .[ocr]   # add [ocr] to enable pytesseract (optional)

# 1. Build manifest (stream library -> manifest.jsonl)
onyx-manifest build --lib .\tests\fixtures --out .\out

# 2. Run full pipeline (manifest -> harvest -> text/OCR -> chunks -> metas -> bm25 -> embeddings -> validate)
onyx-pipeline run --lib .\tests\fixtures --out .\out --ocr-lang eng --include-images

# 3. Validate (exit !=0 on errors)
onyx-validate --out .\out

# 4. Inspect a specific document (doc_id inferred from hash)
onyx-inspect --out .\out --doc-id <DOC_ID>
```

## Dual Demo (Fast vs. Long OCR Book)
You can run a quick, seconds-long demo on the tiny sample fixtures, or a longer OCR-intensive demo using a scanned book PDF you supply. Each run writes to its own timestamped directory under `runs/` so the project root stays clean.

### 1. Place Long Demo PDF
Add your scanned book PDF to: `tests/fixtures_long/scanned_book.pdf` (create the folder if needed). Keep it out of git if it's large.

### 2. Run Short Demo
```bash
bash scripts/demo-short.sh
```
Produces: `runs/<UTC_ISO_TIMESTAMP>-short/` (locally) or `runs/short/` in CI with manifest, chunks, metas, embeddings, bm25, reports.

### 3. Run Long (OCR) Demo
```bash
bash scripts/demo-long.sh
```
Produces: `runs/<UTC_ISO_TIMESTAMP>-long/` (locally) or `runs/long/` in CI – suitable for narrating stages; you can `tail -f runs/<...>/reports/events.jsonl` for live events.

### 4. Inspect a Doc (optional)
After a demo you can inspect the first doc:
```bash
DOC_ID=$(basename -s .jsonl $(ls runs/*-short/chunks@v2/*.jsonl | head -n1))
onyx-inspect --out $(ls -d runs/*-short | tail -n1) --doc-id "$DOC_ID"
```

### 5. Prune Old Runs
```bash
bash scripts/prune-runs.sh   # removes runs older than 7 days
```

## Release Playbook (example for v0.1.0)
```bash
zip -r runs-short.zip runs/short 2>/dev/null || true  # optional attachment
git tag v0.1.0
git push origin v0.1.0
# Draft GitHub release -> paste summary below
```
Release notes template:
> First public cut. Manifest-first deterministic pipeline with atomic writes, OCR fallback, quarantine, and validation. Dual demos (short/long), CI on push, scheduled long demo. Outputs: manifest.jsonl, chunks@v2, metas@v3, reports/*, BM25 + deterministic embeddings for tests.



## Produced Artifacts
```
out/
  manifest.jsonl
  docs@v1/                # per-doc harvested assets (e.g. pdf meta, optional images stub)
  images@v1/              # (optional) placeholder image harvest output
  chunks@v2/              # one <doc_id>.jsonl per doc (lines = chunks)
  metas@v3/metas.index.jsonl
  embeddings/             # embeddings.npy + rowmap.jsonl
  bm25_index.pkl / bm25.meta.json
  quarantine.jsonl        # JSONL records of quarantined docs (reason, stage)
  reports/
    events.jsonl          # streaming event log
    run_summary.json      # consolidated summary (timings, counts, schema versions)
```

## Run Summary (`reports/run_summary.json`)
Contains:
* `version` (summary schema) & per‑component schema versions
* `counts`: docs, chunks, metas, (optional) quarantine count
* `timings`: per stage elapsed seconds
* `warnings`: structured warning objects (if any)
* `duration_s`, `started_at`, `finished_at`

## Quarantine
`quarantine.jsonl` entries look like:
```json
{"doc_id": "abc123...", "path": "sample.pdf", "reason": "no_text_after_ocr", "stage": "ocr", "timestamp": 1730000000.123}
```
Reasons today: `no_text_after_ocr`, `exception` (plus optional `error`).

## Inspect CLI
```
onyx-inspect --out .\out --doc-id <DOC_ID> [--preview-chunks 3]
```
Prints JSON with manifest row, meta row, and first N chunk texts (truncated) for quick debugging.

## Directory Layout (source)
```
src/onyx_pipeline/
  manifest/   harvest/   text/   chunking/   metas/
  search/     reporting/ storage/ validate/  cli/
```

## Determinism Notes
* Doc IDs derived from file SHA256 (stable across runs if content unchanged).
* Component outputs written atomically (`.tmp` + replace) to avoid partial files.
* Embeddings deterministic via fixed RNG seed.

## License
Apache-2.0
