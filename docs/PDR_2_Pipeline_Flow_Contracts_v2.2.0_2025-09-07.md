# PDR 2: Pipeline Flow & Contracts (Authoritative)
**Version:** 2.2.0  
**Date:** 2025-09-07  
**Scope:** Phases 1-5 (Onyx Scribe, Golden Pipeline Core, Ritual Player UI) + Out-of-Band Enrichment (Phase E)  
**Author:** AI Assistant

---

## 1. Executive Summary & North Star
This PDR details the sequential execution, inter-phase contracts, and gating for the Golden Pipeline. Version 2.2.0 preserves the deterministic pipeline (Phases 1-5) and introduces a separate Enrichment Tool (Phase E) that can call AI APIs to pre-compute a frozen cache consumed offline by Phase 3. This design reconciles semantic lift with pipeline determinism.

North Star: Deterministic, faithful, and scholarly - rituals become guided experiences, symbols become comparative knowledge, and every derived fact is traceable to source text with explicit provenance.

---

## 2. Global Invariants (Non-Negotiable)
- Determinism: Given identical inputs (corpus bytes + code + config + dataset cache), every pipeline run produces byte-for-byte identical artifacts.
- No Wall-Clock: No timestamps, UUIDs, or uncontrolled random seeds in deterministic artifacts or their generation. All random operations must use a fixed, configurable seed.
- IDs & Ordering:
  - doc_id: doc_<sha256[:12]> from canonical content hash.
  - chunk_id: <doc_id>_<zeroPaddedSeq5>, strictly monotonic within doc.
  - Collections are canonically sorted (typically by primary ID).
- Schemas: Every artifact conforms to its schema in tools/schemas/.
- Environment:
  - PYTHONHASHSEED=0 must be set for all pipeline executions.
  - No Network Calls in Phases 1-4. Any online operation is confined to Phase E tooling.
- Fidelity & Provenance: Every derived record maintains explicit traceability back to its doc_id via source_chunk_id and, where applicable, character spans within the chunk.
- Dataset Inputs: datasets/phase3/enrichment_cache.jsonl is a read-only, deterministic input to the pipeline. Its digest is pinned in metrics_phase3.json.

---

## 3. Phase 1 - Onyx Scribe: Freeze / Ingest -> artifacts/phase1/
Goal: Ingest multi-modal sources; extract canonical text, metadata, and binary assets; establish ground-truth manifests.

Scripts (Strict Order):
1. onyx_scribe/manifest_builder.py
2. onyx_scribe/document_processor.py (Multi-Modal Ingestion Policy)
3. onyx_scribe/phase1_gate.py

Artifacts (Exact, UTF-8 + LF):
- manifest.jsonl: Canonical list of processed documents with metadata and content hash.
- chunks.jsonl: Deterministic text chunks with source_doc_id.
- events.jsonl: Processing events/logs per document (text_layer, ocr_full, text_direct, audio_cataloged).
- quarantine.jsonl: Records of documents/pages that failed processing.
- media_assets.jsonl: Manifest of extracted or primary binary media (images, audio) with content hashes (asset_id) and source_doc_id.

Multi-Modal Ingestion Policy (Deterministic, Per-File):
- PDF (.pdf): Extract text layer + embedded images (images hashed into asset_ids). Compute text metrics and select mode: TEXT_LAYER, OCR_FULL, or OCR_RESCUE based on thresholds in config.ingestion.pdf. Chunk final text; log decision in events.jsonl.
- Images (.png, .jpg, .tiff): Treat image as an asset; record in media_assets.jsonl. Perform pinned OCR; chunk OCR text; log status as ocr_full.
- Audio (.mp3, .flac, .wav): Record audio as an asset; transcribe with a pinned local model; log status as audio_cataloged. Contract: audio_cataloged docs MUST have zero chunks.
- Plain Text (.txt, .md): Normalize text; chunk directly; log status text_direct.

