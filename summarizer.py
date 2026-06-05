"""
summarizer.py
=============

Shared, dependency-free text utilities used across the app.

These functions were originally inside app.py. They were moved here in v1.1.0 so
that BOTH the website screener (app.py) and the YouTube channel lookup
(youtube_api.py) can reuse the same extractive summarizer without duplicating
code or creating a circular import.

Public functions:
    extract_visible_text(html) -> str   Strip HTML down to readable text.
    split_sentences(text)      -> list  Naive sentence splitter.
    summarize_text(text, n)    -> str   Extractive summary (top-n sentences).
"""

import re
from html import unescape

# Very common English words we don't want cluttering the summary scoring.
STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "her", "was", "one", "our", "out", "day", "had", "has", "his", "how",
    "man", "new", "now", "old", "see", "two", "way", "who", "boy", "did",
    "its", "let", "put", "say", "she", "too", "use", "this", "that", "with",
    "from", "they", "will", "would", "there", "their", "what", "about",
    "which", "when", "your", "have", "more", "here", "than", "then", "them",
    "these", "some", "into", "only", "other", "such", "also", "been", "were",
}


def extract_visible_text(html: str) -> str:
    """Strip scripts/styles/tags and return collapsed visible text."""
    # Remove the parts of the page that aren't human-readable content.
    html = re.sub(r"<(script|style|noscript|template)[^>]*>.*?</\1>", " ",
                  html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    # Drop all remaining tags, then decode HTML entities.
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    # Collapse runs of whitespace into single spaces.
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list:
    """A simple sentence splitter good enough for summarization."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 0]


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """
    Pick the most representative sentences using simple word-frequency scoring.

    The idea: words that appear often across the text are likely important, so
    sentences containing many of those words are good summary candidates. We
    keep the chosen sentences in their original reading order.
    """
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    # Count how often each meaningful word appears.
    word_frequencies = {}
    for word in re.findall(r"[a-zA-Z]{3,}", text.lower()):
        if word in STOP_WORDS:
            continue
        word_frequencies[word] = word_frequencies.get(word, 0) + 1

    if not word_frequencies:
        return " ".join(sentences[:max_sentences])

    peak = max(word_frequencies.values())

    # Score each sentence; normalize by length to avoid favoring only the
    # longest sentences. Only the first ~30 sentences are considered so we
    # focus on the main content near the top.
    scored = []
    for index, sentence in enumerate(sentences[:30]):
        words = re.findall(r"[a-zA-Z]{3,}", sentence.lower())
        if not (4 <= len(words) <= 60):
            continue
        score = sum(word_frequencies.get(w, 0) for w in words) / (peak * len(words))
        scored.append((score, index, sentence))

    if not scored:
        return " ".join(sentences[:max_sentences])

    # Take the top-scoring sentences, then restore original order.
    top = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    top_in_order = sorted(top, key=lambda item: item[1])
    return " ".join(sentence for _, _, sentence in top_in_order)
