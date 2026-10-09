"""
goal_stack_planner.py — Goal Stack Planning for Viva Preparation
================================================================
Generates structured, step-by-step preparation plans using Goal Stack
Planning (STRIPS-style operator decomposition).

Covers: SPPU TY AI 2024 — Unit 5 (Planning)

Planning System Formalism:
  - World State: Set of relational predicate strings describing the student's
    current mastery, speech habits, and topic readiness.
  - Goal Stack: LIFO stack containing compound goals, predicate sub-goals,
    and planning operators (actions).
  - Operators: Schema with Preconditions, Add List, and Delete List.
  - Plan Output: Total-order sequence of concrete actions required to transition
    from current state to goal state.

Main entry: generate_study_plan(performance_report, target_score)
Accepts output directly from inference_engine.py and text_analyzer.py
Returns: list[dict] with keys:
    step, goal, sub_goal, action, estimated_time, priority
"""

import sys
from typing import Any, NamedTuple

# Windows consoles default to cp1252, which cannot encode emoji/symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════════════
#  OPERATOR DEFINITION (STRIPS-style)
# ═══════════════════════════════════════════════════════════════

class Operator(NamedTuple):
    """Represents a STRIPS planning operator / action."""
    action_id: str
    preconditions: list[str]
    add_list: list[str]
    delete_list: list[str]
    goal_category: str
    sub_goal_label: str
    action_description: str
    estimated_time: str
    priority: str


# ═══════════════════════════════════════════════════════════════
#  DOMAIN OPERATOR FACTORY
# ═══════════════════════════════════════════════════════════════

def _create_topic_operators(
    topic: str,
    missing_keywords: list[str],
    current_score: float,
    target_score: float,
) -> list[Operator]:
    """
    Generate STRIPS operators tailored to a specific topic's deficiencies.
    """
    kw_str = ", ".join(missing_keywords[:4]) if missing_keywords else "domain definitions"
    gap = target_score - current_score

    operators: list[Operator] = []

    # Priority determination
    if gap >= 3.0 or current_score < 4.0:
        prio = "High"
    elif gap >= 1.5:
        prio = "Medium"
    else:
        prio = "Low"

    # Operator 1: Master Missing Terminology / Keywords
    if missing_keywords:
        operators.append(
            Operator(
                action_id=f"OP_LEARN_KW_{topic}",
                preconditions=[],
                add_list=[f"KeywordsMastered({topic})"],
                delete_list=[f"MissingKeywords({topic})"],
                goal_category=f"Master Knowledge in {topic}",
                sub_goal_label=f"Acquire missing keywords for {topic}",
                action_description=(
                    f"Study and memorize core terms: [{kw_str}]. "
                    f"Practice explaining each term in 1 concise sentence."
                ),
                estimated_time="20 mins",
                priority=prio,
            )
        )

    # Operator 2: Conceptual Deep Dive
    operators.append(
        Operator(
            action_id=f"OP_STUDY_CONCEPTS_{topic}",
            preconditions=[f"KeywordsMastered({topic})"] if missing_keywords else [],
            add_list=[f"ConceptsReviewed({topic})"],
            delete_list=[f"ConceptsWeak({topic})"],
            goal_category=f"Master Knowledge in {topic}",
            sub_goal_label=f"Deep dive into core {topic} theory",
            action_description=(
                f"Review standard textbook architectures, diagrams, and proof traces "
                f"for {topic} to bridge a {gap:.1f}-point gap."
            ),
            estimated_time="35 mins",
            priority=prio,
        )
    )

    # Operator 3: Viva Mock Drill (Final topic readiness operator)
    operators.append(
        Operator(
            action_id=f"OP_MOCK_DRILL_{topic}",
            preconditions=[f"ConceptsReviewed({topic})"],
            add_list=[f"TopicPassed({topic})"],
            delete_list=[f"TopicWeak({topic})"],
            goal_category=f"Achieve Target Score in {topic}",
            sub_goal_label=f"Simulate viva questioning on {topic}",
            action_description=(
                f"Speak out loud: answer 3 rapid-fire viva questions on {topic} "
                f"under a 2-minute timer."
            ),
            estimated_time="15 mins",
            priority=prio,
        )
    )

    return operators


