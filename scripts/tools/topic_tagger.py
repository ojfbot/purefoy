#!/usr/bin/env python3
"""
Topic Tagger for Purefoy Transcription Pipeline

Cross-references transcript segments against the Purefoy forum corpus
to extract cinematography-relevant topics, link to related discussions,
and tag segments with domain-specific metadata.

Operates in two modes:
1. Corpus mode: Loads forum JSON posts and builds vocabulary
2. Static mode: Uses a built-in cinematography keyword dictionary
   (fallback when forum data isn't available)
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Built-in cinematography vocabulary (fallback when corpus unavailable)
# ---------------------------------------------------------------------------

CINEMATOGRAPHY_TOPICS: dict[str, list[str]] = {
    "lighting": [
        "lighting", "light", "lights", "lit", "illumination",
        "natural light", "practical", "practicals", "bounce", "fill light",
        "key light", "backlight", "rim light", "edge light", "motivated",
        "hard light", "soft light", "diffusion", "scrim", "flag",
        "negative fill", "china ball", "book light", "muslin",
        "hmi", "tungsten", "led", "kino flo", "fresnel", "par",
        "skypanel", "arri", "litepanels", "aputure",
        "daylight", "moonlight", "candle", "fire light",
        "exposure", "stop", "f-stop", "t-stop", "iris",
        "chiaroscuro", "rembrandt", "high key", "low key",
    ],
    "camera": [
        "camera", "cameras", "arri", "alexa", "alexa 35", "alexa mini",
        "red", "red camera", "panavision", "sony", "venice",
        "blackmagic", "canon", "film camera", "digital camera",
        "sensor", "gate", "movement", "steadicam", "handheld",
        "tripod", "dolly", "crane", "technocrane", "jib",
        "gimbal", "slider", "tracking shot", "pan", "tilt",
        "dutch angle", "low angle", "high angle", "pov",
        "over the shoulder", "close up", "wide shot", "medium shot",
        "two shot", "single", "master shot", "coverage",
    ],
    "lenses": [
        "lens", "lenses", "anamorphic", "spherical", "prime", "zoom",
        "cooke", "panavision", "zeiss", "leitz", "angenieux",
        "master prime", "ultra prime", "s4", "t-series",
        "focal length", "wide angle", "telephoto", "normal lens",
        "18mm", "25mm", "27mm", "32mm", "35mm", "40mm", "50mm",
        "65mm", "75mm", "100mm", "135mm", "200mm",
        "depth of field", "shallow focus", "deep focus", "bokeh",
        "distortion", "flare", "breathing", "chromatic aberration",
        "vintage lens", "rehoused", "diopter", "close focus",
    ],
    "color": [
        "color", "colour", "color grading", "color timing",
        "color temperature", "kelvin", "white balance",
        "warm", "cool", "desaturated", "saturated",
        "davinci resolve", "baselight", "lustre",
        "lut", "look", "color space", "rec 709", "aces",
        "print stock", "bleach bypass", "cross process",
        "ektachrome", "kodak", "fuji", "film stock",
    ],
    "composition": [
        "composition", "framing", "frame", "aspect ratio",
        "rule of thirds", "symmetry", "leading lines",
        "headroom", "nose room", "negative space",
        "foreground", "middleground", "background",
        "depth", "layers", "blocking", "staging",
        "1.33", "1.66", "1.85", "2.00", "2.35", "2.39", "2.76",
        "scope", "flat", "widescreen", "imax",
    ],
    "film_format": [
        "35mm", "16mm", "super 16", "65mm", "70mm", "imax",
        "digital", "film", "celluloid", "negative",
        "print", "dailies", "rushes", "telecine", "scan",
        "resolution", "4k", "6k", "8k", "grain", "texture",
    ],
    "production": [
        "director", "director of photography", "cinematographer",
        "dp", "dop", "gaffer", "grip", "key grip", "best boy",
        "camera operator", "first ac", "second ac", "focus puller",
        "production designer", "art director", "set decorator",
        "location", "studio", "sound stage", "backlot",
        "pre-production", "prep", "tech scout", "recce",
        "schedule", "budget", "day", "night", "exterior", "interior",
    ],
    "post_production": [
        "post production", "editing", "editor", "cut", "assembly",
        "visual effects", "vfx", "cgi", "compositing", "green screen",
        "blue screen", "matte", "plate", "roto",
        "digital intermediate", "di", "conform", "online",
        "sound design", "sound mix", "dub", "foley",
    ],
    "storytelling": [
        "story", "narrative", "character", "emotion", "mood", "tone",
        "atmosphere", "texture", "rhythm", "pace", "pacing",
        "script", "screenplay", "scene", "sequence", "montage",
        "subtext", "visual metaphor", "motif", "theme",
        "collaboration", "relationship", "trust", "communication",
    ],
}

# Roger Deakins filmography — for detecting film-specific discussions
DEAKINS_FILMS: dict[str, list[str]] = {
    "1917": ["1917", "world war one", "one shot", "single take", "sam mendes"],
    "Skyfall": ["skyfall", "james bond", "bond", "silva", "sam mendes"],
    "Blade Runner 2049": ["blade runner", "blade runner 2049", "2049", "villeneuve", "denis villeneuve"],
    "No Country for Old Men": ["no country", "no country for old men", "coen brothers", "coen", "chigurh"],
    "The Shawshank Redemption": ["shawshank", "shawshank redemption", "darabont"],
    "Sicario": ["sicario", "villeneuve", "border"],
    "Prisoners": ["prisoners", "villeneuve", "keller"],
    "Fargo": ["fargo", "coen", "marge"],
    "True Grit": ["true grit", "coen", "rooster cogburn"],
    "A Beautiful Mind": ["beautiful mind", "ron howard", "nash"],
    "The Big Lebowski": ["big lebowski", "lebowski", "dude", "coen"],
    "O Brother Where Art Thou": ["o brother", "odyssey", "coen", "depression era"],
    "Barton Fink": ["barton fink", "coen", "hotel"],
    "The Assassination of Jesse James": ["jesse james", "assassination", "andrew dominik"],
    "Jarhead": ["jarhead", "sam mendes", "gulf war"],
    "Revolutionary Road": ["revolutionary road", "sam mendes"],
    "Hail Caesar": ["hail caesar", "coen"],
    "The Reader": ["the reader", "stephen daldry"],
    "The Goldfinch": ["goldfinch", "john crowley"],
    "Empire of Light": ["empire of light", "sam mendes", "margate"],
    "The Brutalist": ["brutalist", "brady corbet", "corbet"],
}


@dataclass
class TopicMatch:
    """A topic detected in a transcript segment."""
    topic: str
    confidence: float
    keywords_matched: list[str]
    related_forum_topics: list[str] = field(default_factory=list)


@dataclass
class FilmMention:
    """A Deakins film detected in transcript text."""
    film: str
    keywords_matched: list[str]
    confidence: float


@dataclass
class TopicSummary:
    """Episode-level topic summary."""
    topic: str
    segment_count: int
    keywords_matched: list[str]
    related_forum_topics: list[str]


# ---------------------------------------------------------------------------
# Corpus Vocabulary Builder
# ---------------------------------------------------------------------------

class ForumVocabulary:
    """
    Builds a domain-specific vocabulary from the Purefoy forum corpus.

    Loads forum post JSON files and extracts high-frequency terms (TF-IDF
    weighted), author-specific vocabulary (Roger Deakins' terms weighted
    higher), and topic slugs for cross-referencing.
    """

    def __init__(self, library_dir: Path | None = None):
        self.library_dir = library_dir
        self.term_freq: Counter[str] = Counter()
        self.doc_freq: Counter[str] = Counter()
        self.total_docs: int = 0
        self.roger_terms: Counter[str] = Counter()
        self.topic_index: dict[str, list[str]] = defaultdict(list)
        self._loaded = False

    def load(self) -> bool:
        """Load vocabulary from forum JSON posts. Returns True if successful."""
        if self.library_dir is None:
            return False

        posts_dir = self.library_dir / "forums" / "posts"
        if not posts_dir.exists():
            logger.warning("Forum posts directory not found: %s", posts_dir)
            return False

        post_files = list(posts_dir.glob("*.json"))
        if not post_files:
            logger.warning("No post JSON files found in %s", posts_dir)
            return False

        logger.info("Loading vocabulary from %d forum posts...", len(post_files))

        for pf in post_files:
            try:
                data = json.loads(pf.read_text(encoding="utf-8"))
                text = data.get("content_text", "")
                if not text:
                    continue

                self.total_docs += 1
                words = _tokenize(text)
                word_set = set(words)

                for w in words:
                    self.term_freq[w] += 1
                for w in word_set:
                    self.doc_freq[w] += 1

                # Track Roger's vocabulary separately
                author = data.get("author", {})
                display_name = author.get("display_name", "") if isinstance(author, dict) else ""
                if "roger" in display_name.lower() or "deakins" in display_name.lower():
                    for w in words:
                        self.roger_terms[w] += 1

                # Build topic index
                ids = data.get("ids", {})
                topic_slug = ids.get("topic_slug", "")
                forum_slug = ids.get("forum_slug", "")
                if topic_slug and forum_slug:
                    topic_key = f"{forum_slug}__{topic_slug}"
                    for w in word_set:
                        self.topic_index[w].append(topic_key)

            except Exception as e:
                logger.debug("Error loading post %s: %s", pf.name, e)
                continue

        self._loaded = True
        logger.info(
            "Vocabulary loaded: %d docs, %d unique terms, %d Roger-specific terms",
            self.total_docs, len(self.term_freq), len(self.roger_terms),
        )
        return True

    def tfidf(self, term: str) -> float:
        """Calculate TF-IDF score for a term."""
        if not self._loaded or self.total_docs == 0:
            return 0.0
        tf = self.term_freq.get(term, 0)
        df = self.doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        return tf * math.log(self.total_docs / df)

    def find_related_topics(self, terms: list[str], max_results: int = 5) -> list[str]:
        """Find forum topics most related to a set of terms."""
        if not self._loaded:
            return []

        topic_scores: Counter[str] = Counter()
        for t in terms:
            for topic_key in self.topic_index.get(t, []):
                topic_scores[topic_key] += 1

        return [k for k, _ in topic_scores.most_common(max_results)]


# ---------------------------------------------------------------------------
# Topic Tagger
# ---------------------------------------------------------------------------

class TopicTagger:
    """
    Tags transcript segments with cinematography topics and film references.

    Uses a combination of:
    1. Built-in cinematography keyword dictionary
    2. Forum corpus vocabulary (when available)
    3. Film title detection
    """

    def __init__(self, library_dir: Path | None = None, min_confidence: float = 0.3):
        self.min_confidence = min_confidence
        self.vocab = ForumVocabulary(library_dir)
        self._corpus_available = False

        # Pre-compile keyword patterns for each topic
        self._topic_patterns: dict[str, list[re.Pattern[str]]] = {}
        for topic, keywords in CINEMATOGRAPHY_TOPICS.items():
            patterns = []
            for kw in keywords:
                patterns.append(re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE))
            self._topic_patterns[topic] = patterns

        # Pre-compile film patterns
        self._film_patterns: dict[str, list[re.Pattern[str]]] = {}
        for film, keywords in DEAKINS_FILMS.items():
            patterns = []
            for kw in keywords:
                patterns.append(re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE))
            self._film_patterns[film] = patterns

    def load_corpus(self) -> bool:
        """Attempt to load forum corpus for enhanced tagging."""
        self._corpus_available = self.vocab.load()
        return self._corpus_available

    def tag_segment(self, text: str) -> list[TopicMatch]:
        """
        Tag a single transcript segment with relevant topics.

        Returns a list of TopicMatch objects sorted by confidence (descending).
        """
        if not text or len(text.strip()) < 10:
            return []

        matches: list[TopicMatch] = []
        text_lower = text.lower()

        for topic, patterns in self._topic_patterns.items():
            keywords_hit = []
            for pat in patterns:
                if pat.search(text):
                    keywords_hit.append(pat.pattern.replace(r"\b", "").replace("\\", ""))

            if not keywords_hit:
                continue

            # Confidence based on keyword density and variety
            variety_score = min(len(keywords_hit) / 3.0, 1.0)
            density_score = min(len(keywords_hit) / max(len(text_lower.split()), 1) * 10, 1.0)
            confidence = 0.4 * variety_score + 0.6 * density_score

            # Boost if corpus confirms these terms are significant
            if self._corpus_available:
                corpus_boost = sum(self.vocab.tfidf(kw) for kw in keywords_hit) / max(len(keywords_hit), 1)
                corpus_boost = min(corpus_boost / 100.0, 0.3)  # cap at 0.3 boost
                confidence = min(confidence + corpus_boost, 1.0)

            if confidence >= self.min_confidence:
                related = []
                if self._corpus_available:
                    related = self.vocab.find_related_topics(keywords_hit, max_results=3)

                matches.append(TopicMatch(
                    topic=topic,
                    confidence=round(confidence, 3),
                    keywords_matched=sorted(set(keywords_hit)),
                    related_forum_topics=related,
                ))

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches

    def detect_films(self, text: str) -> list[FilmMention]:
        """Detect mentions of Deakins films in text."""
        if not text or len(text.strip()) < 5:
            return []

        mentions: list[FilmMention] = []

        for film, patterns in self._film_patterns.items():
            keywords_hit = []
            for pat in patterns:
                if pat.search(text):
                    keywords_hit.append(pat.pattern.replace(r"\b", "").replace("\\", ""))

            if keywords_hit:
                confidence = min(len(keywords_hit) / 2.0, 1.0)
                mentions.append(FilmMention(
                    film=film,
                    keywords_matched=sorted(set(keywords_hit)),
                    confidence=round(confidence, 3),
                ))

        mentions.sort(key=lambda m: m.confidence, reverse=True)
        return mentions

    def build_episode_summary(
        self,
        segment_topics: list[list[TopicMatch]],
        segment_films: list[list[FilmMention]],
    ) -> dict[str, Any]:
        """
        Build episode-level topic and film summary from per-segment tags.

        Returns a dict with:
        - topics: list of TopicSummary dicts
        - films_mentioned: list of film mention dicts
        """
        # Aggregate topics
        topic_segments: Counter[str] = Counter()
        topic_keywords: dict[str, set[str]] = defaultdict(set)
        topic_forum_refs: dict[str, set[str]] = defaultdict(set)

        for seg_topics in segment_topics:
            for tm in seg_topics:
                topic_segments[tm.topic] += 1
                topic_keywords[tm.topic].update(tm.keywords_matched)
                topic_forum_refs[tm.topic].update(tm.related_forum_topics)

        topics_summary = []
        for topic, count in topic_segments.most_common():
            topics_summary.append(asdict(TopicSummary(
                topic=topic,
                segment_count=count,
                keywords_matched=sorted(topic_keywords[topic]),
                related_forum_topics=sorted(topic_forum_refs[topic]),
            )))

        # Aggregate films
        film_segments: Counter[str] = Counter()
        film_keywords: dict[str, set[str]] = defaultdict(set)

        for seg_films in segment_films:
            for fm in seg_films:
                film_segments[fm.film] += 1
                film_keywords[fm.film].update(fm.keywords_matched)

        films_summary = []
        for film, count in film_segments.most_common():
            films_summary.append({
                "film": film,
                "segment_count": count,
                "keywords_matched": sorted(film_keywords[film]),
            })

        return {
            "topics": topics_summary,
            "films_mentioned": films_summary,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z][a-z0-9'-]*[a-z0-9]|[a-z]", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer for vocabulary building."""
    return [m.group().lower() for m in _WORD_RE.finditer(text)]
