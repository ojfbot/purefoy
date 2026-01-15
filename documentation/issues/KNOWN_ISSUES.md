# Known Issues

Last updated: 2026-01-15

## Current Status: Production Ready ✅

The forum scraper is production-ready with v2 schema. All critical bugs have been resolved.

---

## Resolved Issues (Fixed in v2)

### ✅ Content Extraction Bug (FIXED)
**Status:** Resolved 2026-01-15
**Severity:** Critical
**Issue:** Posts showing stub data - authors as "#220914" instead of real names, content showing "Topic" instead of full text.

**Root Cause:** bbPress forums have two HTML structures per post:
- `<article id="post-X">` - Contains #XXXXX link but has **stale data** (last editor, stub content)
- `<div class="loop-item-X">` - Has **correct data** (actual author, full content)

Parser was selecting article elements (because they have #XXXXX text) → wrong data extracted.

**Fix:** Prioritize loop-item divs over articles for content extraction.
```python
# Now checks for loop-item class first
for node in nodes:
    if "loop-item" in node.get("class", []):
        extraction_node = node  # Use this!
        break
```

**Verification:** Post 220914 now shows Author "Connor" (correct) instead of "drewvalenti" (last editor).

**Documentation:** `documentation/development/sessions/CONTENT_EXTRACTION_AUDIT_2026-01-15.md`

---

### ✅ Parent Relationship Extraction Bug (FIXED)
**Status:** Resolved 2026-01-15
**Severity:** High
**Issue:** Parent-child threading not working. All posts showing `parent_post_id: null` despite HTML having `bbp-parent-topic-*` CSS classes.

**Root Causes:**
1. Parser searched in wrong container (`#bbpress-forums` instead of `#content`)
2. Articles outside bbpress-forums container weren't found
3. Header divs with id="post-X" were incorrectly skipped
4. Node merging needed to combine classes from multiple candidate nodes

**Fixes:**
1. Changed container scope from `soup.find(id="bbpress-forums")` to `soup.find(id="content") or soup.find(id="main")`
2. Modified header skip logic to check id attributes properly
3. Implemented node merging to combine CSS classes from all candidate nodes
4. Extract parent info from merged class list

**Verification:** Post 220926 now correctly shows `parent_post_id: "220914"`, `parent_type: "topic"`, `position: 1`

**Documentation:** `documentation/development/sessions/V2_SCHEMA_COMPLETION_REPORT.md`

---

### ✅ Analysis Directory Corruption (FIXED)
**Status:** Resolved 2026-01-15
**Severity:** Critical
**Issue:** 190+ files in `analysis/` directory with corrupted data:
- `all_posts.txt`: Authors as "#216430" instead of real names
- `posts.csv`: CSV cells corrupted with post IDs
- `by_author/`: 143 files named `_215559.txt` instead of author names
- `corpus_stats.json`: Statistics showing post IDs instead of authors

**Root Cause:** All exports created BEFORE content extraction bug fix (Jan 15 02:51-03:08 AM). Parser was using stale article data.

**Fix:** Created automated regeneration script `regenerate_analysis.sh` that:
1. Deletes all stale files
2. Rebuilds search index with clean data
3. Regenerates all 9 export formats
4. Verifies data quality

**Result:**
- All exports now have real author names
- CSV files ready for data analysis
- by_author/ directory properly organized (490 author files)
- Statistics accurate and meaningful

**Documentation:** `documentation/development/sessions/ANALYSIS_AUDIT_2026-01-15.md`

---

## Minor Issues / Limitations

### Posts Without Author Data
**Severity:** Low
**Status:** Not a bug - missing source data

Some posts in `analysis/by_author/` still show pattern `_169482.txt` (underscore + post ID).

**Explanation:** These are posts that genuinely have no author information in the source HTML. Not a parser bug - the data doesn't exist on the forum page. Possible causes:
- Deleted user accounts
- Anonymous posts (if forum allows)
- Data corruption on forum server

**Impact:** Minimal. Affects ~10-20 posts out of 3,075+ total.

**Workaround:** These posts are still indexed and searchable. The post ID can be used to locate them.

---

### SQLite Index Not Tracked in Git
**Severity:** N/A (by design)
**Status:** Intentional

The `library/forums/_site/*.sqlite` search index is excluded from git via `.gitignore`.

**Rationale:**
- SQLite binary format not suitable for version control
- Index can be rebuilt quickly from JSON leafs
- Reduces repository size

**Rebuild Command:**
```bash
python -m deakins_forums.cli build-index
```

**Time to rebuild:** ~5-10 seconds for 3,075 posts

---

### HTTP State Not Tracked
**Severity:** N/A (by design)
**Status:** Intentional

HTTP cache files (`http_state.json`, `visited_urls.json`) excluded from git.

**Rationale:**
- Ephemeral runtime state
- ETag/Last-Modified headers change frequently
- Not needed for fresh clones

**Impact:** Fresh git clone will re-fetch all pages on first scrape. Subsequent scrapes will use HTTP conditional GET (304 Not Modified) for efficiency.

---

## Future Enhancements (Not Bugs)

### Reply Tree Depth Statistics
**Priority:** Low
**Status:** Not implemented

Currently `max_depth` is calculated but not displayed in exports.

**Enhancement:** Add depth statistics to `corpus_stats.json` export:
```json
{
  "reply_trees": {
    "max_depth": 12,
    "avg_depth": 3.2,
    "topics_with_depth_gt_5": 42
  }
}
```

---

### Thread Visualization
**Priority:** Low
**Status:** Not implemented

Reply trees are stored in JSON but no visual representation exists.

**Enhancement:** Add CLI command to generate ASCII tree visualization:
```bash
python -m deakins_forums.cli tree team-deakins__bikes
```

Output:
```
📌 Bikes (220914) - Connor
├─ 💬 RE: Bikes (220926) - drewvalenti
│  └─ 💬 RE: RE: Bikes (221003) - Roger Deakins
└─ 💬 Great topic (220950) - Tyler F
```

---

## Testing Coverage

### ✅ Well Tested
- Content extraction (verified with debug scripts)
- Parent relationship extraction (validated on multiple topics)
- Export regeneration (full integration test)
- Search index rebuild (tested with 3,075 posts)

### ⚠️ Limited Testing
- Reply tree building (manual spot checks only)
- Position tracking (verified on sample posts)
- Error handling for malformed HTML

### ❌ Not Tested
- Edge cases: extremely deep threads (>20 levels)
- Performance: forums with >10,000 topics
- Concurrent scraping (rate limiting protects against issues)

---

## Reporting New Issues

If you discover a bug:

1. **Check existing issues** in this file first
2. **Verify it's reproducible** - run the scraper twice
3. **Document the issue:**
   - Expected behavior
   - Actual behavior
   - Steps to reproduce
   - Sample post IDs or URLs
   - Parser version (check `integrity.parser_version` in JSON)

4. **Create debug script** (see `scripts/tools/` for examples)

5. **Add to this file** with severity and status

---

## Version History

- **v2 (2026-01-15)**: Threading support, fixed content extraction
- **v1 (2026-01-14)**: Initial implementation with basic scraping

---

**Current Status:** ✅ Production ready with 3,075+ posts successfully scraped
