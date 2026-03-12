# onlydev

A personal job monitoring tool that discovers company job boards, scans them for matching roles, surfaces new listings, and helps tailor your resume — all from a local web UI or the terminal.

---

## What it does

1. **Discovers** company job boards by searching GitHub for Greenhouse board URLs, extracting tokens, validating them against the Greenhouse API, and saving them to a local database.
2. **Monitors** all active sources in parallel, fetches their current job listings, applies keyword and location filters, and upserts matching jobs into the database.
3. **Reports** on new jobs since the last run, keyword frequency, department breakdown, hiring velocity, remote vs local ratio, and job longevity.
4. **Browser UI** — a local web interface for browsing jobs, filtering, marking applications, and running commands.
5. **AI resume tailoring** — sends a job description and your resume to OpenAI to suggest edits or produce a quick rewrite.

---

## Tech stack

- **Python 3.12+**
- **SQLite** — local database (`jobs.db`) with a `_migrations` table-based migration system
- **FastAPI + Uvicorn** — local API server powering the web UI
- **Greenhouse API** — primary ATS integration
- **Lever API** — secondary ATS integration
- **GitHub Code Search API** — used during discovery to find boards
- **OpenAI API** — used for AI resume tailoring
- **`ThreadPoolExecutor`** — concurrent source fetching; DB writes serialized with `threading.Lock`
- **`python-docx`** — reads your resume from a `.docx` file
- **`beautifulsoup4`** — parses and cleans HTML job descriptions
- **`python-dotenv`** — loads environment variables from `.env`
- **`requests`**

---

## Setup

```bash
# Install in editable mode
pip install -e .

# Create a .env file
GITHUB_TOKEN=your_github_token
OPENAI_API_KEY=your_openai_key
RESUME_PATH=/path/to/your/resume.docx
```

The database (`jobs.db`) and `config.json` are created automatically on first run.

---

## CLI commands

| Command | What it does |
|---|---|
| `od-discover` | Searches GitHub for Greenhouse board URLs, validates tokens, seeds sources into the DB |
| `od-monitor` | Scans all active sources, applies filters, upserts matching jobs, records run stats |
| `od-report` | Prints new jobs, keyword frequency, department breakdown, hiring velocity, remote ratio, job longevity |
| `od-run` | Runs all three in sequence: discover → monitor → report |

`od-report` accepts a `--days` flag to control the history window (default: 7):
```bash
od-report --days 30
```

---

## Web UI

Start the local server:
```bash
fastapi dev src/onlydev/api/app.py
```

Then open `http://localhost:8000` in your browser.

**Features:**
- Split-view job browser — job list on the left, detail on the right
- Filter by company, remote only, new since last run, not yet applied
- One-click to open a job listing in a new tab
- Mark jobs as applied
- AI resume tools — suggest edits or quick rewrite powered by OpenAI
- Controls panel — run CLI commands from the UI and stream output in real time
- Settings panel — edit all configuration values without touching files

---

## Configuration

All configurable values live in `config.json` at the project root. They can be edited directly or via the settings panel in the UI.

```json
{
    "discovery": {
        "max_pages": ,
        "max_workers": 
    },
    "monitor": {
        "max_workers": 
    },
    "filters": {
        "keywords": [],
        "home_zip": "",
        "zip_radius_miles": ,
        "local_city_tokens": [],
        "local_state_tokens": [],
        "remote_tokens": [],
        "exclude_if_not_local_tokens": [],
        "role_tokens": [],
        "exclude_title_tokens": []
    },
    "ats": {
        "greenhouse": {
            "likely_engineering_tokens": []
        }
    }
}
```

---

## How filtering works

A job passes if all four conditions are met:

1. **Title looks like a dev role** — checked against `role_tokens`
2. **Title is not excluded** — checked against `exclude_title_tokens` (managers, interns, etc.)
3. **Keywords match** — title and description must contain at least one configured keyword
4. **Location is acceptable** — remote jobs always pass; on-site/hybrid jobs only pass if they match a local city, state, or ZIP

---

## Project structure

```
src/onlydev/
├── api/
│   ├── app.py              # FastAPI app — all API endpoints
│   ├── description.py      # HTML description cleaning
│   └── static/
│       ├── index.html
│       ├── script.js
│       └── styles.css
├── ats/
│   ├── greenhouse.py       # Greenhouse API client
│   └── lever.py            # Lever API client
├── cli/
│   ├── discover.py         # od-discover entrypoint
│   ├── monitor.py          # od-monitor entrypoint
│   ├── report.py           # od-report entrypoint
│   └── run.py              # od-run entrypoint
├── core/
│   ├── config.py           # Config loader/writer
│   ├── db.py               # SQLite connection + migrations runner
│   ├── filters.py          # Keyword and location filtering logic
│   ├── migrations.py       # All schema migrations as ordered SQL strings
│   ├── models.py           # Source and Job dataclasses
│   ├── monitor.py          # Main job ingestion engine (concurrent)
│   └── repository.py       # All DB read/write operations
└── scripts/
    ├── discovery/
    │   ├── greenhouse.py           # GitHub search + token extraction
    │   └── validate_greenhouse.py  # Token validation via Greenhouse API
    ├── reports/
    │   └── report_trends.py        # Terminal report
    └── sources/
        └── seed_sources.py         # Upserts discovered tokens as sources
```

---

## Database schema

**`sources`** — job board URLs to monitor  
**`jobs`** — matched job listings with title, company, location, department, office, keywords, remote flag, applied flag, active flag  
**`job_run_counts`** — per-run stats: matched and new job counts per company  
**`_migrations`** — tracks which schema migrations have been applied

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes (discover) | GitHub personal access token for code search |
| `OPENAI_API_KEY` | Yes (AI tools) | OpenAI API key for resume tailoring |
| `RESUME_PATH` | Yes (AI tools) | Absolute path to your `.docx` resume file |