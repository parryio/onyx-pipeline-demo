# Contributing

## Environment
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .[ocr]
```

## Quality Gates
- ruff check .
- ruff format .
- mypy src
- pytest -q

## Commit Messages
Conventional Commits (feat:, fix:, chore:, docs:, test:, refactor:).

## Pull Request Checklist
- [ ] Tests added/updated
- [ ] Lint + typecheck pass
- [ ] Updated CHANGELOG.md
- [ ] No network access added

## Releasing
1. Bump version in pyproject.toml & src/onyx_pipeline/version.py
2. Update CHANGELOG.md
3. Build & publish:
```powershell
python -m build
pip install twine
python -m twine upload dist/*
```
