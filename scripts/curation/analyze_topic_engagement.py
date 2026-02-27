#!/usr/bin/env python3
"""
Topic Engagement Analyzer
Identifies low-engagement topics for consolidation.
"""

import json
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List
from datetime import datetime

def analyze_engagement(topics_dir: Path, posts_dir: Path) -> Dict:
    """Analyze topic engagement levels."""

    print("Loading topics and posts...")

    # Load posts for content analysis
    posts_by_id = {}
    for post_file in posts_dir.glob('*.json'):
        try:
            with open(post_file) as f:
                post = json.load(f)
                posts_by_id[post['ids']['post_id']] = post
        except Exception as e:
            continue

    # Analyze topics
    zero_replies = []
    one_reply = []
    two_replies = []
    low_engagement = []  # 3-5 replies but low quality
    medium_engagement = []  # 6-10 replies
    high_engagement = []  # 11+ replies

    total_topics = 0

    for topic_file in topics_dir.glob('*.json'):
        try:
            with open(topic_file) as f:
                topic = json.load(f)

            total_topics += 1

            reply_count = topic.get('reply_count', len(topic.get('post_ids', [])) - 1)
            post_ids = topic.get('post_ids', [])

            # Get topic starter info
            if post_ids:
                starter_post = posts_by_id.get(post_ids[0], {})
                starter_author = starter_post.get('author', {}).get('display_name', 'Unknown')
                starter_content = starter_post.get('content_text', '')
                forum_slug = topic.get('forum_slug', '')
            else:
                starter_author = 'Unknown'
                starter_content = ''
                forum_slug = ''

            # Calculate quality metrics
            total_content_length = 0
            roger_replied = False

            for post_id in post_ids:
                if post_id in posts_by_id:
                    post = posts_by_id[post_id]
                    total_content_length += len(post.get('content_text', ''))
                    if post.get('author', {}).get('display_name') == 'Roger Deakins':
                        roger_replied = True

            avg_content_length = total_content_length / len(post_ids) if post_ids else 0

            topic_summary = {
                'topic_slug': topic.get('topic_slug', ''),
                'title': topic.get('title', ''),
                'forum_slug': forum_slug,
                'reply_count': reply_count,
                'post_count': len(post_ids),
                'starter_author': starter_author,
                'starter_content_preview': starter_content[:200],
                'avg_content_length': round(avg_content_length),
                'roger_replied': roger_replied,
                'topic_url': topic.get('topic_url', ''),
            }

            # Categorize by engagement
            if reply_count == 0:
                zero_replies.append(topic_summary)
            elif reply_count == 1:
                one_reply.append(topic_summary)
            elif reply_count == 2:
                two_replies.append(topic_summary)
            elif reply_count <= 5:
                # Check if low quality (short replies)
                if avg_content_length < 100 and not roger_replied:
                    low_engagement.append(topic_summary)
                else:
                    medium_engagement.append(topic_summary)
            elif reply_count <= 10:
                medium_engagement.append(topic_summary)
            else:
                high_engagement.append(topic_summary)

            if total_topics % 100 == 0:
                print(f"  Processed {total_topics} topics...")

        except Exception as e:
            print(f"Error processing {topic_file.name}: {e}")
            continue

    print(f"\nProcessed {total_topics} topics")

    return {
        'zero_replies': zero_replies,
        'one_reply': one_reply,
        'two_replies': two_replies,
        'low_engagement': low_engagement,
        'medium_engagement': medium_engagement,
        'high_engagement': high_engagement,
        'total_topics': total_topics,
    }

