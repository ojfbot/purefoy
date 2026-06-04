# Git Initialization Checklist

This document provides step-by-step instructions for safely initializing git for this project.

## Pre-Initialization Verification

Before running `git init`, verify the following:

### ✅ 1. Check .gitignore is in place

```bash
cat .gitignore | head -20
```

Should see entries for:
- `downloads/`
- `library/`
- `analysis/`
- `*.mp3`, `*.m4a`, etc.
- `*.sqlite`, `*.db`
- `.env`, `secrets/`, `credentials/`

### ✅ 2. Verify sensitive data locations

Check that no sensitive files exist in tracked locations:

```bash
# Should NOT find any of these
find . -name "*.mp3" -o -name "*.m4a" -not -path "./downloads/*"
find . -name ".env" -o -name "*_key.txt" -o -name "*_token.txt"
find . -name "*.sqlite" -not -path "./library/*"
```

### ✅ 3. Verify data directories are excluded

```bash
# These should be empty or non-existent for the initial commit
ls -la downloads/    # Should only contain .gitkeep and README.md
ls -la library/      # Should only contain .gitkeep and README.md
ls -la analysis/     # Should only contain .gitkeep and README.md
```

### ✅ 4. Check schema examples are ready

```bash
ls -la schema_examples/
```

Should contain:
- `episode/metadata.json`
- `episode/transcript_sources.json`
- `episode/transcript.txt`
- `forum/post.json`
- `forum/topic.json`
- `forum/forum.json`
- `README.md`

## Initialize Git

Once verification is complete:

```bash
# Initialize repository
git init

# Check what will be staged
git status

# Review files to be committed
git ls-files --others --exclude-standard
```

### Expected files to be tracked:

**Source Code:**
- `deakins_forums/*.py`
- `download_episodes.py`
- `ingest_teamdeakins_downloads.py`
- `scrape_forum.py`

**Configuration:**
- `pyproject.toml`
- `requirements.txt`
- `.gitignore`

**Documentation:**
- `README.md`
- `CLAUDE.md`
- `GIT_INIT_CHECKLIST.md` (this file)
- `downloads/README.md`
- `library/README.md`
- `analysis/README.md`

**Schema Examples:**
- `schema_examples/**/*`

**Placeholder files:**
- `downloads/.gitkeep`
- `analysis/.gitkeep`

### Files that should NOT be tracked:

❌ `library/**` (scraped forum/article data — public repo keeps it off-git)
❌ `downloads/S*/**` (episode directories with audio)
❌ `*.mp3`, `*.m4a`, `*.wav` (audio files)
❌ `*.sqlite`, `*.db` (search index - can be rebuilt)
❌ `analysis/*.csv`, `analysis/*.txt`, etc. (generated exports)
❌ `http_state.json`, `visited_urls.json` (HTTP cache)
❌ `.env`, credentials, API keys
❌ `venv/`, `.venv/`, `__pycache__/`

## Initial Commit

```bash
# Add all tracked files
git add .

# Verify nothing sensitive is staged (audio files, SQLite, etc.)
git diff --cached --name-only | grep -E "(\.mp3|\.sqlite|\.env|downloads/S)"

# If the above command returns nothing, proceed
# (Note: library/ scraped data is gitignored — NOT committed)
git commit -m "Initial commit: Team Deakins knowledge base toolkit

- Forum scraper with structured JSON storage
- Podcast episode downloader and ingest scripts
- Schema examples and documentation
- Comprehensive .gitignore for copyright/privacy

Public repo, code only: scraped forum data is gitignored (on-disk).
Audio files and SQLite indices excluded."
```

## Post-Initialization Verification

After the initial commit:

```bash
# Check repository size (may be larger due to forum data)
du -sh .git

# Check what's tracked
git ls-files | wc -l
git ls-files | head -20

# Verify scraped forum data is NOT tracked (gitignored — should find nothing)
git ls-files | grep "library/" && echo "ERROR: scraped data tracked!" || echo "✓ Forum data correctly gitignored"

# Verify excluded files are NOT tracked
git ls-files | grep -E "(downloads/S|\.mp3|\.sqlite|analysis/.*\.csv)" && echo "ERROR: Excluded files tracked!" || echo "✓ Excluded files not tracked"

# Test that ignored files won't be committed
touch downloads/test.mp3
touch library/forums/_site/test.sqlite
git status | grep -E "(test\.mp3|test\.sqlite)" && echo "ERROR: Ignored files showing in status!" || echo "✓ Ignored files are excluded"
rm downloads/test.mp3 library/forums/_site/test.sqlite
```

## Create Remote Repository (Optional)

If pushing to GitHub/GitLab:

```bash
# Add remote
git remote add origin <your-repo-url>

# Push initial commit
git push -u origin main
```

### Double-check before pushing:

```bash
# List all tracked files one more time
git ls-files

# Check repository size
git count-objects -vH
```

## Ongoing Usage

### Before Each Commit

```bash
# Always check what's being staged
git status
git diff --cached --name-only

# Ensure no audio/SQLite files (library/forums is OK)
git diff --cached --name-only | grep -E "(\.mp3|\.sqlite|downloads/S)"
```

### Verify .gitignore is Working

```bash
# After downloading episodes or scraping forums
git status

# Should show:
#   - Modified: source code, docs, library/forums/* (forum data)
#   - Untracked: only new source files you created
#   - Should NOT show: downloads/S*, *.mp3, *.sqlite
```

## Emergency: Remove Sensitive Data

If you accidentally commit sensitive data:

```bash
# For the most recent commit
git reset --soft HEAD~1
git reset HEAD <sensitive-file>
git commit -m "Your commit message"

# If already pushed (requires force push)
# WARNING: Only do this if you haven't shared the repository
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch <sensitive-file>" \
  --prune-empty --tag-name-filter cat -- --all

git push origin --force --all
```

**Better approach**: If repository is not yet public, delete and recreate it.

## Summary

✅ Source code tracked
✅ Documentation tracked
✅ Schema examples tracked
✅ Configuration tracked
❌ **Forum scraped data excluded** (`library/` gitignored — public repo, off-git)
❌ Audio files excluded (.mp3, .m4a, etc.)
❌ Episode metadata excluded (downloads/)
❌ SQLite indices excluded (can rebuild)
❌ Analysis exports excluded (can regenerate)
❌ Sensitive data excluded

This ensures:
- **Privacy**: scraped forum data stays off-git via `.gitignore` (repo is public, code only)
- **Security**: No credentials or API keys
- **Copyright**: For personal/educational use only
- **Size**: Audio files excluded to manage repository size
- **Flexibility**: SQLite index excluded but can be rebuilt from JSON
