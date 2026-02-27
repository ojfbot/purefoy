#!/usr/bin/env python3
"""
Curated Views Generator
Creates filtered and organized views of the forum data based on curation analysis.
"""

import json
import shutil
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set
from datetime import datetime

def load_curation_data(analysis_dir: Path) -> Dict:
    """Load all curation analysis results."""

    print("Loading curation data...")

    with open(analysis_dir / 'author_statistics.json') as f:
        authors = json.load(f)

    with open(analysis_dir / 'housekeeping_posts.json') as f:
        housekeeping = json.load(f)

    with open(analysis_dir / 'low_engagement_topics.json') as f:
        engagement = json.load(f)

    return {
        'authors': authors,
        'housekeeping': housekeeping,
        'engagement': engagement,
    }

def filter_housekeeping_posts(
    posts_dir: Path,
    housekeeping_data: Dict,
    output_dir: Path
) -> Dict:
    """Create filtered post collection without housekeeping."""

    print("\nFiltering housekeeping posts...")

    # Get housekeeping post IDs
    housekeeping_ids = set(p['post_id'] for p in housekeeping_data['housekeeping_posts'])
    uncertain_ids = set(p['post_id'] for p in housekeeping_data['uncertain_posts'])

    print(f"  Housekeeping posts to filter: {len(housekeeping_ids)}")
    print(f"  Uncertain posts (preserved): {len(uncertain_ids)}")

    # Create filtered posts directory
    filtered_posts_dir = output_dir / 'posts' / 'cinematography'
    filtered_posts_dir.mkdir(parents=True, exist_ok=True)

    cinematography_count = 0
    housekeeping_count = 0

    for post_file in posts_dir.glob('*.json'):
        try:
            with open(post_file) as f:
                post = json.load(f)

            post_id = post['ids']['post_id']

            # Add curation metadata
            if 'curation' not in post:
                post['curation'] = {}

            if post_id in housekeeping_ids:
                post['curation'].update({
                    'is_housekeeping': True,
                    'filtered_from_cinematography': True,
                    'curated_at': datetime.now().isoformat(),
                })
                housekeeping_count += 1
                # Don't copy to cinematography dir
            else:
                post['curation'].update({
                    'is_housekeeping': False,
                    'filtered_from_cinematography': False,
                    'curated_at': datetime.now().isoformat(),
                })

                # Copy to filtered directory
                output_file = filtered_posts_dir / post_file.name
                with open(output_file, 'w') as f:
                    json.dump(post, f, indent=2)

                cinematography_count += 1

        except Exception as e:
            print(f"  Error processing {post_file.name}: {e}")
            continue

        if (cinematography_count + housekeeping_count) % 500 == 0:
            print(f"  Processed {cinematography_count + housekeeping_count} posts...")

    print(f"\n  ✓ Cinematography posts: {cinematography_count}")
    print(f"  ✓ Housekeeping filtered: {housekeeping_count}")

    return {
        'cinematography_posts': cinematography_count,
        'housekeeping_filtered': housekeeping_count,
    }

