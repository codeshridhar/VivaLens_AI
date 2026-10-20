"""
slide_analyzer.py — VivaLens AI
=================================
Presentation & Slide Analyzer for PPTX and PDF files.

Evaluates presentation decks on nine measurable dimensions:
  content density, deck structure, typography, layout integrity,
  visual support, bullet quality, topic relevance and delivery timing.

Every score is produced by hand-coded heuristics over data extracted
directly from the file (shape geometry, run-level font sizes, notes,
tables and charts). No external AI service is involved.

Dependencies (optional, handled gracefully if missing):
  - python-pptx  (for .pptx files)
  - PyPDF2       (for .pdf files)
"""

from __future__ import annotations

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

EMU_PER_INCH = 914400

IDEAL_WORDS_MIN = 20
IDEAL_WORDS_MAX = 50
OVERLOAD_THRESHOLD = 80
UNDERLOAD_THRESHOLD = 10
MAX_BULLET_WORDS = 15

MIN_READABLE_FONT_PT = 14.0
IDEAL_BODY_FONT_PT = 18.0
MIN_TITLE_FONT_PT = 24.0

SPEAKING_WPM = 130            # assumed oral delivery speed
DEFAULT_TARGET_MINUTES = 10

BULLET_CHARS = ("•", "·", "–", "-", "▪", "►", "○", "●", "■", "□", "‣")

TOPIC_ALIASES = {
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "dsa": "Data Structures",
    "data structures": "Data Structures",
    "dbms": "Database Management",
    "database management": "Database Management",
    "os": "Operating Systems",
    "operating systems": "Operating Systems",
    "cn": "Computer Networks",
    "computer networks": "Computer Networks",
}

AGENDA_WORDS = ("agenda", "contents", "outline", "roadmap", "overview of")
CONCLUSION_WORDS = ("conclusion", "summary", "wrap up", "wrap-up",
                    "thank you", "references", "q&a", "questions")


# ---------------------------------------------------------------------------
#  SMALL TEXT UTILITIES
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


def _split_bullets(text: str) -> list[str]:
    """Return the individual bullet/paragraph lines of a text block."""
    if not text or not text.strip():
        return []

    bullets: list[str] = []
    for line in text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if (stripped.startswith(BULLET_CHARS)
                or re.match(r"^\d+[\.\)]\s", stripped)
                or re.match(r"^[a-zA-Z][\.\)]\s", stripped)):
            bullets.append(stripped)
    return bullets


def _strip_bullet_marker(line: str) -> str:
    """Remove a leading bullet/number marker from a line."""
    stripped = line.strip()
    stripped = re.sub(r"^[•·–▪►○●■□‣\-*]\s*", "", stripped)
    stripped = re.sub(r"^\d+[\.\)]\s*", "", stripped)
    return stripped.strip()


VERB_FORMS = frozenset({
    "achieves", "adds", "allows", "analyzes", "applies", "approaches", "assumes",
    "avoids", "balances", "beats", "begins", "benefits", "builds", "calculates",
    "checks", "chooses", "combines", "compares", "compares", "completes",
    "computes", "contains", "converges", "creates", "defines", "delivers",
    "demonstrates", "depends", "describes", "detects", "determines", "develops",
    "distinguishes", "drives", "evaluates", "expands", "explains", "explores",
    "extends", "finds", "follows", "forms", "generates", "guarantees", "guides",
    "handles", "helps", "identifies", "improves", "includes", "increases",
    "influences", "introduces", "involves", "keeps", "limits", "makes", "manages",
    "means", "measures", "minimizes", "maximizes", "models", "needs", "obtains",
    "operates", "optimizes", "outperforms", "performs", "permits", "prevents",
    "produces", "prunes", "provides", "raises", "reduces", "refines", "relies",
    "removes", "requires", "represents", "resolves", "returns", "reveals",
    "scales", "searches", "selects", "separates", "shows", "solves", "splits",
    "stores", "supports", "suggests", "supplies", "supports", "terminates",
    "tests", "tracks", "uses", "validates", "works", "improves", "increases",
    "expands", "computes", "defines", "describes", "discusses", "evaluates",
    "explains", "examines", "exploits", "extracts", "formulates", "gains",
    "guarantees", "improves", "includes", "indicates", "integrates", "interprets",
    "introduces", "justifies", "maintains", "modifies", "monitors", "obtains",
    "optimizes", "organizes", "perceives", "predicts", "prepares", "preserves",
    "prevents", "processes", "produces", "provides", "reaches", "reduces",
    "recognizes", "records", "reduces", "relates", "remains", "requires",
    "responds", "restores", "retrieves", "reuses", "satisfies", "scores",
    "selects", "separates", "simplifies", "solves", "specifies", "stores",
    "strengthens", "studies", "summarizes", "supports", "supplies", "targets",
    "tracks", "transforms", "updates", "validates", "yields",
})


def _is_fragment(text: str) -> bool:
    """
    Heuristic: a bullet is a "fragment" if it reads as a noun phrase.

    Detects the classic slide-writing mistake of turning a sentence into
    a label ("Machine learning applications" instead of "Machine learning
    improves prediction accuracy").
    """
    words = _strip_bullet_marker(text).split()
    if len(words) < 3:
        return True

    for word in words:
        token = word.lower().strip(".,:;!?()[]'\"")
        if not token:
            continue
        if token in VERB_FORMS:
            return False
        if len(token) > 5 and token.endswith("ing"):
            return False
        if len(token) > 4 and token.endswith("ed"):
            return False

    return True


def _detect_title_heuristic(text: str) -> str:
    """Heuristic title detection: first short non-bullet line."""
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
    """Estimate on-screen reading time in seconds (not spoken time)."""
    return round(word_count / 3.5, 1)


def _compute_readability(word_count: int, bullet_count: int) -> str:
    """Compute readability heuristic based on avg words per bullet."""
    if bullet_count == 0:
        return "Good" if word_count <= IDEAL_WORDS_MAX else "Dense"

    avg_words_per_bullet = word_count / bullet_count
    if avg_words_per_bullet <= MAX_BULLET_WORDS:
        return "Good"
    if avg_words_per_bullet <= 25:
        return "Dense"
    return "Very Dense"


# ---------------------------------------------------------------------------
#  KNOWLEDGE BASE HELPER
# ---------------------------------------------------------------------------

def _resolve_topic(topic: str) -> str:
    """Map a short topic code (AI, DSA, DBMS...) to the KB topic name."""
    if not topic:
        return ""
    key = topic.strip().lower()
    return TOPIC_ALIASES.get(key, topic.strip())


def _load_topic_keywords(topic: str) -> list[str]:
    """
    Load expected keywords for a given topic from knowledge_base.json.

    Args:
        topic: Topic name or short code (e.g. "AI", "Artificial Intelligence").

    Returns:
        List of lowercase expected keywords, or empty list if the
        topic is not found or the KB is unavailable.
    """
    kb_path = Path(__file__).parent / "knowledge_base.json"
    if not kb_path.exists():
        return []

    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    resolved = _resolve_topic(topic).lower()
    topics_db = kb.get("topics", {})
    for t_name, t_data in topics_db.items():
        if resolved == t_name.lower() or resolved in t_name.lower():
            return [kw.lower() for kw in t_data.get("expected_keywords", [])]

    return []


