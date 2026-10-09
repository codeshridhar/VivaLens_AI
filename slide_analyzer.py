"""
slide_analyzer.py — VivaLens AI
================================
Presentation & Slide Analyzer for PPTX and PDF files.

Evaluates presentation slides on content density, structure,
visual balance, title coverage, and topic keyword relevance.

All scoring heuristics are hand-coded. No external AI APIs used.

Dependencies (optional, gracefully handled if missing):
  - python-pptx  (for .pptx files)
  - PyPDF2       (for .pdf files)

Changelog:
  v1.0 - Initial implementation
  v1.1 - Fixed total_slides count and title_coverage_pct calculation.
         Title detection now explicitly checks slide.shapes.title.
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import Optional

# Windows consoles default to cp1252, which cannot encode emoji/symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
#  GRACEFUL IMPORTS — never crash if a library is missing
# ---------------------------------------------------------------------------

try:
    from pptx import Presentation as PptxPresentation
    from pptx.util import Inches, Pt
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

try:
    from PyPDF2 import PdfReader
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


# ---------------------------------------------------------------------------
#  CONSTANTS & THRESHOLDS
# ---------------------------------------------------------------------------

IDEAL_WORDS_MIN = 20
IDEAL_WORDS_MAX = 50
OVERLOAD_THRESHOLD = 80
UNDERLOAD_THRESHOLD = 10
MAX_BULLET_WORDS = 15
AVG_READING_WPS = 3.5
BULLET_CHARS = ("•", "·", "–", "-", "▪", "►", "○", "●", "■", "□", "‣")


# ---------------------------------------------------------------------------
#  KNOWLEDGE BASE HELPER
# ---------------------------------------------------------------------------

def _load_topic_keywords(topic: str) -> list[str]:
    """
    Load expected keywords for a given topic from knowledge_base.json.

    Args:
        topic: Topic name (e.g., "Artificial Intelligence").

    Returns:
        List of lowercase expected keywords, or empty list if
        topic not found or KB unavailable.
    """
    kb_path = Path(__file__).parent / "knowledge_base.json"
    if not kb_path.exists():
        return []

    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    topics_db = kb.get("topics", {})
    for t_name, t_data in topics_db.items():
        if topic.lower() in t_name.lower() or t_name.lower() in topic.lower():
            return [kw.lower() for kw in t_data.get("expected_keywords", [])]

    return []


# ---------------------------------------------------------------------------
#  TEXT ANALYSIS HELPERS
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    """Count words in a text string."""
    if not text or not text.strip():
        return 0
    return len(text.split())


def _count_bullets(text: str) -> int:
    """Count bullet points by detecting bullet chars and numbered lists."""
    if not text or not text.strip():
        return 0

    count = 0
    for line in text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(BULLET_CHARS):
            count += 1
        elif re.match(r"^\d+[\.\)]\s", stripped):
            count += 1
        elif re.match(r"^[a-zA-Z][\.\)]\s", stripped):
            count += 1
    return count


def _detect_title_heuristic(text: str) -> str:
    """
    Heuristic title detection: first short non-bullet line.

    Args:
        text: Full text of the slide.

    Returns:
        Detected title string, or empty string if none found.
    """
    if not text or not text.strip():
        return ""

    for line in text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(BULLET_CHARS):
            continue
        words = stripped.split()
        if len(words) <= 12:
            return stripped
        break

    return ""


def _estimate_reading_time(word_count: int) -> float:
    """Estimate reading time in seconds."""
    return round(word_count / AVG_READING_WPS, 1)


def _compute_readability(word_count: int, bullet_count: int) -> str:
    """Compute readability heuristic based on avg words per bullet."""
    if bullet_count == 0:
        return "Good" if word_count <= IDEAL_WORDS_MAX else "Dense"

    avg_words_per_bullet = word_count / bullet_count
    if avg_words_per_bullet <= MAX_BULLET_WORDS:
        return "Good"
    elif avg_words_per_bullet <= 25:
        return "Dense"
    else:
        return "Very Dense"


# ---------------------------------------------------------------------------
#  FILE PARSERS
# ---------------------------------------------------------------------------

def _parse_pptx(file_path: str) -> list[dict]:
    """
    Parse a .pptx file and extract per-slide text data.

    [FIX v1.1] Title detection now explicitly checks slide.shapes.title
    and its .text property. total_slides is guaranteed to equal
    len(prs.slides) by iterating with enumerate over prs.slides directly.

    Args:
        file_path: Absolute or relative path to the PPTX file.

    Returns:
        List of dicts, one per slide:
            { "slide_no": int, "title": str, "full_text": str,
              "bullet_count": int, "has_image": bool }

    Raises:
        ImportError: If python-pptx is not installed.
        FileNotFoundError: If the file doesn't exist.
        Exception: If the file is corrupted or unreadable.
    """
    if not HAS_PPTX:
        raise ImportError(
            "python-pptx is not installed. "
            "Install it with: pip install python-pptx"
        )

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    prs = PptxPresentation(file_path)
    slides_data: list[dict] = []

    # [FIX] Use enumerate directly on prs.slides to guarantee
    # total_slides == len(prs.slides). No filtering, no skipping.
    for idx, slide in enumerate(prs.slides, start=1):
        title_text = ""
        body_lines: list[str] = []
        has_image = False

        # ---------------------------------------------------------------
        # [FIX] STEP 1: Explicitly extract the title from the slide's
        # built-in title shape (slide.shapes.title). This is the most
        # reliable way to detect titles in python-pptx.
        # ---------------------------------------------------------------
        title_shape = slide.shapes.title  # Returns None if no title placeholder
        if title_shape is not None and title_shape.has_text_frame:
            raw_title = title_shape.text_frame.text.strip()
            if raw_title:  # [FIX] Only count as title if text is non-empty
                title_text = raw_title

        # ---------------------------------------------------------------
        # [FIX] STEP 2: Iterate all shapes for body text and images.
        # Skip the title shape to avoid double-counting its text.
        # ---------------------------------------------------------------
        title_shape_id = title_shape.shape_id if title_shape else -1

        for shape in slide.shapes:
            # Skip the title shape — already extracted above
            if shape.shape_id == title_shape_id:
                continue

            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        body_lines.append(text)

            # Detect images (shape_type 13 = MSO_SHAPE_TYPE.PICTURE)
            if shape.shape_type == 13:
                has_image = True

        # Build full text for analysis
        full_text = title_text + "\n" + "\n".join(body_lines)
        bullet_count = _count_bullets(full_text)

        # [FIX] STEP 3: If no title was found from the title shape,
        # fall back to heuristic detection from body text.
        if not title_text:
            title_text = _detect_title_heuristic(full_text)

        slides_data.append({
            "slide_no": idx,
            "title": title_text,
            "full_text": full_text,
            "bullet_count": bullet_count,
            "has_image": has_image,
        })

    # [FIX] Sanity check: ensure we captured all slides
    assert len(slides_data) == len(prs.slides), (
        f"Slide count mismatch: parsed {len(slides_data)} "
        f"but prs.slides has {len(prs.slides)}"
    )

    return slides_data


def _parse_pdf(file_path: str) -> list[dict]:
    """
    Parse a .pdf file and extract per-page text data.
    Each page is treated as one "slide".

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        List of dicts, one per page.

    Raises:
        ImportError: If PyPDF2 is not installed.
        FileNotFoundError: If the file doesn't exist.
    """
    if not HAS_PDF:
        raise ImportError(
            "PyPDF2 is not installed. "
            "Install it with: pip install PyPDF2"
        )

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    reader = PdfReader(file_path)
    slides_data: list[dict] = []

    for idx, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""

        title_text = _detect_title_heuristic(raw_text)
        bullet_count = _count_bullets(raw_text)

        slides_data.append({
            "slide_no": idx,
            "title": title_text,
            "full_text": raw_text,
            "bullet_count": bullet_count,
            "has_image": False,
        })

    return slides_data


# ---------------------------------------------------------------------------
#  CORE SCORING ENGINE
# ---------------------------------------------------------------------------

def _score_slides(
    slides_data: list[dict],
    topic: Optional[str] = None
) -> dict:
    """
    Compute all metrics and the overall presentation score.

    [FIX v1.1] title_coverage_pct now correctly counts slides where
    the "title" field is non-empty (after explicit title-shape check
    and heuristic fallback).

    Args:
        slides_data: List of slide dicts from parser or mock data.
        topic: Optional topic name for keyword relevance scoring.

    Returns:
        Full result dictionary matching the analyze_presentation() spec.
    """
    total_slides = len(slides_data)

    if total_slides == 0:
        return {
            "file_name": "N/A",
            "file_type": "unknown",
            "total_slides": 0,
            "overall_score": 0.0,
            "verdict": "Needs Improvement",
            "avg_words_per_slide": 0.0,
            "title_coverage_pct": 0.0,
            "overloaded_slides": [],
            "strengths": [],
            "weaknesses": ["Presentation contains no slides."],
            "recommendations": ["Add content slides to your presentation."],
            "slide_details": [],
        }

    # =====================================================================
    #  PER-SLIDE METRICS
    # =====================================================================
    slide_details: list[dict] = []
    total_words = 0
    slides_with_titles = 0
    overloaded_slides: list[int] = []
    all_text_combined = ""

    for sd in slides_data:
        wc = _count_words(sd.get("full_text", ""))
        bc = sd.get("bullet_count", 0)
        title = sd.get("title", "")
        slide_no = sd.get("slide_no", 0)

        total_words += wc
        all_text_combined += " " + sd.get("full_text", "")

        # [FIX] Explicit check: title exists AND is non-empty after strip
        if title and title.strip():
            slides_with_titles += 1

        is_overloaded = wc > OVERLOAD_THRESHOLD
        if is_overloaded:
            overloaded_slides.append(slide_no)

        reading_time = _estimate_reading_time(wc)
        readability = _compute_readability(wc, bc)

        slide_details.append({
            "slide_no": slide_no,
            "title": title if title else "(No title)",
            "word_count": wc,
            "bullet_count": bc,
            "reading_time_sec": reading_time,
            "readability": readability,
            "is_overloaded": is_overloaded,
        })

    # =====================================================================
    #  GLOBAL METRICS
    # =====================================================================
    avg_words = round(total_words / total_slides, 1)

    # [FIX] Correct percentage calculation: (count / total) * 100
    # Both numerator and denominator are guaranteed correct now.
    title_coverage = round((slides_with_titles / total_slides) * 100.0, 1)

    # =====================================================================
    #  SCORING (hand-coded heuristic, 0–10 scale)
    # =====================================================================
    score = 5.0
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []

    # --- 1. Word Density Score ---
    if IDEAL_WORDS_MIN <= avg_words <= IDEAL_WORDS_MAX:
        score += 1.5
        strengths.append(
            f"Good content density: avg {avg_words} words/slide "
            f"(ideal: {IDEAL_WORDS_MIN}–{IDEAL_WORDS_MAX})."
        )
    elif avg_words < UNDERLOAD_THRESHOLD:
        score -= 1.5
        weaknesses.append(
            f"Slides are too sparse: avg {avg_words} words/slide."
        )
        recommendations.append(
            "Add more explanatory text or speaker notes to each slide."
        )
    elif avg_words < IDEAL_WORDS_MIN:
        score -= 0.5
        weaknesses.append(
            f"Content slightly thin: avg {avg_words} words/slide."
        )
        recommendations.append(
            "Consider adding 1–2 more bullet points per slide."
        )
    elif avg_words <= OVERLOAD_THRESHOLD:
        score -= 0.5
        weaknesses.append(
            f"Slides slightly dense: avg {avg_words} words/slide."
        )
        recommendations.append(
            "Trim some text; aim for 20–50 words per slide."
        )
    else:
        score -= 2.0
        weaknesses.append(
            f"Slides severely overcrowded: avg {avg_words} words/slide."
        )
        recommendations.append(
            "Split dense slides into multiple slides. "
            "Use the 6×6 rule: max 6 bullets, 6 words each."
        )

    # --- 2. Title Coverage Score ---
    if title_coverage >= 90.0:
        score += 1.0
        strengths.append(
            f"Excellent title coverage: {title_coverage}% of slides "
            "have clear headings."
        )
    elif title_coverage >= 70.0:
        score += 0.5
        strengths.append(f"Good title coverage: {title_coverage}%.")
    elif title_coverage >= 50.0:
        score -= 0.3
        weaknesses.append(
            f"Only {title_coverage}% of slides have titles."
        )
        recommendations.append("Every slide should have a descriptive title.")
    else:
        score -= 1.0
        weaknesses.append(
            f"Poor title coverage: only {title_coverage}%."
        )
        recommendations.append("Add a clear, concise title to every slide.")

    # --- 3. Overload Penalty ---
    overload_penalty = min(len(overloaded_slides) * 0.3, 2.0)
    score -= overload_penalty
    if overloaded_slides:
        slide_nums = ", ".join(str(s) for s in overloaded_slides[:10])
        weaknesses.append(
            f"{len(overloaded_slides)} slide(s) exceed "
            f"{OVERLOAD_THRESHOLD}-word density limit "
            f"(slide(s): {slide_nums})."
        )
        recommendations.append(
            "Break overloaded slides into 2–3 focused sub-slides."
        )

    # --- 4. Slide Count Sanity ---
    if total_slides < 3:
        score -= 0.5
        weaknesses.append(
            f"Very few slides ({total_slides}). "
            "A presentation typically needs at least 5–8 slides."
        )
        recommendations.append(
            "Add an introduction, content, and conclusion slide."
        )
    elif total_slides > 30:
        score -= 0.5
        weaknesses.append(
            f"Too many slides ({total_slides})."
        )
        recommendations.append(
            "Consolidate related slides; aim for 10–20 slides."
        )
    else:
        strengths.append(f"Reasonable slide count ({total_slides} slides).")

    # --- 5. Readability Check ---
    dense_slides = [
        sd["slide_no"] for sd in slide_details
        if sd.get("readability") in ("Dense", "Very Dense")
    ]
    if len(dense_slides) > total_slides * 0.4:
        score -= 0.5
        weaknesses.append(
            "Many slides have dense bullet points."
        )
        recommendations.append(
            f"Aim for ≤{MAX_BULLET_WORDS} words per bullet point."
        )
    elif not dense_slides:
        strengths.append("Bullet points are concise and readable.")

    # --- 6. Topic Keyword Relevance ---
    if topic:
        expected_kw = _load_topic_keywords(topic)
        if expected_kw:
            all_lower = all_text_combined.lower()
            matched = [kw for kw in expected_kw if kw in all_lower]
            ratio = len(matched) / len(expected_kw) if expected_kw else 0

            if ratio >= 0.3:
                bonus = min(ratio * 2.0, 1.5)
                score += bonus
                strengths.append(
                    f"Good topic relevance: {len(matched)}/{len(expected_kw)} "
                    f"expected '{topic}' keywords found."
                )
            elif ratio >= 0.1:
                score += 0.3
                weaknesses.append(
                    f"Moderate topic relevance: only {len(matched)} "
                    f"'{topic}' keywords detected."
                )
                recommendations.append(
                    f"Include more '{topic}' terminology."
                )
            else:
                weaknesses.append(
                    f"Low topic relevance for '{topic}'."
                )
                recommendations.append(
                    f"Ensure key '{topic}' terms appear on slides."
                )

    # =====================================================================
    #  CLAMP & VERDICT
    # =====================================================================
    score = max(0.0, min(10.0, round(score, 2)))

    if score >= 8.5:
        verdict = "Excellent"
    elif score >= 7.0:
        verdict = "Good"
    elif score >= 5.0:
        verdict = "Average"
    elif score >= 3.0:
        verdict = "Needs Improvement"
    else:
        verdict = "Overcrowded" if overloaded_slides else "Poor"

    if not strengths:
        strengths.append("Presentation has basic structure.")
    if not recommendations:
        recommendations.append(
            "Practice your delivery to complement the slide content."
        )

    return {
        "file_name": "N/A",
        "file_type": "unknown",
        "total_slides": total_slides,
        "overall_score": score,
        "verdict": verdict,
        "avg_words_per_slide": avg_words,
        "title_coverage_pct": title_coverage,
        "overloaded_slides": overloaded_slides,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "slide_details": slide_details,
    }


# ---------------------------------------------------------------------------
#  MAIN PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def analyze_presentation(
    file_path: str,
    topic: Optional[str] = None
) -> dict:
    """
    Analyze a presentation file (PPTX or PDF) and return a comprehensive
    evaluation report.

    Args:
        file_path: Path to the .pptx or .pdf file.
        topic:     Optional topic name for keyword relevance scoring.

    Returns:
        dict with all required keys as per project specification.
    """
    file_name = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pptx":
        file_type = "pptx"
        try:
            slides_data = _parse_pptx(file_path)
        except ImportError as e:
            return _error_result(file_name, file_type, str(e))
        except Exception as e:
            return _error_result(file_name, file_type, f"PPTX parse error: {e}")

    elif ext == ".pdf":
        file_type = "pdf"
        try:
            slides_data = _parse_pdf(file_path)
        except ImportError as e:
            return _error_result(file_name, file_type, str(e))
        except Exception as e:
            return _error_result(file_name, file_type, f"PDF parse error: {e}")

    else:
        file_type = "unknown"
        return _error_result(
            file_name, file_type,
            f"Unsupported file format '{ext}'. Use .pptx or .pdf."
        )

    result = _score_slides(slides_data, topic)
    result["file_name"] = file_name
    result["file_type"] = file_type

    return result


def _error_result(file_name: str, file_type: str, error_msg: str) -> dict:
    """Return a standardized error result when parsing fails."""
    return {
        "file_name": file_name,
        "file_type": file_type,
        "total_slides": 0,
        "overall_score": 0.0,
        "verdict": "Needs Improvement",
        "avg_words_per_slide": 0.0,
        "title_coverage_pct": 0.0,
        "overloaded_slides": [],
        "strengths": [],
        "weaknesses": [error_msg],
        "recommendations": [
            "Ensure the file is valid and the required library is installed."
        ],
        "slide_details": [],
    }


# ---------------------------------------------------------------------------
#  SELF-TESTS
# ---------------------------------------------------------------------------

def test_slide_analyzer() -> None:
    """
    Self-contained mock test — no physical file required.
    Run: python slide_analyzer.py
    """
    print("=" * 70)
    print("  VivaLens AI — Slide Analyzer Test Suite (v1.1)")
    print("=" * 70)

    # ---- TEST 1: Good AI Presentation ----
    print("\n--- TEST 1: Good AI Presentation (6 slides, all titled) ---")
    good_slides = [
        {
            "slide_no": 1,
            "title": "Introduction to Artificial Intelligence",
            "full_text": (
                "Introduction to Artificial Intelligence\n"
                "• AI is defined as the simulation of human intelligence\n"
                "• Covers search, logic, planning, and learning\n"
                "• Goal: build rational agents"
            ),
            "bullet_count": 3, "has_image": False,
        },
        {
            "slide_no": 2,
            "title": "Search Algorithms",
            "full_text": (
                "Search Algorithms\n"
                "• BFS explores level by level using a queue\n"
                "• DFS goes deep using a stack\n"
                "• A* uses heuristic h(n) + path cost g(n)\n"
                "• A* is optimal when heuristic is admissible"
            ),
            "bullet_count": 4, "has_image": True,
        },
        {
            "slide_no": 3,
            "title": "Constraint Satisfaction Problems",
            "full_text": (
                "Constraint Satisfaction Problems\n"
                "• CSP consists of variables, domains, and constraints\n"
                "• Backtracking search with constraint propagation\n"
                "• Arc consistency reduces domain sizes\n"
                "• Example: map coloring, Sudoku"
            ),
            "bullet_count": 4, "has_image": False,
        },
        {
            "slide_no": 4,
            "title": "Knowledge Representation & Logic",
            "full_text": (
                "Knowledge Representation & Logic\n"
                "• Propositional logic uses boolean variables\n"
                "• First-order logic adds predicates and quantifiers\n"
                "• Inference via forward and backward chaining\n"
                "• Resolution and unification for theorem proving"
            ),
            "bullet_count": 4, "has_image": False,
        },
        {
            "slide_no": 5,
            "title": "Planning with STRIPS",
            "full_text": (
                "Planning with STRIPS\n"
                "• STRIPS: preconditions, add list, delete list\n"
                "• Goal stack planning decomposes into subgoals\n"
                "• State space search finds valid action sequences"
            ),
            "bullet_count": 3, "has_image": True,
        },
        {
            "slide_no": 6,
            "title": "Conclusion",
            "full_text": (
                "Conclusion\n"
                "• AI combines search, logic, and planning\n"
                "• Real-world applications: robotics, NLP, vision\n"
                "• Thank you! Questions?"
            ),
            "bullet_count": 3, "has_image": False,
        },
    ]

    result1 = _score_slides(good_slides, topic="Artificial Intelligence")
    result1["file_name"] = "mock_good_ai.pptx"
    result1["file_type"] = "pptx"
    _print_report(result1)

    # [FIX] Verify title coverage is 100% for all-titled presentation
    assert result1["title_coverage_pct"] == 100.0, (
        f"Expected 100.0% title coverage, got {result1['title_coverage_pct']}%"
    )
    assert result1["total_slides"] == 6, (
        f"Expected 6 slides, got {result1['total_slides']}"
    )
    print("  ✅ ASSERTION PASSED: total_slides=6, title_coverage=100.0%")

    # ---- TEST 2: Overcrowded, no titles ----
    print("\n--- TEST 2: Overcrowded, No Titles (3 slides) ---")
    bad_slides = [
        {
            "slide_no": 1, "title": "",
            "full_text": (
                "Operating systems are software that manage computer "
                "hardware and software resources and provide common "
                "services for computer programs. The operating system "
                "acts as an intermediary between programs and the "
                "computer hardware. Major functions include process "
                "management, memory management, file system management, "
                "device management, security, and networking. Examples "
                "of operating systems include Windows, Linux, macOS, "
                "Android, and iOS. Process management involves creating, "
                "scheduling, and terminating processes."
            ),
            "bullet_count": 0, "has_image": False,
        },
        {
            "slide_no": 2, "title": "",
            "full_text": (
                "CPU scheduling algorithms determine the order in which "
                "processes are executed. FCFS is the simplest algorithm "
                "where processes are executed in arrival order. SJF "
                "selects the process with the shortest burst time. "
                "Round Robin assigns a time quantum to each process "
                "in a circular fashion. Priority scheduling assigns "
                "priorities to processes. Multilevel queue scheduling "
                "divides the ready queue into multiple queues."
            ),
            "bullet_count": 0, "has_image": False,
        },
        {
            "slide_no": 3, "title": "Summary",
            "full_text": (
                "Summary\n"
                "• OS manages resources\n"
                "• Scheduling, memory, deadlocks are key topics"
            ),
            "bullet_count": 2, "has_image": False,
        },
    ]

    result2 = _score_slides(bad_slides, topic="Operating Systems")
    result2["file_name"] = "mock_bad_os.pptx"
    result2["file_type"] = "pptx"
    _print_report(result2)

    # [FIX] Verify: only 1 of 3 slides has a title → 33.3%
    assert result2["total_slides"] == 3
    assert result2["title_coverage_pct"] == 33.3, (
        f"Expected 33.3%, got {result2['title_coverage_pct']}%"
    )
    print("  ✅ ASSERTION PASSED: total_slides=3, title_coverage=33.3%")

    # ---- TEST 3: Empty ----
    print("\n--- TEST 3: Empty Presentation ---")
    result3 = _score_slides([], topic=None)
    result3["file_name"] = "mock_empty.pptx"
    result3["file_type"] = "pptx"
    _print_report(result3)

    # ---- TEST 4: Unsupported ----
    print("\n--- TEST 4: Unsupported File Type ---")
    result4 = analyze_presentation("fake_file.docx", topic="Data Structures")
    _print_report(result4)

    print("\n" + "=" * 70)
    print("  All slide analyzer tests completed successfully.")
    print("=" * 70)


def _print_report(result: dict) -> None:
    """Pretty-print a slide analysis report."""
    print(f"  File      : {result['file_name']} ({result['file_type']})")
    print(f"  Slides    : {result['total_slides']}")
    print(f"  Score     : {result['overall_score']}/10  [{result['verdict']}]")
    print(f"  Avg Words : {result['avg_words_per_slide']} words/slide")
    print(f"  Titles    : {result['title_coverage_pct']}% coverage")
    print(f"  Overloaded: {result['overloaded_slides'] or 'None'}")
    print(f"  Strengths :")
    for s in result["strengths"]:
        print(f"    ✅ {s}")
    print(f"  Weaknesses:")
    for w in result["weaknesses"]:
        print(f"    ⚠️  {w}")
    print(f"  Recommendations:")
    for r in result["recommendations"]:
        print(f"    💡 {r}")
    if result["slide_details"]:
        print(f"  Slide Breakdown:")
        for sd in result["slide_details"]:
            flag = " 🔴" if sd.get("is_overloaded") else ""
            print(
                f"    Slide {sd['slide_no']:2d}: "
                f"{sd['word_count']:3d} words, "
                f"{sd['bullet_count']:2d} bullets, "
                f"{sd.get('readability', 'N/A'):>10s}"
                f"{flag}  \"{sd['title'][:40]}\""
            )


# ---------------------------------------------------------------------------
#  ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_slide_analyzer()