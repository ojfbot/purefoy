# Project Structure

Last updated: 2026-01-15

This document describes the organization of the purefoy repository after cleanup for git initialization.

## Root Directory

```
purefoy/
├── README.md                           # Main project documentation
├── CLAUDE.md                           # Instructions for Claude Code
├── QUICKSTART.md                       # Quick start guide
├── pyproject.toml                      # Python package configuration
├── requirements.txt                    # Python dependencies
├── .gitignore                          # Git ignore rules
│
├── download_episodes.py                # Podcast episode downloader
├── ingest_teamdeakins_downloads.py     # Episode metadata organizer
├── regenerate_analysis.sh              # Analysis regeneration script
│
├── deakins_forums/                     # Forum scraper package (v2)
├── deakins_articles/                   # Articles scraper package
│
├── library/                            # Scraped data storage (TRACKED)
│   ├── forums/                         # Forum JSON leafs
│   │   ├── posts/                      # Individual post files
│   │   ├── topics/                     # Topic index files
│   │   ├── forums/                     # Forum metadata
│   │   └── _site/                      # SQLite index, HTTP state
│   └── articles/                       # Article JSON leafs
│
├── docs/                               # Documentation
│   ├── guides/                         # Technical guides & references
│   ├── session-reports/                # Development session summaries
│   ├── examples-articles/              # Sample article HTML/JSON
│   ├── examples-schemas/               # Schema documentation
│   ├── GIT_INIT_CHECKLIST.md
│   └── QUICK_GIT_INIT.sh
│
└── scripts/                            # Utility scripts
    ├── scrape_forum.py                 # Legacy forum scraper (v1)
    └── tools/                          # Development/testing tools
        ├── test_*.py                   # Test scripts
        ├── demo_*.py                   # Demo scripts
        └── extract_*.py                # Transcript extraction tools
```

## Excluded from Git (via .gitignore)

```
# Generated/Downloaded Content
downloads/                  # Podcast MP3 files (large, can be re-downloaded)
analysis/                   # Export files (can be regenerated)
teamdeakins_transcripts/    # Extracted transcripts (generated data)

# Runtime State
*.sqlite, *.db             # Search index (can be rebuilt)
http_state.json            # HTTP cache (ephemeral)
visited_urls.json          # Scrape tracking (ephemeral)

# Python & Development
.venv/                     # Virtual environment
__pycache__/               # Python bytecode
*.egg-info/                # Package metadata
.pytest_cache/             # Test cache

# IDE & OS
.claude/                   # Claude Code working files
.vscode/, .idea/           # Editor configs
.DS_Store                  # macOS metadata
```

## Directory Purposes

### Core Packages
- **`deakins_forums/`**: Modular forum scraper with v2 schema (threading, parent-child relationships)
- **`deakins_articles/`**: Articles scraper for rogerdeakins.com/articles

### Data Storage
- **`library/`**: Primary data storage with JSON "leafs" (TRACKED in git for private repo)
  - Structured, version-controllable JSON files
  - Enables incremental updates via content hashing
  - Ready for AI/MCP consumption

### Documentation
- **`docs/guides/`**: Technical documentation, architecture notes, feature guides
- **`docs/session-reports/`**: Development session summaries (dated)
- **`docs/examples-*/`**: Sample data and schema documentation

### Scripts
- **Root scripts**: Main operational tools (download, ingest, regenerate)
- **`scripts/tools/`**: Development utilities, tests, demos

## Key Design Decisions

### What's Tracked in Git
- ✅ Source code (Python packages)
- ✅ Documentation (guides, examples)
- ✅ Library JSON data (structured knowledge base)
- ✅ Configuration files (pyproject.toml, requirements.txt)
- ✅ Main operational scripts

### What's Not Tracked
- ❌ Generated exports (analysis/)
- ❌ Downloaded audio files (downloads/)
- ❌ Runtime state (SQLite index, HTTP cache)
- ❌ Virtual environments (.venv/)
- ❌ IDE/OS metadata

### Regenerable Data
These can be rebuilt from library/ JSON leafs:
```bash
# Rebuild search index
python -m deakins_forums.cli build-index

# Regenerate all exports
./regenerate_analysis.sh

# Re-download episodes (from RSS)
python download_episodes.py
```

## Git Workflow Ready

The project is now organized for:
1. Clean git commits (no generated files)
2. Collaborative development (clear structure)
3. Version control of knowledge base (JSON leafs)
4. Reproducible builds (requirements.txt, pyproject.toml)

## Next Steps

```bash
# Initialize git repository
git init

# Add all tracked files
git add .

# Create initial commit
git commit -m "Initial commit: Forum & article scrapers with v2 schema

- Forum scraper with threading (parent-child relationships)
- Articles scraper for rogerdeakins.com
- 3,075+ posts collected from 9 forums
- 691 topics with full conversation trees
- Clean data with real author names (no stubs)
- Ready for AI/MCP consumption"
```

## Documentation Index

### User Documentation
- `README.md` - Project overview and usage
- `QUICKSTART.md` - Quick start guide
- `CLAUDE.md` - Claude Code instructions

### Technical Guides
- `docs/guides/FORUM_SCRAPER_AUDIT.md` - Architecture overview
- `docs/guides/FORUM_STRUCTURE_DIAGRAM.md` - Data structure
- `docs/guides/COVERAGE_TRACKING_DEMO.md` - Incremental scraping
- `docs/guides/ARTICLES_SCRAPER_README.md` - Articles scraper guide

### Development History
- `docs/session-reports/COMPLETE_SESSION_SUMMARY_2026-01-15.md` - Full session overview
- `docs/session-reports/V2_SCHEMA_COMPLETION_REPORT.md` - Threading implementation
- `docs/session-reports/CONTENT_EXTRACTION_AUDIT_2026-01-15.md` - Bug fix details

---

**Repository Status**: ✅ Ready for git initialization
**Last Cleanup**: 2026-01-15
**Data Quality**: Production-ready with v2 schema