# ---------------------------------------------------------------------------
#  GEOMETRY HELPERS (PPTX only)
# ---------------------------------------------------------------------------

def _emu_inches(value: Optional[int]) -> float:
    """Convert EMU to inches (0.0 when unknown)."""
    if not value:
        return 0.0
    return float(value) / EMU_PER_INCH


def _rect_overlap_ratio(a: dict, b: dict) -> float:
    """
    Fraction of the smaller rectangle covered by the intersection of two.

    Used to detect content boxes that visually collide.
    """
    ax1, ay1 = a["left"], a["top"]
    ax2, ay2 = ax1 + a["width"], ay1 + a["height"]
    bx1, by1 = b["left"], b["top"]
    bx2, by2 = bx1 + b["width"], by1 + b["height"]

    inter_w = min(ax2, bx2) - max(ax1, bx1)
    inter_h = min(ay2, by2) - max(ay1, by1)
    if inter_w <= 0 or inter_h <= 0:
        return 0.0

    inter_area = inter_w * inter_h
    area_a = max(a["width"] * a["height"], 1.0)
    area_b = max(b["width"] * b["height"], 1.0)
    smaller = min(area_a, area_b)
    if smaller <= 0:
        return 0.0
    return inter_area / smaller


def _text_capacity_chars(width_in: float, height_in: float, font_pt: float) -> float:
    """
    Estimate how many characters fit inside a text box.

    Uses a per-character width of 0.5em and a line height of 1.25em, which
    approximates how a renderer lays out mixed-case Latin text.
    """
    if width_in <= 0 or height_in <= 0 or font_pt <= 0:
        return 0.0
    char_width_in = (font_pt * 0.5) / 72.0
    line_height_in = (font_pt * 1.25) / 72.0
    chars_per_line = max(width_in / char_width_in, 1.0)
    lines = max(height_in / line_height_in, 1.0)
    return chars_per_line * lines


# ---------------------------------------------------------------------------
#  FILE PARSERS
# ---------------------------------------------------------------------------

def _para_has_bullet_marker(para) -> bool:
    """True when the paragraph XML declares a bullet (buChar / buAutoNum)."""
    try:
        pPr = para._p.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}pPr"
        )
        if pPr is None:
            return False
        for child in pPr:
            tag = child.tag.split("}")[-1]
            if tag in ("buChar", "buAutoNum"):
                return True
            if tag == "buNone":
                return False
    except Exception:
        return False
    return False


def _para_is_bullet(para, inherits_bullets: bool = False) -> bool:
    """
    Detect whether a paragraph is a bulleted list item.

    PowerPoint stores bullets as a paragraph property (a:buChar / a:buAutoNum
    inside a:pPr) rather than as a literal character in the text, so a plain
    text scan misses every real bullet in a deck. Bullets are frequently
    inherited from the slide layout instead of being declared on the slide,
    which is why the caller can pass inherits_bullets=True.
    """
    try:
        if para.level and int(para.level) > 0:
            return True
    except (TypeError, ValueError):
        pass

    if _para_has_bullet_marker(para):
        return True

    return inherits_bullets


def _layout_bullet_placeholders(slide) -> set[int]:
    """
    Indices of layout placeholders whose text is bulleted by default.

    A body placeholder in a standard template renders its paragraphs as
    bullets even though the slide itself carries no bullet markup.
    """
    indices: set[int] = set()
    try:
        for ph in slide.slide_layout.placeholders:
            if not getattr(ph, "has_text_frame", False):
                continue
            for para in ph.text_frame.paragraphs:
                if _para_has_bullet_marker(para):
                    indices.add(ph.placeholder_format.idx)
                    break
            else:
                # No explicit marker in the layout either - a body-style
                # placeholder still renders bulleted paragraphs.
                try:
                    ph_type = _enum_value(ph.placeholder_format.type)
                except Exception:
                    ph_type = -1
                if ph_type not in (13, 0):     # not TITLE / CENTER_TITLE
                    indices.add(ph.placeholder_format.idx)
    except Exception:
        pass
    return indices


def _enum_value(member) -> int:
    """Return the integer value of a python-pptx enum member."""
    raw = getattr(member, "value", member)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return -1


def _shape_font_sizes(shape, explicit_only: bool = False) -> list[float]:
    """
    Collect font sizes (in points) from a shape.

    Explicit sizes are the ones set on the runs. When a shape inherits its
    size from the slide master no run carries a size, so a placeholder
    default is substituted - unless explicit_only is requested.

    Args:
        shape: The python-pptx shape to inspect.
        explicit_only: Return only sizes that are explicitly declared.
    """
    sizes: list[float] = []

    if not getattr(shape, "has_text_frame", False):
        return sizes

    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            if run.font.size is not None:
                try:
                    sizes.append(float(run.font.size.pt))
                except (AttributeError, TypeError):
                    pass

    if explicit_only:
        return sizes

    for para in shape.text_frame.paragraphs:
        if para.font.size is not None:
            try:
                sizes.append(float(para.font.size.pt))
            except (AttributeError, TypeError):
                pass

    if not sizes and getattr(shape, "is_placeholder", False):
        try:
            ph_type = _enum_value(shape.placeholder_format.type)
        except (AttributeError, TypeError, ValueError):
            ph_type = -1
        # 13 = TITLE, 0 = CENTER_TITLE -> title sized; everything else body
        if ph_type in (13, 0):
            sizes.append(44.0)
        else:
            sizes.append(IDEAL_BODY_FONT_PT)

    return sizes


def _shape_font_families(shape) -> list[str]:
    """Collect explicit font family names from a shape's runs."""
    families: list[str] = []
    if not getattr(shape, "has_text_frame", False):
        return families

    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            if run.font.name:
                families.append(str(run.font.name))
    return families


