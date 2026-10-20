# VivaLens AI — Presentation & Viva Performance Analyzer

> A 100% free, locally-running Python + Streamlit app that analyzes how well a student performs in academic vivas and presentations — scoring answers, simulating viva sessions, and generating improvement plans using hand-coded AI algorithms from the SPPU TY AI syllabus. No paid APIs. No cloud. No subscriptions.

---

## Features

| # | Module | What it does |
|---|--------|--------------|
| 1 | **FOL Inference Engine** | Forward chaining scores your answer against First-Order Logic rules; backward chaining diagnoses *why* an answer scored low. |
| 2 | **Speech & Text Analysis** | Offline speech-to-text (Vosk), filler-word detection, keyword coverage, pace (WPM) estimation and confidence scoring. |
| 3 | **CSP Question Generator** | Backtracking search + constraint propagation generates balanced, non-repeating viva question sets (difficulty, time, Bloom's taxonomy). |
| 4 | **A\* Improvement Path Finder** | A* search with an admissible heuristic finds the optimal study sequence to lift weak topics above a target score. |
| 5 | **Goal Stack Study Plan** | STRIPS-style goal stack planning turns your score gap into a concrete, step-by-step preparation plan. |
| + | **Slide Deck Analyzer** *(bonus)* | Reads the actual PPTX (shape geometry, run-level font sizes, notes, tables, charts) and scores the deck across **nine dimensions**. |
| + | **Analytics Dashboard** *(bonus)* | Stores every answer you evaluate and shows the trend, topic mastery, score distribution, a drill-down log of how each answer was given, and CSV export. |

### Slide Deck Analyzer — nine measured dimensions

| Dimension | What it measures |
|-----------|------------------|
| Content Density | Words per slide against the 20–50 word sweet spot |
| Deck Structure | Title coverage, plus detection of title / agenda / conclusion slides and duplicate titles |
| Typography | Smallest and largest font, number of font families, title-vs-body hierarchy |
| Layout Integrity | Off-slide shapes, overlapping boxes and text that overflows its frame |
| Visual Support | Share of slides carrying an image, chart or table |
| Bullet Quality | Bullet length, sentence fragments, average words per bullet |
| Topic Relevance | Keyword coverage against the unit's knowledge base, with the missing terms listed |
| Delivery Timing | Estimated speaking time against your target slot |
| Speaker Notes | How much of the deck you have actually prepared |

---

## Syllabus Mapping — SPPU TY AI (2024)

| Unit | Topic | Project Module | File(s) |
|------|-------|----------------|---------|
| Unit 1 | Intelligent Agent & Perception | Module 2 — Speech & Text Analysis Pipeline | `speech_module.py`, `text_analyzer.py` |
| Unit 2 | Heuristic Search | Module 4 — A* Improvement Path Finder | `astar_improvement.py` |
| Unit 3 | CSP & Adversarial Search | Module 3 — CSP-based Viva Question Generator | `csp_question_gen.py` |
| Unit 4 | Logic & Inference | Module 1 — FOL Inference Engine & Knowledge Base | `inference_engine.py`, `knowledge_base.json` |
| Unit 5 | Planning | Module 5 — Goal Stack Study Plan Generator | `goal_stack_planner.py` |

---

## Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Language | Python 3.10+ | Free |
| UI | Streamlit | Free |
| Speech-to-Text | Vosk (offline) | Free |
| Text Analysis | NLTK + Regex | Free |
| Slide Parsing | python-pptx + PyPDF2 | Free |
| Audio I/O | sounddevice + soundfile | Free |
| AI Algorithms | Hand-coded (no external AI APIs) | Free |
| Cloud / APIs | **None** | — |

---

## Installation

```bash
# 1. Clone / download the project
cd VivaLens_AI

# 2. Install all dependencies
pip install -r requirements.txt
```

> Requires Python 3.10 or newer. Everything runs 100% offline.

---

## How to Run

```bash
# Option A — launcher (prints install help if Streamlit is missing)
python main.py

# Option B — Streamlit directly
streamlit run app.py
```

Then open the local URL shown in the terminal (default: `http://localhost:8501`).

### Run the tests

```bash
# Per-module test suites
python inference_engine.py
python csp_question_gen.py
python astar_improvement.py
python goal_stack_planner.py
python slide_analyzer.py
python speech_module.py
python text_analyzer.py

# Full end-to-end suite
python test_all.py
```

---

## Project Structure

```
VivaLens_AI/
├── main.py                  # Entry point / launcher
├── app.py                   # Streamlit UI
├── .streamlit/config.toml   # Headless + offline Streamlit config
├── knowledge_base.json      # FOL rules + topics + keywords (Unit 4)
├── inference_engine.py      # Forward/backward chaining (Unit 4)
├── speech_module.py         # Offline STT + audio recording (Unit 1)
├── text_analyzer.py         # Filler/keyword/pace analysis (Unit 1)
├── csp_question_gen.py      # CSP backtracking question gen (Unit 3)
├── astar_improvement.py     # A* study path finder (Unit 2)
├── goal_stack_planner.py    # Goal stack study planner (Unit 5)
├── slide_analyzer.py        # PPTX/PDF deck scoring (bonus)
├── test_all.py              # End-to-end test suite (13 tests)
├── requirements.txt         # All dependencies
├── README.md                # This file
└── sample_data/
    ├── sample_answers.txt   # Sample viva answers for testing
    ├── sample_slides.pptx   # Ready-made sample deck (with a few realistic flaws)
    └── generate_sample_deck.py  # Rebuilds the sample deck
```

### Try it without uploading anything

The Slide Analyzer tab has a **"Use the bundled sample deck"** checkbox. It
analyses `sample_data/sample_slides.pptx`, which deliberately contains an
overloaded slide, an unreadable 11pt slide and a slide with no notes — so
you can see the analyzer catch real problems.

```bash
# regenerate the sample deck at any time
python sample_data/generate_sample_deck.py
```

---

## Credits & Acknowledgments

- **Architecture & core algorithms** — designed and implemented in-house using
  classical AI techniques (forward/backward chaining, constraint satisfaction,
  A* heuristic search, and goal stack planning) as taught in the SPPU TY AI syllabus.
- **Built with free, open tools** — Python, Streamlit, Vosk, NLTK (optional),
  python-pptx, and PyPDF2. No paid services or external AI APIs are used.

---

## License

MIT License — free to use, modify, and share for academic and personal purposes.

Copyright (c) 2026 VivaLens AI Team
