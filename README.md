# Onyx Hall / Onyx Scribe – Golden Pipeline Core

Deterministic multi‑phase knowledge pipeline turning a curated esoteric corpus (`Library/`) into structured, reproducible artifacts. Phases 1–2 (Onyx Scribe) ingest & index. Phases 3–4 (Golden Pipeline) parse & assemble kits. Phase 5 prepares UI payloads. Phase E (out‑of‑band) can pre-compute enrichment caches; the main pipeline itself performs no network calls.

North Star: Immutable Text, Mutable Insight — every derived record is traceable back to stable chunk spans.

---

## High-Level Phases
| Phase | Scope | Key Inputs | Key Artifacts |
|-------|-------|------------|---------------|
| 1 | Ingest / Freeze | `Library/` sources | `manifest.jsonl`, `chunks.jsonl`, `events.jsonl`, `media_assets.jsonl`, `quarantine.jsonl` |
| 2 | Index / Embeddings / Provenance | Phase 1 artifacts | `search/`, `embeddings.<slug>.jsonl`, `entity_index.jsonl`, `provenance.jsonl` |
| 3 | Parsing (Lexicon Entities, etc.) | Phase 1 + `lexicons/` + cache (optional) | `entities.jsonl`, `doc_metadata.jsonl`, `metrics_phase3.json` |
| 4 | Orchestration / Kits | Phase 3 artifacts | `kits/*.kit.json`, `kit_index.jsonl`, `crosslinks.jsonl` |
| 5 | UI Data | Phases 1–4 | `ui_catalog.jsonl`, `assets_manifest.jsonl` |
| E | Enrichment (out-of-band) | Phase 1 chunks | `datasets/phase3/enrichment_cache.jsonl` |

Authoritative structural & flow contracts live in the PDRs under `docs/` (see `PDR_1_*` and `PDR_2_*`).

---

## New: Deterministic Lexicon Engine (Phase 3)
Phase 3 now derives `entities.jsonl` via curated YAML lexicons in `lexicons/`. Each file contributes canonical terms and variants. Extraction rules:
* Case-insensitive literal matching; surfaces preserved as `raw_value`.
* Overlap resolution: longest span first, then left-to-right.
* `entity_id` = `ent_<type-slug>_<sha256[:12]>` computed from `(type|norm_value)` — variants collapse.
* Spans: `char_start` (inclusive) / `char_end` (exclusive) validated against chunk text by the gate (with random spot‑check).

Example entity record:
```json
{
	"entity_id": "ent_tarot-major_a1b2c3d4e5f6",
	"raw_value": "The Fool",
	"norm_value": "The Fool",
	"type": "tarot_major",
	"source_chunk_id": "doc_abc123456789_00001",
	"char_start": 128,
	"char_end": 136
}
```

Add / refine lexicons by editing `lexicons/*.yaml` (tracked, deterministic). All changes must keep ordering stable and avoid introducing regex meta (currently literal matching).

---

## Quick Start (Windows PowerShell)
```powershell
# Phase 1 ingest
python -m onyx_scribe.cli phase1 --root Library --artifacts artifacts --config config/onyx.yml

# Phase 2 indexing
python -m onyx_scribe.cli phase2 --root Library --artifacts artifacts --config config/onyx.yml

# (Optional) produce enrichment cache out-of-band (Phase E tooling not shown)

# Phase 3 parsing (lexicon-driven entities & metadata)
python -m onyx_scribe.cli phase3 --root Library --artifacts artifacts --config config/onyx.yml
```

Set `PYTHONHASHSEED=0` (or ensure the launcher does) to guarantee hashing determinism.

---

## Configuration Highlights (`config/onyx.yml`)
Key sections:
* `root` – corpus root (`Library`).
* `phase1.chunking` – deterministic chunk size & overlap.
* `phase2.embeddings.model_slug` – drives embeddings file name.
* `phase3.enrichment_cache` – location of optional frozen semantic cache.
* `paths.lexicons` – points to `lexicons/` directory.
* `auxiliary.phase1_qa_report` / `phase1_metrics` – enable extra Phase 1 outputs.

---

## Enable the Phase 1 QA Report
In `config/onyx.yml` set:
```yaml
auxiliary:
	phase1_metrics: true
	phase1_qa_report: true
```
Run Phase 1; if any OCR content was produced you'll get `artifacts/phase1/qa_report.jsonl`.

---

## Quarantine Triage Workflow
Categorize problem documents and optionally relocate irrecoverable ones:
```powershell
python scripts/triage_quarantine.py artifacts --library-root Library --move-unrecoverable
```
Outputs:
* `artifacts/phase1/quarantine_triage.jsonl`
* Moves Category A items to `Library/.quarantined/` when `--move-unrecoverable` is supplied.

Fix encoding issues (Category B) by rewriting as UTF‑8:
```powershell
python scripts/fix_encoding.py artifacts --library-root Library --dry-run
python scripts/fix_encoding.py artifacts --library-root Library
```

---

## Gates & Determinism
Each phase ends with a gate script that enforces:
* JSON Schema conformance
* Ordering and ID invariants
* Referential integrity across artifacts
* Hash pinning (e.g., enrichment cache digest in Phase 3 metrics)
* Span fidelity (Phase 3 entities)

CI (future) should re-run phases to assert byte-identical artifacts. No network access is allowed inside Phases 1–4.

---

## Testing Philosophy (PDR-Aligned)
Determinism and a pristine baseline are core invariants:
* Never write to the repo-root `artifacts/` in tests.
* Always isolate via `tmp_path` or `TemporaryDirectory`.
* Pass explicit `--artifacts` pointing to a temp dir.
* Destructive operations scoped to temp dirs only.
* Favor pure functions; integration tests prove orchestration.

Violations are treated as gate failures for test contributions.

---

## Contributing Lexicons
1. Keep YAML structure: `terms: - category: <type> canonical: <Canonical Name> variants: [..]`.
2. Avoid ambiguous ultra-short tokens that cause high false-positive density.
3. Prefer adding disambiguating variants (e.g., "Sun (Tarot)") instead of removing canonical forms.
4. Run Phase 3 locally; ensure gate passes with span fidelity.

---

## Roadmap (Excerpt)
* Phase 3: Add correspondence & ritual step parsers.
* Phase 4: Kit assembly & crosslink density heuristics.
* Phase 5: UI payload compaction.
* Optional: cache-derived semantic augmentation for entities beyond lexicon surface matches.

---

## License
TBD.

---

## Attribution
Generated & maintained with deterministic build principles and automated assistance.


## Library
The `library/` folder at the repository root is excluded from version control. Place your local PDFs, scans, or images here before running the pipeline. This keeps the repository small, clean, and safe to share, avoiding version history bloat and protecting private or rare texts.

Notes:
- The default corpus path used in examples is `Library/` (capitalized) included in this repo for sample structure. You can use the local `library/` directory instead and point the CLI accordingly via `--root library` or configure in `config/onyx.yml`.
- Common binary formats (e.g., `*.pdf`, `*.tif(f)`, images, and archives) are ignored by `.gitignore`.

