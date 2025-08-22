# onyx-pipeline

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
