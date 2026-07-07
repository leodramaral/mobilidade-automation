# AGENTS.md

## What this is

Python project that monitors ride-hailing prices (currently 99 app) via Appium automation on Android, stores snapshots in SQLite, and displays them in a Streamlit dashboard.

## Entry points

- **CLI collector**: `python main.py` — reads `config.json`, connects to Appium, scrapes prices in a loop, saves to the configured persistence backend.
- **Dashboard**: `streamlit run ui/app.py` — reads from the SQLite database, shows filterable table + JSON download.

## Architecture

```
main.py                  ← CLI entrypoint
config.json              ← all runtime config (app target, Appium server, persistence)
automacoes/              ← Appium automation (base class + per-app impl)
  automacao_99.py        ← 99 app scraping logic (UiAutomator2)
modelos/                 ← data models (Corrida, Snapshot)
persistencia/            ← storage backends (SQLite, markdown file)
ui/app.py                ← Streamlit dashboard
```

**Persistence layer**: `RepositorioBanco` (SQLite). The SQLite DB file (`mobilidade.db`) is gitignored.

## Prerequisites

- **Appium server** running at `http://127.0.0.1:4723` (must be started separately before `main.py`)
- **Android device/emulator** connected with the 99 app installed
- Python venv with deps from `requirements.txt`: `pip install -r requirements.txt`

## Key quirks

- `ui/app.py` uses `sys.path.insert(0, ...)` to import from the project root — not a standard Python package layout.
- The 99 app element IDs (e.g. `com.taxis99:id/oc_home_where_to_tv`) are hardcoded in `automacao_99.py`. If the app updates its UI, these break silently.
- Prices are parsed from Brazilian format (`R$ 12,50` → `12.50`) via string replacement in `automacao_99.py`.
- `config.json → app` currently only supports `"99"`. Adding a new app means creating a new class under `automacoes/` that extends `BaseAutomacao`.

## Conventions

- Commit messages use conventional commits: `feat:`, `fix:`, etc.
- All source code and UI labels are in **Portuguese (Brazilian)** — variable names, comments, dashboard text.
- No test suite, linter, formatter, or type checker configured. No CI.
- `__init__.py` files are empty (packages exist for import structure only).
