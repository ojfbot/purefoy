#!/usr/bin/env python3
"""
Test if we can construct TTML download URLs and fetch them directly.
"""

import requests
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "Library/Group Containers/243LU875E5.groups.com.apple.podcasts/Documents/MTLibrary.sqlite"

# Get a sample episode
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

query = """
    SELECT e.ZTITLE, e.ZTRANSCRIPTIDENTIFIER, e.ZGUID, e.ZASSETURL, e.ZENCLOSUREURL
    FROM ZMTEPISODE e
    JOIN ZMTPODCAST p ON e.ZPODCAST = p.Z_PK
    WHERE p.ZTITLE = 'Team Deakins'
      AND e.ZTRANSCRIPTIDENTIFIER IS NOT NULL
    LIMIT 1
"""

cursor.execute(query)
episode = dict(cursor.fetchone())
conn.close()

print("Sample Episode:")
print(f"  Title: {episode['ZTITLE']}")
print(f"  Transcript ID: {episode['ZTRANSCRIPTIDENTIFIER']}")
print(f"  GUID: {episode['ZGUID']}")
print()

# Try various potential URL patterns
transcript_id = episode['ZTRANSCRIPTIDENTIFIER']
# Extract: transcript_1000590147486
transcript_num = transcript_id.split('transcript_')[1].split('.')[0] if 'transcript_' in transcript_id else None

if transcript_num:
    potential_urls = [
        f"https://sylvan.apple.com/Podcasts/{transcript_id}",
        f"https://sylvan.apple.com/{transcript_id}",
        f"https://amp-api.podcasts.apple.com/v1/transcript/{transcript_num}",
        f"https://podcasts.apple.com/transcript/{transcript_num}",
        f"https://itunesu-assets.itunes.apple.com/{transcript_id}",
    ]

    print("Trying potential TTML download URLs:")
    print()

    for url in potential_urls:
        print(f"Trying: {url}")
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✓ SUCCESS! Found working URL")
                print(f"  Content-Type: {response.headers.get('Content-Type')}")
                break
        except Exception as e:
            print(f"  Error: {e}")
        print()
