# Analysis Directory Audit - Stub & Stale Data
**Date:** 2026-01-15
**Status:** IDENTIFIED - Requires Regeneration

---

## 🔍 AUDIT FINDINGS

### Files with Stub/Stale Data (Requires Regeneration)

#### 1. **all_posts.txt** ⚠️ STALE
- **Size:** 126K
- **Created:** Jan 15 02:51 (before parser fix)
- **Issue:** Authors shown as "#216430" instead of real names
- **Impact:** PRIMARY export file with corrupt author data
- **Action:** DELETE and regenerate

#### 2. **all_posts_expanded.txt** ⚠️ STALE
- **Size:** 454K
- **Created:** Jan 15 03:08 (before parser fix)
- **Issue:** Authors as post IDs, stub content
- **Impact:** Extended export with same corruption
- **Action:** DELETE and regenerate

#### 3. **posts.csv** ⚠️ STALE
- **Size:** 109K
- **Created:** Jan 15 02:52 (before parser fix)
- **Issue:** CSV with author="#216430" in cells
- **Impact:** Breaks data analysis, charts, imports
- **Action:** DELETE and regenerate

#### 4. **posts_expanded.csv** ⚠️ STALE
- **Size:** 386K
- **Created:** Jan 15 03:08 (before parser fix)
- **Issue:** Same CSV corruption, larger dataset
- **Impact:** Extended CSV unusable for analysis
- **Action:** DELETE and regenerate

#### 5. **by_author/** directory ⚠️ COMPLETELY CORRUPT
- **Files:** 143 files
- **Created:** Jan 15 02:52 (before parser fix)
- **Issue:** Files named `_215559.txt` instead of `john_smith.txt`
- **Content:** Shows "AUTHOR: #215559" instead of real names
- **Impact:** ENTIRE author-based organization broken
- **Action:** DELETE entire directory and regenerate

#### 6. **corpus_stats.json** ⚠️ STALE
- **Size:** 5.0K
- **Created:** Jan 15 02:51 (before parser fix)
- **Issue:** Top authors list shows "#216430" etc.
- **Impact:** Statistics corrupted with post IDs
- **Action:** DELETE and regenerate

#### 7. **corpus_stats_expanded.json** ⚠️ STALE
- **Size:** 16K
- **Created:** Jan 15 03:08 (before parser fix)
- **Issue:** Extended stats with same corruption
- **Impact:** Detailed statistics unusable
- **Action:** DELETE and regenerate

#### 8. **all_links.csv** ⚠️ STALE
- **Size:** 36K
- **Created:** Jan 15 02:52 (before parser fix)
- **Issue:** Links attributed to post IDs instead of authors
- **Impact:** Link analysis broken
- **Action:** DELETE and regenerate

#### 9. **all_quotes.txt** ⚠️ STALE
- **Size:** 6.6K
- **Created:** Jan 15 02:52 (before parser fix)
- **Issue:** Quotes attributed to post IDs
- **Impact:** Quote analysis broken
- **Action:** DELETE and regenerate

#### 10. **by_topic/** directory ⚠️ PARTIALLY STALE
- **Files:** 47 files
- **Created:** Jan 15 02:52 (before parser fix)
- **Issue:** Posts within topics have stub authors
- **Impact:** Topic-based organization has corrupt data
- **Action:** DELETE entire directory and regenerate

---

### Files ALREADY Fixed ✅

#### 1. **all_posts_current.txt** ✅ GOOD
- **Size:** 501K
- **Created:** Jan 15 05:11 (after parser fix)
- **Status:** Generated with fixed parser
- **Content:** Correct authors (e.g., "Connor", "drewvalenti")
- **Action:** KEEP - This is the correct version

#### 2. **roger_deakins_posts.txt** ✅ GOOD
- **Size:** 21K
- **Created:** Jan 15 02:56
- **Status:** Appears correct (shows "Roger Deakins", "Keymaster")
- **Action:** VERIFY but likely keep

#### 3. **roger_deakins_posts_expanded.txt** ⚠️ UNCERTAIN
- **Size:** 61K
- **Created:** Jan 15 03:08 (before parser fix)
- **Status:** May have issues with OTHER authors mentioned
- **Action:** Regenerate to be safe

---

## 📊 CORRUPTION SUMMARY

**Total Files Affected:** 10+ files + 2 entire directories (190+ files total)

**Corruption Pattern:**
- Authors shown as post IDs: "#216430" instead of "Quadra"
- Filenames using post IDs: `_215559.txt` instead of `quadra.txt`
- CSV cells corrupted: Breaks data analysis
- Statistics corrupted: Top authors list unusable
- Content may show stubs: "Topic" instead of full text

