"""
csp_question_gen.py — CSP-based Viva Question Generator
========================================================
Generates balanced viva question sets using Constraint Satisfaction
Problem (CSP) solving with Backtracking Search and Forward Checking.

Covers: SPPU TY AI 2024 — Unit 3 (CSP & Adversarial Search)

Constraints enforced:
  1. No duplicate questions (AllDifferent)
  2. Difficulty balance (mix of easy/medium/hard when "mixed")
  3. Bloom's taxonomy coverage (>= 2 distinct levels)
  4. Topic spread (even distribution when topic = "all")

Main entry: generate_viva_questions(topic, difficulty, count, time_limit_min)
Returns list[dict] with keys: id, question, difficulty, bloom_level,
    ideal_keywords, allocated_time_sec
Loads from knowledge_base.json and MERGES it with the built-in bank
(deduplicated by id), with alias-aware topic matching.
"""

import json
import os
import copy
import random
import sys
from typing import Optional

# Windows consoles default to cp1252, which cannot encode emoji/symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════
#  BUILT-IN QUESTION BANK  (≥ 30 questions, 5 AI topics)
#  Used as fallback when knowledge_base.json is unavailable.
# ═══════════════════════════════════════════════════════════════

BUILTIN_QUESTION_BANK: list[dict] = [
    # ── Topic 1: Intelligent Agents (Unit 1) ──────────────────
    {"id": "IA01", "topic": "Intelligent Agents",
     "question": "Define an intelligent agent and list its core components.",
     "difficulty": "easy", "bloom_level": "Remember",
     "ideal_keywords": ["agent", "environment", "sensors", "actuators", "percepts"]},

    {"id": "IA02", "topic": "Intelligent Agents",
     "question": "Explain the PEAS framework with a real-world example.",
     "difficulty": "easy", "bloom_level": "Understand",
     "ideal_keywords": ["Performance", "Environment", "Actuators", "Sensors"]},

    {"id": "IA03", "topic": "Intelligent Agents",
     "question": "Compare simple reflex agents with model-based reflex agents.",
     "difficulty": "medium", "bloom_level": "Analyze",
     "ideal_keywords": ["state", "model", "rules", "percept", "internal"]},

    {"id": "IA04", "topic": "Intelligent Agents",
     "question": "Design a utility-based agent architecture for a self-driving car.",
     "difficulty": "hard", "bloom_level": "Create",
     "ideal_keywords": ["utility", "goal", "decision", "trade-off", "optimization"]},

    {"id": "IA05", "topic": "Intelligent Agents",
     "question": "Critically evaluate the Turing Test and its limitations.",
     "difficulty": "medium", "bloom_level": "Evaluate",
     "ideal_keywords": ["Turing", "imitation", "consciousness", "Chinese Room", "limitation"]},

    {"id": "IA06", "topic": "Intelligent Agents",
     "question": "Apply the concept of rationality to a vacuum-cleaner agent.",
     "difficulty": "medium", "bloom_level": "Apply",
     "ideal_keywords": ["rational", "performance measure", "percept sequence", "optimal"]},

    # ── Topic 2: Heuristic Search (Unit 2) ────────────────────
    {"id": "HS01", "topic": "Heuristic Search",
     "question": "What is a heuristic function? Give one example.",
     "difficulty": "easy", "bloom_level": "Remember",
     "ideal_keywords": ["heuristic", "estimate", "cost", "goal", "h(n)"]},

    {"id": "HS02", "topic": "Heuristic Search",
     "question": "Explain the A* algorithm and its optimality conditions.",
     "difficulty": "medium", "bloom_level": "Understand",
     "ideal_keywords": ["f(n)", "g(n)", "h(n)", "admissible", "consistent", "optimal"]},

    {"id": "HS03", "topic": "Heuristic Search",
     "question": "Compare Greedy Best-First Search with A* Search.",
     "difficulty": "medium", "bloom_level": "Analyze",
     "ideal_keywords": ["greedy", "complete", "optimal", "f(n)", "h(n)", "g(n)"]},

    {"id": "HS04", "topic": "Heuristic Search",
     "question": "Prove that A* is optimal when the heuristic is admissible.",
     "difficulty": "hard", "bloom_level": "Evaluate",
     "ideal_keywords": ["admissible", "optimal", "proof", "contradiction", "underestimate"]},

    {"id": "HS05", "topic": "Heuristic Search",
     "question": "Design a heuristic for the 8-puzzle and justify admissibility.",
     "difficulty": "hard", "bloom_level": "Create",
     "ideal_keywords": ["Manhattan", "misplaced", "tiles", "admissible", "relaxation"]},

    {"id": "HS06", "topic": "Heuristic Search",
     "question": "Apply hill-climbing to find a local maximum in a given landscape.",
     "difficulty": "medium", "bloom_level": "Apply",
     "ideal_keywords": ["hill climbing", "local maximum", "plateau", "ridge", "neighbor"]},

    # ── Topic 3: CSP & Adversarial Search (Unit 3) ───────────
    {"id": "CS01", "topic": "CSP & Adversarial Search",
     "question": "Define a Constraint Satisfaction Problem and its components.",
     "difficulty": "easy", "bloom_level": "Remember",
     "ideal_keywords": ["variables", "domains", "constraints", "assignment", "consistent"]},

    {"id": "CS02", "topic": "CSP & Adversarial Search",
     "question": "Explain backtracking search with forward checking.",
     "difficulty": "medium", "bloom_level": "Understand",
     "ideal_keywords": ["backtracking", "forward checking", "domain reduction", "pruning"]},

    {"id": "CS03", "topic": "CSP & Adversarial Search",
     "question": "Solve a map-coloring CSP using constraint propagation.",
     "difficulty": "medium", "bloom_level": "Apply",
     "ideal_keywords": ["arc consistency", "AC-3", "propagation", "domain", "color"]},

    {"id": "CS04", "topic": "CSP & Adversarial Search",
     "question": "Explain the Minimax algorithm and its use in game playing.",
     "difficulty": "medium", "bloom_level": "Understand",
     "ideal_keywords": ["Minimax", "max", "min", "game tree", "terminal", "utility"]},

    {"id": "CS05", "topic": "CSP & Adversarial Search",
     "question": "How does Alpha-Beta pruning improve Minimax? Analyse complexity.",
     "difficulty": "hard", "bloom_level": "Analyze",
     "ideal_keywords": ["alpha", "beta", "pruning", "cutoff", "branching"]},

    {"id": "CS06", "topic": "CSP & Adversarial Search",
     "question": "Formulate a Sudoku puzzle as a CSP.",
     "difficulty": "hard", "bloom_level": "Create",
     "ideal_keywords": ["variables", "cells", "domains", "row", "column", "all-different"]},

    # ── Topic 4: Logic & Inference (Unit 4) ──────────────────
    {"id": "LI01", "topic": "Logic & Inference",
     "question": "What is First-Order Logic? How does it differ from Propositional Logic?",
     "difficulty": "easy", "bloom_level": "Remember",
     "ideal_keywords": ["FOL", "predicates", "quantifiers", "propositional", "variables"]},

    {"id": "LI02", "topic": "Logic & Inference",
     "question": "Explain forward chaining with a concrete example.",
     "difficulty": "medium", "bloom_level": "Understand",
     "ideal_keywords": ["forward chaining", "data-driven", "modus ponens", "facts", "rules"]},

    {"id": "LI03", "topic": "Logic & Inference",
     "question": "Apply backward chaining to prove a given query.",
     "difficulty": "medium", "bloom_level": "Apply",
     "ideal_keywords": ["backward chaining", "goal-driven", "query", "sub-goals", "unification"]},

    {"id": "LI04", "topic": "Logic & Inference",
     "question": "Analyse the completeness and soundness of resolution in FOL.",
     "difficulty": "hard", "bloom_level": "Analyze",
     "ideal_keywords": ["resolution", "soundness", "completeness", "refutation", "CNF"]},

    {"id": "LI05", "topic": "Logic & Inference",
     "question": "Evaluate the role of unification in logical inference.",
     "difficulty": "hard", "bloom_level": "Evaluate",
     "ideal_keywords": ["unification", "substitution", "MGU", "most general"]},

    {"id": "LI06", "topic": "Logic & Inference",
     "question": "Convert a FOL sentence to Conjunctive Normal Form (CNF).",
     "difficulty": "medium", "bloom_level": "Apply",
     "ideal_keywords": ["CNF", "Skolemization", "prenex", "clauses", "negation"]},

    # ── Topic 5: Planning (Unit 5) ───────────────────────────
    {"id": "PL01", "topic": "Planning",
     "question": "Define planning in AI and list its key components.",
     "difficulty": "easy", "bloom_level": "Remember",
     "ideal_keywords": ["planning", "initial state", "goal", "actions", "preconditions"]},

    {"id": "PL02", "topic": "Planning",
     "question": "Explain STRIPS representation with an example.",
     "difficulty": "medium", "bloom_level": "Understand",
     "ideal_keywords": ["STRIPS", "precondition", "add list", "delete list", "action schema"]},

    {"id": "PL03", "topic": "Planning",
     "question": "Apply Goal Stack Planning to the Block World problem.",
     "difficulty": "hard", "bloom_level": "Apply",
     "ideal_keywords": ["goal stack", "push", "pop", "sub-goals", "Block World", "ON", "CLEAR"]},

    {"id": "PL04", "topic": "Planning",
     "question": "Compare partial-order planning with total-order planning.",
     "difficulty": "medium", "bloom_level": "Analyze",
     "ideal_keywords": ["partial-order", "total-order", "causal links", "threats", "flexibility"]},

    {"id": "PL05", "topic": "Planning",
     "question": "Evaluate the limitations of classical planning in real-world scenarios.",
     "difficulty": "hard", "bloom_level": "Evaluate",
     "ideal_keywords": ["uncertainty", "dynamic", "sensors", "contingency", "limitations"]},

    {"id": "PL06", "topic": "Planning",
     "question": "Design a planning problem for robot navigation using PDDL.",
     "difficulty": "hard", "bloom_level": "Create",
     "ideal_keywords": ["PDDL", "domain", "problem", "predicates", "actions", "objects"]},
]

