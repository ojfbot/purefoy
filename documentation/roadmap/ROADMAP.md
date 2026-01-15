# Project Roadmap

Last updated: 2026-01-15

## Vision

Build a comprehensive, structured knowledge base of Roger Deakins' cinematography wisdom from:
- **Team Deakins Podcast** episodes with transcripts
- **rogerdeakins.com Forums** with threaded discussions
- **rogerdeakins.com Articles** with technical insights

All data structured for AI/MCP consumption, research, and analysis.

---

## Current Status (v2.0)

### ✅ Completed

#### Forum Scraper (v2 Schema)
- [x] Full forum scraping across 9 forums
- [x] 3,075+ posts collected
- [x] 691 topics indexed
- [x] Threading support (parent-child relationships)
- [x] Reply tree generation
- [x] Position tracking in conversations
- [x] Content extraction (fixed - real authors, full content)
- [x] SQLite FTS5 search index
- [x] Multiple export formats (CSV, text, by-author, by-topic)
- [x] HTTP caching (ETag/Last-Modified support)
- [x] Incremental updates
- [x] Rate limiting (respectful scraping)

#### Articles Scraper
- [x] Basic article extraction
- [x] HTML to structured JSON
- [x] Content block parsing
- [x] Image/media extraction

#### Podcast Episode Management
- [x] RSS feed parsing
- [x] Episode metadata extraction
- [x] MP3 download automation
- [x] Directory organization (S02E176 format)
- [x] Transcript scaffolding
- [x] Podcasting 2.0 transcript URL support

---

## Phase 1: Data Collection Completion (Next 2-4 weeks)

### Forum Scraper Enhancements

#### 1.1 Complete Forum Coverage
**Priority:** High
**Status:** In progress (3,075/~6,000 posts)

- [ ] Verify all 9 forums fully scraped
- [ ] Handle forum pagination edge cases
- [ ] Scrape historical archived topics (if any)
- [ ] Validate no missing posts via forum post count APIs

**Success Criteria:** 100% forum coverage, verified against forum statistics

---

#### 1.2 Enhanced Error Recovery
**Priority:** Medium

- [ ] Resume interrupted scrapes from checkpoint
- [ ] Handle transient network errors (retry logic)
- [ ] Detect and report parsing failures
- [ ] Create error log with post IDs and failure reasons

**Use Case:** Long-running scrapes across unstable connections

---

#### 1.3 Data Quality Validation
**Priority:** High

- [ ] Automated validation suite (see `deakins_forums/validate.py`)
- [ ] Detect orphaned posts (parent_id references non-existent posts)
- [ ] Identify circular references in reply trees
- [ ] Verify all timestamps parsed correctly
- [ ] Check for duplicate post IDs

**Deliverable:** `python -m deakins_forums.cli validate --verbose`

---

### Articles Scraper Completion

#### 1.4 Full Article Collection
**Priority:** Medium
**Status:** Prototype exists

- [ ] Scrape all articles from rogerdeakins.com/articles
- [ ] Extract article metadata (date, category, tags)
- [ ] Parse embedded videos and image galleries
- [ ] Handle multi-page articles
- [ ] Store in structured JSON leafs (matching forum pattern)

**Target:** ~50-100 articles indexed

---

#### 1.5 Article Search Integration
**Priority:** Low

- [ ] Add articles to SQLite FTS5 index
- [ ] Unified search across forums + articles
- [ ] Cross-reference articles mentioned in forum posts
- [ ] Generate article citation index

---

### Podcast Transcript Integration

#### 1.6 Transcript Extraction at Scale
**Priority:** High
**Status:** Tools exist, not automated

- [ ] Automate transcript fetching for all episodes
- [ ] Parse TTML/VTT/JSON transcript formats
- [ ] Extract speaker labels (Roger, James, guests)
- [ ] Timestamp alignment with audio
- [ ] Store transcripts in structured format

**Current:** Manual extraction tools in `scripts/tools/`
**Target:** Automated pipeline for 200+ episodes

---

#### 1.7 Podcast Search Index
**Priority:** High

- [ ] Index all transcripts in SQLite FTS5
- [ ] Search by speaker (Roger, James, guests)
- [ ] Search by episode metadata (guest, date, topics)
- [ ] Generate episode content summaries
- [ ] Link transcript segments to timestamps

**Deliverable:** `python -m deakins_podcasts.cli search "natural lighting" --speaker Roger`

---

## Phase 2: Enhanced Access & Analysis (1-2 months)

### Query & Search Improvements

