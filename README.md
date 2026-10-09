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
| + | **Slide Analyzer** *(bonus)* | Upload a PPT/PDF and get scored on content density, structure, visual balance and topic relevance. |

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
├── slide_analyzer.py        # PPT/PDF scoring (bonus)
├── test_all.py              # End-to-end test suite
├── requirements.txt         # All dependencies
├── README.md                # This file
└── sample_data/
    ├── sample_answers.txt   # Sample viva answers for testing
    └── sample_slides.pptx   # Sample presentation for testing
```

---

## Agent Credits

| Agent | Role |
|-------|------|
| **ARCHON** | Master Head — Project Coordinator |
| **NEXUS** | Knowledge & Logic Architect |
| **CIPHER** | Algorithm Specialist |
| **PRISM** | UI/UX & Speech Engineer |
| **FORGE** | Integration & Debug Master |

---

## License

MIT License — free to use, modify, and share for academic and personal purposes.

Copyright (c) 2026 VivaLens AI Team