def _parse_pptx(file_path: str) -> dict:
    """
    Parse a .pptx file into per-slide data including geometry and fonts.

    Args:
        file_path: Absolute or relative path to the PPTX file.

    Returns:
        dict with keys:
            slides   - list of per-slide dicts
            width    - slide width in EMU
            height   - slide height in EMU

    Raises:
        ImportError:   If python-pptx is not installed.
        FileNotFoundError: If the file does not exist.
        Exception:     If the file is corrupted or unreadable.
    """
    if not HAS_PPTX:
        raise ImportError(
            "python-pptx is not installed. "
            "Install it with: pip install python-pptx"
        )

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    prs = PptxPresentation(file_path)
    slide_w = int(prs.slide_width or 0)
    slide_h = int(prs.slide_height or 0)

    slides: list[dict] = []

    for idx, slide in enumerate(prs.slides, start=1):
        title_text = ""
        body_lines: list[str] = []
        shapes: list[dict] = []
        has_image = False
        has_chart = False
        has_table = False
        title_font_sizes: list[float] = []
        title_font_explicit: list[float] = []
        body_font_sizes: list[float] = []
        all_families: list[str] = []

        title_shape = slide.shapes.title
        if title_shape is not None and getattr(title_shape, "has_text_frame", False):
            raw_title = title_shape.text_frame.text.strip()
            if raw_title:
                title_text = raw_title
                title_font_sizes = _shape_font_sizes(title_shape)
                title_font_explicit = _shape_font_sizes(title_shape, explicit_only=True)
                all_families.extend(_shape_font_families(title_shape))

        title_shape_id = title_shape.shape_id if title_shape is not None else -1
        bullet_placeholder_idx = _layout_bullet_placeholders(slide)
        body_font_explicit: list[float] = []

        for shape in slide.shapes:
            is_title_shape = shape.shape_id == title_shape_id
            shape_type = shape.shape_type
            is_visual = False

            inherits_bullets = False
            if getattr(shape, "is_placeholder", False):
                try:
                    inherits_bullets = (
                        shape.placeholder_format.idx in bullet_placeholder_idx
                    )
                except (AttributeError, TypeError):
                    inherits_bullets = False

            info = {
                "shape_id": shape.shape_id,
                "name": shape.name or "",
                "left": float(shape.left or 0),
                "top": float(shape.top or 0),
                "width": float(shape.width or 0),
                "height": float(shape.height or 0),
                "is_placeholder": bool(getattr(shape, "is_placeholder", False)),
                "text": "",
                "font_sizes": [],
                "font_families": [],
                "is_visual": False,
                "is_table": False,
                "is_chart": False,
                "is_title": is_title_shape,
            }

            # Pictures / groups / graphic frames carrying media
            try:
                if _enum_value(shape_type) == 13:      # MSO_SHAPE_TYPE.PICTURE
                    is_visual = True
                    has_image = True
            except (TypeError, ValueError):
                pass

            if getattr(shape, "has_table", False):
                info["is_table"] = True
                has_table = True
                is_visual = True
                try:
                    cell_texts = []
                    for row in shape.table.rows:
                        for cell in row.cells:
                            if cell.text and cell.text.strip():
                                cell_texts.append(cell.text.strip())
                    info["text"] = "\n".join(cell_texts)
                except Exception:
                    info["text"] = ""

            if getattr(shape, "has_chart", False):
                info["is_chart"] = True
                has_chart = True
                is_visual = True

            if getattr(shape, "has_text_frame", False):
                para_texts: list[str] = []
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    # Bullets are paragraph properties in PPTX; materialise them
                    # as a marker so density/quality checks can see them.
                    if _para_is_bullet(para, inherits_bullets) and not text.startswith(BULLET_CHARS):
                        text = f"• {text}"
                    para_texts.append(text)
                shape_text = "\n".join(para_texts)

                if shape_text and not info["is_table"]:
                    info["text"] = shape_text
                    if not is_title_shape:
                        # The title is captured separately; counting it twice
                        # would inflate every word-count based metric.
                        body_lines.extend(para_texts)
                    sizes = _shape_font_sizes(shape)
                    info["font_sizes"] = sizes
                    info["font_families"] = _shape_font_families(shape)
                    if not is_title_shape:
                        body_font_sizes.extend(sizes)
                        body_font_explicit.extend(
                            _shape_font_sizes(shape, explicit_only=True)
                        )
                    all_families.extend(info["font_families"])

            info["is_visual"] = is_visual
            shapes.append(info)

        # Speaker notes
        notes_text = ""
        try:
            if slide.has_notes_slide:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            notes_text = ""

        full_text = (title_text + "\n" + "\n".join(body_lines)).strip()
        bullet_count = _count_bullets(full_text)

        if not title_text:
            title_text = _detect_title_heuristic(full_text)

        slides.append({
            "slide_no": idx,
            "title": title_text,
            "full_text": full_text,
            "bullet_count": bullet_count,
            "has_image": has_image,
            "has_chart": has_chart,
            "has_table": has_table,
            "notes": notes_text,
            "shapes": shapes,
            "title_font_sizes": title_font_sizes,
            "body_font_sizes": body_font_sizes,
            "title_font_explicit": title_font_explicit,
            "body_font_explicit": body_font_explicit,
            "font_families": sorted(set(all_families)),
            "is_title_slide": False,
        })

    return {"slides": slides, "width": slide_w, "height": slide_h}


def _parse_pdf(file_path: str) -> dict:
    """
    Parse a .pdf file into per-page text data.

    PDFs carry no reliable geometry through PyPDF2, so layout and
    typography dimensions are simply unavailable for this format.

    Raises:
        ImportError: If PyPDF2 is not installed.
        FileNotFoundError: If the file does not exist.
    """
    if not HAS_PDF:
        raise ImportError(
            "PyPDF2 is not installed. "
            "Install it with: pip install PyPDF2"
        )

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    reader = PdfReader(file_path)
    slides: list[dict] = []

    for idx, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""

        title_text = _detect_title_heuristic(raw_text)
        bullet_count = _count_bullets(raw_text)

        slides.append({
            "slide_no": idx,
            "title": title_text,
            "full_text": raw_text,
            "bullet_count": bullet_count,
            "has_image": False,
            "has_chart": False,
            "has_table": False,
            "notes": "",
            "shapes": [],
            "title_font_sizes": [],
            "body_font_sizes": [],
            "font_families": [],
            "is_title_slide": False,
        })

    return {"slides": slides, "width": 0, "height": 0}


# ---------------------------------------------------------------------------
#  PER-SLIDE ANALYSIS
# ---------------------------------------------------------------------------