def _create_speech_operators(speech_metrics: dict[str, Any]) -> list[Operator]:
    """Generate STRIPS operators for verbal delivery and speech habits."""
    operators: list[Operator] = []

    filler_count = speech_metrics.get("filler_count", 0)
    pace_wpm = speech_metrics.get("pace_wpm", 130)

    # Operator for filler word reduction
    if filler_count >= 4:
        fillers = speech_metrics.get("filler_words", ["um", "like", "basically"])
        sample_fillers = ", ".join(f'"{f}"' for f in set(fillers[:3]))
        operators.append(
            Operator(
                action_id="OP_REDUCE_FILLERS",
                preconditions=[],
                add_list=["FillersControlled()"],
                delete_list=["ExcessiveFillers()"],
                goal_category="Speech & Delivery Polish",
                sub_goal_label="Eliminate verbal crutches and filler words",
                action_description=(
                    f"Practice silent pauses instead of fillers ({sample_fillers}). "
                    f"Record a 1-minute explanation and aim for 0 fillers."
                ),
                estimated_time="15 mins",
                priority="High" if filler_count >= 8 else "Medium",
            )
        )

    # Operator for pace correction
    if pace_wpm < 100:  # Too slow
        operators.append(
            Operator(
                action_id="OP_ADJUST_PACE_FAST",
                preconditions=[],
                add_list=["PaceOptimized()"],
                delete_list=["PaceTooSlow()"],
                goal_category="Speech & Delivery Polish",
                sub_goal_label="Increase speaking pace to optimal range (120-150 WPM)",
                action_description=(
                    f"Current pace ({pace_wpm} WPM) is sluggish. Practice speaking with "
                    f"deliberate cadence at ~130 WPM using a metronome or timer."
                ),
                estimated_time="10 mins",
                priority="Medium",
            )
        )
    elif pace_wpm > 170:  # Too fast
        operators.append(
            Operator(
                action_id="OP_ADJUST_PACE_SLOW",
                preconditions=[],
                add_list=["PaceOptimized()"],
                delete_list=["PaceTooFast()"],
                goal_category="Speech & Delivery Polish",
                sub_goal_label="Moderate speaking speed to avoid rushing (120-150 WPM)",
                action_description=(
                    f"Current pace ({pace_wpm} WPM) is too rushed. Insert 1-second "
                    f"pauses between sentences to ensure examiners catch key concepts."
                ),
                estimated_time="10 mins",
                priority="Medium",
            )
        )

    return operators


# ═══════════════════════════════════════════════════════════════
#  GOAL STACK PLANNER ENGINE
# ═══════════════════════════════════════════════════════════════

class GoalStackPlanner:
    """
    Classical Goal Stack Planning Engine.
    Resolves sub-goals recursively using stack-based operator decomposition.
    """

    def __init__(
        self,
        initial_state: set[str],
        goals: list[str],
        operators: list[Operator],
    ) -> None:
        self.current_state: set[str] = set(initial_state)
        self.target_goals: list[str] = list(goals)
        self.operator_map: dict[str, list[Operator]] = {}
        for op in operators:
            for add_pred in op.add_list:
                self.operator_map.setdefault(add_pred, []).append(op)

    def solve(self) -> list[Operator]:
        """
        Execute Goal Stack Planning algorithm.
        Returns ordered sequence of operators.
        """
        plan: list[Operator] = []
        stack: list[Any] = []

        # Push top-level compound goal, then individual predicate goals
        # Reverse order so first goal is on top of stack
        for g in reversed(self.target_goals):
            stack.append(g)

        max_iterations = 200  # Guard against planning loops
        iterations = 0

        while stack and iterations < max_iterations:
            iterations += 1
            top = stack.pop()

            # ── Case 1: Stack item is an Operator ──
            if isinstance(top, Operator):
                # Apply operator to world state
                for p in top.delete_list:
                    self.current_state.discard(p)
                for p in top.add_list:
                    self.current_state.add(p)
                plan.append(top)
                continue

            # ── Case 2: Stack item is a Predicate Goal (str) ──
            predicate = str(top)
            if predicate in self.current_state:
                continue  # Already satisfied in current world state

            # Find an operator that achieves this predicate
            candidate_ops = self.operator_map.get(predicate, [])
            if not candidate_ops:
                # Primitive predicate with no operator; skip or mark satisfied
                continue

            chosen_op = candidate_ops[0]

            # Push Operator back, followed by its unsatisfied preconditions
            stack.append(chosen_op)
            for pre in reversed(chosen_op.preconditions):
                if pre not in self.current_state:
                    stack.append(pre)

        return plan


