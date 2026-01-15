"""
Reply tree construction and analysis utilities.

Builds hierarchical reply trees from flat post lists for agent-friendly traversal.
"""

from __future__ import annotations

from typing import Any, Optional

from .models import PostLeaf, PostType
from .store_json import JsonLeafStore


def build_reply_tree(post_ids: list[str], store: JsonLeafStore) -> Optional[dict[str, Any]]:
    """
    Build a nested reply tree from a flat list of post IDs.

    Parameters
    ----------
    post_ids:
        Flat list of post IDs in the topic (chronological order)
    store:
        Store to read post data from

    Returns
    -------
    Tree structure with format:
    {
        "post_id": "12345",
        "post_type": "topic",
        "author": "johndoe",
        "timestamp": "2026-01-15T10:00:00",
        "children": [
            {"post_id": "12346", "children": [...]},
            ...
        ]
    }

    Returns None if no posts or no topic starter found.
    """
    if not post_ids:
        return None

    # Load all posts
    posts: dict[str, PostLeaf] = {}
    for post_id in post_ids:
        post = store.read_post(post_id)
        if post:
            posts[post_id] = post

    if not posts:
        return None

    # Find the root (topic starter - post with no parent)
    root_post = None
    for post in posts.values():
        if post.post_type == PostType.TOPIC or post.ids.parent_post_id is None:
            root_post = post
            break

    if not root_post:
        # Fallback: use first post as root
        root_post = posts[post_ids[0]]

    # Build children map: parent_id -> [child posts]
    children_map: dict[str, list[PostLeaf]] = {}
    for post in posts.values():
        if post.ids.parent_post_id and post.ids.parent_post_id in posts:
            if post.ids.parent_post_id not in children_map:
                children_map[post.ids.parent_post_id] = []
            children_map[post.ids.parent_post_id].append(post)

    # Sort children by position or timestamp
    for parent_id in children_map:
        children_map[parent_id].sort(
            key=lambda p: (
                p.ids.position if p.ids.position is not None else 999999,
                p.timestamps.parsed_iso or "",
            )
        )

    def build_node(post: PostLeaf) -> dict[str, Any]:
        """Recursively build tree node."""
        node = {
            "post_id": post.ids.post_id,
            "post_type": post.post_type.value,
            "author": post.author.display_name if post.author else None,
            "timestamp": post.timestamps.parsed_iso,
            "children": []
        }

        # Recursively build children
        if post.ids.post_id in children_map:
            for child in children_map[post.ids.post_id]:
                node["children"].append(build_node(child))

        return node

    return build_node(root_post)


def calculate_thread_stats(reply_tree: Optional[dict[str, Any]]) -> dict[str, int]:
    """
    Calculate statistics from a reply tree.

    Parameters
    ----------
    reply_tree:
        Tree structure returned by build_reply_tree

    Returns
    -------
    Dictionary with:
        - reply_count: Total number of replies (excludes root)
        - max_depth: Maximum nesting depth
        - total_posts: Total posts including root
    """
    if not reply_tree:
        return {"reply_count": 0, "max_depth": 0, "total_posts": 0}

    def traverse(node: dict[str, Any], depth: int = 0) -> tuple[int, int]:
        """
        Traverse tree counting posts and tracking max depth.

        Returns (post_count, max_depth_seen)
        """
        post_count = 1  # Count this node
        max_depth_seen = depth

        for child in node.get("children", []):
            child_count, child_depth = traverse(child, depth + 1)
            post_count += child_count
            max_depth_seen = max(max_depth_seen, child_depth)

        return post_count, max_depth_seen

    total_posts, max_depth = traverse(reply_tree)
    reply_count = total_posts - 1  # Exclude root (topic starter)

    return {
        "reply_count": reply_count,
        "max_depth": max_depth,
        "total_posts": total_posts,
    }


def extract_post_ids_from_tree(reply_tree: Optional[dict[str, Any]]) -> list[str]:
    """
    Extract flat list of post IDs from reply tree.

    Useful for validation: ensure tree matches flat post_ids list.

    Parameters
    ----------
    reply_tree:
        Tree structure

    Returns
    -------
    Flat list of post IDs in depth-first order
    """
    if not reply_tree:
        return []

    post_ids = []

    def traverse(node: dict[str, Any]) -> None:
        post_ids.append(node["post_id"])
        for child in node.get("children", []):
            traverse(child)

    traverse(reply_tree)
    return post_ids


def find_author_posts_in_tree(
    reply_tree: Optional[dict[str, Any]],
    author_name: str,
    case_sensitive: bool = False
) -> list[dict[str, Any]]:
    """
    Find all posts by a specific author in the reply tree.

    Parameters
    ----------
    reply_tree:
        Tree structure
    author_name:
        Author name to search for
    case_sensitive:
        Whether to do case-sensitive matching

    Returns
    -------
    List of tree nodes (with full subtree) where author matches
    """
    if not reply_tree:
        return []

    matches = []

    def matches_author(node_author: Optional[str]) -> bool:
        if not node_author:
            return False
        if case_sensitive:
            return author_name in node_author
        return author_name.lower() in node_author.lower()

    def traverse(node: dict[str, Any]) -> None:
        if matches_author(node.get("author")):
            matches.append(node)

        for child in node.get("children", []):
            traverse(child)

    traverse(reply_tree)
    return matches


def find_direct_replies_to_post(
    reply_tree: dict[str, Any],
    target_post_id: str
) -> list[dict[str, Any]]:
    """
    Find all direct replies to a specific post.

    Parameters
    ----------
    reply_tree:
        Tree structure
    target_post_id:
        Post ID to find replies to

    Returns
    -------
    List of direct child nodes (not recursive - just immediate children)
    """
    def traverse(node: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        if node["post_id"] == target_post_id:
            return node.get("children", [])

        for child in node.get("children", []):
            result = traverse(child)
            if result is not None:
                return result

        return None

    result = traverse(reply_tree)
    return result if result is not None else []
