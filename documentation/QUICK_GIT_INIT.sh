#!/bin/bash
# Quick Git Initialization Script
# Run this after reviewing GIT_INIT_CHECKLIST.md

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════"
echo "  Team Deakins Knowledge Base - Git Initialization"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Pre-flight checks
echo "Running pre-flight checks..."
echo ""

# Check if .gitignore exists
if [ ! -f .gitignore ]; then
    echo "❌ ERROR: .gitignore not found!"
    exit 1
fi
echo "✅ .gitignore exists"

# Check if git is already initialized
if [ -d .git ]; then
    echo "⚠️  WARNING: Git repository already initialized!"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Look for sensitive files that shouldn't be there
echo ""
echo "Checking for sensitive files in wrong locations..."
SENSITIVE_FILES=$(find . -maxdepth 1 -name "*.mp3" -o -name "*.sqlite" -o -name ".env" 2>/dev/null)
if [ ! -z "$SENSITIVE_FILES" ]; then
    echo "⚠️  WARNING: Found sensitive files in root directory:"
    echo "$SENSITIVE_FILES"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
else
    echo "✅ No sensitive files in root"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Initializing Git Repository"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Initialize git
if [ ! -d .git ]; then
    git init
    echo "✅ Git repository initialized"
else
    echo "ℹ️  Git repository already exists"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Files that will be tracked:"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Show what will be added
git status --short 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Verification"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check for files that shouldn't be tracked (audio, SQLite, etc.)
# Note: library/forums IS expected to be tracked
SHOULD_BE_IGNORED=$(git status --short 2>/dev/null | grep -E "(\.mp3|\.sqlite|downloads/S|analysis/.*\.csv)" || true)
if [ ! -z "$SHOULD_BE_IGNORED" ]; then
    echo "❌ ERROR: Files that should be ignored are showing up!"
    echo "$SHOULD_BE_IGNORED"
    echo ""
    echo "Please check your .gitignore file."
    exit 1
else
    echo "✅ All ignored files are properly excluded"
fi

# Check that forum data WILL be tracked
FORUM_DATA_TRACKED=$(git status --short 2>/dev/null | grep "library/forums" || true)
if [ ! -z "$FORUM_DATA_TRACKED" ]; then
    echo "✅ Forum data will be tracked (expected for private repo)"
fi

echo ""
read -p "Ready to create initial commit? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Exiting without commit. Run 'git status' to review."
    exit 0
fi

echo ""
echo "Creating initial commit..."

# Stage all files
git add .

# Show what's being committed
echo ""
echo "Files staged for commit:"
git diff --cached --name-only | head -20

echo ""
read -p "Proceed with commit? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Commit cancelled. Files remain staged."
    exit 0
fi

# Create commit
git commit -m "Initial commit: Team Deakins knowledge base toolkit

- Forum scraper with structured JSON storage
- Podcast episode downloader and ingest scripts
- Schema examples and documentation
- Comprehensive .gitignore for copyright/privacy

Forum data included for private research use.
Audio files and SQLite indices excluded."

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✅ SUCCESS!"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Show stats
echo "Repository statistics:"
echo "  Files tracked: $(git ls-files | wc -l)"
echo "  Repository size: $(du -sh .git | cut -f1)"
echo ""

# Final verification
echo "Final verification:"
BAD_FILES=$(git ls-files | grep -E "(\.mp3|\.sqlite|downloads/S)" || true)
if [ ! -z "$BAD_FILES" ]; then
    echo "❌ WARNING: Audio/SQLite files are tracked!"
    echo "$BAD_FILES"
else
    echo "✅ No audio/SQLite files tracked"
fi

FORUM_FILES=$(git ls-files | grep "library/forums" || true)
if [ ! -z "$FORUM_FILES" ]; then
    echo "✅ Forum data is tracked (expected for private repo)"
    echo "   Files: $(git ls-files | grep -c "library/forums" || echo 0) forum files"
else
    echo "ℹ️  No forum data found yet"
fi

echo ""
echo "⚠️  IMPORTANT REMINDER:"
echo "   This repository contains scraped forum data."
echo "   Keep it PRIVATE - do not make public!"
echo ""
echo "Next steps:"
echo "  1. Review commits: git log"
echo "  2. Create PRIVATE remote repo on GitHub/GitLab"
echo "  3. Add remote: git remote add origin <url>"
echo "  4. Push to remote: git push -u origin main"
echo ""
echo "See GIT_INIT_CHECKLIST.md for detailed post-initialization steps."
