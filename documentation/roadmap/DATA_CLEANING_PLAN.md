# Forum Data Cleaning & Curation Plan

**Created:** 2026-01-15
**Status:** Planning Phase

---

## Overview

This document outlines the strategy for cleaning and curating the forum data to create a high-quality knowledge base focused on cinematography content.

---

## Current State

### Data Inventory
- **Posts:** 3,075 total
- **Topics:** 691 total
- **Authors:** 490 unique
- **Forums:** 9 forums

### Issues Identified
1. **Housekeeping posts** - Book tours, events, announcements, admin posts
2. **Low engagement topics** - Topics with 0-2 replies that didn't generate discussion
3. **Unstructured persona data** - Posts from 490 authors need categorization

---

## Objectives

### 1. Remove Housekeeping Posts
**Goal:** Filter out non-cinematography content

**Criteria for Removal:**
- Book tour announcements
- Event scheduling
- Appearance notices
- Forum administration posts
- Website maintenance notices
- Merchandise/product announcements (unless camera gear)

**Detection Strategy:**
- **Keyword matching**: "book tour", "signing", "appearance", "event", "schedule", "available now", "announcement"
- **Author filtering**: Posts by "Team Deakins" (admin account) about non-technical topics
- **Forum filtering**: "website-news" forum likely has most housekeeping
- **Manual review**: Sample and verify automated classification

**Preservation:**
- Keep original files intact in `library/forums/`
- Mark filtered posts in metadata
- Create "filtered" view in `library/forums/_curated/`

---

### 2. Consolidate Low-Engagement Topics
**Goal:** Group unanswered questions into consolidated buckets

**Criteria for Consolidation:**
- **0 replies** - Question asked, no response
- **1-2 replies** - Minimal engagement, no substantive discussion
- **Short replies** - "I agree", "Thanks", etc. without technical content

**Consolidation Strategy:**

#### Bucket Categories:
1. **Unanswered Technical Questions** - Valid questions that got no response
2. **Unanswered Film-Specific** - Questions about specific films/scenes
3. **Unanswered Gear Questions** - Camera/lens/equipment questions
4. **Short Discussions** - Topics with 1-2 brief replies
5. **Off-Topic/Unclear** - Posts that don't fit cinematography focus

**Implementation:**
- Keep original topic files intact
- Create consolidated topic files in `library/forums/_curated/topics/`
- Add metadata field: `consolidation_status`: "standalone" | "consolidated_into"
- Cross-reference: Link original topics to consolidated buckets

**Example Structure:**
```json
{
  "consolidated_topic_id": "unanswered-technical-2024",
  "title": "Unanswered Technical Questions - 2024",
  "description": "Collection of technical cinematography questions that didn't receive responses",
  "original_topics": [
    {
      "topic_slug": "question-about-lighting-setup",
      "title": "Question about lighting setup",
      "author": "John Doe",
      "asked_date": "2024-03-15",
      "post_ids": ["123456"]
    },
    ...
  ],
  "total_questions": 45,
  "categories": {
    "lighting": 15,
    "camera": 12,
    "lenses": 8,
    "color": 10
  }
}
```

---

### 3. Create Persona Buckets
**Goal:** Categorize authors into 5 personas for easier navigation and analysis

**Proposed Personas:**

#### 1. **Master Cinematographers** (Tier S)
- Roger Deakins
- Other ASC/BSC members who post
- Professional DPs with major credits
- **Estimated:** 5-10 authors

**Identifier:**
- Role: "Keymaster" (Roger)
- Known professional credentials
- Posts demonstrate master-level knowledge

---

#### 2. **Working Professionals** (Tier A)
- Active cinematographers
- Working camera operators
- Professional gaffers/lighting technicians
- **Estimated:** 30-50 authors

**Identifiers:**
- Posts reference real productions
- Detailed technical knowledge
- Consistent professional terminology
- May mention specific projects or crews

---

#### 3. **Serious Students & Emerging DPs** (Tier B)
- Film school students (advanced)
- Early-career cinematographers
- Dedicated enthusiasts with strong technical foundation
- **Estimated:** 100-150 authors

**Identifiers:**
- Thoughtful, detailed questions
- References to learning/education
- Building portfolio/demo reel
- Technically literate responses

---

#### 4. **Enthusiasts & Hobbyists** (Tier C)
- Photography hobbyists
- Amateur filmmakers
- Beginning learners
- Casual forum participants
- **Estimated:** 200-250 authors

