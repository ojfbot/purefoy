#!/usr/bin/env python3
"""
Smart Chapter Generator for Purefoy Transcription Pipeline

Detects natural chapter boundaries in podcast transcripts using multiple
signals (topic shifts, pauses, speaker patterns, keyword density) and
generates titled, summarised chapters in multiple formats.

Designed for long-form interview podcasts like Team Deakins where the
conversation flows between subjects organically — no hard cuts, no
bumpers, just people talking about cinematography.

Algorithm overview
------------------
1. Build sliding-window "topic vectors" across the transcript
2. Score every potential break point using a weighted combination of:
   - Semantic coherence drop between adjacent windows (cosine distance)
   - Pause duration between segments (silence = natural break)
   - Topic-tag distribution shift
   - Speaker-turn density change
   - Film-mention boundary (new film = new chapter)
3. Pick the top N break points that meet the minimum chapter length
4. Extract a title for each chapter from its most distinctive content
5. Generate a short summary from the chapter's key sentences
6. Write chapters in multiple formats

Standalone usage
----------------
  python scripts/tools/chapter_generator.py transcript.json --out chapters.json

Library usage
-------------
  from chapter_generator import ChapterGenerator
  gen = ChapterGenerator()
  chapters = gen.generate(segments, episode_duration)
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ChapterConfig:
    """Tunable parameters for chapter detection."""

    # Chapter length constraints (seconds)
    min_chapter_seconds: float = 120.0    # No chapter shorter than 2 minutes
    max_chapter_seconds: float = 1200.0   # Force a break after 20 minutes
    target_chapter_seconds: float = 420.0 # Aim for ~7 minute chapters

    # How many segments per sliding window for coherence scoring
    window_segments: int = 12

    # Signal weights (sum to 1.0)
    weight_coherence: float = 0.35
    weight_pause: float = 0.20
    weight_topic_shift: float = 0.20
    weight_speaker_turn: float = 0.10
    weight_film_boundary: float = 0.15

    # Thresholds
    pause_significant_seconds: float = 2.0   # Pauses longer than this are notable
    pause_max_score_seconds: float = 8.0     # Pauses this long get max pause score
    min_break_score: float = 0.30            # Minimum combined score to consider a break

    # Title extraction
    title_max_words: int = 8
    title_stopwords: set[str] = field(default_factory=lambda: {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "it", "that", "this", "was", "be",
        "are", "were", "been", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "can", "shall",
        "i", "you", "he", "she", "we", "they", "me", "him", "her", "us",
        "them", "my", "your", "his", "its", "our", "their", "what", "which",
        "who", "whom", "how", "when", "where", "why", "so", "if", "then",
        "than", "because", "as", "about", "into", "through", "just", "very",
        "really", "actually", "like", "know", "think", "yeah", "yes", "no",
        "well", "right", "okay", "oh", "um", "uh", "gonna", "going",
        "thing", "things", "lot", "kind", "sort", "something", "anything",
        "everything", "nothing", "much", "many", "some", "any", "all",
        "get", "got", "go", "went", "come", "came", "say", "said",
        "tell", "told", "see", "look", "make", "take", "give", "also",
        "still", "even", "back", "up", "out", "there", "here", "now",
        "way", "don't", "didn't", "it's", "i'm", "that's", "there's",
        "wasn't", "weren't", "couldn't", "wouldn't", "shouldn't",
    })

    # Summary extraction
    summary_max_sentences: int = 2
    summary_max_words: int = 40


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Chapter:
    """A single chapter within an episode."""
    index: int
    title: str
    start_time: float         # seconds
    end_time: float           # seconds
    duration: float           # seconds

    summary: str = ""
    segment_range: tuple[int, int] = (0, 0)
    word_count: int = 0

    topics: list[str] = field(default_factory=list)
    films: list[str] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)

    break_score: float = 0.0
    break_signals: dict[str, float] = field(default_factory=dict)
    key_phrases: list[str] = field(default_factory=list)


@dataclass
class ChapterSet:
    """Complete chapter data for one episode."""
    episode_title: str | None = None
    episode_duration: float = 0.0
    chapter_count: int = 0
    chapters: list[Chapter] = field(default_factory=list)
    generation_config: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z][a-z'-]*[a-z]|[a-z]", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [m.group().lower() for m in _WORD_RE.finditer(text)]


def _cosine_distance(vec_a: Counter[str], vec_b: Counter[str]) -> float:
    """
    Cosine distance (1 - cosine_similarity) between two term-frequency vectors.
    Returns 0.0 (identical) to 1.0 (orthogonal).
    """
    if not vec_a or not vec_b:
        return 1.0

    common = set(vec_a.keys()) & set(vec_b.keys())
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 1.0

    return 1.0 - dot / (mag_a * mag_b)


def _build_term_vector(texts: list[str], stopwords: set[str]) -> Counter[str]:
    """Build a term-frequency vector from a list of text segments."""
    vec: Counter[str] = Counter()
    for t in texts:
        for word in _tokenize(t):
            if word not in stopwords and len(word) > 2:
                vec[word] += 1
    return vec


def _extract_topic_set(segments: list[dict[str, Any]]) -> set[str]:
    """Extract the set of topic labels from a group of segments."""
    topics: set[str] = set()
    for seg in segments:
        for t in seg.get("topics", []):
            if isinstance(t, dict):
                topics.add(t.get("topic", ""))
            elif isinstance(t, str):
                topics.add(t)
    return topics - {""}


def _extract_film_set(segments: list[dict[str, Any]]) -> set[str]:
    """Extract the set of film names from a group of segments."""
    films: set[str] = set()
    for seg in segments:
        for f in seg.get("films", []):
            if isinstance(f, dict):
                films.add(f.get("film", ""))
            elif isinstance(f, str):
                films.add(f)
    return films - {""}


def _jaccard_distance(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard distance between two sets. 0.0 = identical, 1.0 = disjoint."""
    union = set_a | set_b
    if not union:
        return 0.0
    return 1.0 - len(set_a & set_b) / len(union)


