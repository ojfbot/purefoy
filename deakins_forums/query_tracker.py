#!/usr/bin/env python3
"""
Query provenance tracking for forum scraping.

Tracks which queries touched which topics, when, and by whom.
Provides research activity lineage and query-to-content mapping.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
import json


@dataclass
class QuerierPersona:
    """Metadata about who is performing the query."""
    role: str  # e.g., "Director", "DP", "Gaffer"
    department: str  # e.g., "Camera", "Lighting", "Production"
    context: str  # e.g., "TV miniseries development", "Feature pre-production"


@dataclass
class QueryMetadata:
    """Complete metadata for a research query."""
    query_id: str  # unique identifier
    query_name: str  # human-readable name
    querier: QuerierPersona
    intent: str  # research objective/question
    target_forums: List[str]
    timestamp: str
    topics_accessed: List[str] = field(default_factory=list)  # topic slugs
    topics_newly_scraped: List[str] = field(default_factory=list)
    topics_revisited: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        return data


@dataclass
class TopicAccessRecord:
    """Record of a single topic access."""
    query_id: str
    query_name: str
    querier_role: str
    timestamp: str
    was_new_scrape: bool  # True if first time scraped, False if revisited


class QueryTracker:
    """Tracks queries and their relationship to topics."""

    def __init__(self, storage_path: Path):
        self.storage_path = Path(storage_path)
        self.query_log_file = self.storage_path / "_site" / "query_log.json"
        self.query_log_file.parent.mkdir(parents=True, exist_ok=True)

    def load_query_log(self) -> Dict[str, Any]:
        """Load existing query log."""
        if not self.query_log_file.exists():
            return {
                "queries": {},
                "topic_access_index": {}  # topic_slug -> [access_records]
            }

        with open(self.query_log_file, 'r') as f:
            return json.load(f)

    def save_query_log(self, log: Dict[str, Any]):
        """Save query log to disk."""
        with open(self.query_log_file, 'w') as f:
            json.dump(log, f, indent=2)

    def start_query(
        self,
        query_name: str,
        querier_role: str,
        querier_department: str,
        query_context: str,
        query_intent: str,
        target_forums: List[str]
    ) -> QueryMetadata:
        """
        Start tracking a new query.

        Returns a QueryMetadata object with a unique query_id.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        query_id = f"{querier_role.lower().replace(' ', '-')}_{timestamp[:19].replace(':', '-')}"

        querier = QuerierPersona(
            role=querier_role,
            department=querier_department,
            context=query_context
        )

        metadata = QueryMetadata(
            query_id=query_id,
            query_name=query_name,
            querier=querier,
            intent=query_intent,
            target_forums=target_forums,
            timestamp=timestamp
        )

        return metadata

    def log_topic_access(
        self,
        query_metadata: QueryMetadata,
        topic_slug: str,
        forum_slug: str,
        was_new_scrape: bool
    ):
        """
        Log that a query accessed a specific topic.

        Args:
            query_metadata: The query being executed
            topic_slug: The topic that was accessed
            forum_slug: The forum containing the topic
            was_new_scrape: True if this was the first time scraping this topic
        """
        # Update query metadata
        full_topic_id = f"{forum_slug}__{topic_slug}"
        query_metadata.topics_accessed.append(full_topic_id)

        if was_new_scrape:
            query_metadata.topics_newly_scraped.append(full_topic_id)
        else:
            query_metadata.topics_revisited.append(full_topic_id)

        # Load current log
        log = self.load_query_log()

        # Create access record
        access_record = TopicAccessRecord(
            query_id=query_metadata.query_id,
            query_name=query_metadata.query_name,
            querier_role=query_metadata.querier.role,
            timestamp=datetime.now(timezone.utc).isoformat(),
            was_new_scrape=was_new_scrape
        )

        # Add to topic access index
        if full_topic_id not in log["topic_access_index"]:
            log["topic_access_index"][full_topic_id] = []

        log["topic_access_index"][full_topic_id].append(asdict(access_record))

        # Save updated log
        self.save_query_log(log)

    def finalize_query(self, query_metadata: QueryMetadata):
        """
        Finalize and save a completed query.

        Stores the complete query metadata in the query log.
        """
        log = self.load_query_log()

        # Store query metadata
        log["queries"][query_metadata.query_id] = query_metadata.to_dict()

        # Save updated log
        self.save_query_log(log)

    def get_topic_provenance(self, topic_slug: str, forum_slug: str) -> List[Dict[str, Any]]:
        """
        Get all queries that have accessed a specific topic.

        Returns a list of access records showing who accessed it and when.
        """
        log = self.load_query_log()
        full_topic_id = f"{forum_slug}__{topic_slug}"
        return log["topic_access_index"].get(full_topic_id, [])

    def get_query_summary(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of a specific query's activity."""
        log = self.load_query_log()
        return log["queries"].get(query_id)

    def get_all_queries(self) -> Dict[str, Any]:
        """Get all queries in the log."""
        log = self.load_query_log()
        return log["queries"]

    def generate_provenance_report(self) -> str:
        """Generate a human-readable provenance report."""
        log = self.load_query_log()

        lines = []
        lines.append("=" * 80)
        lines.append("QUERY PROVENANCE REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary stats
        num_queries = len(log["queries"])
        num_topics_touched = len(log["topic_access_index"])

        lines.append(f"Total Queries Executed: {num_queries}")
        lines.append(f"Unique Topics Accessed: {num_topics_touched}")
        lines.append("")

        # Query details
        lines.append("─" * 80)
        lines.append("QUERIES")
        lines.append("─" * 80)

        for query_id, query_data in log["queries"].items():
            lines.append(f"\n{query_data['query_name']}")
            lines.append(f"  ID: {query_id}")
            lines.append(f"  Querier: {query_data['querier']['role']} ({query_data['querier']['department']})")
            lines.append(f"  Context: {query_data['querier']['context']}")
            lines.append(f"  Intent: {query_data['intent']}")
            lines.append(f"  Timestamp: {query_data['timestamp']}")
            lines.append(f"  Topics Accessed: {len(query_data['topics_accessed'])}")
            lines.append(f"    - Newly Scraped: {len(query_data['topics_newly_scraped'])}")
            lines.append(f"    - Revisited: {len(query_data['topics_revisited'])}")

        lines.append("")
        lines.append("─" * 80)
        lines.append("TOPIC ACCESS INDEX")
        lines.append("─" * 80)
        lines.append(f"\nShowing topics with multiple accesses:")
        lines.append("")

        # Show topics accessed by multiple queries
        multi_access_topics = {
            topic: accesses
            for topic, accesses in log["topic_access_index"].items()
            if len(accesses) > 1
        }

        if multi_access_topics:
            for topic, accesses in sorted(multi_access_topics.items(),
                                         key=lambda x: len(x[1]),
                                         reverse=True)[:20]:
                lines.append(f"{topic} ({len(accesses)} accesses)")
                for access in accesses[:3]:  # Show first 3 accesses
                    lines.append(f"  - {access['querier_role']}: {access['query_name']} ({access['timestamp'][:10]})")
                if len(accesses) > 3:
                    lines.append(f"  ... and {len(accesses) - 3} more")
                lines.append("")
        else:
            lines.append("(No topics accessed by multiple queries yet)")

        lines.append("=" * 80)

        return "\n".join(lines)