def _analyze_slide(slide: dict, slide_w: int, slide_h: int) -> dict:
    """
    Analyse one slide and return its detail record plus issue list.

    Checks performed: missing title, word density, bullet length, bullet
    completeness, font readability, text overflow risk, off-slide shapes,
    colliding shapes, visual support and speaker notes.
    """
    issues: list[dict] = []
    word_count = _count_words(slide.get("full_text", ""))
    bullet_count = slide.get("bullet_count", 0)
    title = (slide.get("title") or "").strip()

    def _issue(severity: str, message: str) -> None:
        issues.append({"severity": severity, "message": message})

    # --- Title ---
    if not title:
        _issue("critical", "Slide has no title — viewers lose context instantly.")
    elif len(title.split()) > 12:
        _issue("warning", f"Title is long ({len(title.split())} words); trim to under 12.")

    # --- Word density ---
    if word_count > OVERLOAD_THRESHOLD:
        _issue("critical", f"Text overload: {word_count} words on one slide.")
    elif word_count > IDEAL_WORDS_MAX:
        _issue("warning", f"Dense slide: {word_count} words (ideal is 20-50).")
    elif 0 < word_count < UNDERLOAD_THRESHOLD:
        _issue("info", "Very little text — the slide may rely on an unexplained visual.")
    elif word_count == 0:
        _issue("info", "No text at all (image-only slide).")

    # --- Bullets ---
    bullets = _split_bullets(slide.get("full_text", ""))
    long_bullets = [b for b in bullets if _count_words(_strip_bullet_marker(b)) > MAX_BULLET_WORDS]
    fragments = [b for b in bullets if _is_fragment(b)]

    if long_bullets:
        _issue(
            "warning",
            f"{len(long_bullets)} bullet(s) exceed {MAX_BULLET_WORDS} words — "
            "break them up.",
        )
    if fragments:
        _issue(
            "info",
            f"{len(fragments)} bullet(s) read as fragments; write them as full sentences.",
        )

    # --- Typography ---
    font_sizes = (slide.get("title_font_sizes", []) or []) + \
                 (slide.get("body_font_sizes", []) or [])
    explicit_sizes = (slide.get("title_font_explicit", []) or []) + \
                     (slide.get("body_font_explicit", []) or [])
    min_font = min(font_sizes) if font_sizes else None
    max_font = max(font_sizes) if font_sizes else None
    min_explicit = min(explicit_sizes) if explicit_sizes else None

    if min_explicit is not None and min_explicit < MIN_READABLE_FONT_PT:
        _issue("critical", f"Font size {min_explicit:.0f}pt is below the {MIN_READABLE_FONT_PT:.0f}pt readability floor.")
    elif min_explicit is not None and min_explicit < IDEAL_BODY_FONT_PT:
        _issue("warning", f"Smallest text is {min_explicit:.0f}pt; {IDEAL_BODY_FONT_PT:.0f}pt is safer for a room.")

    # --- Layout: off-slide and colliding shapes ---
    off_slide: list[str] = []
    collisions: list[str] = []

    if slide_w and slide_h:
        tolerance = EMU_PER_INCH * 0.05
        free_shapes = []

        for shape in slide.get("shapes", []):
            left, top = shape["left"], shape["top"]
            right, bottom = left + shape["width"], top + shape["height"]

            if (left < -tolerance or top < -tolerance
                    or right > slide_w + tolerance or bottom > slide_h + tolerance):
                off_slide.append(shape["name"] or f"shape #{shape['shape_id']}")

            if not shape["is_placeholder"] and shape["text"]:
                free_shapes.append(shape)

        for i in range(len(free_shapes)):
            for j in range(i + 1, len(free_shapes)):
                if _rect_overlap_ratio(free_shapes[i], free_shapes[j]) > 0.25:
                    a = free_shapes[i]["name"] or f"#{free_shapes[i]['shape_id']}"
                    b = free_shapes[j]["name"] or f"#{free_shapes[j]['shape_id']}"
                    collisions.append(f"{a} / {b}")

        if off_slide:
            _issue("critical", f"Content extends past the slide edge: {', '.join(off_slide[:3])}.")
        if collisions:
            _issue("warning", f"Overlapping content boxes: {', '.join(collisions[:3])}.")

    # --- Text overflow risk ---
    overflow_shapes: list[str] = []
    for shape in slide.get("shapes", []):
        text = shape.get("text") or ""
        if not text.strip():
            continue
        w_in = _emu_inches(shape["width"])
        h_in = _emu_inches(shape["height"])
        if w_in <= 0 or h_in <= 0:
            continue
        sizes = shape.get("font_sizes") or [IDEAL_BODY_FONT_PT]
        font_pt = max(sizes)
        capacity = _text_capacity_chars(w_in, h_in, font_pt)
        if capacity > 0 and len(text) > capacity:
            overflow_shapes.append(shape["name"] or f"#{shape['shape_id']}")

    if overflow_shapes:
        _issue(
            "critical",
            f"Text likely overflows its box: {', '.join(overflow_shapes[:3])}.",
        )

    # --- Visual support ---
    has_visual = slide.get("has_image") or slide.get("has_chart") or slide.get("has_table")
    if not has_visual and word_count > IDEAL_WORDS_MAX:
        _issue("info", "Text-heavy slide with no visual — add a diagram or chart.")

    # --- Speaker notes ---
    notes = (slide.get("notes") or "").strip()
    if not notes:
        _issue("info", "No speaker notes — you will have to improvise this slide.")

    # --- Slide score ---
    score = 10.0
    score -= len([i for i in issues if i["severity"] == "critical"]) * 1.5
    score -= len([i for i in issues if i["severity"] == "warning"]) * 0.8
    score -= len([i for i in issues if i["severity"] == "info"]) * 0.3
    score = max(0.0, min(10.0, round(score, 2)))

    if score >= 8.5:
        level = "Excellent"
    elif score >= 7.0:
        level = "Good"
    elif score >= 5.0:
        level = "Average"
    elif score >= 3.0:
        level = "Needs Improvement"
    else:
        level = "Poor"

    if not title:
        title_display = "(No title)"
    else:
        title_display = title

    return {
        "slide_no": slide.get("slide_no", 0),
        "title": title_display,
        "word_count": word_count,
        "bullet_count": bullet_count,
        "long_bullets": len(long_bullets),
        "fragment_bullets": len(fragments),
        "reading_time_sec": _estimate_reading_time(word_count),
        "readability": _compute_readability(word_count, bullet_count),
        "is_overloaded": word_count > OVERLOAD_THRESHOLD,
        "has_image": slide.get("has_image", False),
        "has_chart": slide.get("has_chart", False),
        "has_table": slide.get("has_table", False),
        "has_notes": bool(notes),
        "min_font_pt": min_font,
        "max_font_pt": max_font,
        "off_slide_shapes": off_slide,
        "collisions": collisions,
        "overflow_shapes": overflow_shapes,
        "issues": issues,
        "score": score,
        "level": level,
    }


# ---------------------------------------------------------------------------
#  DECK-LEVEL ANALYSIS
# ---------------------------------------------------------------------------

def _analyze_structure(slides: list[dict]) -> dict:
    """Detect the overall arc of the deck (title / agenda / conclusion)."""
    titles = [(s.get("title") or "").lower() for s in slides]

    has_title_slide = False
    if slides:
        first = slides[0]
        first_words = _count_words(first.get("full_text", ""))
        has_title_slide = bool(first.get("title")) and first_words <= 25

    has_agenda = any(any(w in t for w in AGENDA_WORDS) for t in titles)
    has_conclusion = any(any(w in t for w in CONCLUSION_WORDS) for t in titles)

    duplicates = sorted({t for t in titles if t and titles.count(t) > 1})

    return {
        "has_title_slide": has_title_slide,
        "has_agenda": has_agenda,
        "has_conclusion": has_conclusion,
        "duplicate_titles": duplicates,
    }


def _analyze_typography(slides: list[dict]) -> dict:
    """Aggregate font sizes and families across the whole deck."""
    sizes: list[float] = []
    explicit: list[float] = []
    families: list[str] = []
    title_sizes: list[float] = []
    body_sizes: list[float] = []
    title_explicit: list[float] = []
    body_explicit: list[float] = []

    for slide in slides:
        sizes.extend(slide.get("title_font_sizes", []) or [])
        sizes.extend(slide.get("body_font_sizes", []) or [])
        explicit.extend(slide.get("title_font_explicit", []) or [])
        explicit.extend(slide.get("body_font_explicit", []) or [])
        title_sizes.extend(slide.get("title_font_sizes", []) or [])
        body_sizes.extend(slide.get("body_font_sizes", []) or [])
        title_explicit.extend(slide.get("title_font_explicit", []) or [])
        body_explicit.extend(slide.get("body_font_explicit", []) or [])
        families.extend(slide.get("font_families", []) or [])

    distinct_families = sorted(set(families))

    return {
        "min_pt": min(sizes) if sizes else None,
        "max_pt": max(sizes) if sizes else None,
        "min_explicit_pt": min(explicit) if explicit else None,
        "title_size_pt": round(sum(title_sizes) / len(title_sizes), 1) if title_sizes else None,
        "body_size_pt": round(sum(body_sizes) / len(body_sizes), 1) if body_sizes else None,
        "title_explicit_pt": (round(sum(title_explicit) / len(title_explicit), 1)
                              if title_explicit else None),
        "body_explicit_pt": (round(sum(body_explicit) / len(body_explicit), 1)
                             if body_explicit else None),
        "distinct_families": distinct_families,
        "family_count": len(distinct_families),
        "slides_below_readable": sum(
            1 for s in slides
            if (s.get("body_font_explicit") and min(s["body_font_explicit"]) < MIN_READABLE_FONT_PT)
        ),
    }


