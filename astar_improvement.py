"""
astar_improvement.py — A* Search for Optimal Study Improvement Path
===================================================================
Part of VivaLens AI | Agent: CIPHER (Algorithm Specialist)

Finds the optimal sequence of study sessions to elevate underperforming
viva topic scores above a target threshold using A* Search.

Covers: SPPU TY AI 2024 — Unit 2 (Heuristic Search)

Search Problem Formulation:
  • State: tuple of current topic scores (s₁, s₂, ..., sₙ)
  • Initial State: scores extracted from performance report / inference engine
  • Goal State: ∀ topic i, score[i] ≥ target_score (e.g. 7.0/10)
  • Actions: study_topic(i, hours) → increases score[i] by (hours × rate)
  • Path Cost g(n): Total study hours invested so far
  • Heuristic h(n): Admissible estimate of remaining study hours needed
                   h(n) = Σ max(0, target - score[i]) / rate
                   (Admissible & Consistent: never overestimates hours)
  • Evaluation Function: f(n) = g(n) + h(n)

Integration notes for PRISM / FORGE:
  - Main entry: find_improvement_path(current_scores, target_score, max_hours)
  - Returns: list[dict] with keys:
      topic, current_score, target_score, hours_needed, priority, action
"""

import heapq
import itertools
import sys
from typing import Optional

# Windows consoles default to cp1252, which cannot encode emoji/symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION & DOMAIN KNOWLEDGE
# ═══════════════════════════════════════════════════════════════

# Score points gained per hour of focused study
POINTS_PER_STUDY_HOUR: float = 1.5

# Maximum allowed viva score
MAX_SCORE: float = 10.0

# Action recommendation templates per syllabus topic (SPPU TY AI 2024)
TOPIC_RECOMMENDATIONS: dict[str, str] = {
    "Intelligent Agents": (
        "Review PEAS framework, agent environments (observable/deterministic), "
        "and compare reflex vs utility agent architectures."
    ),
    "Heuristic Search": (
        "Practice A* trace with admissibility proofs, 8-puzzle heuristics, "
        "and compare greedy search vs A* optimality."
    ),
    "CSP & Adversarial Search": (
        "Solve map-coloring via AC-3 / backtracking with forward checking, "
        "and practice Minimax with Alpha-Beta pruning traces."
    ),
    "Logic & Inference": (
        "Review FOL resolution refutation, forward/backward chaining step traces, "
        "and CNF conversion rules."
    ),
    "Planning": (
        "Practice Goal Stack Planning on Block World (ON, ONTABLE, CLEAR), "
        "and review STRIPS action representations."
    ),
}

DEFAULT_RECOMMENDATION: str = (
    "Review core concepts, definitions, diagrams, and practice viva-style "
    "concise keyword explanations."
)


# ═══════════════════════════════════════════════════════════════
#  A* SEARCH IMPLEMENTATION
# ═══════════════════════════════════════════════════════════════

def _heuristic(
    state: tuple[float, ...],
    targets: tuple[float, ...],
    rate: float = POINTS_PER_STUDY_HOUR,
) -> float:
    """
    Admissible and consistent heuristic function h(n).

    Estimates the minimum remaining study hours needed to bring all topics
    to their target scores:
        h(n) = Σ max(0, target[i] - state[i]) / rate

    Because a student cannot gain score faster than `rate` points/hour,
    h(n) is guaranteed to never overestimate the true remaining cost.
    """
    remaining_gap = sum(max(0.0, target - score) for score, target in zip(state, targets))
    return remaining_gap / rate


def _is_goal(state: tuple[float, ...], targets: tuple[float, ...]) -> bool:
    """Check if all topic scores have reached or exceeded target scores."""
    return all(score >= target for score, target in zip(state, targets))