def organize_by_persona(
    posts_dir: Path,
    author_stats: Dict,
    output_dir: Path
) -> Dict:
    """Organize posts by author persona tiers."""

    print("\nOrganizing posts by persona...")

    # Create persona directories
    personas_dir = output_dir / 'personas'
    personas_dir.mkdir(parents=True, exist_ok=True)

    tier_dirs = {
        'S': personas_dir / 's_tier_masters',
        'A': personas_dir / 'a_tier_professionals',
        'B': personas_dir / 'b_tier_students',
        'C': personas_dir / 'c_tier_enthusiasts',
        'D': personas_dir / 'd_tier_visitors',
    }

    for tier_dir in tier_dirs.values():
        (tier_dir / 'posts').mkdir(parents=True, exist_ok=True)

    # Build author -> tier lookup
    author_to_tier = {
        name: stats['persona_tier']
        for name, stats in author_stats.items()
    }

    # Create author metadata files for each tier
    tier_authors = defaultdict(list)
    for name, stats in author_stats.items():
        tier = stats['persona_tier']
        tier_authors[tier].append({
            'display_name': name,
            'persona_name': stats['persona_name'],
            'persona_score': stats['persona_score'],
            'post_count': stats['post_count'],
            'roger_replied_count': stats['roger_replied_count'],
        })

    # Save author lists for each tier
    for tier, authors_list in tier_authors.items():
        tier_dir = tier_dirs[tier]
        authors_file = tier_dir / 'authors.json'

        authors_data = {
            'tier': tier,
            'tier_name': authors_list[0]['persona_name'] if authors_list else '',
            'author_count': len(authors_list),
            'authors': sorted(authors_list, key=lambda x: x['persona_score'], reverse=True),
            'generated_at': datetime.now().isoformat(),
        }

        with open(authors_file, 'w') as f:
            json.dump(authors_data, f, indent=2)

    # Organize posts by tier
    tier_counts = defaultdict(int)

    for post_file in posts_dir.glob('*.json'):
        try:
            with open(post_file) as f:
                post = json.load(f)

            author = post.get('author', {}).get('display_name', 'Unknown')
            tier = author_to_tier.get(author, 'D')  # Default to D-tier for unknown

            # Add persona metadata to post
            if 'curation' not in post:
                post['curation'] = {}

            post['curation'].update({
                'author_persona_tier': tier,
                'author_persona_score': author_stats.get(author, {}).get('persona_score', 0),
            })

            # Copy to tier directory
            tier_dir = tier_dirs[tier]
            output_file = tier_dir / 'posts' / post_file.name

            with open(output_file, 'w') as f:
                json.dump(post, f, indent=2)

            tier_counts[tier] += 1

        except Exception as e:
            print(f"  Error processing {post_file.name}: {e}")
            continue

        if sum(tier_counts.values()) % 500 == 0:
            print(f"  Processed {sum(tier_counts.values())} posts...")

    print("\n  Posts by tier:")
    for tier in ['S', 'A', 'B', 'C', 'D']:
        count = tier_counts[tier]
        author_count = len(tier_authors[tier])
        tier_name = tier_authors[tier][0]['persona_name'] if tier_authors[tier] else 'N/A'
        print(f"    {tier}-Tier ({tier_name}): {count} posts from {author_count} authors")

    return dict(tier_counts)

def create_high_engagement_collection(
    topics_dir: Path,
    posts_dir: Path,
    engagement_data: Dict,
    output_dir: Path
) -> Dict:
    """Create collection of high-engagement topics."""

    print("\nCreating high-engagement collection...")

    # Get high engagement topics
    high_engagement = engagement_data['high_engagement']

    collection_dir = output_dir / 'topics' / 'high_engagement'
    collection_dir.mkdir(parents=True, exist_ok=True)

    # Copy high-engagement topic files
    copied = 0
    for topic_summary in high_engagement:
        topic_slug = topic_summary['topic_slug']

        # Find the topic file
        for topic_file in topics_dir.glob('*.json'):
            try:
                with open(topic_file) as f:
                    topic = json.load(f)

                if topic.get('topic_slug') == topic_slug:
                    # Add curation metadata
                    if 'curation' not in topic:
                        topic['curation'] = {}

                    topic['curation'].update({
                        'engagement_tier': 'high',
                        'consolidation_status': 'standalone',
                        'curated_at': datetime.now().isoformat(),
                    })

                    # Save to collection
                    output_file = collection_dir / topic_file.name
                    with open(output_file, 'w') as f:
                        json.dump(topic, f, indent=2)

                    copied += 1
                    break
            except:
                continue

    print(f"  ✓ High-engagement topics: {copied}")

    return {'high_engagement_topics': copied}