def _analyze_bullets(slides: list[dict]) -> dict:
    """Aggregate bullet statistics across the deck."""
    total_bullets = 0
    total_words = 0
    long_bullets = 0
    fragments = 0

    for slide in slides:
        for line in _split_bullets(slide.get("full_text", "")):
            total_bullets += 1
            words = _count_words(_strip_bullet_marker(line))
            total_words += words
            if words > MAX_BULLET_WORDS:
                long_bullets += 1
            if _is_fragment(line):
                fragments += 1

    return {
        "total_bullets": total_bullets,
        "avg_words_per_bullet": round(total_words / total_bullets, 1) if total_bullets else 0.0,
        "long_bullets": long_bullets,
        "fragment_bullets": fragments,
    }


def _analyze_visual(slides: list[dict]) -> dict:
    """Aggregate visual support statistics."""
    with_visual = sum(
        1 for s in slides
        if s.get("has_image") or s.get("has_chart") or s.get("has_table")
    )
    return {
        "slides_with_visuals": with_visual,
        "visual_ratio": round(with_visual / len(slides), 3) if slides else 0.0,
        "images": sum(1 for s in slides if s.get("has_image")),
        "charts": sum(1 for s in slides if s.get("has_chart")),
        "tables": sum(1 for s in slides if s.get("has_table")),
    }


def _analyze_topic(slides: list[dict], topic: Optional[str]) -> dict:
    """Score topic relevance and report which keywords are missing."""
    report = {
        "topic": topic or "",
        "resolved_topic": _resolve_topic(topic) if topic else "",
        "expected_keywords": [],
        "matched_keywords": [],
        "missing_keywords": [],
        "coverage_pct": 0.0,
        "slides_with_keywords": 0,
    }

    if not topic:
        return report

    expected = _load_topic_keywords(topic)
    if not expected:
        return report

    report["expected_keywords"] = expected
    combined = " ".join(s.get("full_text", "") for s in slides).lower()
    matched = [kw for kw in expected if kw in combined]
    missing = [kw for kw in expected if kw not in combined]

    slides_hit = 0
    for slide in slides:
        text = slide.get("full_text", "").lower()
        if any(kw in text for kw in expected):
            slides_hit += 1

    report["matched_keywords"] = matched
    report["missing_keywords"] = missing
    report["coverage_pct"] = round(len(matched) / len(expected) * 100.0, 1)
    report["slides_with_keywords"] = slides_hit
    return report


# ---------------------------------------------------------------------------
#  DIMENSION SCORING
# ---------------------------------------------------------------------------

def _score_dimension(score: float, label: str, detail: str) -> dict:
    """Package one dimension score for the report."""
    return {"score": round(max(0.0, min(10.0, score)), 2), "label": label, "detail": detail}