# ═══════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════

def generate_study_plan(
    performance_report: dict[str, Any],
    target_score: float = 7.0,
) -> list[dict[str, Any]]:
    """
    Generate a step-by-step study plan using Goal Stack Planning.

    Parameters
    ----------
    performance_report : dict[str, Any]
        Performance output from inference_engine or overall analysis.
        Accepts formats such as:
          {
            "topics": {
              "TopicName": {
                "score": float,
                "missing_keywords": list[str],
                "found_keywords": list[str],
                "verdict": str
              }, ...
            },
            "speech_metrics": {
              "filler_count": int,
              "filler_words": list[str],
              "pace_wpm": int
            }
          }
        Also tolerates flat dict structures {topic_name: score_or_dict}.
    target_score : float, optional
        Target threshold score to reach (default 7.0).

    Returns
    -------
    list[dict[str, Any]]
        Ordered plan steps:
        [
          {
            "step": int,
            "goal": str,
            "sub_goal": str,
            "action": str,
            "estimated_time": str,
            "priority": str
          }, ...
        ]
        Returns empty list if all targets are already met.
    """
    if not performance_report or not isinstance(performance_report, dict):
        return []

    target_score = max(0.1, min(float(target_score), 10.0))

    # ── 1. Parse topics and speech data from report ──
    raw_topics = performance_report.get("topics", performance_report)
    speech_metrics = performance_report.get("speech_metrics", {})

    initial_state: set[str] = set()
    goals: list[str] = []
    operators: list[Operator] = []

    # ── 2. Build World State & Operators for Topics ──
    for topic_name, details in raw_topics.items():
        if topic_name in ("speech_metrics", "overall_score", "verdict"):
            continue

        if isinstance(details, dict):
            score = float(details.get("score", 0.0))
            missing_kw = list(details.get("missing_keywords", []))
        elif isinstance(details, (int, float)):
            score = float(details)
            missing_kw = []
        else:
            continue

        if score < target_score:
            initial_state.add(f"TopicWeak({topic_name})")
            if missing_kw:
                initial_state.add(f"MissingKeywords({topic_name})")
            else:
                initial_state.add(f"KeywordsMastered({topic_name})")

            # Final goal for this topic
            goals.append(f"TopicPassed({topic_name})")

            # Generate available STRIPS operators for this topic
            ops = _create_topic_operators(
                topic=topic_name,
                missing_keywords=missing_kw,
                current_score=score,
                target_score=target_score,
            )
            operators.extend(ops)
        else:
            initial_state.add(f"TopicPassed({topic_name})")
            initial_state.add(f"KeywordsMastered({topic_name})")
            initial_state.add(f"ConceptsReviewed({topic_name})")

    # ── 3. Build World State & Operators for Speech / Delivery ──
    if isinstance(speech_metrics, dict) and speech_metrics:
        filler_count = speech_metrics.get("filler_count", 0)
        pace_wpm = speech_metrics.get("pace_wpm", 130)

        if filler_count >= 4:
            initial_state.add("ExcessiveFillers()")
            goals.append("FillersControlled()")

        if pace_wpm < 100:
            initial_state.add("PaceTooSlow()")
            goals.append("PaceOptimized()")
        elif pace_wpm > 170:
            initial_state.add("PaceTooFast()")
            goals.append("PaceOptimized()")
        else:
            initial_state.add("PaceOptimized()")

        speech_ops = _create_speech_operators(speech_metrics)
        operators.extend(speech_ops)

    # ── 4. Edge Case: Student already satisfies all goals ──
    if not goals:
        return []

    # ── 5. Run Goal Stack Planner ──
    planner = GoalStackPlanner(
        initial_state=initial_state,
        goals=goals,
        operators=operators,
    )
    executed_plan = planner.solve()

    # ── 6. Format Result for UI & Integration ──
    formatted_steps: list[dict[str, Any]] = []
    for step_num, op in enumerate(executed_plan, 1):
        formatted_steps.append({
            "step": step_num,
            "goal": op.goal_category,
            "sub_goal": op.sub_goal_label,
            "action": op.action_description,
            "estimated_time": op.estimated_time,
            "priority": op.priority,
        })

    return formatted_steps