# ---------------------------------------------------------------------------
# Break-point scoring
# ---------------------------------------------------------------------------

def _score_break_points(
    segments: list[dict[str, Any]],
    config: ChapterConfig,
) -> list[tuple[int, float, dict[str, float]]]:
    """
    Score every potential break point between segments.

    Returns:
        List of (segment_index, score, signal_breakdown) sorted by index.
        A break at index i means: chapters [..., i-1] | [i, ...]
    """
    n = len(segments)
    if n < 4:
        return []

    w = config.window_segments
    half_w = w // 2
    scores: list[tuple[int, float, dict[str, float]]] = []

    for i in range(1, n):
        left_segs = segments[max(0, i - half_w):i]
        right_segs = segments[i:min(n, i + half_w)]

        if len(left_segs) < 2 or len(right_segs) < 2:
            continue

        signals: dict[str, float] = {}

        # 1) Coherence: vocabulary shift
        left_vec = _build_term_vector([s["text"] for s in left_segs], config.title_stopwords)
        right_vec = _build_term_vector([s["text"] for s in right_segs], config.title_stopwords)
        signals["coherence"] = _cosine_distance(left_vec, right_vec)

        # 2) Pause: gap between segment i-1 and segment i
        pause = max(0, segments[i].get("start", 0) - segments[i - 1].get("end", 0))
        if pause >= config.pause_significant_seconds:
            signals["pause"] = min(pause / config.pause_max_score_seconds, 1.0)
        else:
            signals["pause"] = 0.0

        # 3) Topic shift: change in tagged topics
        signals["topic_shift"] = _jaccard_distance(
            _extract_topic_set(left_segs),
            _extract_topic_set(right_segs),
        )

        # 4) Speaker pattern change
        left_speakers: Counter[str] = Counter(s.get("speaker") for s in left_segs if s.get("speaker"))
        right_speakers: Counter[str] = Counter(s.get("speaker") for s in right_segs if s.get("speaker"))
        if left_speakers and right_speakers:
            left_dom = left_speakers.most_common(1)[0][0]
            right_dom = right_speakers.most_common(1)[0][0]
            signals["speaker_turn"] = 1.0 if left_dom != right_dom else 0.0
        else:
            signals["speaker_turn"] = 0.0

        # 5) Film boundary: new film introduced
        left_films = _extract_film_set(left_segs)
        right_films = _extract_film_set(right_segs)
        new_films = right_films - left_films
        signals["film_boundary"] = min(len(new_films) / max(len(right_films), 1), 1.0) if new_films else 0.0

        total = (
            config.weight_coherence * signals["coherence"]
            + config.weight_pause * signals["pause"]
            + config.weight_topic_shift * signals["topic_shift"]
            + config.weight_speaker_turn * signals["speaker_turn"]
            + config.weight_film_boundary * signals["film_boundary"]
        )

        scores.append((i, total, signals))

    return scores