**Identifiers:**
- Basic questions
- Infrequent posting
- Consumer gear references
- Learning foundational concepts

---

#### 5. **One-Time Visitors** (Tier D)
- Single post or minimal engagement
- Drive-by questions
- No follow-up
- **Estimated:** 100-150 authors

**Identifiers:**
- 1-3 total posts
- No responses to replies
- Generic usernames
- No profile information

---

### Persona Classification Algorithm

**Automated Scoring (0-100):**

```python
def calculate_persona_score(author_data):
    score = 0

    # Post count and consistency
    if author_data['post_count'] >= 50:
        score += 20
    elif author_data['post_count'] >= 20:
        score += 15
    elif author_data['post_count'] >= 10:
        score += 10
    elif author_data['post_count'] >= 5:
        score += 5

    # Engagement quality
    if author_data['avg_reply_depth'] > 3:
        score += 15  # Generates discussions

    if author_data['received_replies_from_roger'] > 0:
        score += 20  # Roger responded to them

    # Content quality indicators
    score += min(author_data['technical_terms_per_post'] * 5, 20)
    score += min(author_data['helpful_ratings'] * 2, 10)

    # Role-based bonuses
    if author_data['role'] == 'Keymaster':
        score = 100  # Roger Deakins
    elif author_data['role'] == 'Moderator':
        score += 15

    # Professional indicators (keyword matching)
    if any(keyword in author_data['bio_or_posts'] for keyword in
           ['ASC', 'BSC', 'cinematographer', 'DP on', 'shot on']):
        score += 15

    return min(score, 100)

# Persona mapping
def assign_persona(score):
    if score >= 90:
        return 'Master Cinematographers'
    elif score >= 70:
        return 'Working Professionals'
    elif score >= 50:
        return 'Serious Students & Emerging DPs'
    elif score >= 30:
        return 'Enthusiasts & Hobbyists'
    else:
        return 'One-Time Visitors'
```

---

## Implementation Plan

### Phase 1: Data Analysis (Week 1)
**Tasks:**
1. ✅ Analyze current data structure
2. ⏳ Build author statistics aggregator
3. ⏳ Identify housekeeping posts (automated + manual review)
4. ⏳ Identify low-engagement topics
5. ⏳ Generate persona classification scores

**Deliverables:**
- `analysis/author_statistics.json` - Author metrics
- `analysis/housekeeping_posts.json` - Posts to filter
- `analysis/low_engagement_topics.json` - Topics to consolidate
- `analysis/persona_classifications.json` - Author persona scores

---

### Phase 2: Create Curation Tools (Week 1-2)
**Tasks:**
1. ⏳ Build housekeeping post detector
2. ⏳ Build topic consolidation tool
3. ⏳ Build persona classifier
4. ⏳ Create curated data pipeline

**Scripts:**
- `scripts/curation/detect_housekeeping.py`
- `scripts/curation/consolidate_topics.py`
- `scripts/curation/classify_personas.py`
- `scripts/curation/generate_curated_views.py`

---

### Phase 3: Manual Review & Refinement (Week 2)
**Tasks:**
1. ⏳ Review automated classifications
2. ⏳ Adjust thresholds and criteria
3. ⏳ Handle edge cases
4. ⏳ Validate consolidation buckets

**Quality Checks:**
- Sample 10% of filtered housekeeping posts → verify all are non-cinematography
- Sample 10% of consolidated topics → verify low engagement
- Sample 20 authors from each persona → verify classification accuracy

---

### Phase 4: Generate Curated Views (Week 2-3)
**Tasks:**
1. ⏳ Create filtered post collections
2. ⏳ Generate consolidated topic files
3. ⏳ Build persona-based exports
4. ⏳ Update search index with curation metadata

**Output Structure:**
```
library/forums/
├── posts/                      # Original posts (preserved)
├── topics/                     # Original topics (preserved)
├── forums/                     # Original forums (preserved)
└── _curated/                   # NEW: Curated views
    ├── posts/
    │   ├── cinematography/     # Housekeeping removed
    │   └── metadata.json       # Curation provenance
    ├── topics/
    │   ├── high-engagement/    # 3+ substantive replies
    │   ├── consolidated/       # Low-engagement buckets
    │   └── metadata.json
    └── personas/
        ├── master_cinematographers/
        │   ├── authors.json
        │   └── posts/          # All posts by masters
        ├── working_professionals/
        ├── serious_students/
        ├── enthusiasts/
        └── one_time_visitors/
```

