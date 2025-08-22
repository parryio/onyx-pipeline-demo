from __future__ import annotations

from pathlib import Path
from typing import Any

from .chunking.chunker import chunk_text
from .chunking.rules import ChunkRules
from .config import PipelineConfig
from .harvest.ocr_engine import run_ocr
from .harvest.ocr_gate import needs_ocr
from .harvest.pdf import harvest_pdf
from .ids import doc_dirname_from_path, doc_id_from_hash
from .manifest import builder as manifest_builder
from .manifest.reader import iter_manifest
from .metas.writer import json_line, write_metas_index
from .reporting import logger as event_logger
from .reporting.events import Event, make_event
from .reporting.quarantine import write_quarantine_record
from .reporting.summary import RunSummary, SummaryBuilder, build_summary, persist_run_summary
from .search.bm25 import write_bm25
from .search.embeddings import build_embeddings
from .storage import paths
from .storage.atomic import atomic_write_bytes, atomic_write_lines
from .text.extract_pdf import extract_pdf_text
from .validate.validator import validate


class Orchestrator:
    """Pipeline orchestrator implementing deterministic safe-mode run.

    The classmethod `run` is the canonical entrypoint returning a summary dict.
    Instance method `_run_internal` retains backward compatibility for tests.
    """

    def __init__(self, config: PipelineConfig, *, prefer_text_first: bool = True):
        self.config = config
        self.rules = ChunkRules()
        self.events: list[Event] = []
        self.prefer_text_first = prefer_text_first

    # ------------------ logging helpers ------------------ #
    def _log(self, stage: str, type_: str, **payload) -> None:
        # Create and record event (both in-memory and append to events file)
        ev = make_event(stage, type_, **payload)
        self.events.append(ev)
        events_file = self.config.out_root / "reports" / "events.jsonl"
        event_logger.log_event(ev, events_file=events_file)

    # ------------------ stages ------------------ #
    def build_manifest(self) -> Path:
        m_path = paths.manifest_path(self.config.out_root)
        if m_path.exists():
            self._log("manifest", "reuse", path=str(m_path))
            return m_path
        rows = manifest_builder.scan_library(self.config.lib_root, self.config.out_root)
        manifest_builder.write_manifest_jsonl(rows, m_path)
        self._log("manifest", "built", rows=len(rows))
        return m_path

    def _maybe_harvest_images(self, src_path: Path) -> None:
        if not self.config.include_images or src_path.suffix.lower() != ".pdf":
            return
        doc_dirname = doc_dirname_from_path(src_path)
        img_dir = paths.images_dir(self.config.out_root, doc_dirname)
        img_dir.mkdir(parents=True, exist_ok=True)
        # placeholder deterministic stub image marker
        atomic_write_bytes(img_dir / "_stub.info", b"stub")
        self._log("harvest", "images_stub", path=str(img_dir))

    def _extract_or_ocr(self, src_path: Path, prefer_text_first: bool) -> list[str]:
        pages: list[str] = []
        if src_path.suffix.lower() == ".pdf" and prefer_text_first:
            self._log("text", "extract_start", file=str(src_path))
            pages = extract_pdf_text(src_path)
            self._log("text", "extract_done", file=str(src_path), pages=len(pages))
        if not pages and src_path.suffix.lower() == ".pdf" and needs_ocr(src_path):
            self._log("ocr", "start", file=str(src_path))
            pages = run_ocr(src_path, self.config.ocr_lang)
            self._log("ocr", "done", file=str(src_path), pages=len(pages))
        if not pages and src_path.suffix.lower() != ".pdf":
            pages = [src_path.read_text(encoding="utf-8", errors="ignore")]
        if not pages and src_path.suffix.lower() == ".pdf":  # fallback raw
            pages = []
        return pages

    # ------------------ run core ------------------ #
    def _run_internal(self) -> RunSummary:
        self.config.ensure()
        sb: SummaryBuilder = SummaryBuilder()
        sb.stage_start("manifest")
        m_path = self.build_manifest()
        sb.stage_end("manifest")
        all_chunks: list[dict[str, Any]] = []
        metas_rows: list[dict[str, Any]] = []
        docs_processed = 0
        sb.stage_start("docs")
        for row in iter_manifest(m_path):
            doc_id = doc_id_from_hash(row["file_hash"])  # deterministic id
            src_path = self.config.lib_root / row["path"]
            try:
                if row["doc_type"] == "pdf":
                    self._log("harvest", "pdf_start", path=row["path"])
                    harvest_pdf(src_path, paths.doc_folder(self.config.out_root, doc_id))
                    self._maybe_harvest_images(src_path)
                    self._log("harvest", "pdf_done", path=row["path"])
                pages = self._extract_or_ocr(src_path, self.prefer_text_first)
                if row["doc_type"] == "pdf" and not pages and needs_ocr(src_path):
                    self._log("ocr", "attempt", doc_id=doc_id)
                    pages = run_ocr(src_path, self.config.ocr_lang)
                    if not pages:
                        write_quarantine_record(
                            self.config.out_root,
                            {"doc_id": doc_id, "path": row["path"], "reason": "no_text_after_ocr", "stage": "ocr"},
                        )
                        self._log("quarantine", "no_text_after_ocr", doc_id=doc_id)
                        continue
                chunks = chunk_text(doc_id, pages, self.rules)
                if not chunks:
                    self._log("chunk", "empty", doc_id=doc_id)
                    continue
                atomic_write_lines(
                    paths.chunks_path(self.config.out_root, doc_id), (json_line(c) for c in chunks)
                )
                metas_rows.append(
                    {"doc_id": doc_id, "num_chunks": len(chunks), "file_hash": row["file_hash"]}
                )
                all_chunks.extend(chunks)
                self._log("chunk", "written", doc_id=doc_id, chunks=len(chunks))
                docs_processed += 1
            except Exception as e:  # log and continue
                self._log("error", "doc", doc_id=doc_id, error=str(e))
                write_quarantine_record(
                    self.config.out_root,
                    {"doc_id": doc_id, "path": row.get("path", "?"), "reason": "exception", "stage": "processing", "error": str(e)},
                )
        sb.stage_end("docs")
        sb.stage_start("metas")
        write_metas_index(metas_rows, paths.metas_index_path(self.config.out_root))
        self._log("metas", "index_written", docs=len(metas_rows))
        sb.stage_end("metas")
        sb.stage_start("bm25")
        write_bm25(
            all_chunks,
            paths.bm25_index_path(self.config.out_root),
            paths.bm25_meta_path(self.config.out_root),
        )
        self._log("bm25", "written", chunks=len(all_chunks))
        sb.stage_end("bm25")
        sb.stage_start("embeddings")
        build_embeddings(
            all_chunks,
            paths.embeddings_npy_path(self.config.out_root),
            paths.embeddings_rowmap_path(self.config.out_root),
            seed=self.config.seed,
        )
        self._log("embeddings", "written", chunks=len(all_chunks))
        sb.stage_end("embeddings")
        sb.stage_start("validate")
        validation = validate(self.config.out_root)
        self._log("validate", "complete", errors=len(validation.get("errors", [])))
        sb.stage_end("validate")
        self._log("pipeline", "complete", docs=len(metas_rows), chunks=len(all_chunks))
        run_summary_obj = sb.finalize(
            docs=len(metas_rows), chunks=len(all_chunks), validation=validation
        )
        persist_run_summary(self.config.out_root, run_summary_obj)
        summary = build_summary(
            self.events,
            extra_stats={"docs": len(metas_rows), "chunks": len(all_chunks), **validation},
            run_summary=run_summary_obj,
        )
        return summary

    # ------------------ public API ------------------ #
    @classmethod
    def run(
        cls,
        lib: Path,
        out: Path,
        *,
        ocr_lang: str = "eng",
        include_images: bool = True,
        prefer_text_first: bool = True,
        seed: int | None = None,
    ) -> dict[str, Any]:
        cfg = PipelineConfig(lib_root=lib, out_root=out, ocr_lang=ocr_lang, include_images=include_images, seed=seed or 13)
        orch = cls(cfg, prefer_text_first=prefer_text_first)
        run_summary = orch._run_internal()
        return run_summary.to_dict()


def run_safe_pipeline(lib_root: Path, out_root: Path, *, ocr_lang: str = "eng", include_images: bool = False) -> RunSummary:  # backward compat for tests
    cfg = PipelineConfig(lib_root=lib_root, out_root=out_root, ocr_lang=ocr_lang, include_images=include_images)
    orch = Orchestrator(cfg)
    return orch._run_internal()