def _select_break_points(
    scores: list[tuple[int, float, dict[str, float]]],
    segments: list[dict[str, Any]],
    total_duration: float,
    config: ChapterConfig,
) -> list[tuple[int, float, dict[str, float]]]:
    """
    Select the best break points that satisfy chapter-length constraints.

    Greedy: picks the highest-scoring break that doesn't violate
    minimum-length, then repeats.
    """
    if not scores:
        return []

    candidates = [(i, s, d) for i, s, d in scores if s >= config.min_break_score]
    candidates.sort(key=lambda x: x[1], reverse=True)

    selected: list[int] = []

    for seg_idx, _score, _detail in candidates:
        seg_time = segments[seg_idx]["start"]

        check_points = sorted([0.0] + [segments[b]["start"] for b in selected] + [total_duration])
        too_close = False

        for j in range(len(check_points) - 1):
            left_edge = check_points[j]
            right_edge = check_points[j + 1]

            if left_edge < seg_time < right_edge:
                if (seg_time - left_edge) < config.min_chapter_seconds:
                    too_close = True
                if (right_edge - seg_time) < config.min_chapter_seconds:
                    too_close = True
                break

        if not too_close:
            selected.append(seg_idx)

    # Force breaks if any chapter exceeds max length
    selected.sort()
    forced = _force_max_length_breaks(selected, segments, total_duration, config)
    all_breaks = sorted(set(selected + forced))

    score_map = {i: (s, d) for i, s, d in scores}
    result: list[tuple[int, float, dict[str, float]]] = []
    for idx in all_breaks:
        if idx in score_map:
            s, d = score_map[idx]
            result.append((idx, s, d))
        else:
            result.append((idx, 0.0, {"forced_max_length": 1.0}))

    return result


def _force_max_length_breaks(
    breaks: list[int],
    segments: list[dict[str, Any]],
    total_duration: float,
    config: ChapterConfig,
) -> list[int]:
    """Insert forced breaks where chapters exceed max length."""
    forced: list[int] = []
    boundaries = [0] + breaks + [len(segments)]

    for j in range(len(boundaries) - 1):
        start_idx = boundaries[j]
        end_idx = boundaries[j + 1]
        if end_idx <= start_idx:
            continue

        start_time = segments[start_idx]["start"]
        end_time = (
            segments[min(end_idx, len(segments)) - 1]["end"]
            if end_idx <= len(segments)
            else total_duration
        )
        chapter_dur = end_time - start_time

        if chapter_dur > config.max_chapter_seconds:
            target_time = start_time + chapter_dur / 2
            best_mid = start_idx
            for k in range(start_idx, end_idx):
                if segments[k]["start"] <= target_time:
                    best_mid = k
            if best_mid > start_idx and best_mid < end_idx:
                forced.append(best_mid)

    return forced


# ---------------------------------------------------------------------------
# Title and summary extraction
# ---------------------------------------------------------------------------

