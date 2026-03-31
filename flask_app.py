"""
Lightweight Flask UI for the Team Deakins knowledge base.
Netflix-style: dark theme, horizontal carousels, no vertical scroll.

Serves transcript data from either:
- Local filesystem (DOWNLOADS_DIR) — default for local dev
- Remote CDN (DATA_CDN_URL) — production on Vercel (ADR-010)

API responses match the Express contract (PaginatedResponse envelope,
camelCase keys) so both tde.jim.software and purefoy.jim.software work.

Usage:
    pip install flask flask-cors
    python flask_app.py
    # → http://localhost:5050
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__)

# CORS for cross-origin requests from React MF remote and Frame shell
CORS(app, resources={r"/api/*": {"origins": [
    "https://purefoy.jim.software",
    "https://tde.jim.software",
    "https://frame.jim.software",
    "http://localhost:3020",
    "http://localhost:4000",
]}})

DOWNLOADS_DIR = Path(os.environ.get("DOWNLOADS_DIR", "./downloads"))
LIBRARY_DIR = Path(os.environ.get("LIBRARY_DIR", "./library"))
FORUMS_DIR = LIBRARY_DIR / "forums"

# CDN URL for remote data (S3 + CloudFront). When set, fetch data from CDN
# instead of local filesystem. See ADR-010.
DATA_CDN_URL: str | None = os.environ.get("DATA_CDN_URL")

# Read-only mode: enabled on Vercel (no writable filesystem) or via READ_ONLY=1.
# In this mode all write endpoints return 405 and the UI suppresses save/flush.
READ_ONLY: bool = bool(os.environ.get("VERCEL") or os.environ.get("READ_ONLY"))

# In-memory episode index cache (populated on first request).
# Intentionally never invalidated — on Vercel each request may be a fresh
# cold start anyway, and in local dev a server restart is sufficient.
_episode_index: list[dict] | None = None


# ---------------------------------------------------------------------------
# CDN helpers
# ---------------------------------------------------------------------------

def _cdn_fetch_json(path: str) -> dict | list | None:
    """Fetch JSON from CDN. Returns None on error (falls through to filesystem)."""
    if not DATA_CDN_URL:
        return None
    url = f"{DATA_CDN_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except (URLError, json.JSONDecodeError, OSError) as exc:
        print(f"[cdn] fetch failed: {url} — {exc}", file=__import__("sys").stderr)
        return None


def _cdn_stream(path: str):
    """Stream raw bytes from CDN. Returns a response-like object or None."""
    if not DATA_CDN_URL:
        return None
    url = f"{DATA_CDN_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        req = Request(url)
        return urlopen(req, timeout=30)
    except (URLError, OSError):
        return None


# ---------------------------------------------------------------------------
# Episode index (CDN or filesystem)
# ---------------------------------------------------------------------------

def _load_episode_index() -> list[dict]:
    """Load episode index — from CDN if available, otherwise from filesystem."""
    global _episode_index
    if _episode_index is not None:
        return _episode_index

    if DATA_CDN_URL:
        items = _cdn_fetch_json("episodes/index.json")
        if items and isinstance(items, list):
            _episode_index = items
            return _episode_index

    # Fallback: build from filesystem
    _episode_index = _load_all_episodes_from_fs()
    return _episode_index


def _load_all_episodes_from_fs() -> list[dict]:
    """Load and sort all episodes from filesystem, returning camelCase dicts."""
    eps = []
    if not DOWNLOADS_DIR.exists():
        return eps
    for d in DOWNLOADS_DIR.iterdir():
        if d.is_dir() and d.name.startswith("S") and re.match(r"S\d+E\d+__", d.name):
            ep = _parse_episode_dir(d)
            if ep:
                eps.append(ep)
    eps.sort(key=lambda e: (e.get("pubDate", ""), e.get("episode", 0)), reverse=True)
    return eps


# ---------------------------------------------------------------------------
# Filesystem helpers (local dev fallback)
# ---------------------------------------------------------------------------

def _parse_episode_dir(d: Path) -> dict | None:
    """Parse an episode directory into a camelCase EpisodeListItem dict."""
    meta_path = d / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    name = d.name
    m = re.match(r"S(\d+)E(\d+)__(\d{4}-\d{2}-\d{2})__(.+?)__libsyn_", name)
    season = int(m.group(1)) if m else meta.get("itunes_season")
    episode = int(m.group(2)) if m else meta.get("itunes_episode")
    pub_date = m.group(3) if m else meta.get("pub_date_iso", "")

    # Transcript info
    has_transcript = False
    canonical_run = None
    chapters = []
    run_manifest = d / "transcript" / "run_manifest.json"
    if run_manifest.exists():
        try:
            rm = json.loads(run_manifest.read_text())
            canonical_run = rm.get("canonical") or rm.get("canonical_run_id")
            if canonical_run:
                has_transcript = True
        except (json.JSONDecodeError, OSError):
            pass

    # Chapter data from canonical run
    if canonical_run:
        ch_path = d / "transcript" / "runs" / canonical_run / "chapters.json"
        if ch_path.exists():
            try:
                ch_data = json.loads(ch_path.read_text())
                chapters = ch_data.get("chapters", ch_data) if isinstance(ch_data, dict) else ch_data
            except (json.JSONDecodeError, OSError):
                pass

    # Collect topics and films from chapters
    all_topics: set[str] = set()
    all_films: set[str] = set()
    for ch in (chapters if isinstance(chapters, list) else []):
        for t in ch.get("topics", []):
            all_topics.add(t)
        for f in ch.get("films", []):
            all_films.add(f)

    # Stats from extraction_report
    stats = None
    if canonical_run:
        report_path = d / "transcript" / "runs" / canonical_run / "extraction_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
                if report.get("success"):
                    stats = {
                        "chapters": report.get("chapters_generated", 0),
                        "words": report.get("word_count", 0),
                        "speakers": report.get("speakers_detected", 0),
                        "topics": sorted(all_topics),
                        "films": sorted(all_films),
                    }
            except (json.JSONDecodeError, OSError):
                pass

    # Goal data check
    has_goal = (_goal_dir(d) / "transcript_segments_goal.jsonl").exists()
    review_coverage = 0.0
    review_path = _goal_dir(d) / "review_progress.json"
    if review_path.exists():
        try:
            rp = json.loads(review_path.read_text())
            review_coverage = rp.get("review_coverage", 0.0)
        except (json.JSONDecodeError, OSError):
            pass

    title = meta.get("title", name)
    clean_title = re.sub(r"^SEASON\s+\d+\s*-\s*EPISODE\s+\d+\s*-\s*", "", title, flags=re.I).strip()

    return {
        "slug": name,
        "title": clean_title or title,
        "pubDate": pub_date,
        "season": season,
        "episode": episode,
        "duration": meta.get("itunes_duration", ""),
        "hasTranscript": has_transcript,
        "canonicalRunId": canonical_run,
        "hasGoal": has_goal,
        "reviewCoverage": review_coverage,
        "stats": stats,
    }


def _get_episode_detail_fs(slug: str) -> dict | None:
    """Build EpisodeDetail from filesystem (local dev)."""
    d = DOWNLOADS_DIR / slug
    if not d.exists():
        return None
    item = _parse_episode_dir(d)
    if not item:
        return None

    meta_path = d / "metadata.json"
    try:
        meta = json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    # Parse duration
    duration_seconds = 0
    itunes_duration = meta.get("itunes_duration", "")
    if itunes_duration:
        parts = itunes_duration.split(":")
        try:
            nums = [int(p) for p in parts]
            if len(nums) == 3:
                duration_seconds = nums[0] * 3600 + nums[1] * 60 + nums[2]
            elif len(nums) == 2:
                duration_seconds = nums[0] * 60 + nums[1]
        except ValueError:
            pass
    if not duration_seconds:
        am = meta.get("audio_metadata", {})
        if am and am.get("duration_seconds"):
            duration_seconds = int(am["duration_seconds"])

    # All run IDs
    all_run_ids = []
    manifest = None
    manifest_path = d / "transcript" / "run_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            all_run_ids = [r.get("run_id", "") for r in manifest.get("runs", [])]
        except (json.JSONDecodeError, OSError):
            pass

    item.update({
        "descriptionHtml": meta.get("description_html", ""),
        "durationSeconds": duration_seconds,
        "imageUrl": meta.get("itunes_image"),
        "allRunIds": all_run_ids,
    })
    return item


def _load_forum_topics() -> list[dict]:
    """Load all forum topic summaries."""
    topics_dir = FORUMS_DIR / "topics"
    if not topics_dir.exists():
        return []
    topics = []
    for f in topics_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            topics.append({
                "slug": f.stem,
                "title": data.get("title", f.stem),
                "topic_url": data.get("topic_url", ""),
                "reply_count": data.get("reply_count", 0),
                "post_ids": data.get("post_ids", []),
                "forum_slug": data.get("forum_slug", ""),
            })
        except (json.JSONDecodeError, OSError):
            continue
    topics.sort(key=lambda t: t["reply_count"], reverse=True)
    return topics


def _load_post(post_id: str) -> dict | None:
    post_path = FORUMS_DIR / "posts" / f"{post_id}.json"
    if not post_path.exists():
        return None
    try:
        return json.loads(post_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _load_topic_with_posts(slug: str) -> dict | None:
    topic_path = FORUMS_DIR / "topics" / f"{slug}.json"
    if not topic_path.exists():
        return None
    try:
        topic = json.loads(topic_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    posts = []
    for pid in topic.get("post_ids", []):
        p = _load_post(pid)
        if p:
            posts.append({
                "post_id": p.get("ids", {}).get("post_id", pid),
                "author": p.get("author", {}).get("display_name", "Unknown"),
                "role": p.get("author", {}).get("role", ""),
                "content": p.get("content_text", ""),
                "post_type": p.get("post_type", "reply"),
            })
    return {"topic": topic, "posts": posts}


def _resolve_canonical(d: Path) -> str | None:
    """Resolve the canonical run_id for an episode directory."""
    run_manifest = d / "transcript" / "run_manifest.json"
    if not run_manifest.exists():
        return None
    try:
        rm = json.loads(run_manifest.read_text())
        return rm.get("canonical") or rm.get("canonical_run_id")
    except (json.JSONDecodeError, OSError):
        return None


def _goal_dir(d: Path) -> Path:
    """Return the goal data directory for an episode."""
    return d / "transcript" / "goal"


GOAL_SEGMENT_FIELDS = {"id", "start", "end", "text", "speaker",
                        "segment_type", "chapter_id", "confidence", "topics"}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", read_only=READ_ONLY)


@app.route("/robots.txt")
def robots_txt():
    return Response(
        "User-agent: *\nDisallow: /api/\n",
        mimetype="text/plain",
    )


def _valid_slug(slug: str) -> bool:
    """Reject path traversal attempts in episode slugs."""
    return ".." not in slug and not slug.startswith("/") and re.match(r"S\d+E\d+__", slug) is not None


@app.route("/api/episodes")
def api_episodes():
    all_eps = _load_episode_index()

    # Filters
    season = request.args.get("season", type=int)
    topic = request.args.get("topic")
    film = request.args.get("film")
    if season is not None:
        all_eps = [e for e in all_eps if e.get("season") == season]
    if topic:
        all_eps = [e for e in all_eps if topic in (e.get("stats") or {}).get("topics", [])]
    if film:
        all_eps = [e for e in all_eps if film in (e.get("stats") or {}).get("films", [])]

    # Pagination
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 500)
    total = len(all_eps)
    start = (page - 1) * limit
    items = all_eps[start:start + limit]

    resp = jsonify({
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "hasMore": start + limit < total,
    })
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@app.route("/api/episodes/<slug>")
def api_episode_detail(slug):
    if not _valid_slug(slug):
        return jsonify({"error": "invalid slug"}), 400
    # Try CDN first
    if DATA_CDN_URL:
        detail = _cdn_fetch_json(f"episodes/{slug}/meta.json")
        if detail:
            resp = jsonify(detail)
            resp.headers["Cache-Control"] = "public, max-age=3600"
            return resp

    # Filesystem fallback
    detail = _get_episode_detail_fs(slug)
    if not detail:
        return jsonify({"error": "not found"}), 404
    resp = jsonify(detail)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@app.route("/api/episodes/<slug>/chapters")
def api_episode_chapters(slug):
    if not _valid_slug(slug):
        return jsonify({"error": "invalid slug"}), 400
    # Try CDN first
    if DATA_CDN_URL:
        chapters = _cdn_fetch_json(f"episodes/{slug}/chapters.json")
        if chapters is not None:
            resp = jsonify(chapters)
            resp.headers["Cache-Control"] = "public, max-age=3600"
            return resp

    # Filesystem fallback
    d = DOWNLOADS_DIR / slug
    run_manifest = d / "transcript" / "run_manifest.json"
    if not run_manifest.exists():
        return jsonify([])
    try:
        rm = json.loads(run_manifest.read_text())
        canonical = rm.get("canonical") or rm.get("canonical_run_id")
        if not canonical:
            return jsonify([])
        ch_path = d / "transcript" / "runs" / canonical / "chapters.json"
        if not ch_path.exists():
            return jsonify([])
        data = json.loads(ch_path.read_text())
        chapters = data.get("chapters", data) if isinstance(data, dict) else data
        resp = jsonify(chapters)
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
    except (json.JSONDecodeError, OSError):
        return jsonify([])


@app.route("/api/episodes/<slug>/transcript")
def api_episode_transcript(slug):
    if not _valid_slug(slug):
        return jsonify({"error": "invalid slug"}), 400
    # Try CDN first
    if DATA_CDN_URL:
        stream = _cdn_stream(f"episodes/{slug}/transcript.jsonl")
        if stream:
            def generate():
                try:
                    while True:
                        chunk = stream.read(8192)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    stream.close()

            resp = Response(generate(), mimetype="application/x-ndjson")
            resp.headers["Cache-Control"] = "public, max-age=3600"
            return resp

    # Filesystem fallback
    d = DOWNLOADS_DIR / slug
    run_manifest = d / "transcript" / "run_manifest.json"
    if not run_manifest.exists():
        return jsonify([])
    try:
        rm = json.loads(run_manifest.read_text())
        canonical = rm.get("canonical") or rm.get("canonical_run_id")
        if not canonical:
            return jsonify([])
        seg_path = d / "transcript" / "runs" / canonical / "transcript_segments.jsonl"
        if not seg_path.exists():
            return jsonify([])

        def generate():
            with open(seg_path) as f:
                yield from f

        resp = Response(generate(), mimetype="application/x-ndjson")
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
    except (json.JSONDecodeError, OSError):
        return jsonify([])


@app.route("/api/episodes/<slug>/transcript/goal")
def api_episode_goal(slug):
    if not _valid_slug(slug):
        return jsonify({"error": "invalid slug"}), 400
    d = DOWNLOADS_DIR / slug
    goal_path = _goal_dir(d) / "transcript_segments_goal.jsonl"
    if not goal_path.exists():
        return jsonify({"exists": False}), 404

    def generate():
        with open(goal_path) as f:
            yield from f

    return Response(generate(), mimetype="application/x-ndjson")


@app.route("/api/episodes/<slug>/transcript/goal/meta")
def api_episode_goal_meta(slug):
    if not _valid_slug(slug):
        return jsonify({"error": "invalid slug"}), 400
    d = DOWNLOADS_DIR / slug
    manifest_path = _goal_dir(d) / "goal_manifest.json"
    if not manifest_path.exists():
        return jsonify({"exists": False}), 404
    try:
        return jsonify(json.loads(manifest_path.read_text()))
    except (json.JSONDecodeError, OSError):
        return jsonify({"exists": False}), 404


@app.route("/api/episodes/<slug>/transcript/goal", methods=["POST"])
def api_save_goal(slug):
    if not _valid_slug(slug):
        return jsonify({"error": "invalid slug"}), 400
    if READ_ONLY:
        return jsonify({"error": "read-only mode"}), 405
    d = DOWNLOADS_DIR / slug
    if not d.exists():
        return jsonify({"error": "episode not found"}), 404

    canonical = _resolve_canonical(d)
    if not canonical:
        return jsonify({"error": "no canonical transcript"}), 400

    data = request.get_json()
    if not data or "segments" not in data:
        return jsonify({"error": "missing segments"}), 400

    segments = data["segments"]

    # Validate each segment has required fields
    for i, seg in enumerate(segments):
        missing = GOAL_SEGMENT_FIELDS - set(seg.keys())
        if missing:
            return jsonify({"error": f"segment {i} missing fields: {missing}"}), 400

    # Write goal JSONL
    goal_path = _goal_dir(d)
    goal_path.mkdir(parents=True, exist_ok=True)

    seg_file = goal_path / "transcript_segments_goal.jsonl"
    with open(seg_file, "w") as f:
        for seg in segments:
            f.write(json.dumps(seg, ensure_ascii=False) + "\n")

    # Count modifications vs original
    orig_path = d / "transcript" / "runs" / canonical / "transcript_segments.jsonl"
    speaker_changes = 0
    text_edits = 0
    if orig_path.exists():
        try:
            orig_segs = []
            with open(orig_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        orig_segs.append(json.loads(line))
            for orig, goal in zip(orig_segs, segments):
                if orig.get("speaker") != goal.get("speaker"):
                    speaker_changes += 1
                if orig.get("text") != goal.get("text"):
                    text_edits += 1
        except (json.JSONDecodeError, OSError):
            pass

    # Write/update goal manifest
    manifest_path = goal_path / "goal_manifest.json"
    now = datetime.now(timezone.utc).isoformat()  # noqa: UP017 — 3.9 compat
    existing = {}
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    manifest = {
        "tag": "Goal Data",
        "source_run": canonical,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
        "segment_count": len(segments),
        "correction_summary": {
            "speaker_reassignments": speaker_changes,
            "text_edits": text_edits,
            "total_segments_modified": speaker_changes + text_edits,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    return jsonify({"ok": True, "manifest": manifest})


@app.route("/api/episodes/<slug>/transcript/review", methods=["GET", "POST"])
def api_episode_review(slug):
    """Track which segments have been human-reviewed in edit mode."""
    if not _valid_slug(slug):
        return jsonify({"error": "invalid slug"}), 400
    if READ_ONLY and request.method == "POST":
        return jsonify({"error": "read-only mode"}), 405
    d = DOWNLOADS_DIR / slug
    if not d.exists():
        return jsonify({"error": "not found"}), 404

    review_path = _goal_dir(d) / "review_progress.json"

    if request.method == "GET":
        if not review_path.exists():
            return jsonify({"exists": False})
        try:
            return jsonify(json.loads(review_path.read_text()))
        except (json.JSONDecodeError, OSError):
            return jsonify({"exists": False})

    # POST — merge new reviewed segment indices
    data = request.get_json()
    if not data:
        return jsonify({"error": "missing data"}), 400

    now = datetime.now(timezone.utc).isoformat()  # noqa: UP017 — 3.9 compat
    existing = {"reviewed_segments": [], "sessions": []}
    if review_path.exists():
        try:
            existing = json.loads(review_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Merge reviewed segment IDs (union)
    prev_reviewed = set(existing.get("reviewed_segments", []))
    new_reviewed = set(data.get("reviewed_segments", []))
    all_reviewed = sorted(prev_reviewed | new_reviewed)

    total_segments = data.get("total_segments", 0)

    # Record session
    sessions = existing.get("sessions", [])
    sessions.append({
        "timestamp": now,
        "segments_reviewed_this_session": len(new_reviewed - prev_reviewed),
        "cumulative_reviewed": len(all_reviewed),
    })

    review = {
        "exists": True,
        "slug": slug,
        "reviewed_segments": all_reviewed,
        "total_segments": total_segments,
        "review_coverage": round(len(all_reviewed) / total_segments, 4) if total_segments else 0,
        "first_opened": existing.get("first_opened", now),
        "last_reviewed": now,
        "sessions": sessions[-20:],  # keep last 20 sessions
    }

    _goal_dir(d).mkdir(parents=True, exist_ok=True)
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False))
    return jsonify(review)


@app.route("/api/forum/topics")
def api_forum_topics():
    return jsonify(_load_forum_topics())


@app.route("/api/forum/topics/<slug>")
def api_forum_topic(slug):
    result = _load_topic_with_posts(slug)
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
