"""
test_all.py — VivaLens AI End-to-End Test Suite
=================================================
Imports EVERY module and exercises its core function with sample data.
Prints PASS/FAIL per test and a final summary.

Run:
    python test_all.py

Exit code: 0 = all tests passed, 1 = at least one failure.

Agent: FORGE (Integration & Debug Master)
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

# --- Setup: project dir on path, UTF-8 safe output (Windows cp1252 fix) ---
PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESULTS: list[tuple[str, bool, str]] = []


# ---------------------------------------------------------------------------
#  TEST RUNNER
# ---------------------------------------------------------------------------

def run_test(test_id: str, title: str, fn) -> None:
    """Run one test, capture PASS/FAIL, never let an exception stop the suite."""
    try:
        fn()
        RESULTS.append((f"TEST {test_id}: {title}", True, ""))
        print(f"[PASS] TEST {test_id}: {title}")
    except Exception as exc:  # noqa: BLE001 - suite must survive any failure
        RESULTS.append((f"TEST {test_id}: {title}", False, str(exc)))
        print(f"[FAIL] TEST {test_id}: {title}")
        print(f"       -> {exc}")
        traceback_indent = traceback.format_exc().strip().splitlines()
        for line in traceback_indent[-4:]:
            print(f"       {line}")


# ---------------------------------------------------------------------------
#  TEST CASES
# ---------------------------------------------------------------------------

def test_knowledge_base_topics() -> None:
    """Load knowledge_base.json and verify exactly 5 topics exist."""
    kb_path = PROJECT_DIR / "knowledge_base.json"
    assert kb_path.is_file(), f"knowledge_base.json not found at {kb_path}"
    kb = json.loads(kb_path.read_text(encoding="utf-8"))
    topics = kb.get("topics")
    assert isinstance(topics, dict), "'topics' key missing or not a dict"
    assert len(topics) == 5, f"expected 5 topics, got {len(topics)}: {list(topics)}"


def test_evaluate_answer() -> None:
    """Forward chaining: evaluate a sample AI answer, expect a score."""
    from inference_engine import evaluate_answer

    answer = (
        "Artificial Intelligence is a field of computer science that aims "
        "to build systems capable of performing tasks that typically require "
        "human intelligence, such as learning, reasoning, and problem solving. "
        "For example, a search algorithm explores the state space to find an "
        "optimal goal state using heuristics."
    )
    result = evaluate_answer(answer, "Artificial Intelligence")
    assert isinstance(result, dict), f"expected dict, got {type(result).__name__}"
    assert "score" in result, f"'score' key missing; got keys {list(result)}"
    assert isinstance(result["score"], (int, float)), "score is not numeric"
    assert 0.0 <= result["score"] <= 10.0, f"score out of range: {result['score']}"


def test_diagnose_weakness() -> None:
    """Backward chaining: diagnose weaknesses from an evaluation result."""
    from inference_engine import diagnose_weakness, evaluate_answer

    result = evaluate_answer("um so basically like it is you know a thing", "Artificial Intelligence")
    diagnosis = diagnose_weakness(result)
    assert isinstance(diagnosis, list), f"expected list, got {type(diagnosis).__name__}"
    assert all(isinstance(d, str) for d in diagnosis), "diagnosis entries must be strings"


def test_text_analyzer_fillers() -> None:
    """Filler detection: 'Um so basically ... like' must be flagged."""
    from text_analyzer import analyze_text

    analysis = analyze_text("Um so basically AI is like, you know, um, the field of machines.")
    assert isinstance(analysis, dict), f"expected dict, got {type(analysis).__name__}"
    assert "filler_count" in analysis, "'filler_count' key missing"
    assert analysis["filler_count"] >= 1, (
        f"expected >= 1 filler, got {analysis['filler_count']} "
        f"({analysis.get('filler_words_found')})"
    )
    assert isinstance(analysis.get("filler_words_found"), list), "'filler_words_found' missing"


def test_csp_question_generation() -> None:
    """CSP generator: produce exactly 3 questions for a topic."""
    from csp_question_gen import generate_viva_questions

    questions = generate_viva_questions("Artificial Intelligence", count=3)
    assert isinstance(questions, list), f"expected list, got {type(questions).__name__}"
    assert len(questions) == 3, f"expected 3 questions, got {len(questions)}"
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)), f"duplicate questions returned: {ids}"
    for q in questions:
        assert "question" in q and "difficulty" in q, f"question dict incomplete: {q}"


def test_astar_improvement_path() -> None:
    """A* search: find a study plan for weak topics."""
    from astar_improvement import find_improvement_path

    plan = find_improvement_path({"AI": 4.0, "DSA": 7.5})
    assert isinstance(plan, list), f"expected list, got {type(plan).__name__}"
    assert len(plan) >= 1, "expected at least 1 study step (AI score 4.0 < 7.0)"
    first = plan[0]
    for key in ("topic", "hours_needed", "priority", "action"):
        assert key in first, f"plan step missing '{key}'; got keys {list(first)}"


def test_goal_stack_plan() -> None:
    """Goal stack planner: build steps from a performance report."""
    from goal_stack_planner import generate_study_plan

    steps = generate_study_plan({"score": 4.5})
    assert isinstance(steps, list), f"expected list, got {type(steps).__name__}"
    assert len(steps) >= 1, "expected at least 1 plan step for score 4.5"
    first = steps[0]
    for key in ("step", "goal", "action"):
        assert key in first, f"plan step missing '{key}'; got keys {list(first)}"


def test_slide_analyzer_graceful_error() -> None:
    """Slide analyzer: nonexistent file must return an error dict, not crash."""
    from slide_analyzer import analyze_presentation

    result = analyze_presentation("nonexistent.pptx")
    assert isinstance(result, dict), f"expected dict, got {type(result).__name__}"
    assert result.get("overall_score") == 0.0, (
        f"expected 0.0 score for missing file, got {result.get('overall_score')}"
    )
    assert result.get("weaknesses"), "expected a weakness/error message"


def test_all_modules_import() -> None:
    """Integration: every project module must import without ImportError."""
    modules = [
        "inference_engine",
        "text_analyzer",
        "csp_question_gen",
        "astar_improvement",
        "goal_stack_planner",
        "slide_analyzer",
        "speech_module",
    ]
    for name in modules:
        importlib.import_module(name)


def test_speech_module_availability() -> None:
    """Speech module: availability probe returns a structured dict."""
    from speech_module import is_speech_available

    status = is_speech_available()
    assert isinstance(status, dict), f"expected dict, got {type(status).__name__}"


# ---------------------------------------------------------------------------
#  MAIN
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 68)
    print("  VivaLens AI — End-to-End Test Suite")
    print("  FORGE | run: python test_all.py")
    print("=" * 68)
    print()

    run_test(1, "knowledge_base.json has 5 topics", test_knowledge_base_topics)
    run_test(2, "evaluate_answer returns dict with score", test_evaluate_answer)
    run_test(3, "diagnose_weakness returns list", test_diagnose_weakness)
    run_test(4, "text_analyzer detects fillers", test_text_analyzer_fillers)
    run_test(5, "csp generates 3 questions", test_csp_question_generation)
    run_test(6, "A* returns improvement plan", test_astar_improvement_path)
    run_test(7, "goal stack returns plan steps", test_goal_stack_plan)
    run_test(8, "slide_analyzer graceful on missing file", test_slide_analyzer_graceful_error)
    run_test(9, "all 7 modules import cleanly", test_all_modules_import)
    run_test(10, "speech_module availability probe", test_speech_module_availability)

    # --- Summary ---
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed

    print()
    print("=" * 68)
    for title, ok, err in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {title}")
        if err:
            print(f"         {err}")
    print("-" * 68)
    print(f"  TOTAL: {len(RESULTS)} | PASSED: {passed} | FAILED: {failed}")
    print("=" * 68)

    if failed:
        print("  RESULT: FAILURES DETECTED — see details above.")
        return 1
    print("  RESULT: ALL TESTS PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
