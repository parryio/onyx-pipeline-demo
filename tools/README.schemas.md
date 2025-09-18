# Schema Precompilation (AJV Standalone)

This workspace uses AJV's standalone generator to precompile JSON Schemas into eval-free validator modules for the Phase 5 Electron app.

Why:
- CSP in the renderer forbids `unsafe-eval`.
- Our PDRs require deterministic, offline behavior in Phases 1–5.
- Precompiling validators removes runtime `new Function(...)` and keeps the UI secure.

What it does:
- Reads `onyx-hall-phase5-app/tools/schemas/*.schema.json`.
- Compiles each schema with AJV (Node) and writes validators to `onyx-hall-phase5-app/src/renderer/src/validators/`.
- Generates an index that maps schema base names to validator functions.

How to run:

```powershell
# From repo root
node .\onyx-hall-phase5-app\tools\precompile_schemas.mjs
```

Build hooks:
- `npm run dev` / `npm run build` in `onyx-hall-phase5-app` run the precompile step automatically via `predev`/`prebuild`.

Renderer usage:
- Import validators: `import validators from '../validators'`
- Use `validators['ui_catalog'](row)` to validate rows.

Determinism:
- Stable file ordering, no network calls, strict codegen.

If you add a new schema:
1. Drop `*.schema.json` under `onyx-hall-phase5-app/tools/schemas/`.
2. Re-run the precompile step.
3. Use the new key (basename of the file) in the renderer.