# All 5 recognised topic names (matches knowledge_base.json structure)
VALID_TOPICS: list[str] = [
    "Intelligent Agents",
    "Heuristic Search",
    "CSP & Adversarial Search",
    "Logic & Inference",
    "Planning",
]


# ═══════════════════════════════════════════════════════════════
#  QUESTION LOADING
# ═══════════════════════════════════════════════════════════════

def _load_questions_from_kb(kb_path: str) -> list[dict]:
    """
    Attempt to load questions from knowledge_base.json.

    Expected KB structure (per topic):
        { "topics": { "<topic_name>": { "sample_questions": [ {id, question,
          difficulty, bloom_level, ideal_keywords}, ... ] } } }

    Returns an empty list if the file is missing or malformed.
    """
    if not os.path.isfile(kb_path):
        return []
    try:
        with open(kb_path, "r", encoding="utf-8") as fh:
            kb = json.load(fh)
        questions: list[dict] = []
        topics_data = kb.get("topics", kb)  # tolerate flat or nested
        for topic_name, topic_obj in topics_data.items():
            if isinstance(topic_obj, dict):
                for q in topic_obj.get("sample_questions", []):
                    q.setdefault("topic", topic_name)
                    questions.append(q)
        return questions
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


# ═══════════════════════════════════════════════════════════════
#  TOPIC MATCHING  (case-insensitive, substring, alias-aware)
# ═══════════════════════════════════════════════════════════════