Gate (Fail Fast):
- Schema conformance; manifest/events parity; duplicate detection; ordering and encoding checks.
- Media Manifest Integrity: Every doc_id in media_assets.jsonl exists in manifest.jsonl.
- Ingestion Evidence: Every events.status is valid per config.
- No Blank Chunks: chunks.jsonl must not contain empty text.
- Contract: audio_cataloged MUST have zero chunks; text_layer/ocr_full/text_direct MUST have >=1 chunk.
- CLI: onyx phase1 orchestrates script execution and the gate.

---

## 4. Phase 2 - Onyx Scribe: Index / Enrichment -> artifacts/phase2/
Goal: Build search indices and embeddings; generate granular provenance.

Scripts (Strict Order):
1. onyx_scribe/search_indexer.py
2. onyx_scribe/embedding_generator.py
3. onyx_scribe/entity_recognizer.py
4. onyx_scribe/provenance_builder.py
5. onyx_scribe/phase2_gate.py

Artifacts (Exact):
- search/bm25.index: Pre-computed BM25 index from chunks.jsonl.
- embeddings.<model_slug>.jsonl: Embeddings per chunk_id (pinned model slug, e.g., localhash-8d-v1).
- entity_index.jsonl: Raw discovered entities linked to source_chunk_id.
- provenance.jsonl: Traceability for each chunk_id, including ingestion method logged in Phase 1.

Contracts:
- Embeddings & provenance maintain 1:1 alignment with chunks.jsonl, sorted by chunk_id.
- entity_index entries reference valid source_chunk_id s.

Gate (Fail Fast):
- Schema conformance; counts parity vs. chunks.jsonl; ordering and model slug checks.
- Single embeddings file enforcement: exactly one embeddings.<model_slug>.jsonl present.
- Entity Traceability: All entities trace back to valid chunk_id s.

CLI: onyx phase2 orchestrates script execution and the gate.

---

## 5. Phase 3 - Golden Pipeline: Parser Plugins -> artifacts/phase3/
Goal: Convert text chunks into structured knowledge (entities, correspondences, ritual steps) offline, consuming the frozen enrichment cache.

Scripts (Strict Order):
1. golden_pipeline/entity_parser.py
2. golden_pipeline/correspondence_parser.py
3. golden_pipeline/ritual_step_parser.py
4. golden_pipeline/doc_metadata_parser.py
5. golden_pipeline/phase3_gate.py

