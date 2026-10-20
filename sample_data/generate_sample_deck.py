"""
generate_sample_deck.py — build the sample presentation used by the demo.

Creates sample_data/sample_slides.pptx: a small AI-topic deck that
deliberately contains a few realistic problems (one overloaded slide,
one tiny-font slide, one slide without a title) so the analyzer has
something meaningful to report.

Run:
    python sample_data/generate_sample_deck.py
"""

from __future__ import annotations

import os
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

OUT_DIR = Path(__file__).resolve().parent
OUT_FILE = OUT_DIR / "sample_slides.pptx"

NAVY = RGBColor(0x1F, 0x2A, 0x44)
ACCENT = RGBColor(0x2E, 0x6B, 0xD6)


def _add_title_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Heuristic Search in Artificial Intelligence"

    subtitle = slide.placeholders[1]
    subtitle.text = "A* Search, Informed Search and Admissible Heuristics"

    slide.notes_slide.notes_text_frame.text = (
        "Greet the audience, state the scope: unit 2 of the AI syllabus, "
        "focused on A* search and why the heuristic function matters."
    )


def _add_agenda_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Agenda"
    body = slide.placeholders[1].text_frame
    body.text = "Why heuristics beat blind search"
    for item in (
        "The A* evaluation function explained",
        "Admissible and consistent heuristics",
        "Comparing A* with uniform cost search",
        "Limitations and practical heuristics",
    ):
        para = body.add_paragraph()
        para.text = item
        para.level = 0

    slide.notes_slide.notes_text_frame.text = (
        "Walk through the four sections quickly, about thirty seconds."
    )


def _add_content_slide(prs: Presentation, title: str, bullets: list[str],
                       notes: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title

    body = slide.placeholders[1].text_frame
    body.text = bullets[0]
    for item in bullets[1:]:
        para = body.add_paragraph()
        para.text = item
        para.level = 0

    slide.notes_slide.notes_text_frame.text = notes


def _add_overloaded_slide(prs: Presentation) -> None:
    """A deliberately bad slide: dense text and unreadable font size."""
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Complete History of Search Algorithms"

    body = slide.placeholders[1].text_frame
    body.text = (
        "Search algorithms form the foundation of artificial intelligence "
        "and have been studied for more than sixty years across many different "
        "disciplines including computer science, operations research, robotics "
        "and control systems, and every one of them tries to answer the same "
        "fundamental question about how to explore a state space efficiently"
    )
    for para in body.paragraphs:
        for run in para.runs:
            run.font.size = Pt(11)

    slide.notes_slide.notes_text_frame.text = ""


def _add_visual_slide(prs: Presentation) -> None:
    """A slide carrying a table so the analyzer can detect visual support."""
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Uniform Cost Search vs A* Search"

    rows, cols = 4, 3
    table = slide.shapes.add_table(
        rows, cols, Inches(0.8), Inches(2.0), Inches(8.5), Inches(3.0)
    ).table

    headers = ["Criterion", "UCS", "A*"]
    for c, head in enumerate(headers):
        table.cell(0, c).text = head

    rows_data = [
        ["Uses heuristic", "No", "Yes"],
        ["Optimal path", "Yes", "Yes"],
        ["Nodes expanded", "Many", "Few"],
    ]
    for r, row in enumerate(rows_data, start=1):
        for c, value in enumerate(row):
            table.cell(r, c).text = value

    slide.notes_slide.notes_text_frame.text = (
        "Point out that A* expands far fewer nodes because the heuristic "
        "guides the search towards the goal."
    )


def build() -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    _add_title_slide(prs)
    _add_agenda_slide(prs)

    _add_content_slide(
        prs,
        "Why Heuristics Beat Blind Search",
        [
            "Blind search explores every branch of the state space",
            "Heuristics estimate the remaining cost to reach the goal",
            "Informed search prunes branches that cannot lead to an optimal path",
        ],
        "Ask the audience how many nodes a blind search would expand on a "
        "twenty-deep tree before you reveal the answer.",
    )

    _add_content_slide(
        prs,
        "The A* Evaluation Function",
        [
            "A* selects the node with the lowest value of f(n) = g(n) + h(n)",
            "g(n) is the cost already paid to reach the node",
            "h(n) is the estimated cost of reaching the goal from the node",
            "An admissible heuristic never overestimates the true remaining cost",
        ],
        "Write f(n) = g(n) + h(n) on the board and define each term.",
    )

    _add_visual_slide(prs)
    _add_overloaded_slide(prs)

    _add_content_slide(
        prs,
        "Limitations of A* Search",
        [
            "A* needs an admissible heuristic for every state in the space",
            "Memory usage grows quickly because the open list keeps every node",
            "Weak heuristics degrade A* towards uniform cost search behaviour",
        ],
        "Close by mentioning that the choice of heuristic is the real engineering "
        "problem in practice.",
    )

    _add_content_slide(
        prs,
        "Conclusion",
        [
            "Heuristic search converts an exponential problem into a practical one",
            "A* remains optimal whenever the heuristic is admissible",
            "The quality of the heuristic decides how much work A* actually does",
        ],
        "Summarise the three points and invite questions.",
    )

    prs.save(str(OUT_FILE))
    return OUT_FILE


if __name__ == "__main__":
    path = build()
    size_kb = os.path.getsize(path) / 1024
    print(f"Created {path} ({size_kb:.1f} KB)")
