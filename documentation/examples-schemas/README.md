# Schema Examples

This directory contains example files showing the structure of data used in this project.

## Purpose

These examples serve as:
- **Documentation** of the data models without including actual scraped content
- **Reference** for developers working with the data
- **Templates** for understanding expected formats

## Directory Structure

```
schema_examples/
├── episode/                    # Podcast episode data schemas
│   ├── metadata.json          # Episode metadata structure
│   ├── transcript_sources.json # Transcript source tracking
│   └── transcript.txt         # Transcript text format
└── forum/                      # Forum data schemas
    ├── post.json              # Individual post structure (PostLeaf)
    ├── topic.json             # Topic metadata structure (TopicLeaf)
    └── forum.json             # Forum metadata structure (ForumLeaf)
```

## Episode Schemas

### metadata.json
Comprehensive episode metadata extracted from RSS feed including:
- Title, GUID, publication date
- iTunes-specific metadata (season, episode, duration)
- RSS description and content
- Audio file metadata (format, bitrate, duration)
- Provenance information (source URL, scrape timestamp)

### transcript_sources.json
Tracks available transcript sources and fetch status:
- Podcasting 2.0 transcript URLs
- Third-party sources (Tapesearch, etc.)
- Priority and availability status

### transcript.txt
Plain text format for episode transcripts.

## Forum Schemas

### post.json (PostLeaf)
Individual forum post with:
- Identifiers (post ID, forum slug, topic slug, permalink)
- Author information (name, role)
- Timestamps (raw and parsed ISO 8601)
- Content (plain text, HTML, structured blocks)
- Extracted elements (quotes, links, media)
- Provenance and integrity metadata

### topic.json (TopicLeaf)
Forum topic metadata with:
- Topic identifiers and URL
- Title and author
- Creation and activity timestamps
- Statistics (replies, voices, views)
- Post ID index (actual posts are separate files)
- Provenance and integrity metadata

### forum.json (ForumLeaf)
Forum-level metadata with:
- Forum identifiers and URL
- Title and description
- Statistics (topic count, post count)
- Topic reference list
- Provenance and integrity metadata

## Data Model Features

All schemas include:

### Provenance
- **source_url**: Original URL of the content
- **scraped_at**: ISO 8601 timestamp of scrape
- **http**: HTTP headers (ETag, Last-Modified) for caching

### Integrity
- **content_hash**: SHA-256 hash for change detection
- **parser_version**: Version identifier for schema evolution

## Related Documentation

- See `deakins_forums/models.py` for Pydantic model definitions
- See `CLAUDE.md` for detailed architecture documentation
- See `README.md` for usage instructions