**Root Cause:**
- All files created BEFORE content extraction fix (Jan 15 05:00+)
- Parser was using article elements (stale data) instead of loop-item divs (correct data)
- Fix applied at ~11:00 AM, old exports never regenerated

---

## 🔧 REGENERATION PLAN

### Phase 1: Cleanup (Delete Stale Files)
```bash
cd /Users/yuri/ojfbot/purefoy/analysis/

# Delete stale text exports
rm all_posts.txt all_posts_expanded.txt

# Delete stale CSVs
rm posts.csv posts_expanded.csv

# Delete corrupted directories
rm -rf by_author/ by_topic/

# Delete stale statistics
rm corpus_stats.json corpus_stats_expanded.json

# Delete stale link/quote exports
rm all_links.csv all_quotes.txt

# Delete uncertain Roger exports (will regenerate)
rm roger_deakins_posts_expanded.txt
```

### Phase 2: Regenerate All Exports

**Wait for scraping teams to complete** (~2-3 hours), then:

```bash
cd /Users/yuri/ojfbot/purefoy

# 1. Rebuild search index (required first)
.venv/bin/python -m deakins_forums.cli build-index

# 2. Export all posts (clean version)
.venv/bin/python -m deakins_forums.cli export all-text -o analysis/all_posts.txt

# 3. Export to CSV
.venv/bin/python -m deakins_forums.cli export csv -o analysis/posts.csv

# 4. Export Roger Deakins posts
.venv/bin/python -m deakins_forums.cli export roger-only -o analysis/roger_deakins_posts.txt

# 5. Export by author (NEW - will create by_author/ directory)
.venv/bin/python -m deakins_forums.cli export by-author -o analysis/by_author/

# 6. Export by topic (NEW - will create by_topic/ directory)
.venv/bin/python -m deakins_forums.cli export by-topic -o analysis/by_topic/

# 7. Export all links
.venv/bin/python -m deakins_forums.cli export links -o analysis/all_links.csv

# 8. Generate corpus statistics (NEW)
.venv/bin/python -m deakins_forums.cli export stats -o analysis/corpus_stats.json
```

### Phase 3: Verification

```bash
# Check that authors are real names, not post IDs
head -30 analysis/all_posts.txt | grep "AUTHOR:"

# Check CSV has real authors
head -5 analysis/posts.csv

# Check by_author directory has real names
ls analysis/by_author/ | head -10

# Check corpus stats has real author names
cat analysis/corpus_stats.json | grep -A 5 "top_authors"
```

---

## 📋 EXPECTED RESULTS

### After Regeneration:

**File Structure:**
```
analysis/
├── all_posts.txt              # CLEAN - real authors
├── all_posts_current.txt      # KEEP - already clean
├── posts.csv                  # CLEAN - real authors in CSV
├── roger_deakins_posts.txt    # CLEAN - Roger's posts only
├── all_links.csv              # CLEAN - links with real authors
├── corpus_stats.json          # CLEAN - stats with real names
├── by_author/
│   ├── roger_deakins.txt      # Real name!
│   ├── connor.txt             # Real name!
│   ├── drewvalenti.txt        # Real name!
│   └── ...
└── by_topic/
    ├── bikes.txt
    ├── gaining-set-experience.txt
    └── ...
```

**Data Quality:**
- Authors: Real names ("Connor", "Roger Deakins", "drewvalenti")
- Content: Full post text (not "Topic" stubs)
- CSVs: Clean cells for data analysis
- Statistics: Accurate author counts and metrics
- Organization: Logical file naming by real authors

---

## 🎯 PRIORITY

**CRITICAL** - Analysis directory is currently unusable for:
- Data analysis (CSV corrupted)
- Author research (by_author/ broken)
- Topic research (by_topic/ has stub data)
- Statistics (corpus stats corrupted)
- Citation (authors are post IDs)

**Timeline:**
1. ⏳ Wait for scraping teams to complete (~2-3 hours)
2. 🔄 Clean up stale files (5 minutes)
3. 🔄 Regenerate all exports (~10-15 minutes)
4. ✅ Verify data quality (5 minutes)

**Total Time to Clean Analysis:** ~20-25 minutes after scraping completes

---

## 📊 IMPACT ASSESSMENT

**Before Cleanup:**
- 190+ files with corrupted/stale data
- Unusable for research, analysis, or citation
- Authors appear as meaningless post IDs
- Statistics are nonsensical

**After Cleanup:**
- 100% clean data with real author names
- Full content extraction (no stubs)
- Proper CSV formatting for analysis
- Logical organization by actual authors
- Accurate statistics and metrics
- Ready for AI/MCP consumption

---

**Status:** AUDIT COMPLETE - Awaiting scraping completion for regeneration
**Next Action:** Clean up and regenerate analysis directory
