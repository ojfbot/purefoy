#!/usr/bin/env python3
"""
Author Statistics Aggregator
Analyzes all posts to build comprehensive author profiles for persona classification.
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List, Set

# Technical terms that indicate expertise
TECHNICAL_TERMS = {
    # Camera/Lenses
    'anamorphic', 'spherical', 'prime', 'zoom', 'focal length', 'aperture', 'f-stop',
    't-stop', 'depth of field', 'dof', 'bokeh', 'sensor', 'full frame', 'super 35',
    'alexa', 'arri', 'red', 'sony venice', 'panavision', 'cooke', 'zeiss', 'leica',

    # Lighting
    'key light', 'fill light', 'backlight', 'practicals', 'motivated lighting',
    'bounce', 'diffusion', 'neg fill', 'kino flo', 'hmi', 'tungsten', 'led',
    'color temperature', 'kelvin', 'cto', 'ctb', 'minus green', 'plus green',
    'skypanel', 'dedolight', 'leko', 'fresnel', 'par', 'softbox', 'chimera',

    # Exposure
    'exposure', 'stop', 'underexpose', 'overexpose', 'latitude', 'dynamic range',
    'clipping', 'zebras', 'false color', 'waveform', 'histogram', 'lut',
    'log', 'rec709', 'rec2020', 'aces', 'gamma', 'linear',

    # Color/Grade
    'color grading', 'color correction', 'davinci', 'baselight', 'primaries',
    'secondaries', 'luma', 'chroma', 'saturation', 'hue', 'lift', 'gamma', 'gain',
    'contrast', 'film emulation', 'print', 'digital intermediate', 'di',

    # Composition
    'rule of thirds', 'leading lines', 'symmetry', 'negative space', 'framing',
    'aspect ratio', 'widescreen', 'cinemascope', 'academy', 'golden ratio',

    # Movement
    'dolly', 'track', 'crane', 'jib', 'steadicam', 'ronin', 'movi', 'gimbal',
    'handheld', 'whip pan', 'tilt', 'pan', 'dutch angle', 'crab',

    # Production
    'gaffer', 'best boy', 'grip', 'key grip', 'dolly grip', 'focus puller',
    'ac', '1st ac', '2nd ac', 'dit', 'loader', 'da', 'production designer',
    'production value', 'call sheet', 'blocking', 'coverage', 'master shot',

    # Film specific
    'emulsion', 'film stock', 'grain', 'push process', 'pull process', 'bleach bypass',
    'skip bleach', 'force develop', '5219', '5207', 'vision3', 'ektachrome',
}

# Professional indicators
PROFESSIONAL_INDICATORS = {
    'asc', 'bsc', 'dop', 'cinematographer', 'director of photography',
    'camera operator', 'gaffer', 'key grip', 'focus puller',
    'shot on', 'filmed on', 'dp on', 'working on', 'wrapped on',
    'in production', 'in post', 'principal photography',
}

def count_technical_terms(text: str) -> int:
    """Count technical terms in text."""
    text_lower = text.lower()
    count = 0
    for term in TECHNICAL_TERMS:
        # Use word boundaries for more accurate matching
        pattern = r'\b' + re.escape(term) + r'\b'
        count += len(re.findall(pattern, text_lower))
    return count

def has_professional_indicators(text: str) -> List[str]:
    """Check for professional indicators in text."""
    text_lower = text.lower()
    found = []
    for indicator in PROFESSIONAL_INDICATORS:
        pattern = r'\b' + re.escape(indicator) + r'\b'
        if re.search(pattern, text_lower):
            found.append(indicator)
    return found

def analyze_author_posts(posts_dir: Path, topics_dir: Path) -> Dict:
    """Analyze all posts and build author profiles."""

    print("Loading posts and topics...")

    # Load all posts
    posts_by_author = defaultdict(list)
    posts_by_id = {}

    for post_file in posts_dir.glob('*.json'):
        try:
            with open(post_file) as f:
                post = json.load(f)
                post_id = post['ids']['post_id']
                author = post.get('author', {}).get('display_name', 'Unknown')
                posts_by_author[author].append(post)
                posts_by_id[post_id] = post
        except Exception as e:
            print(f"Error loading {post_file.name}: {e}")
            continue

    # Load all topics to analyze engagement
    topics_data = []
    for topic_file in topics_dir.glob('*.json'):
        try:
            with open(topic_file) as f:
                topic = json.load(f)
                topics_data.append(topic)
        except Exception as e:
            print(f"Error loading {topic_file.name}: {e}")
            continue

    print(f"Loaded {len(posts_by_id)} posts from {len(posts_by_author)} authors")
    print(f"Loaded {len(topics_data)} topics")
    print("\nAnalyzing authors...")

    # Build author profiles
    author_stats = {}

    for author, posts in posts_by_author.items():
        if author in ['Unknown', '#169482']:  # Skip corrupted/unknown authors
            continue

        # Basic counts
        post_count = len(posts)
        total_content_length = sum(len(p.get('content_text', '')) for p in posts)
        avg_content_length = total_content_length / post_count if post_count > 0 else 0

        # Role (take most common role from posts)
        roles = [p.get('author', {}).get('role') for p in posts if p.get('author', {}).get('role')]
        role = Counter(roles).most_common(1)[0][0] if roles else None

        # Technical depth
        all_content = ' '.join(p.get('content_text', '') for p in posts)
        technical_term_count = count_technical_terms(all_content)
        technical_terms_per_post = technical_term_count / post_count if post_count > 0 else 0
        professional_indicators = has_professional_indicators(all_content)

        # Engagement metrics
        # Check if Roger Deakins replied to any of their posts
        roger_replied_count = 0
        started_topics_count = 0

        for topic in topics_data:
            # Check if author started this topic
            if topic.get('post_ids') and len(topic['post_ids']) > 0:
                first_post_id = topic['post_ids'][0]
                if first_post_id in posts_by_id:
                    first_post = posts_by_id[first_post_id]
                    if first_post.get('author', {}).get('display_name') == author:
                        started_topics_count += 1

            # Check if Roger replied in topics where this author posted
            author_post_ids = {p['ids']['post_id'] for p in posts}
            topic_post_ids = set(topic.get('post_ids', []))

            if author_post_ids & topic_post_ids:  # Author participated in this topic
                # Check if Roger replied
                for post_id in topic_post_ids:
                    if post_id in posts_by_id:
                        post = posts_by_id[post_id]
                        if post.get('author', {}).get('display_name') == 'Roger Deakins':
                            roger_replied_count += 1
                            break

        # Calculate average reply depth (topics they participate in)
        participated_topics = [t for t in topics_data
                              if any(pid in {p['ids']['post_id'] for p in posts}
                                    for pid in t.get('post_ids', []))]
        avg_reply_count = sum(t.get('reply_count', 0) for t in participated_topics) / len(participated_topics) if participated_topics else 0

        # Time span (if we have timestamps)
        timestamps = [p.get('timestamps', {}).get('parsed_iso') for p in posts
                     if p.get('timestamps', {}).get('parsed_iso')]
        time_span_days = None
        if len(timestamps) >= 2:
            try:
                dates = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in timestamps if ts]
                if len(dates) >= 2:
                    time_span_days = (max(dates) - min(dates)).days
            except:
                pass

        # Build profile
        author_stats[author] = {
            'display_name': author,
            'role': role,
            'post_count': post_count,
            'started_topics_count': started_topics_count,
            'total_content_length': total_content_length,
            'avg_content_length': avg_content_length,
            'technical_term_count': technical_term_count,
            'technical_terms_per_post': round(technical_terms_per_post, 2),
            'professional_indicators': professional_indicators,
            'roger_replied_count': roger_replied_count,
            'avg_reply_count_in_topics': round(avg_reply_count, 2),
            'time_span_days': time_span_days,
            'post_ids': [p['ids']['post_id'] for p in posts],
        }

    print(f"Analyzed {len(author_stats)} authors")

    return author_stats

def calculate_persona_scores(author_stats: Dict) -> Dict:
    """Calculate persona scores for each author."""

    print("\nCalculating persona scores...")

    for author, stats in author_stats.items():
        score = 0
        indicators = []

        # Post count and consistency (0-20 points)
        if stats['post_count'] >= 50:
            score += 20
            indicators.append('very_high_post_count')
        elif stats['post_count'] >= 20:
            score += 15
            indicators.append('high_post_count')
        elif stats['post_count'] >= 10:
            score += 10
            indicators.append('moderate_post_count')
        elif stats['post_count'] >= 5:
            score += 5
            indicators.append('multiple_posts')

        # Engagement quality (0-15 points)
        if stats['avg_reply_count_in_topics'] > 5:
            score += 15
            indicators.append('high_engagement_topics')
        elif stats['avg_reply_count_in_topics'] > 3:
            score += 10
            indicators.append('moderate_engagement')
        elif stats['avg_reply_count_in_topics'] > 1:
            score += 5

        # Roger replied (0-20 points) - VERY significant
        if stats['roger_replied_count'] >= 5:
            score += 20
            indicators.append('frequent_roger_replies')
        elif stats['roger_replied_count'] >= 2:
            score += 15
            indicators.append('multiple_roger_replies')
        elif stats['roger_replied_count'] >= 1:
            score += 10
            indicators.append('roger_replied')

        # Technical depth (0-20 points)
        tech_score = min(stats['technical_terms_per_post'] * 5, 20)
        score += tech_score
        if tech_score >= 15:
            indicators.append('high_technical_depth')
        elif tech_score >= 10:
            indicators.append('moderate_technical_depth')

        # Professional indicators (0-15 points)
        if stats['professional_indicators']:
            score += 15
            indicators.append(f"professional_keywords: {', '.join(stats['professional_indicators'][:3])}")

        # Role-based bonuses
        if stats['role'] == 'Keymaster':
            score = 100
            indicators.append('keymaster_role')
        elif stats['role'] == 'Moderator':
            score += 15
            indicators.append('moderator_role')

        # Started topics (initiative)
        if stats['started_topics_count'] >= 10:
            score += 10
            indicators.append('topic_starter')
        elif stats['started_topics_count'] >= 5:
            score += 5

        # Cap at 100
        score = min(score, 100)

        # Assign persona
        if score >= 90:
            persona = 'Master Cinematographers'
            tier = 'S'
        elif score >= 70:
            persona = 'Working Professionals'
            tier = 'A'
        elif score >= 50:
            persona = 'Serious Students & Emerging DPs'
            tier = 'B'
        elif score >= 30:
            persona = 'Enthusiasts & Hobbyists'
            tier = 'C'
        else:
            persona = 'One-Time Visitors'
            tier = 'D'

        # Update stats
        stats['persona_score'] = score
        stats['persona_tier'] = tier
        stats['persona_name'] = persona
        stats['persona_indicators'] = indicators

    return author_stats

def main():
    """Main analysis function."""

    base_dir = Path(__file__).parent.parent.parent
    posts_dir = base_dir / 'library' / 'forums' / 'posts'
    topics_dir = base_dir / 'library' / 'forums' / 'topics'
    output_dir = base_dir / 'analysis' / 'curation'

    output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze authors
    author_stats = analyze_author_posts(posts_dir, topics_dir)

    # Calculate persona scores
    author_stats = calculate_persona_scores(author_stats)

    # Sort by score descending
    sorted_authors = sorted(author_stats.items(),
                           key=lambda x: x[1]['persona_score'],
                           reverse=True)

    # Generate summary statistics
    persona_counts = Counter(stats['persona_tier'] for _, stats in sorted_authors)

    print("\n" + "="*70)
    print("PERSONA DISTRIBUTION")
    print("="*70)
    for tier in ['S', 'A', 'B', 'C', 'D']:
        count = persona_counts.get(tier, 0)
        persona_name = {
            'S': 'Master Cinematographers',
            'A': 'Working Professionals',
            'B': 'Serious Students & Emerging DPs',
            'C': 'Enthusiasts & Hobbyists',
            'D': 'One-Time Visitors'
        }[tier]
        print(f"{tier}-Tier ({persona_name}): {count} authors")

    print("\n" + "="*70)
    print("TOP 20 AUTHORS BY SCORE")
    print("="*70)
    for i, (author, stats) in enumerate(sorted_authors[:20], 1):
        print(f"{i:2}. [{stats['persona_tier']}] {author[:30]:30} "
              f"Score: {stats['persona_score']:3} "
              f"Posts: {stats['post_count']:3} "
              f"Roger replies: {stats['roger_replied_count']:2}")

    # Save full results
    output_file = output_dir / 'author_statistics.json'
    with open(output_file, 'w') as f:
        json.dump(dict(sorted_authors), f, indent=2)

    print(f"\n✅ Full author statistics saved to: {output_file}")

    # Save summary
    summary = {
        'generated_at': datetime.now().isoformat(),
        'total_authors': len(sorted_authors),
        'persona_distribution': {
            'S_tier_masters': persona_counts.get('S', 0),
            'A_tier_professionals': persona_counts.get('A', 0),
            'B_tier_students': persona_counts.get('B', 0),
            'C_tier_enthusiasts': persona_counts.get('C', 0),
            'D_tier_visitors': persona_counts.get('D', 0),
        },
        'top_20_authors': [
            {
                'display_name': author,
                'persona_tier': stats['persona_tier'],
                'persona_score': stats['persona_score'],
                'post_count': stats['post_count'],
                'roger_replied_count': stats['roger_replied_count'],
            }
            for author, stats in sorted_authors[:20]
        ]
    }

    summary_file = output_dir / 'author_statistics_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"✅ Summary saved to: {summary_file}")

if __name__ == '__main__':
    main()
