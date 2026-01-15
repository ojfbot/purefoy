#!/usr/bin/env python3
"""
Coverage tracking and reporting for forum scraping.

Tracks which forums/topics have been scraped and generates
coverage reports similar to test coverage tools.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import json


@dataclass
class ForumCoverage:
    """Coverage statistics for a single forum."""
    forum_slug: str
    forum_name: str
    total_topics_available: int
    topics_scraped: int
    posts_scraped: int
    last_scraped: Optional[str] = None
    first_scraped: Optional[str] = None

    @property
    def coverage_percent(self) -> float:
        """Calculate coverage percentage."""
        if self.total_topics_available == 0:
            return 0.0
        return (self.topics_scraped / self.total_topics_available) * 100

    @property
    def is_complete(self) -> bool:
        """Check if forum is fully scraped."""
        return self.topics_scraped >= self.total_topics_available


@dataclass
class QueryCoverage:
    """Coverage for a specific research query."""
    query_name: str
    target_forums: List[str]
    keywords: List[str]
    posts_matching: int = 0
    coverage_complete: bool = False
    notes: str = ""


@dataclass
class CoverageReport:
    """Complete coverage report for all forums."""
    timestamp: str
    total_forums: int = 0
    forums_covered: int = 0
    total_topics: int = 0
    topics_scraped: int = 0
    total_posts: int = 0
    forums: Dict[str, ForumCoverage] = field(default_factory=dict)
    queries: Dict[str, QueryCoverage] = field(default_factory=dict)

    @property
    def overall_coverage_percent(self) -> float:
        """Calculate overall coverage across all forums."""
        if self.total_topics == 0:
            return 0.0
        return (self.topics_scraped / self.total_topics) * 100


class CoverageTracker:
    """Tracks and reports on scraping coverage."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.coverage_file = storage_path / "_site" / "coverage.json"
        self.previous_report: Optional[CoverageReport] = None

    def load_previous_coverage(self) -> Optional[CoverageReport]:
        """Load previous coverage report if it exists."""
        if not self.coverage_file.exists():
            return None

        try:
            with open(self.coverage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            report = CoverageReport(
                timestamp=data['timestamp'],
                total_forums=data['total_forums'],
                forums_covered=data['forums_covered'],
                total_topics=data['total_topics'],
                topics_scraped=data['topics_scraped'],
                total_posts=data['total_posts']
            )

            # Reconstruct forums
            for slug, forum_data in data.get('forums', {}).items():
                report.forums[slug] = ForumCoverage(**forum_data)

            # Reconstruct queries
            for name, query_data in data.get('queries', {}).items():
                report.queries[name] = QueryCoverage(**query_data)

            self.previous_report = report
            return report

        except Exception as e:
            print(f"Warning: Could not load previous coverage: {e}")
            return None

    def save_coverage(self, report: CoverageReport):
        """Save coverage report to disk."""
        self.coverage_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'timestamp': report.timestamp,
            'total_forums': report.total_forums,
            'forums_covered': report.forums_covered,
            'total_topics': report.total_topics,
            'topics_scraped': report.topics_scraped,
            'total_posts': report.total_posts,
            'forums': {
                slug: {
                    'forum_slug': f.forum_slug,
                    'forum_name': f.forum_name,
                    'total_topics_available': f.total_topics_available,
                    'topics_scraped': f.topics_scraped,
                    'posts_scraped': f.posts_scraped,
                    'last_scraped': f.last_scraped,
                    'first_scraped': f.first_scraped
                }
                for slug, f in report.forums.items()
            },
            'queries': {
                name: {
                    'query_name': q.query_name,
                    'target_forums': q.target_forums,
                    'keywords': q.keywords,
                    'posts_matching': q.posts_matching,
                    'coverage_complete': q.coverage_complete,
                    'notes': q.notes
                }
                for name, q in report.queries.items()
            }
        }

        with open(self.coverage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def generate_report(self, storage_path: Path) -> CoverageReport:
        """Generate current coverage report by scanning stored data."""
        from .store_json import JsonLeafStore

        store = JsonLeafStore(storage_path)

        report = CoverageReport(
            timestamp=datetime.utcnow().isoformat()
        )

        # Count all stored data
        forums_data = {}

        # Scan topics to determine forum structure
        topics_dir = storage_path / "topics"
        if topics_dir.exists():
            for topic_file in topics_dir.glob("*.json"):
                try:
                    with open(topic_file, 'r', encoding='utf-8') as f:
                        topic_data = json.load(f)

                    # Handle both formats: direct fields or nested in ids
                    forum_slug = topic_data.get('forum_slug', topic_data.get('ids', {}).get('forum_slug'))
                    topic_slug = topic_data.get('topic_slug', topic_data.get('ids', {}).get('topic_slug'))

                    if not forum_slug or not topic_slug:
                        continue

                    if forum_slug not in forums_data:
                        forums_data[forum_slug] = {
                            'topics': set(),
                            'posts': 0,
                            'first_scraped': None,
                            'last_scraped': None
                        }

                    forums_data[forum_slug]['topics'].add(topic_slug)
                    forums_data[forum_slug]['posts'] += len(topic_data.get('post_ids', []))

                    scraped_at = topic_data.get('provenance', {}).get('scraped_at')
                    if scraped_at:
                        if not forums_data[forum_slug]['first_scraped']:
                            forums_data[forum_slug]['first_scraped'] = scraped_at
                        forums_data[forum_slug]['last_scraped'] = scraped_at

                except Exception as e:
                    print(f"Warning: Could not parse topic file {topic_file}: {e}")
                    continue

        # Load forum metadata to get total topic counts
        forums_dir = storage_path / "forums"
        forum_totals = {}

        if forums_dir.exists():
            for forum_file in forums_dir.glob("*.json"):
                try:
                    with open(forum_file, 'r', encoding='utf-8') as f:
                        forum_data = json.load(f)

                    slug = forum_data.get('forum_slug', forum_data.get('ids', {}).get('forum_slug'))
                    if not slug:
                        continue

                    forum_totals[slug] = {
                        'name': forum_data.get('title', forum_data.get('forum_name', slug)),
                        'total_topics': len(forum_data.get('topic_refs', []))
                    }
                except Exception as e:
                    print(f"Warning: Could not parse forum file {forum_file}: {e}")
                    continue

        # Build coverage for each forum
        for slug, data in forums_data.items():
            total_available = forum_totals.get(slug, {}).get('total_topics', len(data['topics']))

            report.forums[slug] = ForumCoverage(
                forum_slug=slug,
                forum_name=forum_totals.get(slug, {}).get('name', slug.replace('-', ' ').title()),
                total_topics_available=total_available,
                topics_scraped=len(data['topics']),
                posts_scraped=data['posts'],
                first_scraped=data['first_scraped'],
                last_scraped=data['last_scraped']
            )

        # Update aggregate stats
        report.total_forums = len(report.forums)
        report.forums_covered = len(report.forums)
        report.total_topics = sum(f.total_topics_available for f in report.forums.values())
        report.topics_scraped = sum(f.topics_scraped for f in report.forums.values())
        report.total_posts = sum(f.posts_scraped for f in report.forums.values())

        # Analyze query coverage
        report.queries = self._analyze_query_coverage(storage_path, report)

        return report

    def _analyze_query_coverage(self, storage_path: Path, report: CoverageReport) -> Dict[str, QueryCoverage]:
        """Analyze which queries can be answered with current data."""
        from .index_sqlite import SqliteIndex

        queries = {}

        # Define research queries
        query_definitions = [
            {
                'name': 'lighting_techniques',
                'display': 'Lighting Techniques & Setups',
                'forums': ['forum', 'film-talk'],
                'keywords': ['lighting', 'setup', 'lamp', 'practical', 'key light', 'fill'],
                'min_posts': 50
            },
            {
                'name': 'camera_equipment',
                'display': 'Camera & Lens Choices',
                'forums': ['forum', 'camera'],
                'keywords': ['camera', 'lens', 'ARRI', 'focal length', 'anamorphic'],
                'min_posts': 20
            },
            {
                'name': 'color_grading',
                'display': 'Color Grading & DI',
                'forums': ['post', 'forum'],
                'keywords': ['color', 'grade', 'LUT', 'DI', 'timing'],
                'min_posts': 30
            },
            {
                'name': 'roger_insights',
                'display': "Roger Deakins' Direct Advice",
                'forums': ['team-deakins', 'forum', 'film-talk', 'post'],
                'keywords': ['Roger Deakins'],
                'min_posts': 20
            },
            {
                'name': 'film_recommendations',
                'display': 'Film Study Recommendations',
                'forums': ['film-talk', 'team-deakins'],
                'keywords': ['film', 'watch', 'recommend', 'favorite'],
                'min_posts': 30
            },
            {
                'name': 'post_production',
                'display': 'Post Production Workflows',
                'forums': ['post'],
                'keywords': ['post', 'workflow', 'DI', 'grade', 'transfer'],
                'min_posts': 25
            }
        ]

        try:
            index = SqliteIndex(storage_path / "_site" / "kb.sqlite")

            for query_def in query_definitions:
                # Count matching posts
                matching_posts = 0
                for keyword in query_def['keywords']:
                    results = index.search_posts(
                        query=keyword,
                        limit=1000
                    )
                    matching_posts += len(results)

                # Check forum coverage
                required_forums = query_def['forums']
                forums_available = [f for f in required_forums if f in report.forums]

                coverage_complete = (
                    len(forums_available) >= len(required_forums) * 0.5 and
                    matching_posts >= query_def['min_posts']
                )

                notes = ""
                if coverage_complete:
                    notes = f"✓ {matching_posts} relevant posts found"
                else:
                    missing = set(required_forums) - set(forums_available)
                    if missing:
                        notes = f"⚠ Missing forums: {', '.join(missing)}"
                    else:
                        notes = f"⚠ Only {matching_posts}/{query_def['min_posts']} posts found"

                queries[query_def['name']] = QueryCoverage(
                    query_name=query_def['display'],
                    target_forums=required_forums,
                    keywords=query_def['keywords'],
                    posts_matching=matching_posts,
                    coverage_complete=coverage_complete,
                    notes=notes
                )

        except Exception as e:
            print(f"Warning: Could not analyze query coverage: {e}")

        return queries

    def calculate_delta(self, current: CoverageReport) -> Dict[str, Any]:
        """Calculate changes since previous report."""
        if not self.previous_report:
            return {
                'new_forums': list(current.forums.keys()),
                'new_topics': current.topics_scraped,
                'new_posts': current.total_posts,
                'coverage_increase': current.overall_coverage_percent
            }

        prev = self.previous_report

        new_forums = [
            slug for slug in current.forums.keys()
            if slug not in prev.forums
        ]

        # Calculate per-forum deltas
        forum_deltas = {}
        for slug, curr_forum in current.forums.items():
            if slug in prev.forums:
                prev_forum = prev.forums[slug]
                forum_deltas[slug] = {
                    'new_topics': curr_forum.topics_scraped - prev_forum.topics_scraped,
                    'new_posts': curr_forum.posts_scraped - prev_forum.posts_scraped,
                    'coverage_increase': curr_forum.coverage_percent - prev_forum.coverage_percent
                }
            else:
                forum_deltas[slug] = {
                    'new_topics': curr_forum.topics_scraped,
                    'new_posts': curr_forum.posts_scraped,
                    'coverage_increase': curr_forum.coverage_percent
                }

        return {
            'new_forums': new_forums,
            'new_topics': current.topics_scraped - prev.topics_scraped,
            'new_posts': current.total_posts - prev.total_posts,
            'coverage_increase': current.overall_coverage_percent - prev.overall_coverage_percent,
            'forum_deltas': forum_deltas
        }