---

### Phase 5: Documentation & Exports (Week 3)
**Tasks:**
1. ⏳ Document curation methodology
2. ⏳ Generate curated export formats
3. ⏳ Create persona-based analysis exports
4. ⏳ Update CLI to query curated data

**New CLI Commands:**
```bash
# Query curated data
python -m deakins_forums.cli search "lighting" --curated-only

# Filter by persona
python -m deakins_forums.cli search "anamorphic" --persona "Master Cinematographers"

# Export curated data
python -m deakins_forums.cli export curated-csv -o analysis/curated_posts.csv

# Generate persona reports
python -m deakins_forums.cli persona-report --persona "Working Professionals"
```

---

## Data Preservation Principles

### Non-Destructive Curation
- **Never delete original data** - All original JSON files preserved
- **Additive metadata** - Add curation fields, don't remove data
- **Versioned views** - Curated views are versions, not replacements
- **Provenance tracking** - Record why/when/how each decision was made

### Metadata Fields to Add

**For Posts:**
```json
{
  "curation": {
    "is_housekeeping": false,
    "housekeeping_confidence": 0.05,
    "housekeeping_reasons": [],
    "content_quality_score": 85,
    "technical_depth_score": 78,
    "curated_at": "2026-01-15T12:00:00Z",
    "curator": "automated-v1"
  }
}
```

**For Topics:**
```json
{
  "curation": {
    "engagement_tier": "high",  // high | medium | low | none
    "consolidation_status": "standalone",  // standalone | consolidated_into
    "consolidated_bucket": null,  // or "unanswered-technical-2024"
    "quality_score": 92,
    "curated_at": "2026-01-15T12:00:00Z"
  }
}
```

**For Authors:**
```json
{
  "persona": {
    "tier": "Working Professionals",
    "score": 78,
    "confidence": 0.85,
    "indicators": [
      "high_post_count",
      "technical_terminology",
      "roger_replied"
    ],
    "classified_at": "2026-01-15T12:00:00Z"
  }
}
```

---

## Success Metrics

### Housekeeping Removal
- **Target:** Reduce non-cinematography content by 80-90%
- **Measure:** Manual review of 100 random "housekeeping" posts → 95%+ accuracy

### Topic Consolidation
- **Target:** Consolidate 100-150 low-engagement topics into 10-15 buckets
- **Measure:** Average replies per topic increases from 4.5 to 6+

### Persona Classification
- **Target:** Classify all 490 authors with 90%+ accuracy
- **Measure:** Manual review of 50 authors → verify tier assignment

### Data Quality
- **Target:** Curated corpus is 70% of original size but 95%+ cinematography content
- **Measure:** Random sample of 100 posts → verify relevance

---

## Future Enhancements

### Phase 6: Semantic Clustering (Future)
- Use embeddings to cluster similar questions
- Identify duplicate/near-duplicate topics
- Auto-link related discussions

### Phase 7: Content Enrichment (Future)
- Add film/gear entity tags
- Extract technical specifications
- Link to external resources (IMDb, ASC articles)

### Phase 8: Quality Scoring (Future)
- Score posts by educational value
- Highlight "best answers"
- Create curated learning paths

---

## Questions for User

Before proceeding, need clarification on:

1. **Persona Naming:** Do these 5 tiers work? Any name changes?
   - Master Cinematographers (S-tier)
   - Working Professionals (A-tier)
   - Serious Students (B-tier)
   - Enthusiasts (C-tier)
   - One-Time Visitors (D-tier)

2. **Housekeeping Scope:** What level of filtering?
   - Strict: Only pure cinematography (remove all event/social posts)
   - Moderate: Remove obvious announcements, keep community posts
   - Minimal: Remove only admin/spam, keep everything else

3. **Consolidation Threshold:** When to consolidate?
   - 0 replies only
   - 0-1 replies
   - 0-2 replies

4. **Priority:** Which should we tackle first?
   - Housekeeping removal (cleaner data immediately)
   - Persona bucketing (better organization)
   - Topic consolidation (reduce clutter)

---

**Status:** Awaiting user input to finalize plan
**Next Step:** Create analysis scripts to generate statistics
