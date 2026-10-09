"""
inference_engine.py — VivaLens AI
==================================
Forward & Backward Chaining Inference Engine for Viva Answer Evaluation.

Author : NEXUS (Knowledge & Logic Architect)
Version: 1.1  (Enhancement release)
License: Free / Academic

Changelog:
  v1.1 — Added "suggested_followup_questions" to evaluate_answer() output.
         Generates 2-3 follow-up questions from missing keywords and KB.
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import Optional

# Windows consoles default to cp1252, which cannot encode symbols like '→'.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
#  KNOWLEDGE BASE LOADER
# ---------------------------------------------------------------------------

_KB_CACHE: Optional[dict] = None


def _get_kb_path() -> Path:
    """Return the absolute path to knowledge_base.json."""
    return Path(__file__).parent / "knowledge_base.json"


def load_knowledge_base(force_reload: bool = False) -> dict:
    """Load and cache the knowledge base JSON."""
    global _KB_CACHE
    if _KB_CACHE is not None and not force_reload:
        return _KB_CACHE

    kb_path = _get_kb_path()
    if not kb_path.exists():
        raise FileNotFoundError(
            f"Knowledge base not found at {kb_path}."
        )

    with open(kb_path, "r", encoding="utf-8") as f:
        _KB_CACHE = json.load(f)

    return _KB_CACHE


# ---------------------------------------------------------------------------
#  TEXT FEATURE EXTRACTION HELPERS
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lowercase and split text into word tokens."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in cleaned.split() if w]


def _count_fillers(tokens: list[str], filler_list: list[str]) -> int:
    """Count occurrences of filler words/phrases."""
    count = 0
    joined = " ".join(tokens)
    for filler in filler_list:
        filler_lower = filler.lower().strip()
        if " " in filler_lower:
            count += joined.count(filler_lower)
        else:
            count += tokens.count(filler_lower)
    return count


def _find_keyword_matches(
    tokens: list[str],
    keyword_list: list[str]
) -> tuple[list[str], list[str]]:
    """Find which keywords appear in the answer tokens."""
    joined = " ".join(tokens)
    found: list[str] = []
    missing: list[str] = []
    for kw in keyword_list:
        kw_lower = kw.lower().strip()
        if " " in kw_lower:
            if kw_lower in joined:
                found.append(kw)
            else:
                missing.append(kw)
        else:
            if kw_lower in tokens:
                found.append(kw)
            else:
                missing.append(kw)
    return found, missing


def _check_phrases(tokens: list[str], phrases: list[str]) -> bool:
    """Check if any of the given phrases appear in the answer."""
    joined = " ".join(tokens)
    for phrase in phrases:
        if phrase.lower() in joined:
            return True
    return False


def _count_phrase_matches(tokens: list[str], phrases: list[str]) -> int:
    """Count how many distinct phrases from a list appear."""
    joined = " ".join(tokens)
    count = 0
    for phrase in phrases:
        if phrase.lower() in joined:
            count += 1
    return count


# ---------------------------------------------------------------------------
#  [NEW] FOLLOW-UP QUESTION GENERATOR
# ---------------------------------------------------------------------------

def _generate_followup_questions(
    missing_keywords: list[str],
    topic: str,
    kb: dict,
    max_questions: int = 3
) -> list[str]:
    """
    Generate 2-3 follow-up questions based on missing keywords and
    the knowledge base.

    Strategy:
      1. Pick the most important missing keywords (up to max_questions).
      2. If a question_id's ideal_keywords overlap with missing ones,
         reference that concept.
      3. Format as natural viva-style follow-up questions.

    Args:
        missing_keywords: Keywords the student failed to mention.
        topic: Resolved topic name from the KB.
        kb: The full knowledge base dictionary.
        max_questions: Maximum number of follow-ups to generate.

    Returns:
        List of follow-up question strings.
    """
    if not missing_keywords:
        return [
            "Can you provide a real-world example of this concept?",
            "How does this topic connect to other areas you've studied?"
        ]

    questions: list[str] = []
    topics_db = kb.get("topics", {})

    # Resolve topic data
    topic_data = None
    for t_name, t_data in topics_db.items():
        if topic and (topic.lower() in t_name.lower() or t_name.lower() in topic.lower()):
            topic_data = t_data
            break

    # --- Strategy 1: Questions from missing keywords directly ---
    # Prioritize multi-word keywords (more specific = better questions)
    sorted_missing = sorted(
        missing_keywords,
        key=lambda kw: (len(kw.split()), len(kw)),
        reverse=True
    )

    for kw in sorted_missing:
        if len(questions) >= max_questions:
            break

        kw_title = kw.title()

        # Generate contextual question based on keyword type
        kw_lower = kw.lower()
        if any(term in kw_lower for term in ["sort", "search", "algorithm"]):
            questions.append(
                f"Can you explain how {kw_title} works and discuss "
                f"its time complexity?"
            )
        elif any(term in kw_lower for term in ["layer", "protocol", "tcp", "udp"]):
            questions.append(
                f"What is the role of {kw_title} in the overall "
                f"network architecture?"
            )
        elif any(term in kw_lower for term in ["normal", "acid", "transaction"]):
            questions.append(
                f"Can you elaborate on {kw_title} and why it is "
                f"important in database systems?"
            )
        elif any(term in kw_lower for term in ["deadlock", "paging", "scheduling", "thread"]):
            questions.append(
                f"How does {kw_title} work in an operating system, "
                f"and what problems does it solve?"
            )
        elif any(term in kw_lower for term in ["tree", "graph", "hash", "heap"]):
            questions.append(
                f"Can you describe the structure and operations "
                f"of a {kw_title}?"
            )
        else:
            questions.append(
                f"Can you elaborate on {kw_title} and its significance "
                f"in this topic?"
            )

    # --- Strategy 2: If we still need more, pull from sample questions ---
    if len(questions) < 2 and topic_data:
        sample_qs = topic_data.get("sample_questions", [])
        for sq in sample_qs:
            if len(questions) >= max_questions:
                break
            q_text = sq.get("question", "")
            # Avoid duplicating concepts already covered
            if q_text and not any(q_text[:30] in q for q in questions):
                questions.append(f"Follow-up: {q_text}")

    return questions[:max_questions]


# ---------------------------------------------------------------------------
#  FORWARD CHAINING — ANSWER EVALUATION
# ---------------------------------------------------------------------------

def evaluate_answer(
    answer_text: str,
    topic: str,
    question_id: Optional[str] = None
) -> dict:
    """
    Evaluate a viva answer using Forward Chaining against the knowledge base.

    Args:
        answer_text:  The student's spoken/written answer.
        topic:        One of the 5 KB topics.
        question_id:  Optional question ID for ideal_keyword matching.

    Returns:
        dict with keys:
            - score (float, 0–10)
            - matched_rules (list[str])
            - missing_keywords (list[str])
            - found_keywords (list[str])
            - verdict (str)
            - reasoning_trace (list[str])
            - details (dict)
            - suggested_followup_questions (list[str])  [NEW in v1.1]
    """
    kb = load_knowledge_base()
    meta = kb["meta"]
    trace: list[str] = []
    matched_rules: list[str] = []
    score: float = 5.0

    # --- Edge case: empty answer ---
    if not answer_text or not answer_text.strip():
        return {
            "score": 0.0,
            "matched_rules": [],
            "missing_keywords": [],
            "found_keywords": [],
            "verdict": "Poor",
            "reasoning_trace": ["No answer provided."],
            "details": {"word_count": 0, "filler_count": 0},
            # [NEW] Follow-up for empty answer
            "suggested_followup_questions": [
                "Can you define the core concept being asked about?",
                "What are the key components or properties of this topic?",
                "Can you give a simple example to illustrate your understanding?"
            ]
        }

    # --- Extract features ---
    tokens = _tokenize(answer_text)
    word_count = len(tokens)
    filler_words = meta.get("global_filler_words", [])
    filler_count = _count_fillers(tokens, filler_words)

    trace.append(f"[FACT] Word count: {word_count}")
    trace.append(f"[FACT] Filler count: {filler_count}")

    # --- Resolve topic ---
    topics_db = kb.get("topics", {})
    resolved_topic = None
    for t_name in topics_db:
        if topic.lower() in t_name.lower() or t_name.lower() in topic.lower():
            resolved_topic = t_name
            break

    if resolved_topic is None:
        trace.append(f"[WARN] Topic '{topic}' not found in KB.")
        topic_data = None
        found_kw: list[str] = []
        missing_kw: list[str] = []
    else:
        topic_data = topics_db[resolved_topic]
        trace.append(f"[FACT] Resolved topic: {resolved_topic}")

        if question_id and "sample_questions" in topic_data:
            q_data = None
            for q in topic_data["sample_questions"]:
                if q["id"] == question_id:
                    q_data = q
                    break
            if q_data:
                kw_list = q_data.get("ideal_keywords", [])
                trace.append(
                    f"[FACT] Using ideal_keywords for {question_id} "
                    f"({len(kw_list)} keywords)"
                )
            else:
                kw_list = topic_data.get("expected_keywords", [])
                trace.append(
                    f"[WARN] question_id '{question_id}' not found; "
                    "falling back to topic keywords"
                )
        else:
            kw_list = topic_data.get("expected_keywords", [])

        found_kw, missing_kw = _find_keyword_matches(tokens, kw_list)
        trace.append(
            f"[FACT] Keywords matched: {len(found_kw)}/{len(kw_list)}"
        )

    # =====================================================================
    #  FIRE GLOBAL RULES
    # =====================================================================
    global_rules = meta.get("global_rules", [])

    for rule in global_rules:
        rid = rule["rule_id"]
        rtype = rule.get("type", "")
        fired = False

        if rtype == "length_check":
            condition = rule.get("condition", "")
            if "word_count < 15" in condition and word_count < 15:
                fired = True
            elif "40 <= word_count <= 200" in condition and 40 <= word_count <= 200:
                fired = True
            elif "word_count > 300" in condition and word_count > 300:
                fired = True

        elif rtype == "filler_penalty":
            condition = rule.get("condition", "")
            if "3 <= filler_count <= 5" in condition and 3 <= filler_count <= 5:
                fired = True
            elif "filler_count > 5" in condition and filler_count > 5:
                fired = True
            elif (
                "filler_count == 0 and word_count >= 20" in condition
                and filler_count == 0 and word_count >= 20
            ):
                fired = True

        elif rtype == "structure":
            markers = rule.get("structure_markers", [])
            if _check_phrases(tokens, markers):
                fired = True

        if fired:
            matched_rules.append(rid)
            penalty = rule.get("penalty", 0.0)
            bonus = rule.get("bonus", 0.0)
            score += bonus + penalty
            direction = "BONUS" if bonus > 0 else "PENALTY"
            trace.append(
                f"[FIRE {direction}] {rid}: {rule.get('reason', '')} "
                f"({bonus:+.1f} bonus, {penalty:+.1f} penalty)"
            )

    # =====================================================================
    #  FIRE TOPIC-SPECIFIC RULES
    # =====================================================================
    if topic_data is not None:
        topic_rules = topic_data.get("rules", [])
        matched_kw_count = len(found_kw)

        for rule in topic_rules:
            rid = rule["rule_id"]
            rtype = rule.get("type", "")
            fired = False

            if rtype == "keyword_threshold":
                condition = rule.get("condition", "")
                if "matched_keywords >= 4" in condition and matched_kw_count >= 4:
                    fired = True
                elif "matched_keywords <= 1" in condition and matched_kw_count <= 1:
                    fired = True

            elif rtype == "completeness":
                condition = rule.get("condition", "")
                if "contains_definition_phrase" in condition:
                    def_phrases = rule.get("definition_phrases", [])
                    if _check_phrases(tokens, def_phrases):
                        fired = True
                elif "contains_numbered_list" in condition:
                    numbered = re.findall(
                        r"\b(?:1st|2nd|3rd|4th|first|second|third|fourth|"
                        r"1\.|2\.|3\.|4\.)\b",
                        " ".join(tokens)
                    )
                    if len(numbered) >= 2:
                        fired = True

            elif rtype == "depth":
                condition = rule.get("condition", "")
                if "contains_example_phrase" in condition:
                    ex_phrases = rule.get("example_phrases", [])
                    if _check_phrases(tokens, ex_phrases):
                        fired = True
                elif "contains_complexity_notation" in condition:
                    c_patterns = rule.get("complexity_patterns", [])
                    if _check_phrases(tokens, c_patterns):
                        fired = True
                elif "contains_step_phrases" in condition:
                    s_phrases = rule.get("step_phrases", [])
                    if _count_phrase_matches(tokens, s_phrases) >= 3:
                        fired = True
                elif "contains_mechanism_phrases" in condition:
                    m_phrases = rule.get("mechanism_phrases", [])
                    if _count_phrase_matches(tokens, m_phrases) >= 2:
                        fired = True
                elif "expands_acronyms" in condition:
                    expansions = rule.get("acronym_expansions", {})
                    expansion_found = False
                    for acronym, terms in expansions.items():
                        if acronym.lower() in " ".join(tokens):
                            for term in terms:
                                if term.lower() in " ".join(tokens):
                                    expansion_found = True
                                    break
                        if expansion_found:
                            break
                    if expansion_found:
                        fired = True
                elif "contains_comparison_phrases" in condition:
                    comp_phrases = rule.get("comparison_phrases", [])
                    if _count_phrase_matches(tokens, comp_phrases) >= 2:
                        fired = True

            if fired:
                matched_rules.append(rid)
                penalty = rule.get("penalty", 0.0)
                bonus = rule.get("bonus", 0.0)
                score += bonus + penalty
                direction = "BONUS" if bonus > 0 else "PENALTY"
                trace.append(
                    f"[FIRE {direction}] {rid}: {rule.get('reason', '')} "
                    f"({bonus:+.1f} bonus, {penalty:+.1f} penalty)"
                )

    # =====================================================================
    #  KEYWORD RATIO ADJUSTMENT
    # =====================================================================
    if topic_data is not None:
        total_expected = len(found_kw) + len(missing_kw)
        if total_expected > 0:
            ratio = len(found_kw) / total_expected
            kw_adjustment = (ratio - 0.5) * 4.0
            score += kw_adjustment
            trace.append(
                f"[ADJUST] Keyword ratio {ratio:.2f} → "
                f"score adjustment {kw_adjustment:+.2f}"
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
        verdict = "Weak"
    else:
        verdict = "Poor"

    trace.append(f"[RESULT] Final score: {score}/10 — {verdict}")

    # =====================================================================
    #  [NEW] GENERATE FOLLOW-UP QUESTIONS
    # =====================================================================
    followup_questions = _generate_followup_questions(
        missing_keywords=missing_kw,
        topic=resolved_topic or topic,
        kb=kb,
        max_questions=3
    )
    trace.append(
        f"[FOLLOWUP] Generated {len(followup_questions)} "
        "suggested follow-up questions"
    )

    return {
        "score": score,
        "matched_rules": matched_rules,
        "missing_keywords": missing_kw[:15],
        "found_keywords": found_kw,
        "verdict": verdict,
        "reasoning_trace": trace,
        "details": {
            "word_count": word_count,
            "filler_count": filler_count,
            "topic_resolved": resolved_topic,
            "question_id": question_id,
            "keyword_ratio": (
                round(len(found_kw) / (len(found_kw) + len(missing_kw)), 2)
                if (found_kw or missing_kw) else 0.0
            )
        },
        # [NEW] Follow-up questions for the viva examiner / student
        "suggested_followup_questions": followup_questions,
    }


# ---------------------------------------------------------------------------
#  BACKWARD CHAINING — WEAKNESS DIAGNOSIS
# ---------------------------------------------------------------------------

def diagnose_weakness(evaluation_result: dict) -> list[str]:
    """
    Diagnose WHY an answer scored low using Backward Chaining.

    Args:
        evaluation_result: The dict returned by evaluate_answer().

    Returns:
        List of human-readable diagnosis strings.
    """
    diagnoses: list[str] = []
    score = evaluation_result.get("score", 5.0)
    details = evaluation_result.get("details", {})
    matched_rules = evaluation_result.get("matched_rules", [])
    missing_kw = evaluation_result.get("missing_keywords", [])
    found_kw = evaluation_result.get("found_keywords", [])

    word_count = details.get("word_count", 0)
    filler_count = details.get("filler_count", 0)
    kw_ratio = details.get("keyword_ratio", 0.0)

    is_low = score < 5.0
    is_moderate = 5.0 <= score < 7.0

    # --- Chain 1: Keyword Deficiency ---
    if kw_ratio < 0.3 and len(missing_kw) > 5:
        diagnoses.append(
            f"CRITICAL — Lack of conceptual terms: Only {len(found_kw)} "
            f"keywords found. Missing: {', '.join(missing_kw[:5])}."
        )
    elif kw_ratio < 0.5:
        diagnoses.append(
            f"MODERATE — Insufficient vocabulary: {kw_ratio:.0%} coverage. "
            f"Add terms like: {', '.join(missing_kw[:4])}."
        )

    # --- Chain 2: Brevity ---
    if word_count < 15:
        diagnoses.append(
            f"CRITICAL — Answer too brief ({word_count} words). "
            "Aim for 40–80 words minimum."
        )
    elif word_count < 40 and is_low:
        diagnoses.append(
            f"MODERATE — Somewhat short ({word_count} words). "
            "Expand with details and examples."
        )

    # --- Chain 3: Fillers ---
    if filler_count > 5:
        diagnoses.append(
            f"CRITICAL — Excessive fillers ({filler_count}). "
            "Practice pausing silently instead."
        )
    elif filler_count >= 3:
        diagnoses.append(
            f"MODERATE — Noticeable fillers ({filler_count}). "
            "Reduce verbal crutches."
        )

    # --- Chain 4: Structure ---
    if "GR07_STRUCTURE_BONUS" not in matched_rules:
        diagnoses.append(
            "MODERATE — Lacks organized structure. Use signposting "
            "phrases like 'Firstly...', 'In conclusion...'."
        )

    # --- Chain 5: Definition ---
    definition_rules = [r for r in matched_rules if "DEFINITION" in r]
    if not definition_rules and word_count >= 15:
        diagnoses.append(
            "MODERATE — Missing foundational definition. "
            "Start with 'X is defined as...'."
        )

    # --- Chain 6: Example ---
    example_rules = [r for r in matched_rules if "EXAMPLE" in r]
    if not example_rules and word_count >= 20:
        diagnoses.append(
            "MINOR — No practical example. Include a real-world "
            "or textbook example."
        )

    # --- Chain 7: Depth ---
    depth_rules = [
        r for r in matched_rules
        if any(k in r for k in ["COMPLEXITY", "DEPTH", "DETAIL",
                                 "ALGORITHM", "PROTOCOL", "COMPARISON"])
    ]
    if not depth_rules and is_moderate:
        diagnoses.append(
            "MINOR — Lacks analytical depth. Include complexity "
            "analysis or comparisons."
        )

    # --- Chain 8: Rambling ---
    if "GR03_EXCESSIVE_LENGTH" in matched_rules:
        diagnoses.append(
            "MINOR — Excessively long (>300 words). Be more concise."
        )

    # --- Fallback ---
    if not diagnoses:
        if score >= 8.5:
            diagnoses.append("EXCELLENT — Strong answer. Keep it up!")
        elif score >= 7.0:
            diagnoses.append(
                "GOOD — Solid answer. Add more depth for 'Excellent'."
            )
        else:
            diagnoses.append(
                "AVERAGE — Decent foundation. Add more keywords "
                "and structure."
            )

    return diagnoses


# ---------------------------------------------------------------------------
#  TEST SUITE
# ---------------------------------------------------------------------------

def test_inference() -> None:
    """
    Built-in test suite. Run: python inference_engine.py
    """
    print("=" * 70)
    print("  VivaLens AI — Inference Engine Test Suite (v1.1)")
    print("  Agent: NEXUS | Module: inference_engine.py")
    print("=" * 70)

    # ---- TEST 1: Strong AI Answer ----
    print("\n--- TEST 1: Strong AI Answer (A* Search) ---")
    strong_answer = (
        "A* search is defined as an informed search algorithm that uses "
        "a heuristic function h(n) combined with the path cost g(n) to "
        "compute f(n) = g(n) + h(n). It maintains an open list and a "
        "closed list. A* is optimal when the heuristic is admissible, "
        "meaning it never overestimates the true cost to the goal. "
        "For example, in pathfinding on a grid, the Manhattan distance "
        "is an admissible heuristic. The algorithm is complete and "
        "guarantees the shortest path."
    )
    result1 = evaluate_answer(strong_answer, "Artificial Intelligence", "AI_Q01")
    _print_result(result1)
    diag1 = diagnose_weakness(result1)
    _print_diagnosis(diag1)
    _print_followups(result1)  # [NEW]

    # ---- TEST 2: Weak OS Answer ----
    print("\n--- TEST 2: Weak OS Answer (Deadlocks) ---")
    weak_answer = (
        "Um, so deadlock is like, basically when processes are stuck, "
        "you know, and they can't, um, proceed. It's like, sort of a "
        "problem in operating systems. I guess it happens when, like, "
        "resources are, um, not available."
    )
    result2 = evaluate_answer(weak_answer, "Operating Systems", "OS_Q01")
    _print_result(result2)
    diag2 = diagnose_weakness(result2)
    _print_diagnosis(diag2)
    _print_followups(result2)  # [NEW]

    # ---- TEST 3: Average DBMS Answer ----
    print("\n--- TEST 3: Average DBMS Answer (ACID) ---")
    avg_answer = (
        "ACID properties are important for database transactions. "
        "Atomicity means the transaction is all or nothing. Consistency "
        "ensures the database remains valid. Isolation means concurrent "
        "transactions don't interfere. Durability means once committed, "
        "data is permanent. These properties ensure data integrity."
    )
    result3 = evaluate_answer(avg_answer, "Database Management", "DB_Q02")
    _print_result(result3)
    diag3 = diagnose_weakness(result3)
    _print_diagnosis(diag3)
    _print_followups(result3)  # [NEW]

    # ---- TEST 4: Empty Answer ----
    print("\n--- TEST 4: Empty Answer ---")
    result4 = evaluate_answer("", "Computer Networks")
    _print_result(result4)
    diag4 = diagnose_weakness(result4)
    _print_diagnosis(diag4)
    _print_followups(result4)  # [NEW]

    # ---- TEST 5: Unknown Topic ----
    print("\n--- TEST 5: Unknown Topic ---")
    result5 = evaluate_answer(
        "This is a test answer about an unknown topic.",
        "Quantum Computing"
    )
    _print_result(result5)
    diag5 = diagnose_weakness(result5)
    _print_diagnosis(diag5)
    _print_followups(result5)  # [NEW]

    print("\n" + "=" * 70)
    print("  All tests completed successfully.")
    print("=" * 70)


def _print_result(result: dict) -> None:
    """Pretty-print an evaluation result."""
    print(f"  Score   : {result['score']}/10  [{result['verdict']}]")
    print(f"  Keywords: {len(result['found_keywords'])} found, "
          f"{len(result['missing_keywords'])} missing")
    print(f"  Rules   : {', '.join(result['matched_rules']) or 'None'}")
    print(f"  Trace   :")
    for line in result["reasoning_trace"]:
        print(f"    {line}")


def _print_diagnosis(diagnoses: list[str]) -> None:
    """Pretty-print backward chaining diagnoses."""
    print(f"  Diagnosis ({len(diagnoses)} findings):")
    for d in diagnoses:
        print(f"    → {d}")


def _print_followups(result: dict) -> None:
    """[NEW] Pretty-print suggested follow-up questions."""
    followups = result.get("suggested_followup_questions", [])
    print(f"  Follow-up Questions ({len(followups)}):")
    for i, q in enumerate(followups, 1):
        print(f"    {i}. {q}")


# ---------------------------------------------------------------------------
#  ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_inference()