def generate_metadata(
    stats: Dict,
    output_dir: Path
) -> None:
    """Generate master metadata file for curated data."""

    print("\nGenerating metadata...")

    metadata = {
        'generated_at': datetime.now().isoformat(),
        'curation_version': 'v1',
        'curator': 'automated',

        'statistics': {
            'cinematography_posts': stats.get('cinematography_posts', 0),
            'housekeeping_filtered': stats.get('housekeeping_filtered', 0),
            'consolidated_topics': stats.get('consolidated_topics', 0),
            'consolidation_buckets': stats.get('consolidation_buckets', 0),
            'high_engagement_topics': stats.get('high_engagement_topics', 0),
        },

        'persona_distribution': stats.get('persona_counts', {}),

        'structure': {
            'posts/cinematography/': 'Housekeeping-filtered posts (pure cinematography)',
            'topics/high_engagement/': 'Topics with 11+ substantive replies',
            'topics/consolidated/': 'Low-engagement topics organized into 8 buckets',
            'personas/s_tier_masters/': 'Posts by master cinematographers (Roger, James)',
            'personas/a_tier_professionals/': 'Posts by working professionals',
            'personas/b_tier_students/': 'Posts by serious students & emerging DPs',
            'personas/c_tier_enthusiasts/': 'Posts by enthusiasts & hobbyists',
            'personas/d_tier_visitors/': 'Posts by one-time visitors',
        },

        'provenance': {
            'source_data': 'library/forums/ (original, preserved)',
            'curation_scripts': 'scripts/curation/',
            'analysis_data': 'analysis/curation/',
        },

        'notes': [
            'All original data preserved in library/forums/',
            'Curation is non-destructive and additive',
            'Metadata added to posts/topics via "curation" field',
            'Cross-references maintained for navigation',
        ]
    }

    metadata_file = output_dir / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"  ✓ Metadata saved to: {metadata_file}")

def main():
    """Main generation function."""

    base_dir = Path(__file__).parent.parent.parent
    analysis_dir = base_dir / 'analysis' / 'curation'
    posts_dir = base_dir / 'library' / 'forums' / 'posts'
    topics_dir = base_dir / 'library' / 'forums' / 'topics'
    output_dir = base_dir / 'library' / 'forums' / '_curated'

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load curation data
    data = load_curation_data(analysis_dir)

    # Track statistics
    stats = {}

    # 1. Filter housekeeping posts
    filter_stats = filter_housekeeping_posts(
        posts_dir,
        data['housekeeping'],
        output_dir
    )
    stats.update(filter_stats)

    # 2. Organize by persona
    persona_counts = organize_by_persona(
        posts_dir,
        data['authors'],
        output_dir
    )
    stats['persona_counts'] = persona_counts

    # 3. Create high-engagement collection
    engagement_stats = create_high_engagement_collection(
        topics_dir,
        posts_dir,
        data['engagement'],
        output_dir
    )
    stats.update(engagement_stats)

    # 4. Add consolidation stats (already done in previous script)
    consolidation_file = output_dir / 'consolidation_summary.json'
    if consolidation_file.exists():
        with open(consolidation_file) as f:
            consolidation_data = json.load(f)
            stats['consolidated_topics'] = consolidation_data['total_topics_consolidated']
            stats['consolidation_buckets'] = consolidation_data['total_buckets']

    # 5. Generate metadata
    generate_metadata(stats, output_dir)

    # Summary
    print("\n" + "="*70)
    print("CURATED VIEWS GENERATED")
    print("="*70)
    print(f"\nCinematography posts: {stats['cinematography_posts']}")
    print(f"Housekeeping filtered: {stats['housekeeping_filtered']}")
    print(f"High-engagement topics: {stats['high_engagement_topics']}")
    print(f"Consolidated buckets: {stats.get('consolidation_buckets', 0)}")
    print(f"Topics consolidated: {stats.get('consolidated_topics', 0)}")

    print("\nPosts by persona:")
    for tier in ['S', 'A', 'B', 'C', 'D']:
        count = persona_counts.get(tier, 0)
        print(f"  {tier}-Tier: {count} posts")

    print("\n" + "="*70)
    print("CURATED DATA STRUCTURE")
    print("="*70)
    print(f"\nLocation: {output_dir}")
    print("\nDirectories created:")
    for path in sorted(output_dir.rglob('*')):
        if path.is_dir():
            rel_path = path.relative_to(output_dir)
            file_count = len(list(path.glob('*.json')))
            if file_count > 0:
                print(f"  {rel_path}/: {file_count} files")

    print(f"\n✅ Curated views generation complete!")

if __name__ == '__main__':
    main()
