"""
Data integrity validation utilities.

Validates forum scrape data for consistency, completeness, and correctness.
"""

from __future__ import annotations

from .models import PostLeaf, PostType, TopicLeaf
from .reply_tree import extract_post_ids_from_tree
from .store_json import JsonLeafStore


class ValidationError:
    """Represents a validation error with severity and context."""

    def __init__(self, severity: str, message: str, context: dict | None = None):
        self.severity = severity  # "error", "warning", "info"
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        ctx = f" [{self.context}]" if self.context else ""
        return f"[{self.severity.upper()}] {self.message}{ctx}"

    def __repr__(self) -> str:
        return str(self)


def validate_post(post: PostLeaf, store: JsonLeafStore) -> list[ValidationError]:
    """
    Validate a single post for data integrity.

    Checks:
    - Parent references are valid
    - Post type matches parent relationship
    - Position is set for replies
    - Author and timestamp are present

    Parameters
    ----------
    post:
        Post to validate
    store:
        Store to check parent references

    Returns
    -------
    List of validation errors (empty if valid)
    """
    errors = []

    # Check: posts with parent_post_id should be type REPLY
    if post.ids.parent_post_id and post.post_type != PostType.REPLY:
        errors.append(
            ValidationError(
                "error",
                f"Post {post.ids.post_id} has parent but is type '{post.post_type.value}' (should be 'reply')",
                {"post_id": post.ids.post_id, "parent_post_id": post.ids.parent_post_id},
            )
        )

    # Check: posts without parent should be type TOPIC
    if not post.ids.parent_post_id and post.post_type != PostType.TOPIC:
        errors.append(
            ValidationError(
                "warning",
                f"Post {post.ids.post_id} has no parent but is type '{post.post_type.value}' (expected 'topic')",
                {"post_id": post.ids.post_id},
            )
        )

    # Check: parent reference is valid (post exists)
    if post.ids.parent_post_id:
        parent = store.read_post(post.ids.parent_post_id)
        if not parent:
            errors.append(
                ValidationError(
                    "error",
                    f"Post {post.ids.post_id} references missing parent {post.ids.parent_post_id}",
                    {"post_id": post.ids.post_id, "parent_post_id": post.ids.parent_post_id},
                )
            )

    # Check: replies should have position set
    if post.post_type == PostType.REPLY and post.ids.position is None:
        errors.append(
            ValidationError(
                "warning", f"Reply post {post.ids.post_id} has no position set", {"post_id": post.ids.post_id}
            )
        )

    # Check: author should be present
    if not post.author or not post.author.display_name:
        errors.append(
            ValidationError("warning", f"Post {post.ids.post_id} has no author", {"post_id": post.ids.post_id})
        )

    # Check: timestamp should be parsed
    if not post.timestamps.parsed_iso:
        errors.append(
            ValidationError(
                "info",
                f"Post {post.ids.post_id} has no parsed timestamp (confidence: {post.timestamps.parse_confidence})",
                {"post_id": post.ids.post_id, "raw": post.timestamps.raw},
            )
        )

    return errors


def validate_topic(topic: TopicLeaf, store: JsonLeafStore) -> list[ValidationError]:
    """
    Validate a topic for data integrity.

    Checks:
    - All post_ids have corresponding post files
    - First post is a topic (no parent)
    - Reply tree matches flat post list
    - No circular references
    - Statistics are consistent

    Parameters
    ----------
    topic:
        Topic to validate
    store:
        Store to load post data

    Returns
    -------
    List of validation errors (empty if valid)
    """
    errors = []

    # Check: topic should have posts
    if not topic.post_ids:
        errors.append(
            ValidationError(
                "warning", f"Topic {topic.topic_slug or topic.topic_url} has no posts", {"topic_url": topic.topic_url}
            )
        )
        return errors

    # Check: all post_ids have corresponding files
    missing_posts = []
    for post_id in topic.post_ids:
        post = store.read_post(post_id)
        if not post:
            missing_posts.append(post_id)

    if missing_posts:
        errors.append(
            ValidationError(
                "error",
                f"Topic {topic.topic_slug} has {len(missing_posts)} missing post files",
                {"topic_url": topic.topic_url, "missing": missing_posts[:5]},  # Show first 5
            )
        )

    # Check: first post should be topic type (no parent)
    first_post = store.read_post(topic.post_ids[0])
    if first_post:
        if first_post.ids.parent_post_id is not None:
            errors.append(
                ValidationError(
                    "error",
                    f"First post {first_post.ids.post_id} has parent {first_post.ids.parent_post_id} (should be root)",
                    {"topic_url": topic.topic_url, "first_post": first_post.ids.post_id},
                )
            )

        if first_post.post_type != PostType.TOPIC:
            errors.append(
                ValidationError(
                    "warning",
                    f"First post {first_post.ids.post_id} is type '{first_post.post_type.value}' (expected 'topic')",
                    {"topic_url": topic.topic_url},
                )
            )

    # Check: reply tree matches flat post list
    if topic.reply_tree:
        tree_posts = set(extract_post_ids_from_tree(topic.reply_tree))
        flat_posts = set(topic.post_ids)

        if tree_posts != flat_posts:
            missing_in_tree = flat_posts - tree_posts
            extra_in_tree = tree_posts - flat_posts

            if missing_in_tree:
                errors.append(
                    ValidationError(
                        "error",
                        f"Topic {topic.topic_slug}: {len(missing_in_tree)} posts missing from reply tree",
                        {"topic_url": topic.topic_url, "missing": list(missing_in_tree)[:5]},
                    )
                )

            if extra_in_tree:
                errors.append(
                    ValidationError(
                        "error",
                        f"Topic {topic.topic_slug}: {len(extra_in_tree)} extra posts in reply tree",
                        {"topic_url": topic.topic_url, "extra": list(extra_in_tree)[:5]},
                    )
                )

    # Check: no circular references
    circular = detect_circular_references(topic.post_ids, store)
    if circular:
        errors.append(
            ValidationError(
                "error",
                f"Topic {topic.topic_slug} has circular reference: {' -> '.join(circular)}",
                {"topic_url": topic.topic_url, "cycle": circular},
            )
        )

    # Check: reply_count matches actual replies
    if topic.reply_tree:
        actual_reply_count = len(topic.post_ids) - 1  # Exclude topic starter
        if topic.reply_count != actual_reply_count:
            errors.append(
                ValidationError(
                    "warning",
                    f"Topic {topic.topic_slug}: reply_count is {topic.reply_count} but found {actual_reply_count} replies",
                    {"topic_url": topic.topic_url},
                )
            )

    return errors


