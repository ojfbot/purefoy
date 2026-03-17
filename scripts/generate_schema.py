#!/usr/bin/env python3
"""
Generate OpenAPI 3.1 JSON schema from Python models.

Sources:
  - deakins_forums/models.py     (Pydantic v2 BaseModel classes)
  - scripts/tools/transcribe_episodes.py (stdlib dataclasses)

Output:
  openapi.json  — consumed by `openapi-typescript` via `pnpm codegen`

Usage:
  python scripts/generate_schema.py
  # or via pnpm:
  pnpm codegen  (runs this script then openapi-typescript)

Run this whenever Python models change. Commit the regenerated openapi.json
and the updated packages/shared/src/generated/schema.ts together.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add repo root to path so we can import the packages
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from deakins_forums.models import (  # noqa: E402
    PostLeaf,
    TopicLeaf,
    ForumLeaf,
    PostIds,
    Author,
    Timestamps,
    Integrity,
    Provenance,
    HttpProvenance,
    ContentBlock,
    Quote,
    Link,
    Media,
    PostType,
)


def pydantic_schemas() -> dict:
    """Export JSON schemas from all Pydantic v2 models.

    Uses ref_template='#/components/schemas/{model}' so that $ref values point
    to the OpenAPI components/schemas path rather than the Pydantic default
    '#/$defs/{model}', which openapi-typescript 7.x cannot resolve.

    Any $defs nested inside individual model schemas are hoisted to the top-level
    schemas dict so all $refs resolve correctly.
    """
    models = [
        PostLeaf,
        TopicLeaf,
        ForumLeaf,
        PostIds,
        Author,
        Timestamps,
        Integrity,
        Provenance,
        HttpProvenance,
        ContentBlock,
        Quote,
        Link,
        Media,
    ]
    schemas: dict = {}
    for model in models:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        name = schema.get("title", model.__name__)
        # Hoist any $defs from within this schema up to the top-level schemas dict.
        # Pydantic v2 sometimes emits $defs even when ref_template is set (for
        # self-referential models or models with shared sub-schemas).
        for def_name, def_schema in schema.pop("$defs", {}).items():
            if def_name not in schemas:
                schemas[def_name] = def_schema
        schemas[name] = schema
    # Also include the enum
    schemas["PostType"] = {
        "title": "PostType",
        "type": "string",
        "enum": [e.value for e in PostType],
        "description": "Distinguishes topic starters from replies",
    }
    return schemas


def transcript_dataclass_schemas() -> dict:
    """
    Hand-maintained JSON schemas for transcript pipeline dataclasses.

    These mirror the @dataclass structures in scripts/tools/transcribe_episodes.py.
    They are hand-written here rather than auto-generated because stdlib dataclasses
    don't carry JSON schema metadata. When the dataclasses change, update these schemas.

    TODO: migrate transcribe_episodes.py to pydantic.dataclasses so this section
    can be auto-generated too (low priority — schema is stable post-v2.0.0).
    """
    return {
        "WordTimestamp": {
            "type": "object",
            "properties": {
                "word": {"type": "string"},
                "start": {"type": "number"},
                "end": {"type": "number"},
                "probability": {"type": "number"},
            },
            "required": ["word", "start", "end", "probability"],
        },
        "SegmentResult": {
            "type": "object",
            "description": "Full segment in transcript.json segments[]",
            "properties": {
                "id": {"type": "integer"},
                "start": {"type": "number"},
                "end": {"type": "number"},
                "text": {"type": "string"},
                "speaker": {"type": "string", "description": "e.g. SPEAKER_00"},
                "segment_type": {"type": "string", "enum": ["intro", "outro", "content"]},
                "chapter_id": {"type": "integer"},
                "confidence": {"type": "number"},
                "words": {"type": "array", "items": {"$ref": "#/components/schemas/WordTimestamp"}},
                "topics": {"type": "array", "items": {"type": "string"}},
                "films": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["id", "start", "end", "text", "speaker", "segment_type", "chapter_id"],
        },
        "SegmentCompact": {
            "type": "object",
            "description": "Compact segment in transcript_segments.jsonl (no word data)",
            "properties": {
                "id": {"type": "integer"},
                "start": {"type": "number"},
                "end": {"type": "number"},
                "text": {"type": "string"},
                "speaker": {"type": "string"},
                "segment_type": {"type": "string", "enum": ["intro", "outro", "content"]},
                "chapter_id": {"type": "integer"},
                "confidence": {"type": "number"},
                "topics": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["id", "start", "end", "text", "speaker", "segment_type", "chapter_id"],
        },
        "ChapterResult": {
            "type": "object",
            "properties": {
                "index": {"type": "integer"},
                "title": {"type": "string"},
                "start_time": {"type": "number"},
                "end_time": {"type": "number"},
                "duration": {"type": "number"},
                "summary": {"type": "string"},
                "segment_range": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                "word_count": {"type": "integer"},
                "topics": {"type": "array", "items": {"type": "string"}},
                "films": {"type": "array", "items": {"type": "string"}},
                "speakers": {"type": "array", "items": {"type": "string"}},
                "key_phrases": {"type": "array", "items": {"type": "string"}},
                "break_score": {"type": "number"},
                "break_signals": {"type": "object"},
            },
            "required": ["index", "title", "start_time", "end_time", "duration"],
        },
        "ExtractionReport": {
            "type": "object",
            "properties": {
                "episode_dir": {"type": "string"},
                "episode_title": {"type": "string"},
                "success": {"type": "boolean"},
                "error": {"type": ["string", "null"]},
                "transcribed_at": {"type": "string", "format": "date-time"},
                "pipeline_version": {"type": "string"},
                "processing_time_seconds": {"type": "number"},
                "audio_duration_seconds": {"type": "number"},
                "segment_count": {"type": "integer"},
                "word_count": {"type": "integer"},
                "language": {"type": "string"},
                "speakers_detected": {"type": "integer"},
                "topics_tagged": {"type": "integer"},
                "films_mentioned": {"type": "integer"},
                "chapters_generated": {"type": "integer"},
            },
            "required": ["episode_dir", "episode_title", "success"],
        },
        "RunManifest": {
            "type": "object",
            "properties": {
                "canonical": {"type": "string"},
                "runs": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/RunManifestEntry"},
                },
            },
            "required": ["canonical", "runs"],
        },
        "RunManifestEntry": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "whisper_model": {"type": "string"},
                "diarization": {"type": "boolean"},
                "speaker_embeddings": {"type": "boolean"},
                "pipeline_version": {"type": "string"},
            },
            "required": ["run_id", "created_at", "whisper_model", "diarization", "speaker_embeddings"],
        },
        "EpisodeMetadata": {
            "type": "object",
            "description": "metadata.json at episode root — sourced from RSS XML",
            "properties": {
                "guid": {"type": "string"},
                "title": {"type": "string"},
                "pub_date_iso": {"type": "string", "format": "date"},
                "enclosure_url": {"type": "string"},
                "enclosure_filename": {"type": "string"},
                "enclosure_length": {"type": "integer"},
                "enclosure_type": {"type": "string"},
                "description_html": {"type": "string"},
                "itunes": {
                    "type": "object",
                    "properties": {
                        "season": {"type": ["integer", "null"]},
                        "episode": {"type": ["integer", "null"]},
                        "duration": {"type": "string"},
                        "summary": {"type": "string"},
                        "image": {"type": "string"},
                    },
                    "required": ["season", "episode", "duration"],
                },
            },
            "required": ["guid", "title", "pub_date_iso"],
        },
    }


def build_openapi_spec(
    pydantic: dict,
    transcript: dict,
) -> dict:
    """Combine schemas into an OpenAPI 3.1 document."""
    all_schemas: dict = {}
    all_schemas.update(pydantic)
    all_schemas.update(transcript)

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Purefoy Data Schema",
            "version": "2.0.0",
            "description": (
                "JSON schemas for on-disk data produced by the Purefoy Python pipeline. "
                "These types are consumed by the Node.js purefoy-api and the browser-app. "
                "Source: deakins_forums/models.py (Pydantic v2) and "
                "scripts/tools/transcribe_episodes.py (dataclasses)."
            ),
        },
        "paths": {},  # No HTTP paths — this is a data schema spec only
        "components": {
            "schemas": all_schemas,
        },
    }


def main() -> None:
    output_path = REPO_ROOT / "openapi.json"
    try:
        pydantic = pydantic_schemas()
        transcript = transcript_dataclass_schemas()
        spec = build_openapi_spec(pydantic, transcript)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)
            f.write("\n")
        print(f"✓ openapi.json written to {output_path}")
        print(f"  Pydantic schemas: {len(pydantic)}")
        print(f"  Transcript schemas: {len(transcript)}")
        print(f"  Total: {len(pydantic) + len(transcript)} schemas")
    except ImportError as e:
        print(f"✗ Import error: {e}", file=sys.stderr)
        print(
            "  Make sure you're running with the correct Python environment.\n"
            "  Try: source .venv/bin/activate && python scripts/generate_schema.py",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