Artifacts (Exact):
- entities.jsonl: Canonical entities with type, raw_value, norm_value, source_chunk_id, and char spans; produced deterministically from lexicons/*.yaml.
- correspondences.jsonl: Links between entities with source_chunk_id and derivation rule.
- ritual_steps.jsonl: Structured steps (actions, objects, materials, timing, notes) with spans and order.
- doc_metadata.jsonl: Deterministically parsed metadata from paths/titles.
- Auxiliary: metrics_phase3.json (counts, rule coverage, cache sha256).

Contracts:
- Cache-First: All semantic extractions must be derivable solely from datasets/phase3/enrichment_cache.jsonl and Phase-1 text.
- Span Accuracy: Entities and steps include char_start/char_end within the source chunk.
- Normalization: Deterministic normalization maps (pinned in tools/normalization/*.yaml) generate norm_values and drive entity_id hashes.

Gate (Fail Fast):
- Schema conformance for all artifacts.
- Referential integrity: All source_chunk_id s exist in Phase-1 chunks.jsonl. All correspondence entity IDs exist in entities.jsonl.
- Span fidelity: raw_value must exactly match chunk text [char_start:char_end]; random spot-check performed.
- Density guardrails: Fail if >X% of text-bearing docs produce zero entities and zero steps.
- Ordering checks: All artifacts sorted by their primary IDs.
- Cache digest verification: sha256(enrichment_cache.jsonl) must match metrics_phase3.json.

CLI: onyx phase3 (offline; uses cache), orchestrates scripts and gate.

---

## 6. Phase E - Enrichment (Out-of-Band Tooling) -> datasets/phase3/enrichment_cache.jsonl
Goal: Populate a deterministic cache of AI responses keyed to chunks and prompt templates. This tool is not part of the pipeline and is never run in CI.

CLI: onyx enrich (or onyx enrich phase3)  
Inputs: Phase-1 chunks.jsonl, config prompt templates.  
Outputs: datasets/phase3/enrichment_cache.jsonl (sorted; UTF-8; LF).

Operational Contract:
- API Key: Read from environment (e.g., OPENAI_API_KEY). Never written to disk.
- Pinned Model & Settings: e.g., model: gpt-4o-2024-08-06, temperature: 0.0, seed: 12345, max_tokens: pinned.
- Structured Outputs: Model returns JSON conforming to cache schema; store raw response + metadata: {chunk_hash, prompt_hash, model, seed, system_fingerprint, raw_response}.
- No Timestamps: Do not record variable wall-clock values; use stable sentinels if needed.
- Rate & Retry: Deterministic retry policy; duplicate prevention via cache lookup.
- Sorting & Format: Entire cache file is re-written deterministically on update.

---

## 7. Phase 4 - Golden Pipeline: Orchestration -> artifacts/phase4/
Goal: Assemble deterministic kits (RAW + LEAN), collapse adjacent identical actions, and emit cross-reference & index artifacts.

Scripts (Strict Order):
1. golden_pipeline/kit_assembler.py (produces RAW + LEAN kits + derivations/collapse_map.jsonl)
2. golden_pipeline/crosslinker.py (produces crosslinks.jsonl)
3. golden_pipeline/kit_indexer.py (produces kit_index.jsonl)
4. golden_pipeline/phase4_gate.py (enforces completeness + fidelity)

Artifacts (Exact, Contract):
- kits/<kit_id>.kit.json (schema: kit.raw.v1)
- kits/<kit_id>.kit.lean.json (schema: kit.lean.v1)
- kit_index.jsonl (one record per kit; sorted by kit_id)
- crosslinks.jsonl (mandatory if any kit exists; types: kit_step, kit_doc)
- derivations/collapse_map.jsonl (trace map: lean_index -> source step IDs)

Removed / Deprecated:
- kits.index.json (legacy; produced only by deprecated scripts/build_kits.py; excluded from contract)
- gold/ directory outputs (deprecated experimental curation; removed from contract surface)

Gate (Fail Fast):
- Parity: Every kit in manifest has RAW + LEAN if its source docs yielded ritual steps.
- Crosslinks Presence: crosslinks.jsonl must exist & be non-empty when kits exist.
- Referential Integrity: kit step_ids & doc_ids resolve to Phase 3 / Phase 1 artifacts.
- Span Fidelity: RAW step spans must match underlying chunk substring exactly (hallucination rate = 0).
- Prerequisite Isolation: link_only prerequisites' doc_ids never appear in dependent kits' RAW steps.
- Collapse Determinism: collapse_map entries align 1:1 with lean step groups.

CLI: onyx assemble_kits (Phase 4 partial) or full pipeline run.

---

## 8. Phase 5 - Ritual Player UI: Display -> artifacts/phase5/
Goal: Generate deterministic UI catalog & asset manifest and emit pipeline-wide digest for reproducibility.

Scripts (Strict Order):
1. ritual_player/ui_data_generator.py
2. ritual_player/asset_manifest_builder.py
3. ritual_player/phase5_gate.py
4. (internal) pipeline digest writer (appended after gate)

Artifacts (Exact, Contract):
- ui_catalog.jsonl (sorted by id)
- assets_manifest.jsonl (sorted by (source_doc_id, asset_id))
- pipeline_digest.jsonl (each line: {path, sha256}; sorted by path; excludes aux/ & legacy files)

Gate (Fail Fast):
- Schema Conformance (ui_catalog, assets_manifest).
- Catalog Completeness: Every kit in phase4/kit_index.jsonl appears once in ui_catalog.jsonl.
- Asset Referential Integrity: All referenced primary_asset_id / asset_ids exist in assets_manifest.jsonl.
- Ordering Checks: ui_catalog.jsonl sorted by id; assets_manifest.jsonl sorted.
- (Digest validated indirectly by determinism CI; not gated to avoid self-reference timing.)

CLI: onyx phase5.

---

## 9. Auxiliary & Exclusions
Explicitly excluded from contract / pipeline_digest:
- *.sample.jsonl (example or reference payloads)
- quarantine_triage.jsonl (human triage workspace)
- gold/ (deprecated curation outputs)
- kits.index.json (legacy)
- artifacts/aux/** (future auxiliary staging directory)

Auxiliary files MAY exist but gates must ignore them; they must never influence contract artifact content.

## 10. Gold Path (Full Pipeline 1->5)
```bash
onyx pipeline run --root "Library" --artifacts "artifacts" --config "config/onyx.yml"
```

---

## 11. Config Canon (config/onyx.yml, Extended)
```yaml
root: "Library"
patterns:
  - "**/*.pdf"
  - "**/*.png"
  - "**/*.jpg"
  - "**/*.mp3"
  - "**/*.txt"
