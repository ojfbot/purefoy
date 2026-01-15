# Library Directory

This directory contains scraped forum data organized as JSON "leafs" (individual structured documents).

## Structure

```
library/
└── forums/
    ├── posts/              # Individual post JSON files
    │   └── {post_id}.json
    ├── topics/             # Topic index files
    │   └── {forum_slug}__{topic_slug}.json
    ├── forums/             # Forum metadata files
    │   └── {forum_slug}.json
    └── _site/              # Site metadata & indices
        ├── forums_index.json       # Forums catalog
        ├── kb.sqlite              # Full-text search index
        ├── http_state.json        # HTTP cache (ETags, Last-Modified)
        ├── coverage.json          # Scraping coverage tracking
        └── query_log.jsonl        # Query provenance log
```

## Note

**This directory IS tracked in the private repository** for personal research purposes.

The forum data is included because:
- This is a private repository for personal/educational use
- Forum content is publicly accessible (not behind authentication)
- Structured data enables better research and analysis
- JSON format is git-friendly and allows version control

**Important reminders**:
- This repository should remain **private** (do not make public)
- Content is for **personal research/educational use only**
- Respect copyright and intellectual property rights
- Commercial use requires explicit permission from rogerdeakins.com

The SQLite search index (*.sqlite files) is excluded and can be rebuilt with:
```bash
python -m deakins_forums.cli build-index
```

For schema reference, see `schema_examples/` in the project root.
