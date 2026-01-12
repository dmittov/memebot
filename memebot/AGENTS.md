# Repository Guidelines

## Project Structure & Module Organization
- `main.py` hosts the FastAPI app and Telegram webhook entrypoint.
- `memebot/` contains core bot logic (commands, censoring, retrieval, config).
- `tests/` holds pytest suites plus fixtures (`tests/conftest.py`) and assets (`tests/img/`, media files).
- `app.yaml` defines the production entrypoint and GCP App Engine runtime config.
- `requirements.txt` and `requirements.dev.txt` list runtime and dev tooling dependencies.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` to create/activate a local venv.
- `pip install -r requirements.txt` to install runtime deps.
- `pip install -r requirements.dev.txt` to install dev/test tooling.
- `hypercorn -b :8000 main:app` to run the API locally (matches `app.yaml` entrypoint).
- `pytest` to run the test suite.

## Coding Style & Naming Conventions
- Python style: 4-space indentation, type hints where practical, async-aware code.
- Formatters: `black` (and `isort` with the Black profile). Lint with `flake8`; type-check with `mypy`.
- Naming: modules and functions use `snake_case`, classes use `PascalCase`.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`, `pytest-mock`, `pytest-xdist`.
- Tests live in `tests/` and follow `test_*.py` naming.
- Pub/Sub-dependent tests use the `@pytest.mark.pubsub` marker; skip or provide an emulator when running locally.
- No explicit coverage target is defined; focus on meaningful behavior coverage.

## Commit & Pull Request Guidelines
- Commit messages are short and imperative, sometimes with PR numbers (e.g., `Async Censor (#21)`).
- PRs should describe the change, list tests run (or note why skipped), and call out config/env var updates.
- If behavior changes user-facing responses, include a brief example in the PR description.

## Configuration & Secrets
- Runtime configuration is driven by environment variables (see `app.yaml` for names).
- Secrets are pulled via GCP Secret Manager; avoid hardcoding tokens locally.
