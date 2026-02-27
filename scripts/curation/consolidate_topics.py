#!/usr/bin/env python3
"""
Topic Consolidation Tool
Creates consolidated topic buckets for low-engagement discussions.
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List
from datetime import datetime
import hashlib

def load_analysis_data(analysis_dir: Path) -> Dict:
    """Load Phase 1 analysis results."""

    print("Loading Phase 1 analysis data...")

    # Load low engagement topics
    with open(analysis_dir / 'low_engagement_topics.json') as f:
        engagement_data = json.load(f)

    # Load housekeeping posts
    with open(analysis_dir / 'housekeeping_posts.json') as f:
        housekeeping_data = json.load(f)

    # Load author statistics
    with open(analysis_dir / 'author_statistics.json') as f:
        author_stats = json.load(f)

    return {
        'engagement': engagement_data,
        'housekeeping': housekeeping_data,
        'authors': author_stats,
    }

def create_consolidated_bucket(
    bucket_id: str,
    bucket_name: str,
    description: str,
    topics: List[Dict],
    posts_by_id: Dict
) -> Dict:
    """Create a consolidated topic bucket."""

    # Gather all post IDs from these topics
    all_post_ids = []
    topic_summaries = []

    for topic in topics:
        topic_slug = topic['topic_slug']

        topic_summaries.append({
            'topic_slug': topic_slug,
            'title': topic['title'],
            'author': topic['starter_author'],
            'forum_slug': topic['forum_slug'],
            'reply_count': topic['reply_count'],
            'content_preview': topic['starter_content_preview'],
            'topic_url': topic.get('topic_url', ''),
        })

        # Note: We'll need to load the actual topic files to get post_ids
        # For now, just store the metadata

    # Calculate statistics
    total_questions = len(topics)
    authors = list(set(t['starter_author'] for t in topics))
    forums = list(set(t['forum_slug'] for t in topics))

    # Categorize by forum
    by_forum = defaultdict(list)
    for topic in topics:
        by_forum[topic['forum_slug']].append(topic['topic_slug'])

    # Create consolidated bucket
    bucket = {
        'bucket_id': bucket_id,
        'bucket_name': bucket_name,
        'description': description,
        'total_topics': total_questions,
        'unique_authors': len(authors),
        'forums_represented': forums,
        'topics': topic_summaries,
        'topics_by_forum': dict(by_forum),
        'created_at': datetime.now().isoformat(),
        'curation_version': 'v1',
    }

    return bucket

def consolidate_low_engagement_topics(
    engagement_data: Dict,
    posts_dir: Path,
    topics_dir: Path
) -> List[Dict]:
    """Create consolidated buckets for low-engagement topics."""

    print("\nCreating consolidated topic buckets...")

    # Load posts for context
    posts_by_id = {}
    print("  Loading posts...")
    for post_file in posts_dir.glob('*.json'):
        try:
            with open(post_file) as f:
                post = json.load(f)
                posts_by_id[post['ids']['post_id']] = post
        except:
            continue

    # Get categorized low-engagement topics
    categorized = engagement_data['categorized_low_engagement']

    # Define bucket configurations
    bucket_configs = [
        {
            'id': 'unanswered-lighting',
            'name': 'Unanswered Lighting Questions',
            'description': 'Collection of lighting-related questions that received minimal engagement. Topics cover lighting setups, techniques, equipment, and practical approaches.',
            'category': 'lighting',
        },
        {
            'id': 'unanswered-gear',
            'name': 'Unanswered Camera & Gear Questions',
            'description': 'Questions about camera selection, lens choices, technical specifications, and equipment recommendations that didn\'t receive substantive answers.',
            'category': 'gear_questions',
        },
        {
            'id': 'film-specific-questions',
            'name': 'Film-Specific Questions',
            'description': 'Questions about specific films Roger Deakins worked on, including technique breakdowns, equipment used, and creative decisions.',
            'category': 'film_specific',
        },
        {
            'id': 'technical-questions',
            'name': 'Technical Cinematography Questions',
            'description': 'Technical questions about exposure, color science, workflows, and cinematography fundamentals that need answers.',
            'category': 'technical_questions',
        },
        {
            'id': 'composition-framing',
            'name': 'Composition & Framing Questions',
            'description': 'Questions about aspect ratios, framing choices, visual design, and compositional techniques.',
            'category': 'composition',
        },
        {
            'id': 'color-grading',
            'name': 'Color Grading Questions',
            'description': 'Post-production color workflow questions, LUT creation, and color correction techniques.',
            'category': 'color_grading',
        },
        {
            'id': 'career-advice',
            'name': 'Career Advice & Getting Started',
            'description': 'Questions about breaking into the industry, education paths, building portfolios, and career development.',
            'category': 'career_advice',
        },
        {
            'id': 'community-off-topic',
            'name': 'Community & Off-Topic Discussions',
            'description': 'Forum meta-discussions, introductions, off-topic conversations, and community-building posts.',
            'category': 'off_topic',
        },
    ]

    buckets = []

    for config in bucket_configs:
        category = config['category']
        topics = categorized.get(category, [])

        if len(topics) >= 5:  # Only create bucket if at least 5 topics
            print(f"  Creating bucket: {config['name']} ({len(topics)} topics)")

            bucket = create_consolidated_bucket(
                bucket_id=config['id'],
                bucket_name=config['name'],
                description=config['description'],
                topics=topics,
                posts_by_id=posts_by_id
            )

            buckets.append(bucket)
        else:
            print(f"  Skipping {config['name']}: only {len(topics)} topics (need 5+)")

    return buckets

def add_consolidation_metadata(
    topics_dir: Path,
    buckets: List[Dict],
    output_dir: Path
) -> None:
    """Add consolidation metadata to original topic files (non-destructive)."""

    print("\nAdding consolidation metadata to topics...")

    # Build lookup of topic_slug -> bucket_id
    topic_to_bucket = {}
    for bucket in buckets:
        for topic in bucket['topics']:
            topic_to_bucket[topic['topic_slug']] = bucket['bucket_id']

    # Create curated topics directory
    curated_topics_dir = output_dir / 'topics'
    curated_topics_dir.mkdir(parents=True, exist_ok=True)

    updated_count = 0

    for topic_file in topics_dir.glob('*.json'):
        try:
            with open(topic_file) as f:
                topic = json.load(f)

            topic_slug = topic.get('topic_slug', '')

            if topic_slug in topic_to_bucket:
                # Add curation metadata
                if 'curation' not in topic:
                    topic['curation'] = {}

                topic['curation'].update({
                    'consolidation_status': 'consolidated_into',
                    'consolidated_bucket': topic_to_bucket[topic_slug],
                    'consolidated_at': datetime.now().isoformat(),
                    'curator': 'automated-v1',
                })

                # Save updated topic to curated directory
                output_file = curated_topics_dir / topic_file.name
                with open(output_file, 'w') as f:
                    json.dump(topic, f, indent=2)

                updated_count += 1
        except Exception as e:
            print(f"  Error processing {topic_file.name}: {e}")
            continue

    print(f"  Updated {updated_count} topic files with consolidation metadata")

def main():
    """Main consolidation function."""

    base_dir = Path(__file__).parent.parent.parent
    analysis_dir = base_dir / 'analysis' / 'curation'
    posts_dir = base_dir / 'library' / 'forums' / 'posts'
    topics_dir = base_dir / 'library' / 'forums' / 'topics'
    output_dir = base_dir / 'library' / 'forums' / '_curated'

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load analysis data
    data = load_analysis_data(analysis_dir)

    # Create consolidated buckets
    buckets = consolidate_low_engagement_topics(
        data['engagement'],
        posts_dir,
        topics_dir
    )

    # Save consolidated buckets
    buckets_dir = output_dir / 'topics' / 'consolidated'
    buckets_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving {len(buckets)} consolidated buckets...")

    for bucket in buckets:
        output_file = buckets_dir / f"{bucket['bucket_id']}.json"
        with open(output_file, 'w') as f:
            json.dump(bucket, f, indent=2)
        print(f"  ✓ {bucket['bucket_name']}: {output_file}")

    # Add consolidation metadata to original topics
    add_consolidation_metadata(topics_dir, buckets, output_dir)

    # Create summary
    summary = {
        'generated_at': datetime.now().isoformat(),
        'total_buckets': len(buckets),
        'total_topics_consolidated': sum(b['total_topics'] for b in buckets),
        'buckets': [
            {
                'bucket_id': b['bucket_id'],
                'bucket_name': b['bucket_name'],
                'topics_count': b['total_topics'],
                'authors_count': b['unique_authors'],
            }
            for b in buckets
        ]
    }

    summary_file = output_dir / 'consolidation_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n✅ Consolidation complete!")
    print(f"  Buckets created: {len(buckets)}")
    print(f"  Topics consolidated: {summary['total_topics_consolidated']}")
    print(f"  Summary saved to: {summary_file}")

    # Display bucket summary
    print("\n" + "="*70)
    print("CONSOLIDATED BUCKETS CREATED")
    print("="*70)
    for bucket in buckets:
        print(f"\n📦 {bucket['bucket_name']}")
        print(f"   ID: {bucket['bucket_id']}")
        print(f"   Topics: {bucket['total_topics']}")
        print(f"   Authors: {bucket['unique_authors']}")
        print(f"   Forums: {', '.join(bucket['forums_represented'][:3])}")

if __name__ == '__main__':
    main()