#### 2.1 Advanced Search Features
**Priority:** Medium

- [ ] Semantic search (beyond keyword matching)
- [ ] Search by conversation depth (find deep threads)
- [ ] Filter by date range
- [ ] Filter by author role (Keymaster, Moderator, Participant)
- [ ] Search within specific forums or topics

**Example:**
```bash
python -m deakins_forums.cli search "anamorphic lenses" \
  --forum team-deakins \
  --author "Roger Deakins" \
  --after 2023-01-01
```

---

#### 2.2 Query Result Export
**Priority:** Low

- [ ] Export search results to PDF
- [ ] Generate citation-ready format (with URLs)
- [ ] Create reading lists from query results
- [ ] Markdown export with proper formatting

---

### Visualization & Reporting

#### 2.3 Reply Tree Visualization
**Priority:** Medium

- [ ] ASCII tree output for CLI
- [ ] HTML tree visualization (interactive)
- [ ] Depth statistics in corpus_stats.json
- [ ] Identify most active discussions (by reply count)

**Example:**
```bash
python -m deakins_forums.cli tree team-deakins__bikes --format html -o bikes_tree.html
```

---

#### 2.4 Author Analytics
**Priority:** Low

- [ ] Author contribution graphs
- [ ] Roger Deakins response rate analysis
- [ ] Topic expertise mapping (who talks about what)
- [ ] Collaboration network (who replies to whom)

**Deliverable:** Interactive dashboard or static reports

---

#### 2.5 Topic Trend Analysis
**Priority:** Low

- [ ] Trending topics over time
- [ ] Seasonal patterns (what gets discussed when)
- [ ] Identify evergreen vs. ephemeral topics
- [ ] Topic co-occurrence matrix

---

### Integration & APIs

#### 2.6 MCP Server Implementation
**Priority:** High
**Status:** Design complete (see `documentation/guides/mcp-integration.md`)

- [ ] Implement MCP protocol server
- [ ] Expose forum search via MCP tools
- [ ] Expose podcast transcript search via MCP
- [ ] Allow AI agents to query knowledge base
- [ ] Rate limiting and quota management

**Use Case:** Claude Desktop, other AI tools can query Roger Deakins knowledge base

---

#### 2.7 REST API (Optional)
**Priority:** Low

- [ ] Flask/FastAPI server for HTTP access
- [ ] OpenAPI documentation
- [ ] Authentication/API keys
- [ ] Public vs. private endpoints
- [ ] CORS support for web clients

**Use Case:** Web apps, mobile apps, third-party integrations

---

## Phase 3: Content Enhancement (2-3 months)

### Enrichment & Linking

#### 3.1 Cross-Reference Linking
**Priority:** Medium

- [ ] Link forum posts that mention specific films
- [ ] Connect forum discussions to relevant articles
- [ ] Link podcast episode mentions in forum posts
- [ ] Create film-centric views (all discussions about Skyfall)

**Deliverable:** Knowledge graph with entity relationships

---

#### 3.2 Entity Extraction
**Priority:** Medium

- [ ] Extract film titles mentioned in content
- [ ] Identify equipment/gear mentions (cameras, lenses)
- [ ] Tag lighting techniques (practical, natural, motivated)
- [ ] Extract cinematography terms (exposure, composition, color)

**Use Case:** "Show me all discussions about ARRI cameras"

---

#### 3.3 Image & Media Management
**Priority:** Low

- [ ] Download and archive images from posts
- [ ] Store image references in JSON leafs
- [ ] Generate thumbnails and previews
- [ ] OCR on images (extract text from screenshots)

---

### Content Generation

#### 3.4 Automated Summaries
**Priority:** Medium

- [ ] Generate topic summaries (using AI)
- [ ] Extract key points from long threads
- [ ] Create episode summaries from transcripts
- [ ] Generate study guides by subject

**Use Case:** Quick overview before deep dive

---

#### 3.5 Citation & Reference Manager
**Priority:** Low

- [ ] Generate citations in academic formats
- [ ] Create bibliography for research papers
- [ ] Track content usage and attribution
- [ ] Export to Zotero/Mendeley format

---

## Phase 4: Community & Maintenance (Ongoing)

### Data Quality & Maintenance

#### 4.1 Automated Updates
**Priority:** High

- [ ] Daily/weekly scrape schedule
- [ ] Detect new posts and topics
- [ ] Update changed content (edited posts)
- [ ] Prune deleted content
- [ ] Incremental index updates

**Automation:** Cron job or GitHub Actions

---

#### 4.2 Data Validation Pipeline
**Priority:** Medium

