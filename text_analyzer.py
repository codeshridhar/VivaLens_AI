"""
text_analyzer.py — VivaLens AI
Sprint 2 | Agent: PRISM (UI/UX & Speech Engineer)

Pure-Python NLP text analysis module for evaluating viva/presentation answers.
Detects filler words, measures speaking pace, checks keyword coverage,
and computes heuristic clarity & overall scores.

Dependencies: Python standard library only (NLTK is optional and NOT required).
No paid APIs. No external AI services. Fully standalone.
"""

from __future__ import annotations

import re
import math
import sys
from typing import Optional

# Windows consoles default to cp1252, which cannot encode emoji/symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FILLER_PHRASES: list[str] = [
    "you know",
    "i mean",
    "sort of",
    "kind of",
]

FILLER_WORDS: list[str] = [
    "um",
    "uh",
    "like",
    "basically",
    "actually",
    "so",
    "literally",
    "right",
]

# Pace thresholds (words per minute)
PACE_TOO_SLOW: int = 100
PACE_TOO_FAST: int = 160


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_sentences(text: str) -> int:
    """
    Count the number of sentences by splitting on '.', '!', '?'.
    Ignores empty fragments that result from trailing punctuation.
    """
    fragments = re.split(r'[.!?]+', text)
    # Keep only fragments that contain at least one word character
    sentences = [f for f in fragments if re.search(r'\w', f)]
    return max(len(sentences), 1)  # At least 1 if there is any text


def _tokenize(text: str) -> list[str]:
    """
    Simple whitespace + punctuation tokenizer.
    Returns a list of lowercase word tokens.
    """
    return re.findall(r"[a-z0-9']+", text.lower())


def _detect_fillers(text: str) -> tuple[int, list[str]]:
    """
    Detect filler words and phrases in the given text (case-insensitive).

    Returns:
        (total_filler_count, list_of_unique_fillers_found)
    """
    lower_text = text.lower()
    found_fillers: list[str] = []
    total_count = 0

    # --- Multi-word phrases first (so we don't double-count sub-words) ---
    for phrase in FILLER_PHRASES:
        # Use word-boundary regex for exact phrase matching
        pattern = r'\b' + re.escape(phrase) + r'\b'
        matches = re.findall(pattern, lower_text)
        if matches:
            found_fillers.append(phrase)
            total_count += len(matches)

    # --- Single-word fillers ---
    for word in FILLER_WORDS:
        pattern = r'\b' + re.escape(word) + r'\b'
        matches = re.findall(pattern, lower_text)
        if matches:
            found_fillers.append(word)
            total_count += len(matches)

    return total_count, found_fillers


def _check_keyword_coverage(
    text: str,
    expected_keywords: list[str],
) -> tuple[float, list[str], list[str]]:
    """
    Check how many expected keywords appear in the text.

    Matching strategy (case-insensitive, partial token match):
      - A keyword is considered "matched" if it appears as a substring
        of any token in the text, OR if any token is a substring of the
        keyword. This handles plurals, verb forms, etc.

    Returns:
        (coverage_ratio, matched_list, missing_list)
    """
    if not expected_keywords:
        return 1.0, [], []

    tokens = _tokenize(text)
    matched: list[str] = []
    missing: list[str] = []

    for kw in expected_keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue

        is_found = False
        for token in tokens:
            # Partial match: keyword in token OR token in keyword
            if kw_lower in token or token in kw_lower:
                is_found = True
                break

        if is_found:
            matched.append(kw)
        else:
            missing.append(kw)

    coverage = len(matched) / len(expected_keywords)
    return round(coverage, 4), matched, missing


