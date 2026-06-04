# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Loading discipline (ADR-0081):** this root file is the always-loaded Layer 0 — repo identity, data-safety/fair-use invariants, and the command quick-start. Deeper, path-conditional material is routed out: forum-scraper internals → `deakins_forums/CLAUDE.md` (loads when editing that subtree); record schemas → `documentation/data-model-reference.md`; structure / podcast-ingest / testing reference → `documentation/repo-reference.md`.

## Overview

This is a **Team Deakins Podcast and Forum Knowledge Base** project. It contains:

1. **Podcast Episode Downloader & Ingest**: Scripts to download MP3s from RSS feeds and organize them into structured episode directories with metadata and transcripts.
2. **Forum Scraper (`deakins_forums`)**: A modular, ultra-structured Python package for scraping rogerdeakins.com forums into a searchable JSON-based knowledge base. (Design + CLI: `deakins_forums/CLAUDE.md`.)
3. **TypeScript UI Layer (`packages/`)**: A Module Federation remote (React/Vite micro-frontend on port 3020 + Express API on port 3021) for exploring podcast and forum data locally. Exposes `GET /api/beads` per the fleet-wide ADR-0016 bead projection contract. Architecture decisions: ADR-006 through ADR-009, ADR-0016, ADR-0030.
4. **Standalone Flask UI (`app.py`)**: A single-file dark-theme knowledge browser at `localhost:5050`, reading directly from `downloads/` and `library/forums/`. Zero dependency on the Module Federation stack — used for local debugging against the raw corpus.

## Fair Use & Privacy (must-keep)

All content is for **personal research and educational purposes only** under fair use principles. Commercial use requires explicit permission from copyright holders.

- **Keep this repository PRIVATE** — scraped forum data is for private research use; do not make public.
- **Personal/educational use only** — no commercial redistribution. Contact rogerdeakins.com / Team Deakins for commercial licensing.
- Scripts identify research purpose via User-Agent headers; rate limiting is enforced (3s default); respect `robots.txt` and server resources.
- All content remains property of original copyright holders.

## Git Data Policy

**What is committed to git:**
- All source code (`deakins_forums/`, `deakins_articles/`, scripts)
- Schema examples with fictional/illustrative content (`documentation/examples-schemas/`)
- Documentation and configuration files

**What is gitignored (on disk only):**
- `library/` — actual scraped content (forum posts, articles, images). This is the canonical data store but needs curation before committing. When ready, commit only the canonical subdirectories: `library/forums/posts/`, `library/forums/topics/`, `library/forums/forums/`, `library/articles/articles/`, `library/articles/films/`
- `library/forums/_site/` — derived runtime state (SQLite index, HTTP cache, coverage tracking). Always regenerable.
- `library/forums/_curated/` — derived curation views. Lives in `analysis/curated/` instead.
- `analysis/` — export outputs and curated views (regenerable from library/)
- `downloads/` — podcast MP3s and episode directories

**Schema examples vs. actual data:** The `documentation/examples-schemas/` directory is the git-committed representation of the data layer. Each file shows the shape of a record type with fictional illustrative content — not real scraped data. See `documentation/examples-schemas/README.md` for field-level documentation.

## Deployment

**NEVER deploy directly to production** via CLI (`vercel deploy --prod`, `aws s3 sync` to prod paths, etc.).
All production deployments go through the GitHub PR → CI → merge → automated deploy pipeline.
The only exception is `workflow_dispatch` for manual CI triggers.

The deploy workflow is `.github/workflows/deploy-tde.yml`. It stages files into a clean
`/tmp/tde-stage` directory and deploys via the CI-scoped `VERCEL_TOKEN`.

## Common Commands

### Virtual Environment Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# OR install as editable package
pip install -e .
```

### Code Quality (optional-dependencies)

```bash
# Format code
black .

# Lint code
ruff check .

# Run tests (if available)
pytest
```

**Forum scraping commands** (scrape, index, search, export, provenance) → `deakins_forums/CLAUDE.md`.
**Podcast download & ingest commands** → `documentation/repo-reference.md`.

## Architecture & data model

- **Forum scraper pipeline + design principles** → `deakins_forums/CLAUDE.md`
- **Record schemas** (PostLeaf, TopicLeaf, Episode metadata; authoritative source `deakins_forums/models.py`) → `documentation/data-model-reference.md`
- **Project structure, episode-ingest design, testing notes** → `documentation/repo-reference.md`