- [ ] Continuous validation checks
- [ ] Alert on data quality issues
- [ ] Automated regression testing
- [ ] Performance monitoring (scrape times, index size)

---

#### 4.3 Backup & Archival
**Priority:** High

- [ ] Automated backups of library/ directory
- [ ] Version snapshots (monthly archives)
- [ ] Export to portable formats (ZIP archives)
- [ ] Disaster recovery plan

---

### Documentation & Usability

#### 4.4 User Guides
**Priority:** Medium

- [ ] Beginner's guide to using the CLI
- [ ] Tutorial: Common search queries
- [ ] Tutorial: Exporting data for analysis
- [ ] Video walkthrough (if useful)

---

#### 4.5 Developer Documentation
**Priority:** Medium

- [ ] Architecture deep-dive
- [ ] Parser implementation details
- [ ] Testing guide
- [ ] Contributing guidelines
- [ ] Code style guide

---

### Open Source Considerations

#### 4.6 Public vs. Private Decision
**Priority:** Critical (before git init)

**Options:**
1. **Private Repository**: Keep scraped data private, respect forum ToS
2. **Public Code, Private Data**: Open-source scrapers, private data repo
3. **Fully Public**: Open everything (requires legal review)

**Current:** Private repository assumed

---

#### 4.7 Licensing
**Priority:** High (before sharing)

- [ ] Choose license for code (MIT, Apache 2.0, GPL)
- [ ] Add license headers to source files
- [ ] Create LICENSE file
- [ ] Document content copyright (Roger Deakins, Team Deakins)
- [ ] Fair use statement and disclaimers

---

## Phase 5: Advanced Features (3-6 months)

### Machine Learning & AI

#### 5.1 Semantic Search
**Priority:** Low

- [ ] Embed all content using sentence transformers
- [ ] Vector database (FAISS, Qdrant, Weaviate)
- [ ] Semantic similarity search
- [ ] "Find similar discussions" feature

---

#### 5.2 Question Answering
**Priority:** Low

- [ ] RAG pipeline (Retrieval-Augmented Generation)
- [ ] Answer questions using Claude/GPT
- [ ] Cite sources in answers
- [ ] Confidence scoring

**Use Case:** "What does Roger say about shooting in natural light?"

---

#### 5.3 Topic Modeling
**Priority:** Low

- [ ] Cluster discussions by topic (LDA, BERTopic)
- [ ] Automatic topic labeling
- [ ] Topic evolution over time
- [ ] Discover hidden patterns

---

### Multi-Format Support

#### 5.4 Video Integration (Future)
**Priority:** Low

- [ ] Extract Roger's YouTube videos
- [ ] Link forum discussions to relevant videos
- [ ] Transcript YouTube videos
- [ ] Search across video transcripts

---

#### 5.5 Book/Article References
**Priority:** Low

- [ ] Scrape Roger's recommended reading lists
- [ ] Link to external cinematography resources
- [ ] Create reading pathways by skill level
- [ ] ISBN and DOI linking

---

## Success Metrics

### Data Collection
- ✅ 3,075+ forum posts (Target: 6,000+)
- ⏳ 691 topics (Target: 1,000+)
- ⏳ 0 articles scraped (Target: 50-100)
- ⏳ 0 full transcripts (Target: 200+ episodes)

### Quality
- ✅ 100% real author names (no post ID stubs)
- ✅ Threading working (parent-child relationships)
- ⏳ Automated validation passing
- ⏳ Search recall >95%

### Usability
- ✅ CLI tools functional
- ⏳ MCP server operational
- ⏳ Documentation complete
- ⏳ External users can run successfully

---

## Timeline Summary

| Phase | Focus | Duration | Status |
|-------|-------|----------|--------|
| **Phase 1** | Data Collection | 2-4 weeks | 🟡 In Progress |
| **Phase 2** | Access & Analysis | 1-2 months | 🔵 Planned |
| **Phase 3** | Content Enhancement | 2-3 months | 🔵 Planned |
| **Phase 4** | Maintenance | Ongoing | 🟢 Active |
| **Phase 5** | Advanced Features | 3-6 months | ⚪ Future |

---

## Contributing

Interested in contributing? See `CONTRIBUTING.md` (to be created) for:
- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

---

## Feedback & Suggestions

Have ideas for the roadmap? Open an issue or discussion in:
- GitHub Issues (when public)
- Project discussions
- Direct contact with maintainers

---

**Last Updated:** 2026-01-15
**Next Review:** 2026-02-01