def _score_slides(slides_data: list[dict], topic: Optional[str] = None,
                  target_minutes: int = DEFAULT_TARGET_MINUTES) -> dict:
    """
    Compute every metric, dimension score and the overall presentation score.

    Args:
        slides_data: Per-slide dicts from a parser.
        topic: Optional topic for keyword relevance scoring.
        target_minutes: Expected delivery duration, used by the timing check.

    Returns:
        The full report dict.
    """
    total_slides = len(slides_data)

    if total_slides == 0:
        return {
            "file_name": "N/A",
            "file_type": "unknown",
            "total_slides": 0,
            "overall_score": 0.0,
            "grade": "F",
            "verdict": "Needs Improvement",
            "dimensions": {},
            "avg_words_per_slide": 0.0,
            "title_coverage_pct": 0.0,
            "overloaded_slides": [],
            "slide_details": [],
            "issues": {"critical": [], "warning": [], "info": []},
            "font_stats": {},
            "structure": {},
            "timing": {},
            "visual": {},
            "bullet_stats": {},
            "topic_report": {},
            "strengths": [],
            "weaknesses": ["Presentation contains no slides."],
            "recommendations": ["Add content slides to your presentation."],
            "top_fixes": [],
        }

    slide_w = slides_data[0].get("slide_width", 0)
    slide_h = slides_data[0].get("slide_height", 0)

    slide_details = [_analyze_slide(s, slide_w, slide_h) for s in slides_data]

    total_words = sum(sd["word_count"] for sd in slide_details)
    avg_words = round(total_words / total_slides, 1)

    slides_with_titles = sum(
        1 for sd in slide_details if sd["title"] != "(No title)"
    )
    title_coverage = round((slides_with_titles / total_slides) * 100.0, 1)

    overloaded_slides = [sd["slide_no"] for sd in slide_details if sd["is_overloaded"]]

    structure = _analyze_structure(slides_data)
    font_stats = _analyze_typography(slides_data)
    bullet_stats = _analyze_bullets(slides_data)
    visual = _analyze_visual(slides_data)
    topic_report = _analyze_topic(slides_data, topic)

    # --- Aggregated issue buckets -------------------------------------------
    issues: dict[str, list[str]] = {"critical": [], "warning": [], "info": []}
    for sd in slide_details:
        for issue in sd["issues"]:
            label = f"Slide {sd['slide_no']}: {issue['message']}"
            if label not in issues[issue["severity"]]:
                issues[issue["severity"]].append(label)

    # --- Timing --------------------------------------------------------------
    estimated_minutes = round(total_words / SPEAKING_WPM, 1)
    if estimated_minutes <= target_minutes * 0.6:
        timing_verdict = "far too short"
    elif estimated_minutes <= target_minutes:
        timing_verdict = "on target"
    elif estimated_minutes <= target_minutes * 1.3:
        timing_verdict = "slightly long"
    else:
        timing_verdict = "far too long"

    # =====================================================================
    #  DIMENSION SCORES
    # =====================================================================
    dimensions: dict[str, dict] = {}

    # 1. Content density -----------------------------------------------------
    if IDEAL_WORDS_MIN <= avg_words <= IDEAL_WORDS_MAX:
        density_score = 9.0
    elif avg_words < UNDERLOAD_THRESHOLD:
        density_score = 4.0
    elif avg_words < IDEAL_WORDS_MIN:
        density_score = 7.0
    elif avg_words <= OVERLOAD_THRESHOLD:
        density_score = 6.5
    else:
        density_score = 3.0
    dimensions["content_density"] = _score_dimension(
        density_score,
        "Content Density",
        f"{avg_words} words per slide (ideal {IDEAL_WORDS_MIN}-{IDEAL_WORDS_MAX}).",
    )

    # 2. Structure -----------------------------------------------------------
    structure_score = 5.0
    if structure["has_title_slide"]:
        structure_score += 1.5
    if structure["has_agenda"]:
        structure_score += 1.5
    if structure["has_conclusion"]:
        structure_score += 1.5
    structure_score += (title_coverage / 100.0) * 1.5
    if structure["duplicate_titles"]:
        structure_score -= min(len(structure["duplicate_titles"]) * 0.5, 1.5)
    dimensions["structure"] = _score_dimension(
        structure_score,
        "Deck Structure",
        f"Title coverage {title_coverage}%; "
        f"title slide: {'yes' if structure['has_title_slide'] else 'no'}, "
        f"agenda: {'yes' if structure['has_agenda'] else 'no'}, "
        f"conclusion: {'yes' if structure['has_conclusion'] else 'no'}.",
    )

    # 3. Typography ----------------------------------------------------------
    if not font_stats.get("min_pt"):
        typography_score = 5.0
        typography_detail = "Font data unavailable for this file type."
    else:
        typography_score = 10.0
        typography_detail = (
            f"Smallest {font_stats['min_pt']:.0f}pt, largest {font_stats['max_pt']:.0f}pt, "
            f"{font_stats['family_count']} font famil{'y' if font_stats['family_count'] == 1 else 'ies'}."
        )
        min_explicit = font_stats.get("min_explicit_pt")
        if min_explicit is not None and min_explicit < MIN_READABLE_FONT_PT:
            typography_score -= 2.5
            typography_detail += f" {min_explicit:.0f}pt text is below the readable size."
        elif min_explicit is not None and min_explicit < IDEAL_BODY_FONT_PT:
            typography_score -= 1.0
        if font_stats["family_count"] > 2:
            typography_score -= 1.0
        elif font_stats["family_count"] <= 1:
            # 0 explicit families means the deck relies on theme fonts,
            # which is automatically consistent.
            typography_score += 0.5
            if font_stats["family_count"] == 0:
                typography_detail += " Fonts inherited from the theme."
        title_pt = font_stats.get("title_explicit_pt")
        body_pt = font_stats.get("body_explicit_pt")
        if title_pt and body_pt and title_pt < body_pt * 1.3:
            typography_score -= 1.0
            typography_detail += " Title is not clearly larger than body text."
    dimensions["typography"] = _score_dimension(
        typography_score, "Typography", typography_detail
    )

    # 4. Layout integrity ----------------------------------------------------
    off_slide_total = sum(len(sd["off_slide_shapes"]) for sd in slide_details)
    collision_total = sum(len(sd["collisions"]) for sd in slide_details)
    overflow_total = sum(len(sd["overflow_shapes"]) for sd in slide_details)

    if not slide_w:
        layout_score = 6.0
        layout_detail = "Layout geometry is unavailable for PDF input."
    else:
        layout_score = 10.0
        layout_detail = "No off-slide, overlapping or overflowing content found."
        layout_score -= min(off_slide_total * 1.5, 4.0)
        layout_score -= min(overflow_total * 1.2, 3.0)
        layout_score -= min(collision_total * 0.8, 2.0)
        aspect = slide_w / slide_h if slide_h else 0
        if aspect and abs(aspect - (16 / 9)) > 0.05 and abs(aspect - (4 / 3)) > 0.05:
            layout_score -= 0.5
            layout_detail += " Unusual slide aspect ratio."
    dimensions["layout"] = _score_dimension(layout_score, "Layout Integrity", layout_detail)

    # 5. Visual support ------------------------------------------------------
    visual_score = 10.0 * min(visual["visual_ratio"] / 0.6, 1.0)
    dimensions["visual"] = _score_dimension(
        visual_score,
        "Visual Support",
        f"{visual['slides_with_visuals']}/{total_slides} slides carry an image, chart or table.",
    )

    # 6. Bullet quality ------------------------------------------------------
    if bullet_stats["total_bullets"] == 0:
        bullet_score = 7.0
        bullet_detail = "No bullet lists detected."
    else:
        bullet_score = 10.0
        bullet_detail = (
            f"{bullet_stats['total_bullets']} bullets, "
            f"{bullet_stats['avg_words_per_bullet']} words each on average."
        )
        if bullet_stats["long_bullets"]:
            bullet_score -= min(bullet_stats["long_bullets"] * 0.4, 3.0)
        if bullet_stats["fragment_bullets"]:
            bullet_score -= min(bullet_stats["fragment_bullets"] * 0.2, 2.0)
    dimensions["bullet_quality"] = _score_dimension(bullet_score, "Bullet Quality", bullet_detail)

    # 7. Topic relevance ----------------------------------------------------
    if topic and topic_report["expected_keywords"]:
        cov = topic_report["coverage_pct"]
        # A deck only has to cover the part of the unit it actually presents.
        # Reaching ~18% of the unit keyword list is treated as fully relevant.
        relevance_score = min(cov / 18.0, 10.0)
        dimensions["topic_relevance"] = _score_dimension(
            relevance_score,
            "Topic Relevance",
            f"{len(topic_report['matched_keywords'])}/{len(topic_report['expected_keywords'])} "
            f"'{topic_report['resolved_topic']}' keywords present ({cov}%).",
        )
    else:
        dimensions["topic_relevance"] = _score_dimension(
            5.0, "Topic Relevance", "No topic selected — relevance not scored."
        )

    # 8. Timing --------------------------------------------------------------
    if timing_verdict == "on target":
        timing_score = 9.0
    elif timing_verdict == "slightly long":
        timing_score = 7.0
    elif timing_verdict == "far too long":
        timing_score = 4.0
    elif timing_verdict == "far too short":
        timing_score = 6.0
    else:
        timing_score = 7.0
    dimensions["timing"] = _score_dimension(
        timing_score,
        "Delivery Timing",
        f"~{estimated_minutes} min of speech for a {target_minutes} min slot.",
    )

    # 9. Speaker support ----------------------------------------------------
    notes_count = sum(1 for sd in slide_details if sd["has_notes"])
    notes_score = 10.0 * (notes_count / total_slides)
    dimensions["speaker_notes"] = _score_dimension(
        notes_score,
        "Speaker Notes",
        f"{notes_count}/{total_slides} slides carry speaker notes.",
    )

    # =====================================================================
    #  WEIGHTED OVERALL SCORE
    # =====================================================================
    weights = {
        "content_density": 0.18,
        "structure": 0.15,
        "typography": 0.13,
        "layout": 0.13,
        "visual": 0.11,
        "bullet_quality": 0.10,
        "topic_relevance": 0.10,
        "timing": 0.05,
        "speaker_notes": 0.05,
    }
    weighted = sum(dimensions[k]["score"] * w for k, w in weights.items())
    score = max(0.0, min(10.0, round(weighted, 2)))

    if score >= 8.5:
        verdict, grade = "Excellent", "A"
    elif score >= 7.0:
        verdict, grade = "Good", "B"
    elif score >= 5.0:
        verdict, grade = "Average", "C"
    elif score >= 3.0:
        verdict, grade = "Needs Improvement", "D"
    else:
        verdict, grade = ("Poor", "F")

    # =====================================================================
    #  STRENGTHS / WEAKNESSES / RECOMMENDATIONS
    # =====================================================================
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []

    if dimensions["content_density"]["score"] >= 8.0:
        strengths.append(f"Healthy content density: {avg_words} words per slide.")
    else:
        weaknesses.append(f"Content density is off target: {avg_words} words per slide.")
        recommendations.append(f"Aim for {IDEAL_WORDS_MIN}-{IDEAL_WORDS_MAX} words per slide.")

    if title_coverage >= 90:
        strengths.append(f"Title coverage is {title_coverage}% — every slide is clearly labelled.")
    elif title_coverage < 70:
        weaknesses.append(f"Only {title_coverage}% of slides carry a title.")
        recommendations.append("Add a descriptive title to every slide.")

    if not structure["has_conclusion"]:
        weaknesses.append("The deck has no clear closing/conclusion slide.")
        recommendations.append("End with a summary or conclusion slide.")

    if not structure["has_title_slide"]:
        weaknesses.append("The opening slide does not read as a title slide.")
        recommendations.append("Start with a title slide carrying the topic and your name.")

    min_explicit = font_stats.get("min_explicit_pt") or font_stats.get("min_pt")
    if min_explicit and min_explicit < MIN_READABLE_FONT_PT:
        weaknesses.append(f"Smallest text is only {min_explicit:.0f}pt.")
        recommendations.append(f"Raise body text to at least {IDEAL_BODY_FONT_PT:.0f}pt.")

    if font_stats.get("family_count", 0) > 2:
        weaknesses.append(f"{font_stats['family_count']} different fonts are in use.")
        recommendations.append("Limit the deck to two font families for consistency.")

    if off_slide_total:
        weaknesses.append(f"{off_slide_total} content box(es) extend past the slide edge.")
        recommendations.append("Pull the overflowing shapes back inside the slide canvas.")

    if overflow_total:
        weaknesses.append(f"{overflow_total} text box(es) are likely to overflow their frame.")
        recommendations.append("Shorten the text or enlarge the text box to prevent clipping.")

    if collision_total:
        weaknesses.append(f"{collision_total} overlapping content pair(s) found.")
        recommendations.append("Reposition overlapping boxes so nothing collides.")

    if bullet_stats["long_bullets"]:
        weaknesses.append(f"{bullet_stats['long_bullets']} bullet(s) exceed {MAX_BULLET_WORDS} words.")
        recommendations.append("Split long bullets into shorter, parallel points.")

    if bullet_stats["fragment_bullets"]:
        weaknesses.append(f"{bullet_stats['fragment_bullets']} bullet(s) are fragments, not sentences.")
        recommendations.append("Rewrite fragments as complete sentences.")

    if visual["visual_ratio"] < 0.4:
        weaknesses.append("Only {:.0%} of slides use a visual.".format(visual["visual_ratio"]))
        recommendations.append("Add diagrams or charts to break up the wall of text.")

    if timing_verdict in ("slightly long", "far too long"):
        weaknesses.append(f"At {SPEAKING_WPM} wpm the deck runs about {estimated_minutes} minutes.")
        recommendations.append(f"Cut content to fit a {target_minutes} minute slot.")

    notes_count = sum(1 for sd in slide_details if sd["has_notes"])
    if notes_count < total_slides / 2:
        weaknesses.append(f"Speaker notes exist on only {notes_count}/{total_slides} slides.")
        recommendations.append("Add speaker notes so you are never silent on a slide.")

    if topic_report["missing_keywords"]:
        top_missing = ", ".join(topic_report["missing_keywords"][:8])
        weaknesses.append(
            f"{len(topic_report['missing_keywords'])} expected '{topic_report['resolved_topic']}' "
            f"keywords are missing."
        )
        recommendations.append(f"Work these terms into the slides: {top_missing}.")

    if structure["duplicate_titles"]:
        dups = ", ".join(t for t in structure["duplicate_titles"][:3])
        weaknesses.append(f"Duplicate slide titles found: {dups}.")
        recommendations.append("Give every slide a unique, descriptive title.")

    if not strengths:
        strengths.append("The deck loads and parses cleanly.")
    if not recommendations:
        recommendations.append("Rehearse the deck aloud to check the delivery, not just the slides.")

    # --- Prioritised fix list ----------------------------------------------
    top_fixes: list[dict] = []
    if overflow_total:
        top_fixes.append({
            "priority": 1, "area": "Layout",
            "fix": "Fix text overflow and off-slide shapes",
            "detail": f"{overflow_total} box(es) overflow and {off_slide_total} sit outside the canvas.",
        })
    if min_explicit and min_explicit < MIN_READABLE_FONT_PT:
        top_fixes.append({
            "priority": 2, "area": "Typography",
            "fix": f"Raise the smallest text to {IDEAL_BODY_FONT_PT:.0f}pt",
            "detail": f"Current minimum is {min_explicit:.0f}pt.",
        })
    if overloaded_slides:
        top_fixes.append({
            "priority": 3, "area": "Content",
            "fix": "Split the overloaded slides",
            "detail": f"Slides {', '.join(map(str, overloaded_slides[:8]))} exceed "
                      f"{OVERLOAD_THRESHOLD} words.",
        })
    if topic_report["missing_keywords"]:
        top_fixes.append({
            "priority": 4, "area": "Content",
            "fix": "Add the missing subject keywords",
            "detail": ", ".join(topic_report["missing_keywords"][:8]),
        })
    if bullet_stats["fragment_bullets"]:
        top_fixes.append({
            "priority": 5, "area": "Writing",
            "fix": "Rewrite fragment bullets as full sentences",
            "detail": f"{bullet_stats['fragment_bullets']} fragment bullet(s) detected.",
        })
    if not structure["has_conclusion"]:
        top_fixes.append({
            "priority": 6, "area": "Structure",
            "fix": "Add a closing summary slide",
            "detail": "No conclusion or summary slide was detected.",
        })

    return {
        "file_name": "N/A",
        "file_type": "unknown",
        "total_slides": total_slides,
        "overall_score": score,
        "grade": grade,
        "verdict": verdict,
        "dimensions": dimensions,
        "avg_words_per_slide": avg_words,
        "title_coverage_pct": title_coverage,
        "overloaded_slides": overloaded_slides,
        "slide_details": slide_details,
        "issues": issues,
        "font_stats": font_stats,
        "structure": structure,
        "timing": {
            "estimated_minutes": estimated_minutes,
            "target_minutes": target_minutes,
            "words_per_minute": SPEAKING_WPM,
            "verdict": timing_verdict,
        },
        "visual": visual,
        "bullet_stats": bullet_stats,
        "topic_report": topic_report,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "top_fixes": top_fixes,
    }


