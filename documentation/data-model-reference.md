# Data Model Reference

Deep schema reference for the forum/podcast knowledge base (ADR-0081 Layer 2 — task
reference, not always-loaded). **Authoritative source:** `deakins_forums/models.py`
(Pydantic). Git-committed illustrative examples: `documentation/examples-schemas/`
(see its `README.md` for field-level docs). This file mirrors those shapes for quick
reference when working on the data layer.

## PostLeaf Structure (v2 Schema)

**NEW in v2:** Threading support with parent-child relationships and post types.

```json
{
  "ids": {
    "post_id": "175763",
    "forum_slug": "team-deakins",
    "topic_slug": "lighting-discussion",
    "reply_permalink": "https://...",
    "parent_post_id": "175760",
    "parent_type": "topic",
    "position": 1
  },
  "post_type": "reply",
  "author": {
    "display_name": "Roger A. Deakins",
    "role": "Keymaster"
  },
  "timestamps": {
    "raw": "January 18, 2023 at 3:32 pm #175763",
    "parsed_iso": "2023-01-18T15:32:00",
    "parse_confidence": "medium"
  },
  "content_text": "...",
  "content_html": "...",
  "blocks": [...],
  "quotes": [...],
  "links": [...],
  "media": [...],
  "provenance": {
    "source_url": "...",
    "scraped_at": "2026-01-15T...",
    "http": {"etag": "...", "last_modified": "..."}
  },
  "integrity": {
    "content_hash": "sha256:...",
    "parser_version": "bbpress-v2"
  }
}
```

**Threading Fields:**
- `post_type`: "topic" (starter) or "reply"
- `parent_post_id`: ID of parent post (null for topics)
- `parent_type`: "topic" or "reply" (null for topics)
- `position`: Sequential position in reply list (1-indexed)

## TopicLeaf Structure (v2 Schema)

**NEW in v2:** Hierarchical reply tree with thread statistics.

```json
{
  "topic_url": "https://...",
  "topic_slug": "lighting-discussion",
  "title": "Lighting Discussion",
  "post_ids": ["175760", "175763", "175764"],
  "reply_tree": {
    "post_id": "175760",
    "post_type": "topic",
    "author": "John Doe",
    "timestamp": "2023-01-18T15:00:00",
    "children": [
      {
        "post_id": "175763",
        "post_type": "reply",
        "author": "Roger A. Deakins",
        "timestamp": "2023-01-18T15:32:00",
        "children": []
      },
      {
        "post_id": "175764",
        "post_type": "reply",
        "author": "Jane Smith",
        "timestamp": "2023-01-18T16:00:00",
        "children": []
      }
    ]
  },
  "reply_count": 2,
  "max_depth": 1,
  "provenance": {...},
  "integrity": {
    "content_hash": "sha256:...",
    "parser_version": "bbpress-v2"
  }
}
```

**Reply Tree Fields:**
- `reply_tree`: Recursive nested structure showing conversation flow
- `reply_count`: Total number of replies (excluding topic starter)
- `max_depth`: Maximum nesting depth (0 = no replies, 1 = direct replies only)
- `post_ids`: Flat list for backward compatibility

**Migration Note:** Use `python -m deakins_forums.migrate --rebuild-trees` to rebuild reply trees for existing data.

## Episode metadata.json Structure

```json
{
  "title": "SEASON 2 - EPISODE 176 - Chris Lowe...",
  "guid": "...",
  "pubDate_iso": "2026-01-14",
  "itunes": {
    "season": 2,
    "episode": 176,
    "duration_s": 5400,
    "summary": "..."
  },
  "rss_description": "...",
  "rss_content_encoded": "...",
  "audio": {
    "url": "https://...",
    "mime": "audio/mpeg",
    "size_bytes": 123456789,
    "bitrate_kbps": 128,
    "duration_s": 5400,
    "format": "MP3"
  },
  "provenance": {
    "rss_url": "...",
    "scraped_at": "2026-01-15T...",
    "script_version": "ingest-v2"
  }
}
```