encoding: "utf-8"

ingestion:
  pdf:
    parser_engine: "pypdf_v3.1.0"
    min_text_chars_per_page: 40
    doc_nonempty_ratio_min: 0.02
    doc_min_total_chars: 500
    partial_rescue: false
  image:
    ocr_engine: "tesseract_v5.3.0"
    ocr_model_slug: "eng+osd"
  audio:
    transcription_engine: "whisper_v20231117"
    transcription_model_slug: "base.en"
    transcription_temperature: 0.0

phase1:
  chunking:
    target_chars: 1200
    overlap: 120
    split_on: ["\n\n", "\n", ". ", "; ", ", "]

phase2:
  bm25: { k1: 1.2, b: 0.75 }
  embeddings:
    model: "localhash-8d-v1"
    batch_size: 256
    normalize: true

phase3:
  require_cache: true
  ruleset_slug: "v1"
  normalization_map: "norm-map-v1.yaml"

paths:
  artifacts_phase1: "artifacts/phase1"
  artifacts_phase2: "artifacts/phase2"
  artifacts_phase3: "artifacts/phase3"
  artifacts_phase4: "artifacts/phase4"
  artifacts_phase5: "artifacts/phase5"
  schemas: "tools/schemas"
  enrichment_cache: "datasets/phase3/enrichment_cache.jsonl"

environment_guards:
  disallow_network_calls_in_phases: [1, 2, 3, 4]
  pythonhashseed: "0"

auxiliary:
  phase1_metrics: false
  phase2_bm25_digest: false
```

---

## 12. Acceptance Criteria (Per PR / Release)
- Baseline Empty: artifacts/phase{1-5}/ contain only .gitkeep on default branch.
- Gates Pass: All pipeline gates (P1-P5) pass on onyx pipeline run.
- Determinism Proven: CI job runs the pipeline twice and asserts byte-identical outputs.
- Multi-Modal Compliance: Phase 1 processes all configured file types; produces correct text/media artifacts.
- Cross-Phase Referential Integrity: All IDs resolve correctly across phases.
- Cache Digest Pin: metrics_phase3.json records sha256 of the enrichment cache and the gate verifies it.
- Network Isolation: CI ensures no network calls occur in Phases 1-4; enrichment is never invoked by CI.

Additional Phase 4 Ritual Compiler Criteria:
- Span Fidelity: Hallucination rate = 0 (every RAW kit step span matches underlying chunk substring exactly).
- Prerequisite Isolation: link_only prerequisite kits' steps are not inlined into dependent kits.
- Determinism Digest: pipeline_digest.jsonl present and stable across repeated runs.