def _compute_clarity_score(
    filler_ratio: float,
    avg_sentence_length: float,
    sentence_count: int,
) -> float:
    """
    Heuristic clarity score on a 0–10 scale.

    Factors:
      - Filler ratio  (lower is better)
      - Avg sentence length (15–25 words is ideal)
      - Sentence count (more structure = better, up to a point)
    """
    score = 7.0  # baseline

    # Filler penalty: up to -4.0
    filler_penalty = min(filler_ratio * 15.0, 4.0)
    score -= filler_penalty

    # Sentence length penalty
    if avg_sentence_length > 35:
        score -= 2.0
    elif avg_sentence_length > 25:
        score -= 1.0
    elif avg_sentence_length < 5:
        score -= 1.5

    # Sentence count bonus / penalty
    if sentence_count >= 4:
        score += 1.0
    elif sentence_count >= 2:
        score += 0.5
    elif sentence_count == 1:
        score -= 1.0

    return round(max(0.0, min(10.0, score)), 2)


def _compute_overall_score(
    keyword_coverage: float,
    clarity_score: float,
    filler_ratio: float,
    pace_verdict: str,
) -> float:
    """
    Combined heuristic overall score on a 0–10 scale.

    Weights:
      - Keyword coverage  : 40%
      - Clarity score      : 30%
      - Filler penalty     : 20%
      - Pace quality       : 10%
    """
    kw_component = keyword_coverage * 10.0          # 0-10
    clarity_component = clarity_score                # 0-10
    filler_component = max(0.0, 10.0 - filler_ratio * 30.0)  # 0-10
    if pace_verdict == "ideal":
        pace_component = 10.0
    elif pace_verdict in ("too slow", "too fast"):
        pace_component = 4.0
    else:  # "unknown"
        pace_component = 6.0

    overall = (
        0.40 * kw_component
        + 0.30 * clarity_component
        + 0.20 * filler_component
        + 0.10 * pace_component
    )
    return round(max(0.0, min(10.0, overall)), 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_text(
    text: str,
    expected_keywords: list[str] | None = None,
    duration_seconds: float | None = None,
) -> dict:
    """
    Analyze a viva/presentation answer transcript.

    Parameters
    ----------
    text : str
        The raw transcript or typed answer to evaluate.
    expected_keywords : list[str] | None
        Keywords the examiner expects in a good answer.
    duration_seconds : float | None
        How long the student spoke (seconds). Used for WPM calculation.

    Returns
    -------
    dict
        Analysis results with all required keys.
    """
    # --- Edge case: empty or whitespace-only text ---
    if not text or not text.strip():
        return {
            "word_count": 0,
            "sentence_count": 0,
            "filler_count": 0,
            "filler_words_found": [],
            "filler_ratio": 0.0,
            "speaking_pace_wpm": None,
            "pace_verdict": "unknown",
            "keyword_coverage": 0.0,
            "keywords_matched": [],
            "keywords_missing": expected_keywords or [],
            "avg_sentence_length": 0.0,
            "clarity_score": 0.0,
            "overall_text_score": 0.0,
        }

    # --- Basic counts ---
    tokens = _tokenize(text)
    word_count = len(tokens)
    sentence_count = _count_sentences(text)

    # --- Filler detection ---
    filler_count, filler_words_found = _detect_fillers(text)
    filler_ratio = round(filler_count / word_count, 4) if word_count > 0 else 0.0

    # --- Speaking pace ---
    speaking_pace_wpm: float | None = None
    pace_verdict = "unknown"
    if duration_seconds is not None and duration_seconds > 0:
        speaking_pace_wpm = round((word_count / duration_seconds) * 60.0, 2)
        if speaking_pace_wpm < PACE_TOO_SLOW:
            pace_verdict = "too slow"
        elif speaking_pace_wpm <= PACE_TOO_FAST:
            pace_verdict = "ideal"
        else:
            pace_verdict = "too fast"

    # --- Keyword coverage ---
    keyword_coverage, keywords_matched, keywords_missing = _check_keyword_coverage(
        text, expected_keywords or []
    )

    # --- Sentence-level stats ---
    avg_sentence_length = round(word_count / sentence_count, 2) if sentence_count > 0 else 0.0

    # --- Heuristic scores ---
    clarity_score = _compute_clarity_score(filler_ratio, avg_sentence_length, sentence_count)
    overall_text_score = _compute_overall_score(
        keyword_coverage, clarity_score, filler_ratio, pace_verdict
    )

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "filler_count": filler_count,
        "filler_words_found": filler_words_found,
        "filler_ratio": filler_ratio,
        "speaking_pace_wpm": speaking_pace_wpm,
        "pace_verdict": pace_verdict,
        "keyword_coverage": keyword_coverage,
        "keywords_matched": keywords_matched,
        "keywords_missing": keywords_missing,
        "avg_sentence_length": avg_sentence_length,
        "clarity_score": clarity_score,
        "overall_text_score": overall_text_score,
    }