def _extract_chapter_title(
    segments: list[dict[str, Any]],
    global_term_freq: Counter[str],
    config: ChapterConfig,
    chapter_index: int,
    films_in_chapter: list[str],
) -> tuple[str, list[str]]:
    """
    Generate a chapter title from the most distinctive content.

    Strategy priority:
    1. Film-led: "Skyfall: The Shanghai Sequence"
    2. Question-led: Extract the core question that opens the chapter
    3. TF-IDF distinctive terms: "Anamorphic Lenses and Flares"
    """
    texts = [s["text"] for s in segments]
    chapter_vec = _build_term_vector(texts, config.title_stopwords)

    if not chapter_vec:
        return f"Chapter {chapter_index + 1}", []

    total_global = sum(global_term_freq.values()) or 1
    scored_terms: list[tuple[str, float]] = []
    for term, chapter_count in chapter_vec.most_common(50):
        global_count = global_term_freq.get(term, 0)
        idf = math.log((total_global + 1) / (global_count + 1))
        scored_terms.append((term, chapter_count * idf))

    scored_terms.sort(key=lambda x: x[1], reverse=True)
    key_phrases = [t for t, _ in scored_terms[:10]]

    # Strategy A: Film-led title
    if films_in_chapter:
        film = films_in_chapter[0]
        qualifier = ""
        for phrase in key_phrases[:5]:
            if phrase.lower() not in {f.lower() for f in films_in_chapter}:
                qualifier = phrase.capitalize()
                break
        title = f"{film}: {qualifier}" if qualifier else f"On {film}"
        return _clean_title(title, config), key_phrases

    # Strategy B: Question-led title
    for seg in segments[:3]:
        text = seg["text"].strip()
        if text.endswith("?") or any(text.lower().startswith(q) for q in
            ["what ", "how ", "can you", "could you", "tell us", "when ",
             "where ", "why ", "do you", "did you", "have you"]):
            q_text = text.rstrip("?").strip()
            for prefix in ["So ", "And ", "Now ", "But ", "Well "]:
                if q_text.startswith(prefix):
                    q_text = q_text[len(prefix):]
            words = q_text.split()
            trail_strip = {
                "the", "a", "an", "and", "or", "but", "in", "on",
                "at", "to", "for", "of", "with", "by", "from", "about",
                "into", "your", "you", "our", "his", "her", "its",
            }
            while words and words[-1].lower() in trail_strip:
                words.pop()
            if 3 <= len(words) <= config.title_max_words:
                return _clean_title(" ".join(words), config), key_phrases
            if len(words) > config.title_max_words:
                trimmed = words[:config.title_max_words]
                while trimmed and trimmed[-1].lower() in trail_strip:
                    trimmed.pop()
                return _clean_title(" ".join(trimmed), config), key_phrases

    # Strategy C: Distinctive term combination
    title_words: list[str] = []
    for term, _ in scored_terms:
        if term not in config.title_stopwords and len(term) > 3:
            title_words.append(term.capitalize())
            if len(title_words) >= 3:
                break

    if not title_words:
        return f"Chapter {chapter_index + 1}", key_phrases

    title = f"{title_words[0]} and {title_words[1]}" if len(title_words) >= 2 else title_words[0]
    return _clean_title(title, config), key_phrases


def _clean_title(title: str, config: ChapterConfig) -> str:
    """Clean up a title string."""
    title = title.strip().rstrip(".,;:-—–")
    if not title:
        return "Untitled"
    words = title.split()
    if len(words) > config.title_max_words:
        title = " ".join(words[:config.title_max_words])
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
    return title