def _astar_search(
    topics: list[str],
    initial_scores: list[float],
    target_scores: list[float],
    max_hours: float,
    rate: float = POINTS_PER_STUDY_HOUR,
) -> Optional[list[dict]]:
    """
    Execute A* search to find the optimal sequence of study steps.

    Returns an ordered list of step dicts leading to the goal, or None if
    budget is exceeded without reaching the goal.
    """
    init_state = tuple(round(min(s, MAX_SCORE), 2) for s in initial_scores)
    tgt_state = tuple(round(min(t, MAX_SCORE), 2) for t in target_scores)

    # If already at goal
    if _is_goal(init_state, tgt_state):
        return []

    # Priority queue entries: (f_score, tie_breaker, g_cost, state, path_history)
    counter = itertools.count()
    start_h = _heuristic(init_state, tgt_state, rate)
    open_set: list[tuple[float, int, float, tuple[float, ...], list[dict]]] = []
    heapq.heappush(open_set, (start_h, next(counter), 0.0, init_state, []))

    # Visited state map: state -> lowest g_cost seen
    best_g: dict[tuple[float, ...], float] = {init_state: 0.0}

    while open_set:
        f_cost, _, g_cost, current_state, path = heapq.heappop(open_set)

        # Skip if we already found a cheaper path to this state
        if g_cost > best_g.get(current_state, float("inf")):
            continue

        # Goal check
        if _is_goal(current_state, tgt_state):
            return path

        # Generate successor states: study each topic that is below target
        for idx, (score, target) in enumerate(zip(current_state, tgt_state)):
            if score >= target:
                continue  # already mastered, no need to study

            # Calculate exact hours needed for this topic to reach target
            gap = target - score
            hours_needed = round(gap / rate, 2)

            # Check if taking this step exceeds our max study budget
            new_g = round(g_cost + hours_needed, 2)
            if new_g > max_hours:
                continue

            # Create successor state with score updated to target (capped at 10.0)
            new_score = round(min(score + (hours_needed * rate), MAX_SCORE), 2)
            new_state_list = list(current_state)
            new_state_list[idx] = new_score
            new_state = tuple(new_state_list)

            # Record step action metadata
            topic_name = topics[idx]
            recommendation = TOPIC_RECOMMENDATIONS.get(topic_name, DEFAULT_RECOMMENDATION)
            step_record = {
                "topic": topic_name,
                "current_score": score,
                "target_score": target,
                "hours_needed": hours_needed,
                "action": f"Study {topic_name}: {recommendation} (+{gap:.1f} pts)",
            }
            new_path = path + [step_record]

            # Relaxation step
            if new_g < best_g.get(new_state, float("inf")):
                best_g[new_state] = new_g
                h_cost = _heuristic(new_state, tgt_state, rate)
                f_cost = new_g + h_cost
                heapq.heappush(open_set, (f_cost, next(counter), new_g, new_state, new_path))

    return None  # No path within max_hours budget


# ═══════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════

def find_improvement_path(
    current_scores: dict[str, float],
    target_score: float = 7.0,
    max_hours: int = 20,
) -> list[dict]:
    """
    Find optimal study sequence using A* search.

    Parameters
    ----------
    current_scores : dict[str, float]
        Dictionary mapping topic names to current score (0.0 to 10.0).
        e.g. {"Intelligent Agents": 4.5, "Logic & Inference": 3.0}
    target_score : float, optional
        Minimum threshold score to achieve in every topic (default: 7.0).
    max_hours : int, optional
        Maximum allowed cumulative study budget in hours (default: 20).

    Returns
    -------
    list[dict]
        Ordered list of study steps with priority:
        [
          {
            "topic": str,
            "current_score": float,
            "target_score": float,
            "hours_needed": float,
            "priority": int,
            "action": str
          }, ...
        ]
        Returns empty list if all topics are already at or above target,
        or if current_scores is empty.
    """
    # ── Edge Case 1: Empty input ──
    if not current_scores:
        return []

    # ── Edge Case 2: Target is non-positive ──
    target_score = max(0.1, min(target_score, MAX_SCORE))

    topics = list(current_scores.keys())
    initial_scores = [float(current_scores[t]) for t in topics]
    target_scores = [target_score] * len(topics)

    # ── Edge Case 3: All scores already satisfy target ──
    if all(s >= target_score for s in initial_scores):
        return []

    # ── Run A* Search ──
    path = _astar_search(
        topics=topics,
        initial_scores=initial_scores,
        target_scores=target_scores,
        max_hours=float(max_hours),
        rate=POINTS_PER_STUDY_HOUR,
    )

    # If full path was found within budget
    if path is not None:
        # Assign priorities (1 = highest priority, first in optimal sequence)
        for rank, step in enumerate(path, 1):
            step["priority"] = rank
        return path

    # ── Fallback: Budget exceeded → Return partial plan prioritized by largest gap ──
    gap_list: list[dict] = []
    for topic, score in current_scores.items():
        if score < target_score:
            gap = target_score - score
            hours = round(gap / POINTS_PER_STUDY_HOUR, 2)
            rec = TOPIC_RECOMMENDATIONS.get(topic, DEFAULT_RECOMMENDATION)
            gap_list.append({
                "topic": topic,
                "current_score": round(score, 2),
                "target_score": target_score,
                "hours_needed": hours,
                "action": f"Study {topic} [PARTIAL BUDGET]: {rec} (+{gap:.1f} pts)",
            })

    # Sort descending by gap (largest gap tackled first)
    gap_list.sort(key=lambda x: (x["target_score"] - x["current_score"]), reverse=True)

    accumulated_hours = 0.0
    partial_plan: list[dict] = []
    for rank, item in enumerate(gap_list, 1):
        if accumulated_hours + item["hours_needed"] <= max_hours:
            item["priority"] = rank
            partial_plan.append(item)
            accumulated_hours += item["hours_needed"]

    return partial_plan


