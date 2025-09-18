## Onyx Hall / Onyx Scribe – AI Assistant Working Rules

Focus: Deterministic multi‑phase pipeline converting `Library/` corpus into stable JSONL artifacts consumed by a Phase 5 desktop app. Every change must preserve artifact contracts (see PDR docs in `docs/`). Avoid introducing nondeterminism (no random seeds, no network calls inside Phases 1–4 & 5 orchestration).

### 1. Architecture Snapshot
Phases & ownership:
1. Phase 1 (`onyx_scribe.phase1`): Ingest + chunk + manifest. Outputs in `artifacts/phase1/` (`manifest.jsonl`, `chunks.jsonl`, `events.jsonl`, `quarantine.jsonl`, `media_assets.jsonl`, optional `metrics.json`, `qa_report.jsonl`). Gate: `onyx_scribe.phase1_gate`.
2. Phase 2 (`onyx_scribe.phase2`): Search index (BM25), hash embeddings (deterministic), entity index, provenance. Outputs `artifacts/phase2/` (`search/`, `embeddings.<model_slug>.jsonl`, `entity_index.jsonl`, `provenance.jsonl`, optional `metrics_phase2.json`). Gate: `onyx_scribe.phase2_gate.run_phase2_gate` (+ optional digest verifier script `scripts/verify_phase2.py`).
3. Phase 3 (`golden_pipeline.phase3`): Offline parse using enrichment cache (`datasets/phase3/enrichment_cache.jsonl`) + lexicons (`lexicons/*.yaml`). Produces `doc_metadata.jsonl`, `entities.jsonl`, `ritual_steps.jsonl`, `metrics_phase3.json` with pinned cache digest. Gate: `golden_pipeline.phase3_gate`.
4. Phase 4 (`golden_pipeline.kit_assembler`, plus `crosslinker`, `kit_indexer`): Assembles ritual kits & crosslinks. Key outputs `artifacts/phase4/kits/*.kit.json`, `*.kit.lean.json`, `derivations/collapse_map.jsonl`, `kit_index.jsonl`, `crosslinks.jsonl`. Gate: `golden_pipeline.phase4_gate`.
5. Phase 5 (`ritual_player.phase5`): Generates UI catalog + assets manifest (`artifacts/phase5/ui_catalog.jsonl`, `assets_manifest.jsonl`) then gates via `ritual_player.phase5_gate`.
Out‑of‑Band Phase E (`golden_pipeline.enricher`): Networked enrichment to pre-build cache (never called inside deterministic pipeline path).

### 2. Invocation & CLI Patterns
Primary entrypoint: `python -m onyx_scribe.cli <command>` (script installs as `onyx`). Commands: `phase1`, `phase2`, `phase3`, `assemble_kits`, `phase5`, and `pipeline run` (full best‑effort chain). Provide `--config config/onyx.yml` plus optional `--root` & `--artifacts` overrides. After Phase 1 run, gate is immediately enforced; later phases run their gates near the end.

Scripts under `scripts/` are thin helpers (e.g., `verify_phase1.py`, `cleanup_phase2_embeddings.py`, `build_phase5_ui.py`, `triage_quarantine.py`). Prefer calling the orchestrated functions unless reproducing legacy CI behavior.

### 3. Determinism & Ordering Conventions
* Always write JSONL with `sort_keys=True` and newline `\n`; lists are pre‑sorted explicitly (see Phase 1: sort by `doc_id`, `chunk_id`).
* Phase 1 environment override: `ONYX_PHASE1_MAX_DOCS` limits processed documents for iterative runs (document in any new tooling if honored).
* Entity & kit assembly ordering: explicit stable sort keys (e.g., kit step ordering `(chunk_seq, char_start)`; collapse logic groups adjacent identical canonical actions).
* Never add randomness or time‑based fields to artifacts; any new metadata must be derivable from existing deterministic inputs.

### 4. Lexicon & Parsing Rules
Lexicons live in `lexicons/` (including `ritual_actions.yaml`, `kit_manifest.yaml`, domain profiles `lexicons/domain_profiles/*.yaml`). Entity extraction (Phase 3) performs case-insensitive literal matching, resolves overlaps longest-first, generates deterministic `entity_id` via hash of `(type|norm_value)`. When extending lexicons: keep YAML simple (no regex); preserve ordering; avoid ultra-short ambiguous terms.

### 5. Kit Assembly Nuances (Phase 4)
`kit_assembler` enforces domain profiles: `allowed_actions` filter & `prerequisites` with `link_only` exclusion (do not inline prerequisite kits’ steps). Produces RAW + LEAN variants plus `collapse_map.jsonl` traceability. When modifying logic, keep: (a) stable step ordering, (b) collapse grouping invariant (adjacent identical actions only), (c) prerequisite exclusion semantics (skip only when `kit_id != current`).

### 6. Phase 5 Asset Handling
`ritual_player.phase5` shells out to generators; `build_phase5_ui.py` backfills asset paths by scanning for files whose basenames match `asset_*.` patterns when Phase 1 didn’t record absolute paths. If adding new asset types ensure: (a) deterministic path resolution, (b) JSONL entries include `sha256`, (c) extension guessed via `mimetypes` or explicitly assigned.

### 7. Gate Philosophy & Tests
Gates assert schema presence, referential integrity, ordering, and hash/digest pinning. Any new artifact requires a matching gate assertion to avoid silent drift. In tests: never write under repository `artifacts/`; use temp dirs and pass `--artifacts`. Introduce new pure utility functions where feasible; keep orchestration thin.

### 8. Config Keys of Interest (`config/onyx.yml`)
* `root`, `artifacts_dir` (set/overridden by CLI flags).
* `phase1.max_documents` (optional quick iteration) and `auxiliary.phase1_metrics` / `phase1_qa_report`.
* `phase2.embeddings.model_slug` (drives embeddings filename slug) + `auxiliary.phase2_metrics`.
* `phase3.enrichment_cache` path; `paths.lexicons` override; enrichment cache digest pinned in metrics.

### 9. Safe Extension Patterns
When adding a new derived artifact:
1. Compute from existing committed inputs only.
2. Write deterministically (explicit sort keys/order).
3. Append gate validation (schema + referential checks) before marking phase complete.
4. Document in README Phase table & update this file.

### 10. Common Pitfalls to Avoid
* Forgetting to update gates after adding fields -> nondeterministic drift undetected.
* Using implicit directory existence: always `mkdir(parents=True, exist_ok=True)` like current phases.
* Adding network calls inside phases 1–5 (violates offline contract; only Phase E is allowed network).
* Relying on Python hash randomization: ensure `PYTHONHASHSEED=0` in invoking environment for strict determinism (documented in README).

### 11. Example End‑to‑End (PowerShell)
```powershell
python -m onyx_scribe.cli phase1 --config config/onyx.yml --root Library --artifacts artifacts
python -m onyx_scribe.cli phase2 --config config/onyx.yml --artifacts artifacts
python -m onyx_scribe.cli phase3 --config config/onyx.yml --artifacts artifacts
python -m onyx_scribe.cli assemble_kits --config config/onyx.yml --artifacts artifacts
python -m onyx_scribe.cli phase5 --root Library --artifacts artifacts
```

### 12. Agent Behavior Summary
Do: enforce determinism, extend gates with new artifacts, reuse existing sorting patterns, keep paths configurable. Don’t: introduce randomness, side effects outside artifacts dir, or network dependency in core phases. Keep changes small & schema-aligned.

---
Provide feedback if any section becomes outdated when modifying pipeline code.
