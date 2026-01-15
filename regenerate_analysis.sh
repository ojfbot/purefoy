#!/bin/bash
# Regenerate Analysis Directory with Clean Data
# Run this AFTER scraping teams complete

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo "ANALYSIS DIRECTORY REGENERATION"
echo "========================================================================"
echo ""

# Phase 1: Cleanup
echo "Phase 1: Removing stale/corrupted files..."
echo "----------------------------------------------------------------------"

cd analysis/

# Delete stale text exports
echo "  - Removing stale text exports..."
rm -f all_posts.txt all_posts_expanded.txt

# Delete stale CSVs
echo "  - Removing stale CSVs..."
rm -f posts.csv posts_expanded.csv

# Delete corrupted directories
echo "  - Removing corrupted directories..."
rm -rf by_author/ by_topic/

# Delete stale statistics
echo "  - Removing stale statistics..."
rm -f corpus_stats.json corpus_stats_expanded.json

# Delete stale link/quote exports
echo "  - Removing stale link/quote exports..."
rm -f all_links.csv all_quotes.txt

# Delete uncertain Roger exports
echo "  - Removing uncertain Roger Deakins exports..."
rm -f roger_deakins_posts_expanded.txt roger_deakins_posts.txt

echo "✓ Cleanup complete"
echo ""

cd ..

# Phase 2: Rebuild Index
echo "Phase 2: Rebuilding search index..."
echo "----------------------------------------------------------------------"
.venv/bin/python -m deakins_forums.cli build-index
echo "✓ Index rebuilt"
echo ""

# Phase 3: Regenerate Exports
echo "Phase 3: Regenerating all exports..."
echo "----------------------------------------------------------------------"

echo "  [1/9] Exporting all posts..."
.venv/bin/python -m deakins_forums.cli export all-text -o analysis/all_posts.txt
echo "  ✓ All posts exported"

echo "  [2/9] Exporting to CSV..."
.venv/bin/python -m deakins_forums.cli export csv -o analysis/posts.csv
echo "  ✓ CSV exported"

echo "  [3/9] Exporting Roger Deakins posts..."
.venv/bin/python -m deakins_forums.cli export roger-only -o analysis/roger_deakins_posts.txt
echo "  ✓ Roger Deakins posts exported"

echo "  [4/9] Exporting by author..."
.venv/bin/python -m deakins_forums.cli export by-author -o analysis/by_author/
echo "  ✓ By-author exports created"

echo "  [5/9] Exporting by topic..."
.venv/bin/python -m deakins_forums.cli export by-topic -o analysis/by_topic/
echo "  ✓ By-topic exports created"

echo "  [6/9] Exporting all links..."
.venv/bin/python -m deakins_forums.cli export links -o analysis/all_links.csv
echo "  ✓ Links exported"

echo "  [7/9] Exporting quotes..."
.venv/bin/python -m deakins_forums.cli export quotes -o analysis/all_quotes.txt
echo "  ✓ Quotes exported"

echo "  [8/9] Exporting content blocks..."
.venv/bin/python -m deakins_forums.cli export blocks -o analysis/content_blocks.txt
echo "  ✓ Content blocks exported"

echo "  [9/9] Generating corpus statistics..."
.venv/bin/python -m deakins_forums.cli export stats -o analysis/corpus_stats.json
echo "  ✓ Statistics generated"

echo ""
echo "✓ All exports regenerated"
echo ""

# Phase 4: Verification
echo "Phase 4: Verifying data quality..."
echo "----------------------------------------------------------------------"

echo "Checking all_posts.txt for real author names..."
head -30 analysis/all_posts.txt | grep "AUTHOR:" | head -3
echo ""

echo "Checking posts.csv for real author names..."
head -3 analysis/posts.csv | cut -d',' -f2
echo ""

echo "Checking by_author directory..."
echo "Sample files (should be real names, not post IDs):"
ls analysis/by_author/ | head -5
echo ""

echo "Checking corpus stats..."
cat analysis/corpus_stats.json | python3 -m json.tool | grep -A 3 "top_authors" | head -10
echo ""

# Phase 5: Summary
echo "========================================================================"
echo "REGENERATION COMPLETE"
echo "========================================================================"
echo ""
echo "Summary:"
ls -lh analysis/ | grep -v "^d" | wc -l | xargs echo "  - Files:"
ls analysis/by_author/ 2>/dev/null | wc -l | xargs echo "  - Authors:"
ls analysis/by_topic/ 2>/dev/null | wc -l | xargs echo "  - Topics:"
echo ""
echo "All analysis files have been regenerated with clean data!"
echo "Files are ready for research, analysis, and AI/MCP consumption."
echo ""
