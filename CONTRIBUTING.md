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
   regression test.

## Development setup

```bash
git clone <your-fork>
cd MemoryVault
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cd frontend && npm install && npm run build
```

## Before you open a PR

```bash
pytest tests/ -v          # full test-suite (192+ tests)
cd frontend && npm run build
```

CI runs the suite on Linux, macOS and Windows with Python 3.12 and 3.13,
builds the frontend, and smoke-tests the Docker image.

## Code style

- Python: type hints on public functions, docstrings on modules.
- Keep modules focused; the package layout in `README.md` is the map.
- Frontend: plain React function components, no heavyweight UI libraries —
  the dashboard should stay a small, auditable bundle.

## Reporting issues

Include: OS, Python version, the command you ran, and (for indexing bugs)
a minimal sample file that reproduces the problem.