# ---------------------------------------------------------------------------
#  MAIN PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def analyze_presentation(
    file_path: str,
    topic: Optional[str] = None,
    target_minutes: int = DEFAULT_TARGET_MINUTES,
) -> dict:
    """
    Analyze a presentation file (PPTX or PDF) and return a full report.

    Args:
        file_path: Path to the .pptx or .pdf file.
        topic: Optional topic (name or short code) for relevance scoring.
        target_minutes: Expected delivery duration for the timing check.

    Returns:
        A report dict containing the overall score, per-dimension scores,
        per-slide details, prioritised fixes and textual feedback.
    """
    file_name = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pptx":
        file_type = "pptx"
        try:
            parsed = _parse_pptx(file_path)
        except ImportError as e:
            return _error_result(file_name, file_type, str(e))
        except Exception as e:
            return _error_result(file_name, file_type, f"PPTX parse error: {e}")

    elif ext == ".pdf":
        file_type = "pdf"
        try:
            parsed = _parse_pdf(file_path)
        except ImportError as e:
            return _error_result(file_name, file_type, str(e))
        except Exception as e:
            return _error_result(file_name, file_type, f"PDF parse error: {e}")

    else:
        return _error_result(
            file_name, "unknown",
            f"Unsupported file format '{ext}'. Use .pptx or .pdf."
        )

    slides = parsed["slides"]
    width = parsed["width"]
    height = parsed["height"]
    for slide in slides:
        slide["slide_width"] = width
        slide["slide_height"] = height

    result = _score_slides(slides, topic, target_minutes)
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
        "grade": "F",
        "verdict": "Needs Improvement",
        "dimensions": {},
        "avg_words_per_slide": 0.0,
        "title_coverage_pct": 0.0,
        "overloaded_slides": [],
        "slide_details": [],
        "issues": {"critical": [error_msg], "warning": [], "info": []},
        "font_stats": {},
        "structure": {},
        "timing": {},
        "visual": {},
        "bullet_stats": {},
        "topic_report": {},
        "strengths": [],
        "weaknesses": [error_msg],
        "recommendations": [
            "Ensure the file is valid and the required library is installed."
        ],
        "top_fixes": [],
    }


