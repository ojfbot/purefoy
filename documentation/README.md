# Documentation Index

Welcome to the Purefoy documentation. This directory contains comprehensive documentation for the project.

---

## Quick Navigation

### 📚 For New Users
- **[QUICKSTART.md](../QUICKSTART.md)** (root) - Get started in 5 minutes
- **[guides/](guides/)** - Feature-specific tutorials and how-tos

### 🔧 For Developers
- **[CLAUDE.md](../CLAUDE.md)** (root) - Complete architecture and command reference
- **[architecture/](architecture/)** - System design and implementation details
- **[development/](development/)** - Development history and session reports

### 📋 Project Management
- **[roadmap/](roadmap/)** - Future plans and priorities
- **[issues/](issues/)** - Known issues and bug reports

### 📖 Reference
- **[examples-schemas/](examples-schemas/)** - Data structure documentation
- **[examples-articles/](examples-articles/)** - Sample parsed articles

---

## Directory Structure

```
documentation/
├── README.md                       # This file - documentation index
│
├── guides/                         # User guides and tutorials
│   ├── articles-scraper.md        # Articles scraper usage
│   ├── coverage-tracking.md       # Incremental scraping guide
│   ├── mcp-integration.md         # MCP server design
│   ├── query-based-scraping.md    # Query provenance tracking
│   └── roger-deakins-filmography.md # Film reference list
│
├── architecture/                   # Technical design documents
│   ├── FORUM_SCRAPER_AUDIT.md     # Architecture overview
│   ├── FORUM_STRUCTURE_DIAGRAM.md  # Data structure diagrams
│   └── IMPLEMENTATION_SUMMARY.md   # Implementation details
│
├── issues/                         # Bug tracking and resolutions
│   └── KNOWN_ISSUES.md            # Current and resolved issues
│
├── roadmap/                        # Planning and future work
│   └── ROADMAP.md                 # Project roadmap (phases 1-5)
│
├── development/                    # Development history
│   ├── sessions/                  # Session reports (dated)
│   │   ├── COMPLETE_SESSION_SUMMARY_2026-01-15.md
│   │   ├── V2_SCHEMA_COMPLETION_REPORT.md
│   │   ├── CONTENT_EXTRACTION_AUDIT_2026-01-15.md
│   │   ├── ANALYSIS_AUDIT_2026-01-15.md
│   │   └── ... (historical reports)
│   ├── ARTICLES_SCRAPER_COMPLETE.md
│   ├── SCRAPING_COMPLETION_SUMMARY.md
│   └── PROJECT_STATUS.md
│
├── examples-schemas/               # Data model examples
│   ├── README.md                  # Schema overview
│   ├── forum/                     # Forum JSON examples
│   │   ├── post_leaf.json
│   │   ├── topic_leaf.json
│   │   └── forum_leaf.json
│   └── episode/                   # Episode metadata examples
│       └── metadata.json
│
└── examples-articles/              # Article parsing examples
    ├── skyfall-1.html             # Raw HTML
    ├── skyfall-1_parsed.json      # Parsed JSON
    └── ... (more examples)
```

---

## Documentation by Purpose

### Getting Started
1. **[QUICKSTART.md](../QUICKSTART.md)** - Installation and first commands
2. **[README.md](../README.md)** (root) - Project overview and features
3. **[guides/coverage-tracking.md](guides/coverage-tracking.md)** - How scraping works

### Using the Forum Scraper
1. **[CLAUDE.md](../CLAUDE.md)** - Complete CLI command reference
2. **[guides/query-based-scraping.md](guides/query-based-scraping.md)** - Advanced queries
3. **[architecture/FORUM_SCRAPER_AUDIT.md](architecture/FORUM_SCRAPER_AUDIT.md)** - How it works

### Data Structure Reference
1. **[examples-schemas/README.md](examples-schemas/README.md)** - Schema overview
2. **[architecture/FORUM_STRUCTURE_DIAGRAM.md](architecture/FORUM_STRUCTURE_DIAGRAM.md)** - Visual diagrams
3. **[examples-schemas/forum/](examples-schemas/forum/)** - JSON examples

### Troubleshooting
1. **[issues/KNOWN_ISSUES.md](issues/KNOWN_ISSUES.md)** - Known problems and fixes
2. **[development/sessions/](development/sessions/)** - Historical bug fixes
3. **[CLAUDE.md](../CLAUDE.md)** - Configuration and environment variables

