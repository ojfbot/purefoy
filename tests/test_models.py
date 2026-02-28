"""
Smoke tests for Pydantic data models.

These verify the models can be instantiated and serialise/deserialise
correctly — the minimum bar to catch regressions in the leaf schema.
"""

import pytest
from deakins_forums.models import (
    Author,
    ContentBlock,
    ForumLeaf,
    Integrity,
    Link,
    PostIds,
    PostLeaf,
    PostType,
    Provenance,
    Timestamps,
    TopicLeaf,
)


def _provenance() -> Provenance:
    return Provenance(source_url="https://example.com", scraped_at="2026-01-01T00:00:00")


def _integrity() -> Integrity:
    return Integrity(content_hash="sha256:abc123", parser_version="bbpress-v2")


class TestPostType:
    def test_values(self):
        assert PostType.TOPIC == "topic"
        assert PostType.REPLY == "reply"
        assert PostType.ARTICLE == "article"

    def test_is_str(self):
        assert isinstance(PostType.TOPIC, str)


class TestPostLeaf:
    def test_minimal(self):
        leaf = PostLeaf(
            ids=PostIds(post_id="12345"),
            content_text="Hello world",
            provenance=_provenance(),
            integrity=_integrity(),
        )
        assert leaf.ids.post_id == "12345"
        assert leaf.post_type == PostType.TOPIC
        assert leaf.blocks == []

    def test_roundtrip_json(self):
        leaf = PostLeaf(
            ids=PostIds(post_id="99999", forum_slug="team-deakins"),
            post_type=PostType.REPLY,
            author=Author(display_name="Roger A. Deakins", role="Keymaster"),
            timestamps=Timestamps(parsed_iso="2023-01-01T12:00:00", parse_confidence="high"),
            content_text="Use the light you have.",
            blocks=[ContentBlock(type="paragraph", text="Use the light you have.")],
            links=[Link(href="https://rogerdeakins.com", kind="external")],
            provenance=_provenance(),
            integrity=_integrity(),
        )
        data = leaf.model_dump()
        restored = PostLeaf.model_validate(data)
        assert restored.ids.post_id == "99999"
        assert restored.post_type == PostType.REPLY
        assert restored.author is not None
        assert restored.author.display_name == "Roger A. Deakins"


class TestTopicLeaf:
    def test_minimal(self):
        leaf = TopicLeaf(
            topic_url="https://example.com/topic/foo",
            provenance=_provenance(),
            integrity=_integrity(),
        )
        assert leaf.post_ids == []
        assert leaf.reply_count == 0
        assert leaf.max_depth == 0


class TestForumLeaf:
    def test_minimal(self):
        leaf = ForumLeaf(
            forum_url="https://example.com/forums/team-deakins",
            forum_slug="team-deakins",
            title="Team Deakins",
            provenance=_provenance(),
            integrity=_integrity(),
        )
        assert leaf.forum_slug == "team-deakins"
        assert leaf.description is None
