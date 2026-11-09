# Contributing to MemoryVault

Thanks for your interest in improving MemoryVault!

## Ground rules

1. **Local-first, always.** No feature may introduce a network call, cloud
   dependency or telemetry. The deterministic core (parse → index → search)
   must never require AI.
2. **Determinism matters.** Same input bytes must produce the same vault
   state. Avoid unseeded randomness and time-dependent logic outside the
   event log.
3. **Tests travel with code.** New features need new tests; bug fixes need a
   regression test. See `tests/test_regressions.py` for the pattern.
4. **Both languages ship together.** Any new UI string must be added to
   *both* dictionaries in `frontend/src/i18n.js`; `npm test` enforces key
   parity. Security- and license-related documentation stays in English.

## Development setup

```bash
git clone <your-fork>
cd MemoryVault
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cd frontend && npm ci && npm run build && cd ..
```

Run the API locally with `memoryvault serve` (or `python -m memoryvault serve`);
the Vite dev server proxies `/api` to port 8000.

## Before you open a PR

```bash
pytest tests/ -v                 # 222 Python tests
cd frontend && npm test          # 18 frontend tests
cd frontend && npm run build     # production bundle
cd ..
python scripts/smoke_cli.py      # cross-platform CLI smoke test
python scripts/check_docs.py     # README links and screenshots
```

CI runs the Python suite on Linux, macOS and Windows with Python 3.12 and
3.13, runs the frontend tests and build, validates README links, and
smoke-tests the Docker image (health, search, dashboard HTML, favicon,
JSON 404s and the CORS policy).

## Code style

- Python: type hints on public functions, docstrings on modules.
- Keep modules focused; the package layout in `README.md` is the map.
- Frontend: plain React function components, no heavyweight UI libraries —
  the dashboard should stay a small, auditable, fully offline bundle.
- Never use `dangerouslySetInnerHTML` for document content. The API escapes
  text, and `Highlight` renders it as React text nodes.
- Database access goes through `DocumentRepository` / `LockedConnection`;
  do not open a second raw connection to the same vault.

## Screenshots

`docs/screenshots/` contains four English (`*-en.png`) and four Chinese
(`*-zh.png`) captures referenced by the two READMEs. When the UI changes,
regenerate them so the documentation stays honest:

```bash
python scripts/make_demo_vault.py examples/sample-docs --db /tmp/en.db
python scripts/make_demo_vault.py examples/sample-docs-zh --db /tmp/zh.db
memoryvault --db /tmp/en.db serve --port 8000
memoryvault --db /tmp/zh.db serve --port 8001
# capture /dashboard, /?q=..., /graph, /timeline with ?lang=en / ?lang=zh
```

## Reporting issues

Include: OS, Python version, the command you ran, and (for indexing bugs)
a minimal sample file that reproduces the problem. Never attach private
documents to a public issue.