def categorize_by_type(topics: List[Dict], posts_by_id: Dict) -> Dict:
    """Categorize topics by question type."""

    categories = {
        'technical_questions': [],
        'film_specific': [],
        'gear_questions': [],
        'composition': [],
        'lighting': [],
        'color_grading': [],
        'career_advice': [],
        'off_topic': [],
    }

    # Keywords for categorization
    keywords = {
        'technical_questions': ['how to', 'how do', 'what is', 'why does', 'can you explain'],
        'film_specific': ['in the movie', 'in the film', 'blade runner', 'skyfall', '1917', 'sicario',
                         'true grit', 'fargo', 'no country', 'shawshank', 'jarhead'],
        'gear_questions': ['camera', 'lens', 'alexa', 'arri', 'sony', 'red', 'canon', 'nikon',
                          'zeiss', 'cooke', 'panavision', 'sensor', 'which camera'],
        'composition': ['framing', 'composition', 'aspect ratio', 'rule of thirds', 'golden ratio',
                       'symmetry', 'negative space'],
        'lighting': ['lighting', 'light', 'exposure', 'key light', 'fill light', 'backlight',
                    'practical', 'natural light', 'hmi', 'kino'],
        'color_grading': ['color', 'grading', 'grade', 'lut', 'davinci', 'baselight', 'color correction'],
        'career_advice': ['career', 'how to become', 'getting started', 'film school', 'advice',
                         'portfolio', 'demo reel', 'networking'],
    }

    for topic in topics:
        content = (topic['title'] + ' ' + topic['starter_content_preview']).lower()

        categorized = False
        for category, kw_list in keywords.items():
            if any(kw in content for kw in kw_list):
                categories[category].append(topic)
                categorized = True
                break

        if not categorized:
            categories['off_topic'].append(topic)

    return categories

def main():
    """Main analysis function."""

    base_dir = Path(__file__).parent.parent.parent
    topics_dir = base_dir / 'library' / 'forums' / 'topics'
    posts_dir = base_dir / 'library' / 'forums' / 'posts'
    output_dir = base_dir / 'analysis' / 'curation'

    output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze engagement
    results = analyze_engagement(topics_dir, posts_dir)

    # Load posts for categorization
    posts_by_id = {}
    for post_file in posts_dir.glob('*.json'):
        try:
            with open(post_file) as f:
                post = json.load(f)
                posts_by_id[post['ids']['post_id']] = post
        except:
            continue

    # Categorize low-engagement topics
    print("\nCategorizing low-engagement topics...")

    all_low_engagement = (results['zero_replies'] +
                         results['one_reply'] +
                         results['two_replies'])

    categorized = categorize_by_type(all_low_engagement, posts_by_id)

    # Save results
    output_file = output_dir / 'low_engagement_topics.json'
    results['categorized_low_engagement'] = categorized

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Results saved to: {output_file}")

    # Display summary
    print("\n" + "="*70)
    print("TOPIC ENGAGEMENT SUMMARY")
    print("="*70)
    total = results['total_topics']
    print(f"Total topics: {total}")
    print(f"\nEngagement distribution:")
    print(f"  Zero replies: {len(results['zero_replies'])} ({len(results['zero_replies'])/total*100:.1f}%)")
    print(f"  One reply: {len(results['one_reply'])} ({len(results['one_reply'])/total*100:.1f}%)")
    print(f"  Two replies: {len(results['two_replies'])} ({len(results['two_replies'])/total*100:.1f}%)")
    print(f"  Low engagement (3-5, short): {len(results['low_engagement'])} ({len(results['low_engagement'])/total*100:.1f}%)")
    print(f"  Medium engagement (6-10): {len(results['medium_engagement'])} ({len(results['medium_engagement'])/total*100:.1f}%)")
    print(f"  High engagement (11+): {len(results['high_engagement'])} ({len(results['high_engagement'])/total*100:.1f}%)")

    # Low engagement breakdown
    total_low = len(all_low_engagement)
    print(f"\n  → Total low engagement (0-2 replies): {total_low} ({total_low/total*100:.1f}%)")

    print("\n" + "="*70)
    print("LOW-ENGAGEMENT TOPIC CATEGORIES")
    print("="*70)
    for category, topics in sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(topics)
        if count > 0:
            print(f"  {category}: {count}")

    # Sample topics from each category
    print("\n" + "="*70)
    print("SAMPLE ZERO-REPLY TOPICS")
    print("="*70)
    for i, topic in enumerate(results['zero_replies'][:10], 1):
        print(f"\n{i}. {topic['title']}")
        print(f"   By: {topic['starter_author']} | Forum: {topic['forum_slug']}")
        print(f"   Preview: {topic['starter_content_preview'][:100]}...")

    # Recommendations
    print("\n" + "="*70)
    print("CONSOLIDATION RECOMMENDATIONS")
    print("="*70)
    print(f"\nTopics to consolidate: {total_low}")
    print(f"\nSuggested consolidation buckets:")

    for category, topics in sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(topics)
        if count >= 5:  # Only suggest buckets with at least 5 topics
            print(f"  • '{category.replace('_', ' ').title()}' bucket: {count} topics")

if __name__ == '__main__':
    main()