def _extract_chapter_summary(segments: list[dict[str, Any]], config: ChapterConfig) -> str:
    """
    Extract a brief summary from the chapter's content.

    Picks the longest, most content-rich sentences that are not questions.
    """
    all_text = " ".join(s["text"] for s in segments)
    sentences = re.split(r"(?<=[.!?])\s+", all_text)

    if not sentences:
        return ""

    scored: list[tuple[str, float]] = []
    for sent in sentences:
        sent = sent.strip()
        words = sent.split()
        word_count = len(words)

        if word_count < 5 or word_count > 35:
            continue
        if sent.endswith("?"):
            continue

        substantive = sum(1 for w in words if w.lower() not in config.title_stopwords and len(w) > 3)
        score = substantive / max(word_count, 1)
        if word_count > 20:
            score *= 0.8
        scored.append((sent, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    picked: list[str] = []
    total_words = 0
    for sent, _ in scored:
        words_in = len(sent.split())
        if total_words + words_in > config.summary_max_words:
            break
        picked.append(sent)
        total_words += words_in
        if len(picked) >= config.summary_max_sentences:
            break

    return " ".join(picked)


# ---------------------------------------------------------------------------
# Chapter generator
# ---------------------------------------------------------------------------

class ChapterGenerator:
    """
    Generates smart chapters from transcription segments.

    Usage:
        gen = ChapterGenerator()
        chapter_set = gen.generate(segments, episode_duration, episode_title)
    """

    def __init__(self, config: ChapterConfig | None = None):
        self.config = config or ChapterConfig()

    def generate(
        self,
        segments: list[dict[str, Any]],
        episode_duration: float,
        episode_title: str | None = None,
    ) -> ChapterSet:
        """
        Generate chapters from transcript segments.

        Args:
            segments: List of segment dicts with at minimum:
                      {id, start, end, text} and optionally
                      {speaker, topics, films}
            episode_duration: Total audio duration in seconds
            episode_title: Optional episode title for the intro chapter

        Returns:
            ChapterSet with all chapters
        """
        result = ChapterSet(
            episode_title=episode_title,
            episode_duration=episode_duration,
            generation_config=asdict(self.config),
        )

        if not segments or episode_duration <= 0:
            logger.warning("No segments or zero duration — cannot generate chapters")
            return result

        if len(segments) < 4:
            ch = self._build_single_chapter(segments, episode_duration, episode_title)
            result.chapters = [ch]
            result.chapter_count = 1
            return result

        global_tf = _build_term_vector([s["text"] for s in segments], self.config.title_stopwords)

        logger.info("Scoring %d potential break points...", len(segments) - 1)
        scores = _score_break_points(segments, self.config)
        breaks = _select_break_points(scores, segments, episode_duration, self.config)
        break_indices = [b[0] for b in breaks]
        break_details = {b[0]: (b[1], b[2]) for b in breaks}

        logger.info("Selected %d chapter breaks", len(break_indices))

        boundaries = [0] + break_indices + [len(segments)]
        chapters: list[Chapter] = []

        for j in range(len(boundaries) - 1):
            start_idx = boundaries[j]
            end_idx = boundaries[j + 1]
            chapter_segs = segments[start_idx:end_idx]
            if not chapter_segs:
                continue

            start_time = chapter_segs[0]["start"]
            end_time = chapter_segs[-1]["end"]
            duration = end_time - start_time

            topics = sorted(_extract_topic_set(chapter_segs))
            films = sorted(_extract_film_set(chapter_segs))
            speakers = sorted(set(s.get("speaker") for s in chapter_segs if s.get("speaker")))
            word_count = sum(len(s["text"].split()) for s in chapter_segs)

            title, key_phrases = _extract_chapter_title(
                chapter_segs, global_tf, self.config, j, films,
            )

            # Intro chapter override
            if j == 0 and start_time < 30.0 and episode_title:
                guest = _extract_guest_name(episode_title)
                title = f"Introduction: {guest}" if guest else "Introduction"

            summary = _extract_chapter_summary(chapter_segs, self.config)

            break_score = 0.0
            break_signals: dict[str, float] = {}
            if start_idx in break_details:
                break_score, break_signals = break_details[start_idx]

            chapters.append(Chapter(
                index=j,
                title=title,
                start_time=round(start_time, 3),
                end_time=round(end_time, 3),
                duration=round(duration, 2),
                summary=summary,
                segment_range=(start_idx, end_idx - 1),
                word_count=word_count,
                topics=topics,
                films=films,
                speakers=speakers,
                break_score=round(break_score, 4),
                break_signals=break_signals,
                key_phrases=key_phrases[:5],
            ))

        result.chapters = chapters
        result.chapter_count = len(chapters)

        logger.info(
            "Generated %d chapters (avg %.0fs each)",
            len(chapters),
            episode_duration / max(len(chapters), 1),
        )
        return result

    def _build_single_chapter(
        self,
        segments: list[dict[str, Any]],
        duration: float,
        title: str | None,
    ) -> Chapter:
        """Build a single chapter spanning the whole episode."""
        return Chapter(
            index=0,
            title=title or "Full Episode",
            start_time=0.0,
            end_time=duration,
            duration=duration,
            segment_range=(0, len(segments) - 1),
            word_count=sum(len(s["text"].split()) for s in segments),
            topics=sorted(_extract_topic_set(segments)),
            films=sorted(_extract_film_set(segments)),
        )


def _extract_guest_name(episode_title: str) -> str | None:
    """
    Try to extract a guest name from a Team Deakins episode title.

    Common pattern: "EDGAR WRIGHT - Director"
    """
    m = re.match(r"^(.+?)\s*[-—–]\s*(.+)$", episode_title.strip())
    if m:
        name = m.group(1).strip()
        if name.isupper():
            name = name.title()
        return name
    return None


# ---------------------------------------------------------------------------
# Output format writers
# ---------------------------------------------------------------------------

def chapters_to_dict(chapter_set: ChapterSet) -> dict[str, Any]:
    """Convert ChapterSet to a plain dict for JSON serialization."""
    return {
        "episode_title": chapter_set.episode_title,
        "episode_duration": chapter_set.episode_duration,
        "chapter_count": chapter_set.chapter_count,
        "chapters": [
            {
                "index": ch.index,
                "title": ch.title,
                "start_time": ch.start_time,
                "end_time": ch.end_time,
                "duration": ch.duration,
                "summary": ch.summary,
                "segment_range": list(ch.segment_range),
                "word_count": ch.word_count,
                "topics": ch.topics,
                "films": ch.films,
                "speakers": ch.speakers,
                "break_score": ch.break_score,
                "break_signals": ch.break_signals,
                "key_phrases": ch.key_phrases,
            }
            for ch in chapter_set.chapters
        ],
    }


def write_chapters_json(chapter_set: ChapterSet, path: Path) -> Path:
    """Write chapters in the Purefoy internal JSON format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chapters_to_dict(chapter_set), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_podcastns_chapters(chapter_set: ChapterSet, path: Path) -> Path:
    """
    Write chapters in Podcasting 2.0 JSON Chapters format.

    Spec: https://github.com/Podcastindex-org/podcast-namespace/blob/main/chapters/jsonChapters.md
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    chapters = []
    for ch in chapter_set.chapters:
        entry: dict[str, Any] = {"startTime": round(ch.start_time), "title": ch.title}
        if ch.end_time and ch.end_time > ch.start_time:
            entry["endTime"] = round(ch.end_time)
        entry["toc"] = True
        chapters.append(entry)

    path.write_text(
        json.dumps({"version": "1.2.0", "chapters": chapters}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def write_chapters_txt(chapter_set: ChapterSet, path: Path) -> Path:
    """
    Write chapters as a human-readable text list.

    Format:
        00:00:00  Introduction: Edgar Wright
        00:07:23  Early Influences and Film School
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    if chapter_set.episode_title:
        lines.append(f"CHAPTERS: {chapter_set.episode_title}")
        lines.append("")

    for ch in chapter_set.chapters:
        tc = _format_tc(ch.start_time)
        lines.append(f"{tc}  {ch.title}")
        if ch.summary:
            lines.append(f"          {ch.summary}")
        if ch.topics:
            lines.append(f"          Topics: {', '.join(ch.topics)}")
        if ch.films:
            lines.append(f"          Films: {', '.join(ch.films)}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_chapters_ffmetadata(chapter_set: ChapterSet, path: Path) -> Path:
    """
    Write chapters in FFmpeg metadata format.

    Can be embedded into MP3/MP4 with:
      ffmpeg -i audio.mp3 -i chapters.ffmeta -map_metadata 1 -codec copy output.mp3
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [";FFMETADATA1"]
    if chapter_set.episode_title:
        lines.append(f"title={chapter_set.episode_title}")
    lines.append("")

    for ch in chapter_set.chapters:
        lines.extend([
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={int(ch.start_time * 1000)}",
            f"END={int(ch.end_time * 1000)}",
            f"title={ch.title}",
            "",
        ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _format_tc(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Generate smart chapters from a transcript.json file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/tools/chapter_generator.py downloads/S02E169_.../transcript/transcript.json
  python scripts/tools/chapter_generator.py transcript.json --min-length 180 --target-length 600
        """,
    )
    p.add_argument("transcript", help="Path to transcript.json file")
    p.add_argument("--out-dir", default=None, help="Output directory (default: same as transcript)")
    p.add_argument("--min-length", type=float, default=120)
    p.add_argument("--max-length", type=float, default=1200)
    p.add_argument("--target-length", type=float, default=420)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        logger.error("Transcript not found: %s", transcript_path)
        return 1

    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    meta = data.get("meta", {})
    episode_title = meta.get("episode_title")
    episode_duration = meta.get("audio_duration_seconds", 0) or (
        segments[-1].get("end", 0) if segments else 0
    )

    if not segments:
        logger.error("No segments found in transcript")
        return 1

    logger.info("Loaded transcript: %s — %d segments, %.0fs", episode_title or "unknown", len(segments), episode_duration)

    config = ChapterConfig(
        min_chapter_seconds=args.min_length,
        max_chapter_seconds=args.max_length,
        target_chapter_seconds=args.target_length,
    )
    chapter_set = ChapterGenerator(config).generate(segments, episode_duration, episode_title)

    out_dir = Path(args.out_dir) if args.out_dir else transcript_path.parent
    write_chapters_json(chapter_set, out_dir / "chapters.json")
    write_podcastns_chapters(chapter_set, out_dir / "chapters_podcastns.json")
    write_chapters_txt(chapter_set, out_dir / "chapters.txt")
    write_chapters_ffmetadata(chapter_set, out_dir / "chapters.ffmeta")

    print(f"\nGenerated {chapter_set.chapter_count} chapters:\n")
    for ch in chapter_set.chapters:
        print(f"  {_format_tc(ch.start_time)}  {ch.title}")
        if ch.summary:
            print(f"           {ch.summary[:80]}...")
        print()

    print(f"Written to: {out_dir}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