# ═══════════════════════════════════════════════════════════════
#  TESTS (run standalone: python astar_improvement.py)
# ═══════════════════════════════════════════════════════════════

def _run_tests() -> None:
    """Run A* search test scenarios and print formatted execution output."""

    print("=" * 70)
    print("  CIPHER — astar_improvement.py  |  TEST SUITE")
    print("=" * 70)

    # ── Scenario 1: Standard Viva Performance with Weak Areas ──
    print("\n📌 Scenario 1: Weak areas across multiple AI topics (Target = 7.0)")
    print("-" * 70)
    scores1 = {
        "Intelligent Agents": 4.0,
        "Heuristic Search": 7.5,
        "CSP & Adversarial Search": 3.5,
        "Logic & Inference": 5.0,
        "Planning": 8.0,
    }

    plan1 = find_improvement_path(scores1, target_score=7.0, max_hours=15)
    print(f"Initial Scores: {scores1}")
    print(f"Generated {len(plan1)} study action step(s):\n")

    total_hours = 0.0
    for step in plan1:
        print(f"  Priority {step['priority']}: {step['topic']}")
        print(f"    • Score Gap : {step['current_score']} ➔ {step['target_score']}")
        print(f"    • Study Time: {step['hours_needed']} hrs")
        print(f"    • Strategy  : {step['action']}")
        total_hours += step["hours_needed"]

    print(f"\n  Total Plan Investment: {total_hours:.2f} hours")
    assert len(plan1) == 3, f"Expected 3 topics to study, got {len(plan1)}"
    assert all(step["priority"] > 0 for step in plan1), "Priorities must be positive."
    print("  ✅ Scenario 1 Passed.")

    # ── Scenario 2: All Topics Already Mastered (Edge Case) ──
    print("\n📌 Scenario 2: All topics already above target score (Target = 7.0)")
    print("-" * 70)
    scores2 = {
        "Intelligent Agents": 8.5,
        "Heuristic Search": 9.0,
        "CSP & Adversarial Search": 7.5,
        "Logic & Inference": 7.0,
        "Planning": 8.0,
    }
    plan2 = find_improvement_path(scores2, target_score=7.0)
    print(f"Scores: {scores2}")
    print(f"Result: {plan2}")
    assert plan2 == [], "Should return empty list when no improvement needed."
    print("  ✅ Scenario 2 Passed (No unnecessary study scheduled).")

    # ── Scenario 3: Tight Time Budget (Edge Case) ──
    print("\n📌 Scenario 3: Tight budget constraint (max_hours = 3, needed ~6.3 hrs)")
    print("-" * 70)
    scores3 = {
        "Logic & Inference": 2.5,
        "CSP & Adversarial Search": 4.0,
    }
    plan3 = find_improvement_path(scores3, target_score=7.0, max_hours=3)
    print(f"Scores: {scores3} | Target: 7.0 | Max Hours: 3")
    print(f"Returned {len(plan3)} prioritized step(s) within budget:")
    for step in plan3:
        print(f"  Priority {step['priority']}: {step['topic']} ({step['hours_needed']} hrs)")

    assert sum(s["hours_needed"] for s in plan3) <= 3.0, "Budget exceeded!"
    print("  ✅ Scenario 3 Passed (Budget strictly respected).")

    # ── Scenario 4: Empty Input ──
    print("\n📌 Scenario 4: Empty input dictionary")
    print("-" * 70)
    plan4 = find_improvement_path({})
    assert plan4 == [], "Empty input must return empty list."
    print("  ✅ Scenario 4 Passed.")

    print("\n" + "=" * 70)
    print("  ALL A* SEARCH TESTS PASSED ✅")
    print("=" * 70)


if __name__ == "__main__":
    _run_tests()