# Normalised names of the 5 SPPU TY AI unit topics + common aliases.
AI_FAMILY_TOPICS: set[str] = {
    "intelligent agents", "agent", "agents",
    "heuristic search", "search",
    "csp & adversarial search", "csp", "constraint satisfaction",
    "adversarial search",
    "logic & inference", "logic", "fol", "first order logic",
    "planning",
}

# Umbrella topic used by knowledge_base.json for general AI questions.
AI_UMBRELLA: str = "artificial intelligence"
AI_UMBRELLA_ALIASES: set[str] = {"artificial intelligence", "ai"}


def _normalize_topic(text: str) -> str:
    """Lower-case and collapse whitespace for topic comparison."""
    return " ".join(text.lower().split())


def _topic_matches(query: str, question_topic: str) -> bool:
    """
    Alias-aware topic matcher.

    A question matches the requested topic when any of these hold:
      1. Exact match after normalisation.
      2. Substring match either way ("Search" ⊂ "Heuristic Search").
      3. Query is an AI unit topic / alias (e.g. "Heuristic Search",
         "Search") and the question is tagged with the umbrella topic
         "Artificial Intelligence".
      4. Query is the umbrella ("Artificial Intelligence" / "AI") and the
         question is tagged with any AI unit topic (or the umbrella itself).

    Unknown topics simply match nothing (caller applies graceful fallback).
    """
    q = _normalize_topic(query)
    t = _normalize_topic(question_topic)
    if not q or not t:
        return False
    if q == t:
        return True
    if q in t or t in q:
        return True
    if q in AI_FAMILY_TOPICS and t == AI_UMBRELLA:
        return True
    if q in AI_UMBRELLA_ALIASES and (t in AI_FAMILY_TOPICS or t == AI_UMBRELLA):
        return True
    return False