def quick_summary(analysis_result: dict) -> str:
    """
    Generate a 2–3 line human-readable summary of the analysis.

    Parameters
    ----------
    analysis_result : dict
        The dict returned by `analyze_text()`.

    Returns
    -------
    str
        A concise, student-friendly summary.
    """
    wc = analysis_result.get("word_count", 0)
    score = analysis_result.get("overall_text_score", 0.0)
    fillers = analysis_result.get("filler_count", 0)
    kw_cov = analysis_result.get("keyword_coverage", 0.0)
    pace = analysis_result.get("pace_verdict", "unknown")

    lines = [
        f"📝 Answer length: {wc} words | Overall score: {score}/10.",
    ]

    if fillers > 0:
        lines.append(
            f"⚠️  {fillers} filler word(s) detected — try to reduce "
            f"'um', 'like', 'basically' for a stronger delivery."
        )
    else:
        lines.append("✅ No filler words detected — clean delivery!")

    if kw_cov < 1.0 and analysis_result.get("keywords_missing"):
        missing = ", ".join(analysis_result["keywords_missing"][:5])
        lines.append(
            f"🔑 Keyword coverage {kw_cov:.0%}. Missing: {missing}."
        )

    if pace != "unknown":
        wpm = analysis_result.get("speaking_pace_wpm", 0)
        lines.append(f"🎙️  Pace: {wpm} WPM ({pace}).")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    EXPECTED_KW = [
        "machine learning", "neural network", "backpropagation",
        "gradient", "overfitting", "training", "dataset",
    ]

    # ---- Test A: Strong, clean answer ----
    strong_answer = (
        "Machine learning is a subset of artificial intelligence where "
        "models learn patterns from a training dataset. A neural network "
        "is one such model, composed of layers of nodes. During training, "
        "backpropagation computes the gradient of the loss function and "
        "updates weights to minimize error. To prevent overfitting, we use "
        "techniques like regularization and cross-validation on the dataset."
    )

    # ---- Test B: Short, filler-heavy answer ----
    filler_answer = (
        "Um, so basically, like, machine learning is, uh, you know, "
        "when the computer, like, learns stuff, right? So, um, it's "
        "basically like, training, I mean, sort of, with data, uh, "
        "and stuff like that, you know."
    )

    # ---- Test C: Long, rambling answer ----
    rambling_answer = (
        "Okay so basically machine learning is a very broad field and "
        "it actually encompasses a lot of different techniques and "
        "methodologies that are used in practice. So when we talk about "
        "neural networks, which are like a specific type of model, they "
        "use backpropagation to, you know, update the weights during the "
        "training process. And the gradient is computed using the chain "
        "rule of calculus, which is actually really interesting if you "
        "think about it. But then there's also the issue of overfitting, "
        "which is when the model basically memorizes the training dataset "
        "instead of learning generalizable patterns, so you need to be "
        "careful about that. And there are like many other things to "
        "consider as well, such as the architecture of the neural network "
        "and the choice of activation functions and the learning rate and "
        "so on and so forth. Um, I think that covers most of the important "
        "points about machine learning and neural networks in general."
    )

    print("=" * 60)
    print("  VivaLens AI — text_analyzer.py Test Suite")
    print("=" * 60)

    for label, answer, duration in [
        ("A) Strong Clean Answer", strong_answer, 30.0),
        ("B) Short Filler-Heavy Answer", filler_answer, 20.0),
        ("C) Long Rambling Answer", rambling_answer, 60.0),
    ]:
        result = analyze_text(answer, EXPECTED_KW, duration)
        print(f"\n--- {label} ---")
        for key, value in result.items():
            print(f"  {key:25s}: {value}")
        print(f"\n  Summary:\n{quick_summary(result)}")
        print("-" * 60)