### Contributing & Planning
1. **[roadmap/ROADMAP.md](roadmap/ROADMAP.md)** - Future features and priorities
2. **[README.md](../README.md)** (root) - Contributing section
3. **[development/PROJECT_STATUS.md](development/PROJECT_STATUS.md)** - Current state

---

## Key Documents Explained

### Root Documentation
These live in the project root (`../` from here):

- **README.md** - Main project introduction, features, quick start
- **CLAUDE.md** - Complete technical reference (architecture, CLI, env vars)
- **QUICKSTART.md** - Fast 5-minute onboarding guide

### Guides (User-Facing)
- **articles-scraper.md** - How to scrape rogerdeakins.com articles
- **coverage-tracking.md** - Incremental scraping, HTTP caching, ETag support
- **mcp-integration.md** - Model Context Protocol server design
- **query-based-scraping.md** - Provenance tracking for research auditability
- **roger-deakins-filmography.md** - Reference list of Roger's films

### Architecture (Developer-Facing)
- **FORUM_SCRAPER_AUDIT.md** - System architecture, composable pipeline design
- **FORUM_STRUCTURE_DIAGRAM.md** - bbPress HTML structure, data models
- **IMPLEMENTATION_SUMMARY.md** - Implementation details, code walkthrough

### Issues
- **KNOWN_ISSUES.md** - Bug reports, resolutions, testing status
  - ✅ Resolved issues (v2 fixes)
  - ⚠️ Minor limitations
  - 📋 Future enhancements

### Roadmap
- **ROADMAP.md** - Comprehensive 5-phase plan:
  - Phase 1: Data Collection (in progress)
  - Phase 2: Enhanced Access & Analysis
  - Phase 3: Content Enhancement
  - Phase 4: Maintenance
  - Phase 5: Advanced Features (ML/AI)

### Development
- **sessions/** - Detailed reports from each development session
  - Bug discoveries and fixes
  - Feature implementations
  - Data quality audits
- **PROJECT_STATUS.md** - Snapshot of project state at key milestones

### Examples
- **examples-schemas/** - JSON schema documentation with real examples
- **examples-articles/** - Before/after HTML→JSON parsing examples

---

## Documentation Status

| Category | Completeness | Notes |
|----------|--------------|-------|
| **User Guides** | 🟢 Complete | Core guides written |
| **Architecture** | 🟢 Complete | System well-documented |
| **API Reference** | 🟡 Partial | CLI documented, Python API needs work |
| **Examples** | 🟢 Complete | Schema examples comprehensive |
| **Issues** | 🟢 Current | All v2 bugs documented |
| **Roadmap** | 🟢 Complete | 5 phases detailed |
| **Contributing** | 🟡 Partial | In README, needs expansion |

---

## Contributing to Documentation

### Style Guide
- Use Markdown with GitHub-flavored extensions
- Include code examples in triple backticks with language hints
- Add table of contents for docs >200 lines
- Use emoji sparingly (✅❌🟢🟡 for status only)
- Date session reports: `YYYY-MM-DD` format

### File Naming
- **Guides**: `lowercase-with-dashes.md`
- **Architecture**: `UPPERCASE_WITH_UNDERSCORES.md`
- **Session Reports**: `DESCRIPTIVE_NAME_YYYY-MM-DD.md`
- **Examples**: Match source naming (e.g., `skyfall-1_parsed.json`)

### When to Add New Docs
- **Guide**: When documenting a user-facing feature
- **Architecture**: When implementing a major system component
- **Issue**: When discovering a reproducible bug
- **Session Report**: At end of significant development sessions
- **Example**: When introducing new data formats

---

## Finding What You Need

### "How do I...?"
→ Check **[QUICKSTART.md](../QUICKSTART.md)** first, then **[guides/](guides/)**

### "Why does X work this way?"
→ See **[architecture/](architecture/)** for design decisions

### "Something's broken!"
→ Check **[issues/KNOWN_ISSUES.md](issues/KNOWN_ISSUES.md)** for known problems

### "What's next?"
→ See **[roadmap/ROADMAP.md](roadmap/ROADMAP.md)** for future plans

### "How was this built?"
→ Read **[development/sessions/](development/sessions/)** for historical context

### "What does this JSON mean?"
→ Look at **[examples-schemas/](examples-schemas/)** for schema docs

---

## Feedback

Found a documentation issue?
- Missing information
- Unclear explanation
- Broken link
- Outdated content

Please let us know or submit a PR!

---

**Last Updated:** 2026-01-15
**Maintainer:** Project team
**Status:** Comprehensive and current