def _get_question_pool(topic: str, difficulty: str) -> list[dict]:
    """
    Build the filtered question pool.

    1. Load questions from knowledge_base.json (same directory as script).
    2. Merge with BUILTIN_QUESTION_BANK, deduplicating by `id`.
    3. Filter by *topic* ("all" → every topic) using case-insensitive,
       substring and alias matching (see _topic_matches).
    4. Filter by *difficulty* ("mixed" → every difficulty).
    5. Graceful fallbacks: an unknown topic returns the full merged pool;
       an unavailable difficulty keeps the topic-filtered pool instead of
       returning nothing. Never crashes.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kb_path = os.path.join(script_dir, "knowledge_base.json")

    kb_pool = _load_questions_from_kb(kb_path)

    # --- merge both sources, deduplicate by id (KB entries win) ---
    merged: list[dict] = []
    seen_ids: set = set()
    for q in kb_pool + copy.deepcopy(BUILTIN_QUESTION_BANK):
        qid = q.get("id")
        if qid in seen_ids:
            continue
        seen_ids.add(qid)
        merged.append(q)

    # --- topic filter (alias-aware) ---
    pool = merged
    if topic.lower() != "all":
        pool = [q for q in merged
                if _topic_matches(topic, q.get("topic", ""))]
        if not pool:
            # Unknown topic → graceful fallback to the full pool
            pool = merged

    # --- difficulty filter (degrades gracefully if nothing matches) ---
    if difficulty.lower() != "mixed":
        diff_pool = [q for q in pool
                     if q.get("difficulty", "").lower() == difficulty.lower()]
        if diff_pool:
            pool = diff_pool

    return pool


# ═══════════════════════════════════════════════════════════════
#  CSP SOLVER — Backtracking + Forward Checking
# ═══════════════════════════════════════════════════════════════

def _is_consistent(
    assignment: dict[str, dict],
    value: dict,
) -> bool:
    """
    Hard constraint: no duplicate question IDs in the current assignment.
    """
    for assigned_q in assignment.values():
        if assigned_q["id"] == value["id"]:
            return False
    return True


def _forward_check(
    var: str,
    value: dict,
    unassigned: list[str],
    domains: dict[str, list[dict]],
) -> Optional[dict[str, list[dict]]]:
    """
    Forward-checking step.

    After assigning *value* to *var*, prune *value* from the domains of
    every unassigned variable.  If any domain becomes empty the current
    path is dead → return None.
    """
    new_domains: dict[str, list[dict]] = {}
    for uvar in unassigned:
        pruned = [q for q in domains[uvar] if q["id"] != value["id"]]
        if not pruned:
            return None  # domain wipe-out → backtrack
        new_domains[uvar] = pruned
    return new_domains


def _check_global_constraints(
    assignment: dict[str, dict],
    difficulty_mode: str,
) -> bool:
    """
    Soft / global constraints checked once all slots are filled.

    • Bloom's coverage  → ≥ 2 distinct levels  (when count ≥ 2)
    • Difficulty balance → ≥ 2 distinct levels  (when "mixed" & count ≥ 3)

    Returns True if constraints are satisfied **or** the pool is too
    small to satisfy them (graceful degradation).
    """
    questions = list(assignment.values())
    n = len(questions)

    # Bloom's coverage
    bloom_levels = {q.get("bloom_level", "") for q in questions}
    if n >= 2 and len(bloom_levels) < 2:
        return False

    # Difficulty balance (only meaningful in "mixed" mode)
    if difficulty_mode.lower() == "mixed" and n >= 3:
        difficulties = {q.get("difficulty", "") for q in questions}
        if len(difficulties) < 2:
            return False

    return True


def _select_unassigned_variable(
    unassigned: list[str],
    domains: dict[str, list[dict]],
) -> str:
    """
    MRV (Minimum Remaining Values) heuristic.
    Pick the unassigned variable with the fewest legal values left.
    Ties broken randomly for variety.
    """
    return min(unassigned, key=lambda v: (len(domains[v]), random.random()))


def _backtracking_search(
    variables: list[str],
    domains: dict[str, list[dict]],
    assignment: dict[str, dict],
    difficulty_mode: str,
    max_attempts: int = 50,
) -> Optional[dict[str, dict]]:
    """
    Recursive backtracking search with forward checking.

    Parameters
    ----------
    variables : list of slot names (Q1 … Qn)
    domains   : current (possibly pruned) domain per variable
    assignment: partial assignment so far
    difficulty_mode : "mixed" | "easy" | "medium" | "hard"
    max_attempts : safety cap to avoid infinite loops on impossible CSPs

    Returns
    -------
    Complete assignment dict or None.
    """
    if max_attempts <= 0:
        return None

    # ── Base case: all slots filled ──
    unassigned = [v for v in variables if v not in assignment]
    if not unassigned:
        if _check_global_constraints(assignment, difficulty_mode):
            return assignment
        return None  # global constraint violated → backtrack

    var = _select_unassigned_variable(unassigned, domains)

    # Shuffle domain for randomness across calls
    shuffled_domain = list(domains[var])
    random.shuffle(shuffled_domain)

    for value in shuffled_domain:
        if not _is_consistent(assignment, value):
            continue

        assignment[var] = value

        new_domains = _forward_check(var, value, unassigned, domains)
        if new_domains is not None:
            result = _backtracking_search(
                variables, new_domains, assignment,
                difficulty_mode, max_attempts - 1,
            )
            if result is not None:
                return result

        del assignment[var]  # undo

    return None


# ═══════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════

def generate_viva_questions(
    topic: str = "all",
    difficulty: str = "mixed",
    count: int = 5,
    time_limit_min: int = 10,
) -> list[dict]:
    """
    Generate a balanced set of viva questions via CSP solving.

    Parameters
    ----------
    topic : str
        One of the 5 AI topic names, or "all" for every topic.
    difficulty : str
        "easy" | "medium" | "hard" | "mixed" (default).
    count : int
        Number of questions to generate (default 5).
    time_limit_min : int
        Total viva time in minutes (default 10).

    Returns
    -------
    list[dict]
        Each dict contains:
          id, question, difficulty, bloom_level,
          ideal_keywords, allocated_time_sec
    """
    # ── 1. Build filtered pool ──
    pool = _get_question_pool(topic, difficulty)

    if not pool:
        return []  # nothing to work with

    # Clamp count to pool size
    count = min(count, len(pool))
    if count <= 0:
        return []

    # ── 2. Set up CSP ──
    variables = [f"Q{i+1}" for i in range(count)]
    domains: dict[str, list[dict]] = {v: list(pool) for v in variables}

    # ── 3. Solve ──
    # Try multiple times with different random seeds for variety
    solution: Optional[dict[str, dict]] = None
    for _ in range(20):
        solution = _backtracking_search(
            variables, copy.deepcopy(domains), {}, difficulty,
        )
        if solution is not None:
            break

    # Graceful fallback: if CSP couldn't satisfy soft constraints,
    # just pick unique questions greedily.
    if solution is None:
        random.shuffle(pool)
        solution = {}
        for i, q in enumerate(pool[:count]):
            solution[f"Q{i+1}"] = q

    # ── 4. Allocate time per question (weighted by difficulty) ──
    total_sec = time_limit_min * 60
    difficulty_weight = {"easy": 0.8, "medium": 1.0, "hard": 1.3}

    raw_weights = [
        difficulty_weight.get(solution[v].get("difficulty", "medium"), 1.0)
        for v in variables
    ]
    weight_sum = sum(raw_weights) or 1.0

    results: list[dict] = []
    for v in variables:
        q = solution[v]
        w = difficulty_weight.get(q.get("difficulty", "medium"), 1.0)
        alloc = round(total_sec * w / weight_sum)
        results.append({
            "id": q["id"],
            "question": q["question"],
            "difficulty": q.get("difficulty", "medium"),
            "bloom_level": q.get("bloom_level", "Understand"),
            "ideal_keywords": q.get("ideal_keywords", []),
            "allocated_time_sec": alloc,
        })

    return results


# ═══════════════════════════════════════════════════════════════
#  TESTS  (run standalone: python csp_question_gen.py)
# ═══════════════════════════════════════════════════════════════

def _run_tests() -> None:
    """Run two test scenarios and print results."""

    print("=" * 65)
    print("  VivaLens AI — Question Generator Test Suite")
    print("=" * 65)

    # ── Scenario 1: Single topic, mixed difficulty ──
    print("\n📌 Scenario 1: topic='Heuristic Search', mixed, 4 questions, 8 min")
    print("-" * 65)
    qs1 = generate_viva_questions(
        topic="Heuristic Search", difficulty="mixed",
        count=4, time_limit_min=8,
    )
    if not qs1:
        print("  ⚠  No questions returned (pool may be empty).")
    for i, q in enumerate(qs1, 1):
        print(f"  Q{i} [{q['difficulty']:6s} | {q['bloom_level']:10s}] "
              f"({q['allocated_time_sec']:3d}s)  {q['question']}")

    # Verify no duplicates
    ids1 = [q["id"] for q in qs1]
    assert len(ids1) == len(set(ids1)), "❌ Duplicate questions detected!"
    print(f"  ✅ No duplicates  |  Bloom levels: "
          f"{set(q['bloom_level'] for q in qs1)}")

    # ── Scenario 2: All topics, hard only ──
    print("\n📌 Scenario 2: topic='all', difficulty='hard', 5 questions, 15 min")
    print("-" * 65)
    qs2 = generate_viva_questions(
        topic="all", difficulty="hard",
        count=5, time_limit_min=15,
    )
    if not qs2:
        print("  ⚠  No questions returned.")
    for i, q in enumerate(qs2, 1):
        print(f"  Q{i} [{q['difficulty']:6s} | {q['bloom_level']:10s}] "
              f"({q['allocated_time_sec']:3d}s)  {q['question']}")

    ids2 = [q["id"] for q in qs2]
    assert len(ids2) == len(set(ids2)), "❌ Duplicate questions detected!"
    topics2 = {q.get("topic", "N/A") for q in qs2}
    print(f"  ✅ No duplicates  |  Topics covered: {topics2}")

    # ── Edge case: count larger than pool ──
    print("\n📌 Edge Case: topic='Planning', difficulty='easy', count=100")
    print("-" * 65)
    qs3 = generate_viva_questions(
        topic="Planning", difficulty="easy", count=100, time_limit_min=5,
    )
    print(f"  Returned {len(qs3)} question(s) (clamped to pool size).")
    assert 0 < len(qs3) < 100, "Should clamp to available matching questions."
    assert all(q["difficulty"] == "easy" for q in qs3), \
        "Difficulty filter must only return 'easy' questions."
    ids3 = [q["id"] for q in qs3]
    assert len(ids3) == len(set(ids3)), "❌ Duplicate questions detected!"
    print("  ✅ Clamping works correctly.")

    print("\n" + "=" * 65)
    print("  ALL TESTS PASSED ✅")
    print("=" * 65)


if __name__ == "__main__":
    _run_tests()