def detect_circular_references(post_ids: list[str], store: JsonLeafStore) -> list[str] | None:
    """
    Detect circular references in parent relationships.

    Uses cycle detection (visited set tracking) to find cycles.

    Parameters
    ----------
    post_ids:
        Post IDs to check
    store:
        Store to load post data

    Returns
    -------
    List representing the cycle (e.g., ["A", "B", "C", "A"]) if found, None otherwise
    """

    def find_cycle_from(start_id: str, visited: set[str], path: list[str]) -> list[str] | None:
        if start_id in visited:
            # Found cycle - return the cyclic portion
            cycle_start = path.index(start_id)
            return path[cycle_start:] + [start_id]

        visited.add(start_id)
        path.append(start_id)

        post = store.read_post(start_id)
        if post and post.ids.parent_post_id:
            result = find_cycle_from(post.ids.parent_post_id, visited, path[:])
            if result:
                return result

        return None

    for post_id in post_ids:
        cycle = find_cycle_from(post_id, set(), [])
        if cycle:
            return cycle

    return None


def validate_all_topics(store: JsonLeafStore, verbose: bool = False) -> dict:
    """
    Validate all topics in the store.

    Parameters
    ----------
    store:
        Store to validate
    verbose:
        If True, print each validation error

    Returns
    -------
    Summary dictionary with counts and errors
    """
    all_errors = []
    topics = store.list_all_topics()

    for topic in topics:
        topic_errors = validate_topic(topic, store)
        if topic_errors:
            all_errors.extend(topic_errors)
            if verbose:
                print(f"\n{topic.topic_slug or topic.topic_url}:")
                for err in topic_errors:
                    print(f"  {err}")

    # Count by severity
    error_count = sum(1 for e in all_errors if e.severity == "error")
    warning_count = sum(1 for e in all_errors if e.severity == "warning")
    info_count = sum(1 for e in all_errors if e.severity == "info")

    return {
        "topics_checked": len(topics),
        "total_errors": len(all_errors),
        "errors": error_count,
        "warnings": warning_count,
        "info": info_count,
        "all_errors": all_errors,
    }


def validate_all_posts(store: JsonLeafStore, verbose: bool = False) -> dict:
    """
    Validate all individual posts in the store.

    Parameters
    ----------
    store:
        Store to validate
    verbose:
        If True, print each validation error

    Returns
    -------
    Summary dictionary with counts and errors
    """
    all_errors = []
    posts = store.list_all_posts()

    for post in posts:
        post_errors = validate_post(post, store)
        if post_errors:
            all_errors.extend(post_errors)
            if verbose:
                print(f"\nPost {post.ids.post_id}:")
                for err in post_errors:
                    print(f"  {err}")

    # Count by severity
    error_count = sum(1 for e in all_errors if e.severity == "error")
    warning_count = sum(1 for e in all_errors if e.severity == "warning")
    info_count = sum(1 for e in all_errors if e.severity == "info")

    return {
        "posts_checked": len(posts),
        "total_errors": len(all_errors),
        "errors": error_count,
        "warnings": warning_count,
        "info": info_count,
        "all_errors": all_errors,
    }
