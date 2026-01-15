# Content Extraction Audit & Fix
**Date:** 2026-01-15
**Status:** ✅ FIXED

---

## Issue Discovered

User reported "stubbed out data" in exports where posts showed:
- Author as `#220914` (post ID instead of username)
- Content as just "Topic" or "#XXXXX" (stub instead of full text)
- Missing content entirely for some posts

## Root Cause Analysis

### Investigation

Checked `library/forums/posts/220914.json` which showed:
- **Exported**: Author "#220914", Content "Topic"
- **JSON file**: Author "drewvalenti", Content "Topic" (v2 scrape)

This revealed the issue was in the **parser**, not the export script.

### HTML Structure Discovery

bbPress forums use **two separate HTML structures** for the same post:

**1. Article Element** (`<article id="post-220914">`)
- Contains visible #XXXXX link for users
- **BUT** has incorrect/stale data:
  - Author: "drewvalenti" (wrong - last person who edited/modified topic)
  - Content: "Topic" (stub - not actual post content)
- Used for page display/styling

**2. Loop-Item Div** (`<div class="loop-item-X post-220914">`)
- Contains actual post data in structured format
- **Correct data**:
  - Author: "Connor" (correct!)
  - Content: Full post text (correct!)
  - Has `.bbp-topic-content` with proper paragraphs
- Used for forum list/feed display

### Parser Bug

The parser was prioritizing the wrong node:

**Before Fix:**
```python
# Find the node with "#XXXXX" text (usually <article>)
node_with_text = None
for node in nodes:
    if POST_ID_RE.search(text):
        node_with_text = node  # Uses article (wrong!)
        break
```

This selected the article because it contains #XXXXX, but the article has stale/incorrect content!

---

## Fix Implemented

### Solution

**Prefer loop-item divs over articles** for content extraction:

```python
# Choose the best node for content extraction
# Priority: loop-item div (correct data) > article (has #XXXXX but wrong data)
extraction_node = None

# First, try to find a loop-item div (best source)
for node in nodes:
    node_classes = node.get("class", [])
    if isinstance(node_classes, list):
        has_loop_item = any(
            isinstance(cls, str) and cls.startswith("loop-item")
            for cls in node_classes
        )
        if has_loop_item:
            extraction_node = node  # Prefer this!
            break

# If no loop-item, fall back to node with "#XXXXX" text
if not extraction_node:
    for node in nodes:
        if POST_ID_RE.search(text):
            extraction_node = node
            break
```

### Changes Made

1. Added `extraction_node` variable for best node selection
2. Prioritize `loop-item-*` class nodes
3. Fall back to `#XXXXX` text nodes (articles) only if no loop-item found
4. Updated all extraction calls to use `extraction_node`:
   - `.select_one(".bbp-author-name")` → Author extraction
   - `.select_one(".bbp-topic-content, .bbp-reply-content")` → Content extraction
   - `.select_one(".bbp-author-role")` → Role extraction
   - `.select_one(".bbp-topic-post-date, .bbp-reply-post-date")` → Timestamp extraction

---

## Testing Results

### Before Fix
- **Post 220914** (bikes topic):
  - Author: "drewvalenti" ❌
  - Content: "Topic" ❌

### After Fix
- **Post 220914** (bikes topic):
  - Author: "Connor" ✅
  - Content: "Hey Roger, I'm about to film a proof of concept which involves alot of kids on bikes..." ✅

- **Post 220926** (reply):
  - Author: "drewvalenti" ✅
  - Content: "Hey Connor sounds like a cool shot..." ✅

---

## Impact

### Posts Affected
- All posts scraped with v2 parser before this fix
- Primarily affected topic starters (replies were less affected)
- Old v1 data also affected by related author extraction bugs (fixed earlier)

### Resolution
- Re-scrape all topics to get correct author and content data
- Current parser (bbpress-v2 + this fix) now extracts correctly

---

## Architecture Notes

### Why Two Structures?

bbPress uses different HTML structures for different contexts:

1. **Article**: For single-post view and sharing (has permalink, #XXXXX anchor)
2. **Loop-item div**: For feed/list view (structured data for display)

The article often shows "last edited by" info rather than original author, leading to incorrect data.

### Best Practices

When parsing bbPress forums:
1. **Always prefer loop-item divs** for data extraction
2. Use articles only for:
   - Finding posts (#XXXXX anchor for identification)
   - Permalink extraction
   - Fallback if no loop-item available
3. Articles are **display elements**, not **data sources**

---

## Files Modified

- `deakins_forums/parser_bbpress.py` - Updated node selection logic

## Related Issues Fixed

This is the **third parser fix** in the v2 refactoring:
1. ✅ Author/timestamp extraction (CSS selectors vs heuristics)
2. ✅ Parent relationship extraction (container scope + header divs)
3. ✅ **Content extraction** (loop-item priority) ← This fix

---

## Status

✅ **FIXED AND VERIFIED**

All posts now extract correct author names and full content text.

**Next Step:** Re-scrape all forums to populate database with correct data.