# ---------------------------------------------------------------------------
#  SELF-TESTS
# ---------------------------------------------------------------------------

def _mock_slides(good: bool = True) -> list[dict]:
    """Build mock slide dicts used by the self-tests."""
    if good:
        return [
            {
                "slide_no": 1,
                "title": "A* Search in Heuristic Search",
                "full_text": "A* Search in Heuristic Search\n"
                             "How A* combines g(n) and h(n)\n"
                             "Admissible heuristics guarantee optimality",
                "bullet_count": 2,
                "has_image": True,
                "has_chart": False,
                "has_table": False,
                "notes": "Introduce the idea of informed search.",
                "shapes": [],
                "title_font_sizes": [36.0],
                "body_font_sizes": [20.0, 20.0],
                "title_font_explicit": [36.0],
                "body_font_explicit": [20.0, 20.0],
                "font_families": ["Calibri"],
            },
            {
                "slide_no": 2,
                "title": "Why A* Beats Uniform Cost Search",
                "full_text": "Why A* Beats Uniform Cost Search\n"
                             "A* explores fewer nodes than uniform cost search\n"
                             "The heuristic prunes the search tree effectively",
                "bullet_count": 2,
                "has_image": False,
                "has_chart": True,
                "has_table": False,
                "notes": "Compare the two algorithms with a small example.",
                "shapes": [],
                "title_font_sizes": [36.0],
                "body_font_sizes": [20.0, 20.0],
                "title_font_explicit": [36.0],
                "body_font_explicit": [20.0, 20.0],
                "font_families": ["Calibri"],
            },
            {
                "slide_no": 3,
                "title": "Conclusion",
                "full_text": "Conclusion\n"
                             "A* search is optimal when the heuristic is admissible\n"
                             "It balances exploration and exploitation in one pass",
                "bullet_count": 2,
                "has_image": False,
                "has_chart": False,
                "has_table": False,
                "notes": "Summarise and invite questions.",
                "shapes": [],
                "title_font_sizes": [36.0],
                "body_font_sizes": [20.0, 20.0],
                "title_font_explicit": [36.0],
                "body_font_explicit": [20.0, 20.0],
                "font_families": ["Calibri"],
            },
        ]

    return [
        {
            "slide_no": 1,
            "title": "",
            "full_text": "This slide has no title and contains a very large amount of text "
                         "that goes on and on describing every single detail of the topic "
                         "which is not really a good practice for slides at all",
            "bullet_count": 0,
            "has_image": False,
            "has_chart": False,
            "has_table": False,
            "notes": "",
            "shapes": [],
                "title_font_sizes": [],
                "body_font_sizes": [9.0],
                "title_font_explicit": [],
                "body_font_explicit": [9.0],
                "font_families": ["Arial", "Times New Roman", "Courier New"],
        },
        {
            "slide_no": 2,
            "title": "",
            "full_text": "another slide without any heading whatsoever",
            "bullet_count": 0,
            "has_image": False,
            "has_chart": False,
            "has_table": False,
            "notes": "",
            "shapes": [],
                "title_font_sizes": [],
                "body_font_sizes": [11.0],
                "title_font_explicit": [],
                "body_font_explicit": [11.0],
                "font_families": ["Arial", "Times New Roman", "Courier New"],
        },
    ]


def _print_report(result: dict) -> None:
    """Pretty-print a report dict to the console."""
    print(f"  File      : {result.get('file_name', 'N/A')}")
    print(f"  Slides    : {result.get('total_slides', 0)}")
    print(f"  Score     : {result.get('overall_score', 0)}/10  [{result.get('verdict', 'N/A')}]")
    print(f"  Grade     : {result.get('grade', 'N/A')}")
    print(f"  Avg Words : {result.get('avg_words_per_slide', 0)} words/slide")
    print(f"  Titles    : {result.get('title_coverage_pct', 0)}% coverage")
    print(f"  Overloaded: {result.get('overloaded_slides') or 'None'}")

    dimensions = result.get("dimensions") or {}
    if dimensions:
        print("  Dimensions:")
        for name, data in dimensions.items():
            print(f"    - {data.get('label', name)}: {data.get('score', 0)}/10 "
                  f"({data.get('detail', '')})")

    if result.get("strengths"):
        print("  Strengths :")
        for s in result["strengths"]:
            print(f"    + {s}")

    if result.get("weaknesses"):
        print("  Weaknesses:")
        for w in result["weaknesses"]:
            print(f"    - {w}")

    if result.get("recommendations"):
        print("  Recommendations:")
        for r in result["recommendations"]:
            print(f"    > {r}")

    if result.get("top_fixes"):
        print("  Prioritised fixes:")
        for fix in result["top_fixes"]:
            print(f"    {fix.get('priority')}. [{fix.get('area')}] {fix.get('fix')} "
                  f"-- {fix.get('detail', '')}")


def test_slide_analyzer() -> None:
    """Self-contained mock test — no physical file required."""
    print("=" * 70)
    print("  VivaLens AI — Slide Analyzer Test Suite (v2.0)")
    print("=" * 70)

    print("\n--- TEST 1: Well-structured deck ---")
    good_slides = _mock_slides(good=True)
    for slide in good_slides:
        slide["slide_width"] = 12192000
        slide["slide_height"] = 6858000
    result1 = _score_slides(good_slides, topic="AI")
    _print_report(result1)

    print("\n--- TEST 2: Problem deck (no titles, tiny fonts, overloaded) ---")
    bad_slides = _mock_slides(good=False)
    for slide in bad_slides:
        slide["slide_width"] = 12192000
        slide["slide_height"] = 6858000
    result2 = _score_slides(bad_slides, topic="AI")
    _print_report(result2)

    assert result1["overall_score"] > result2["overall_score"], \
        "A well-structured deck must score higher than a broken one"
    assert len(result1["dimensions"]) == 9, "All nine dimensions must be scored"
    assert result1["slide_details"], "Per-slide details must be produced"
    assert result2["issues"]["critical"], "Critical issues must be detected"
    assert result2["font_stats"]["min_pt"] == 9.0, "Smallest font must be measured"

    print("\n--- TEST 3: Unsupported file format ---")
    result3 = analyze_presentation("fake_file.docx", topic="Data Structures")
    assert result3["overall_score"] == 0.0
    print(f"  Handled gracefully: {result3['weaknesses'][0]}")

    print("\n" + "=" * 70)
    print("  All slide analyzer tests completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    test_slide_analyzer()