# ═══════════════════════════════════════════════════════════════
#  TESTS (run standalone: python goal_stack_planner.py)
# ═══════════════════════════════════════════════════════════════

def _run_tests() -> None:
    """Run Goal Stack Planner test scenarios and print structured output."""

    print("=" * 75)
    print("  VivaLens AI — Goal Stack Planner Test Suite")
    print("=" * 75)

    # ── Scenario 1: Comprehensive Viva Diagnostic Report ──
    print("\n📌 Scenario 1: Multi-Topic Deficiencies & Speech Crutches")
    print("-" * 75)
    sample_report = {
        "overall_score": 4.8,
        "speech_metrics": {
            "filler_count": 9,
            "filler_words": ["um", "uh", "like", "basically"],
            "pace_wpm": 88,  # Sluggish pace
        },
        "topics": {
            "Heuristic Search": {
                "score": 4.0,
                "missing_keywords": ["admissible", "consistent", "Manhattan distance"],
                "found_keywords": ["heuristic", "f(n)"],
                "verdict": "Needs Improvement",
            },
            "Logic & Inference": {
                "score": 5.5,
                "missing_keywords": ["resolution refutation", "CNF"],
                "found_keywords": ["FOL", "predicates"],
                "verdict": "Borderline",
            },
            "Intelligent Agents": {
                "score": 8.5,
                "missing_keywords": [],
                "found_keywords": ["sensors", "actuators", "PEAS"],
                "verdict": "Mastered",
            },
        },
    }

    plan1 = generate_study_plan(sample_report, target_score=7.0)
    print(f"Generated {len(plan1)} Goal-Stack plan step(s):\n")

    for step in plan1:
        print(f"  [Step {step['step']}] Priority: {step['priority']:<6} | Time: {step['estimated_time']}")
        print(f"    🎯 Goal    : {step['goal']}")
        print(f"    📌 Sub-Goal: {step['sub_goal']}")
        print(f"    ⚡ Action  : {step['action']}")
        print()

    assert len(plan1) >= 4, f"Expected at least 4 plan steps, got {len(plan1)}"
    # Intelligent Agents was >= 7.0, so it shouldn't have any steps
    agent_steps = [s for s in plan1 if "Intelligent Agents" in s["goal"]]
    assert len(agent_steps) == 0, "Mastered topics should not be scheduled for study!"
    print("  ✅ Scenario 1 Passed (Sub-goals properly stacked and decomposed).")

    # ── Scenario 2: Perfect Viva Performance (Edge Case) ──
    print("\n📌 Scenario 2: Student already above target with clean delivery")
    print("-" * 75)
    perfect_report = {
        "overall_score": 9.0,
        "speech_metrics": {
            "filler_count": 1,
            "pace_wpm": 135,
        },
        "topics": {
            "CSP & Adversarial Search": {"score": 8.0, "missing_keywords": []},
            "Planning": {"score": 9.0, "missing_keywords": []},
        },
    }
    plan2 = generate_study_plan(perfect_report, target_score=7.0)
    print(f"Result: {plan2}")
    assert plan2 == [], "Should return empty plan when all goals are pre-satisfied."
    print("  ✅ Scenario 2 Passed (No unnecessary actions generated).")

    # ── Scenario 3: Flat Topics Dictionary Input ──
    print("\n📌 Scenario 3: Flat score input format")
    print("-" * 75)
    flat_report = {
        "Planning": 3.5,
        "CSP & Adversarial Search": 7.5,
    }
    plan3 = generate_study_plan(flat_report, target_score=7.0)
    print(f"Plan steps generated: {len(plan3)}")
    for s in plan3:
        print(f"  • Step {s['step']}: {s['sub_goal']} ({s['estimated_time']})")
    assert len(plan3) >= 1, "Should handle flat score mappings gracefully."
    print("  ✅ Scenario 3 Passed.")

    # ── Scenario 4: Empty Report Edge Case ──
    print("\n📌 Scenario 4: Empty report dictionary")
    print("-" * 75)
    plan4 = generate_study_plan({})
    assert plan4 == [], "Empty report must return empty plan."
    print("  ✅ Scenario 4 Passed.")

    print("\n" + "=" * 75)
    print("  ALL GOAL STACK PLANNER TESTS PASSED ✅")
    print("=" * 75)


if __name__ == "__main__":
    _run_tests()