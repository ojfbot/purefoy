#!/usr/bin/env python3
"""
Housekeeping Post Detector
Identifies non-cinematography posts (book tours, events, admin announcements).
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Housekeeping keywords (strong indicators)
HOUSEKEEPING_KEYWORDS = {
    'book_tour': [
        'book tour', 'book signing', 'signing event', 'book event',
        'meet and greet', 'book launch', 'book release'
    ],
    'appearance': [
        'appearance at', 'will be at', 'join us at', 'attending',
        'speaking at', 'panel discussion', 'q&a session', 'screening and q&a'
    ],
    'event': [
        'event details', 'upcoming event', 'save the date', 'rsvp',
        'tickets available', 'register now', 'registration'
    ],
    'announcement': [
        'announcement:', 'we are pleased to announce', 'exciting news',
        'coming soon', 'available now', 'just released', 'now available'
    ],
    'admin': [
        'website maintenance', 'forum update', 'technical issues',
        'downtime', 'server', 'please note'
    ],
    'merchandise': [
        'merchandise', 'store', 'shop', 'purchase', 'buy now',
        'for sale', 'available for order'
    ],
}

# Weak indicators (may be housekeeping in combination with others)
WEAK_INDICATORS = [
    'instagram', 'facebook', 'twitter', 'social media',
    'subscribe', 'newsletter', 'mailing list',
    'new post', 'latest', 'check out',
]

# Forums that are likely to contain housekeeping
HOUSEKEEPING_FORUMS = [
    'website-news',
    'team-deakins/byways',  # Often has book tour posts
]

# Authors who often post housekeeping content
HOUSEKEEPING_AUTHORS = [
    'James',  # Team Deakins admin
    'Team Deakins',
]

def detect_housekeeping(post: Dict) -> Tuple[bool, float, List[str]]:
    """
    Detect if a post is housekeeping content.

    Returns:
        (is_housekeeping, confidence, reasons)
    """
    content = post.get('content_text', '').lower()
    content_html = post.get('content_html', '').lower()
    title = post.get('ids', {}).get('topic_slug', '').lower()
    forum = post.get('ids', {}).get('forum_slug', '')
    author = post.get('author', {}).get('display_name', '')

    reasons = []
    score = 0.0

    # Check strong keywords
    for category, keywords in HOUSEKEEPING_KEYWORDS.items():
        for keyword in keywords:
            if keyword in content or keyword in title:
                score += 0.25
                reasons.append(f'keyword: {keyword} (category: {category})')
                break  # Only count once per category

    # Check weak indicators
    weak_count = sum(1 for indicator in WEAK_INDICATORS
                     if indicator in content or indicator in title)
    if weak_count >= 2:
        score += 0.15
        reasons.append(f'multiple_weak_indicators ({weak_count})')

    # Check forum
    if forum in HOUSEKEEPING_FORUMS:
        score += 0.20
        reasons.append(f'housekeeping_forum: {forum}')

    # Check author
    if author in HOUSEKEEPING_AUTHORS:
        score += 0.15
        reasons.append(f'housekeeping_author: {author}')

    # Check for dates/locations (event indicators)
    date_patterns = [
        r'\b\d{1,2}:\d{2}\s*(am|pm)\b',  # Time
        r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',  # Month Day
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',  # Date
    ]
    location_patterns = [
        r'\b\d+\s+\w+\s+(street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd)\b',  # Address
        r'\b[A-Z]{2,3}\s+\d{1,2}[A-Z]{2}\b',  # UK postcode
    ]

    date_matches = sum(1 for pattern in date_patterns if re.search(pattern, content))
    location_matches = sum(1 for pattern in location_patterns if re.search(pattern, content))

    if date_matches >= 1 and location_matches >= 1:
        score += 0.20
        reasons.append('event_details (date + location)')

    # Very short posts that are just announcements
    if len(content) < 200 and score > 0:
        score += 0.10
        reasons.append('short_announcement')

    # Links to external sites (not cinematography resources)
    links = post.get('links', [])
    external_domains = set()
    for link in links:
        href = link.get('href', '')
        # Extract domain
        match = re.search(r'https?://([^/]+)', href)
        if match:
            domain = match.group(1)
            if 'rogerdeakins.com' not in domain and 'youtube.com' not in domain:
                external_domains.add(domain)

    if external_domains and score > 0:
        score += 0.10
        reasons.append(f'external_links: {list(external_domains)[:3]}')

    # Cap score at 1.0
    score = min(score, 1.0)

    # Threshold for classification
    is_housekeeping = score >= 0.5

    return is_housekeeping, score, reasons

def analyze_all_posts(posts_dir: Path) -> Dict:
    """Analyze all posts for housekeeping content."""

    print("Analyzing posts for housekeeping content...")

    housekeeping_posts = []
    cinematography_posts = []
    uncertain_posts = []

    total = 0
    for post_file in posts_dir.glob('*.json'):
        try:
            with open(post_file) as f:
                post = json.load(f)

            total += 1

            is_housekeeping, confidence, reasons = detect_housekeeping(post)

            post_summary = {
                'post_id': post['ids']['post_id'],
                'author': post.get('author', {}).get('display_name', 'Unknown'),
                'forum_slug': post['ids'].get('forum_slug', ''),
                'topic_slug': post['ids'].get('topic_slug', ''),
                'content_preview': post.get('content_text', '')[:200],
                'is_housekeeping': is_housekeeping,
                'confidence': round(confidence, 2),
                'reasons': reasons,
            }

            if is_housekeeping:
                housekeeping_posts.append(post_summary)
            elif confidence >= 0.3:  # Uncertain
                uncertain_posts.append(post_summary)
            else:
                cinematography_posts.append(post_summary)

            if total % 500 == 0:
                print(f"  Processed {total} posts...")

        except Exception as e:
            print(f"Error processing {post_file.name}: {e}")
            continue

    print(f"\nProcessed {total} posts")
    print(f"  Housekeeping: {len(housekeeping_posts)}")
    print(f"  Uncertain: {len(uncertain_posts)}")
    print(f"  Cinematography: {len(cinematography_posts)}")

    return {
        'housekeeping_posts': housekeeping_posts,
        'uncertain_posts': uncertain_posts,
        'cinematography_posts_count': len(cinematography_posts),
        'total_posts': total,
    }

def main():
    """Main detection function."""

    base_dir = Path(__file__).parent.parent.parent
    posts_dir = base_dir / 'library' / 'forums' / 'posts'
    output_dir = base_dir / 'analysis' / 'curation'

    output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze posts
    results = analyze_all_posts(posts_dir)

    # Sort by confidence (highest first)
    results['housekeeping_posts'].sort(key=lambda x: x['confidence'], reverse=True)
    results['uncertain_posts'].sort(key=lambda x: x['confidence'], reverse=True)

    # Save results
    output_file = output_dir / 'housekeeping_posts.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Results saved to: {output_file}")

    # Show top 10 housekeeping posts
    print("\n" + "="*70)
    print("TOP 10 HOUSEKEEPING POSTS (HIGHEST CONFIDENCE)")
    print("="*70)
    for i, post in enumerate(results['housekeeping_posts'][:10], 1):
        print(f"\n{i}. Post ID: {post['post_id']} | Confidence: {post['confidence']:.2f}")
        print(f"   Author: {post['author']}")
        print(f"   Forum: {post['forum_slug']}")
        print(f"   Reasons: {', '.join(post['reasons'][:3])}")
        print(f"   Preview: {post['content_preview'][:100]}...")

    # Show uncertain posts that need manual review
    print("\n" + "="*70)
    print("UNCERTAIN POSTS (NEED MANUAL REVIEW)")
    print("="*70)
    print(f"Total: {len(results['uncertain_posts'])}")
    if results['uncertain_posts']:
        print("\nTop 5:")
        for i, post in enumerate(results['uncertain_posts'][:5], 1):
            print(f"\n{i}. Post ID: {post['post_id']} | Confidence: {post['confidence']:.2f}")
            print(f"   Reasons: {', '.join(post['reasons'])}")
            print(f"   Preview: {post['content_preview'][:100]}...")

    # Summary statistics
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    total = results['total_posts']
    housekeeping = len(results['housekeeping_posts'])
    uncertain = len(results['uncertain_posts'])
    cinematography = results['cinematography_posts_count']

    print(f"Total posts analyzed: {total}")
    print(f"Housekeeping posts: {housekeeping} ({housekeeping/total*100:.1f}%)")
    print(f"Uncertain posts: {uncertain} ({uncertain/total*100:.1f}%)")
    print(f"Cinematography posts: {cinematography} ({cinematography/total*100:.1f}%)")

    # Breakdown by forum
    from collections import Counter
    housekeeping_by_forum = Counter(p['forum_slug'] for p in results['housekeeping_posts'])
    print("\nHousekeeping posts by forum:")
    for forum, count in housekeeping_by_forum.most_common(10):
        print(f"  {forum}: {count}")

if __name__ == '__main__':
    main()
