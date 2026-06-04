# Lead Generator

Private lead generation and management platform for digital services sales. Discovers local businesses via Google Places API, enriches them through automated website analysis, scores their sales potential, and generates AI-drafted outreach messages within a built-in CRM.

## Stack

- **Backend** — FastAPI (Python 3.14, async)
- **Database** — PostgreSQL 18 · SQLAlchemy (async) · Alembic
- **Frontend** — Jinja2 templates · HTMX
- **AI** — Gemini 2.5 Flash (provider-agnostic adapter)

## Features

- Business discovery via Google Places API with deduplication
- Website scraping — CMS detection, email and owner extraction
- Weighted lead scoring (0–100) with transparent breakdown
- AI-generated message drafts (email / WhatsApp) — never auto-sends
- Mini-CRM with lead status tracking and assignment
- Export to CSV / Excel / Google Sheets
- Multi-user with role-based access (admin / seller)

## Project Structure

```
app/
├── core/          # Config, database, security, logging
├── features/      # Business domains (auth, campaigns, businesses, leads, drafts)
├── pipeline/      # Processing stages (scrape, detect, extract, score)
├── integrations/  # External adapters (Google Places, Gemini, Sheets)
├── export/        # CSV / Excel exporters
├── web/           # Jinja2 templates + static files
└── shared/        # Cross-domain helpers
alembic/           # Database migrations
tests/             # Mirrors app/ structure
```

## Setup

**Requirements:** Python 3.14+, PostgreSQL 18, uv

```powershell
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Apply database migrations
uv run alembic upgrade head

# Run development server
uv run uvicorn app.main:app --reload
```

## Development

```powershell
# Run tests
uv run pytest

# Lint and format
uv run ruff check app/
uv run ruff format app/

# Create a migration after model changes
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Foundation — FastAPI, PostgreSQL, auth skeleton | Done |
| 1 | Google Places integration + business storage | Done |
| 2 | Website split + rule-based scoring | Done |
| 3 | Scraping + tech detection + data extraction | Pending |
| 4 | LLM hybrid layer + AI draft generation | Pending |
| 5 | Mini-CRM + CSV / Sheets export | Pending |
| 6 | Scheduled campaigns + hardening + VPS deploy | Pending |
