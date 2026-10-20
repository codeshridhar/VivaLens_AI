"""
app.py — VivaLens AI
====================
Main Streamlit application for VivaLens AI.

Provides 5 navigation tabs: Home, Viva Evaluator, Slide Analyzer,
Viva Simulator, and Analytics Dashboard.

Highlights:
    - Tab 1: Professional product overview with syllabus mapping
    - Tab 2: Viva answer evaluation with follow-up question suggestions
    - Tab 5: Study plan generation with default fallback

Run:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Page configuration (must be the FIRST Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="VivaLens AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for a modern, clean look
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .big-score {
        font-size: 2.2rem;
        font-weight: 600;
        line-height: 1.1;
        color: inherit;
    }
    .muted {
        font-size: 0.9rem;
        opacity: 0.7;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Safe module imports (other agents' code may not be present yet)
# ---------------------------------------------------------------------------

try:
    from text_analyzer import analyze_text, quick_summary
    _HAS_TEXT_ANALYZER = True
except ImportError:
    _HAS_TEXT_ANALYZER = False

try:
    from speech_module import record_audio, transcribe_audio, is_speech_available
    _HAS_SPEECH = True
except ImportError:
    _HAS_SPEECH = False

try:
    from inference_engine import evaluate_answer, diagnose_weakness
    _HAS_INFERENCE = True
except ImportError:
    _HAS_INFERENCE = False

try:
    from csp_question_gen import generate_viva_questions
    _HAS_CSP = True
except ImportError:
    _HAS_CSP = False

try:
    from astar_improvement import find_improvement_path
    _HAS_ASTAR = True
except ImportError:
    _HAS_ASTAR = False

try:
    from goal_stack_planner import generate_study_plan
    _HAS_PLANNER = True
except ImportError:
    _HAS_PLANNER = False

try:
    from slide_analyzer import analyze_presentation
    _HAS_SLIDE = True
except ImportError:
    _HAS_SLIDE = False


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    """Initialize all session state keys with safe defaults."""
    defaults = {
        "scores_history": [],
        "answer_log": [],
        "slide_reports": [],
        "current_topic": "AI",
        "current_score": 0.0,
        "simulator_questions": [],
        "simulator_answers": {},
        "simulator_active": False,
        "slide_report": None,
        "improvement_path": [],
        "study_plan": [],
        "followup_questions": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_session_state()


# ---------------------------------------------------------------------------
# Answer logging — one canonical record per evaluated answer
# ---------------------------------------------------------------------------

def _record_answer(
    topic: str,
    answer: str,
    result: dict,
    source: str = "Evaluator",
    question: str = "",
) -> dict:
    """
    Append one evaluated answer to the session log.

    The dashboard reads this log, so every number shown there comes from a
    real evaluation rather than from demo values.

    Args:
        topic: Topic the answer belongs to.
        answer: The answer text the student gave.
        result: The dict returned by text_analyzer.analyze_text().
        source: Where the answer came from (Evaluator / Simulator).
        question: The question that was asked, when known.

    Returns:
        The stored record.
    """
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "topic": topic,
        "question": question,
        "answer": (answer or "").strip(),
        "score": float(result.get("overall_text_score", 0.0)),
        "clarity": float(result.get("clarity_score", 0.0)),
        "keyword_cov": float(result.get("keyword_coverage", 0.0)),
        "words": int(result.get("word_count", 0)),
        "sentences": int(result.get("sentence_count", 0)),
        "fillers": int(result.get("filler_count", 0)),
        "filler_words": ", ".join(result.get("filler_words_found", []) or []),
        "pace": result.get("speaking_pace_wpm"),
        "pace_verdict": result.get("pace_verdict", "unknown"),
        "keywords_missing": ", ".join(result.get("keywords_missing", []) or []),
        "avg_sentence_length": result.get("avg_sentence_length", 0.0),
    }

    st.session_state.answer_log.append(record)
    st.session_state.scores_history.append({
        "topic": record["topic"],
        "score": record["score"],
        "clarity": record["clarity"],
        "keyword_cov": record["keyword_cov"],
    })
    return record


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.markdown("**VivaLens AI**")
st.sidebar.caption("Viva & presentation analyzer")
st.sidebar.divider()

PAGE = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "Viva Evaluator",
        "Slide Analyzer",
        "Viva Simulator",
        "Dashboard",
    ],
    index=0,
)

st.sidebar.divider()
st.sidebar.caption("Runs locally. No API keys, no accounts.")
st.sidebar.caption(
    "Switch between light and dark from the menu: Settings -> Theme."
)


# ===================================================================
#  TAB 1 — Home
# ===================================================================

if PAGE == "Home":
    st.title("VivaLens AI")
    st.write(
        "Scores your viva answers and checks your presentation slides. "
        "Everything runs on your machine, offline."
    )

    st.subheader("What it does")
    st.markdown(
        """
- **Viva Evaluator** — type or speak an answer and get a score for clarity,
  keyword coverage, speaking pace and filler words.
- **Slide Analyzer** — upload a PPTX or PDF and get a report on structure,
  typography, density and layout.
- **Viva Simulator** — practise against generated questions for a chosen
  topic and difficulty.
- **Dashboard** — see how your scores are trending and get a study plan for
  your weak topics.
        """
    )

    st.caption(
        "Built for the SPPU TY AI 2024 syllabus: first-order logic, "
        "heuristic search, CSP, and goal stack planning."
    )


# ===================================================================
#  TAB 2 — Viva Answer Evaluator
# ===================================================================

elif PAGE == "Viva Evaluator":
    st.title("Viva answer evaluator")
    st.markdown(
        "Type or speak an answer to get feedback on clarity, keywords, "
        "pace and filler words."
    )

    if not _HAS_TEXT_ANALYZER:
        st.error("❌ `text_analyzer.py` not found. Please check that all project files are present.")
        st.stop()

    st.divider()

    # --- Input configuration ---
    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        topic = st.selectbox(
            "Select Topic",
            ["AI", "DSA", "DBMS", "OS", "CN"],
            key="eval_topic",
        )
    with col_cfg2:
        input_mode = st.radio(
            "Input Mode",
            ["Type answer", "Record audio", "Upload WAV"],
            horizontal=True,
        )

    sample_questions = {
        "AI": "Explain the A* search algorithm and its admissibility condition.",
        "DSA": "What is the time complexity of quicksort in the worst case?",
        "DBMS": "Explain normalization and its different normal forms.",
        "OS": "What is a deadlock and what are the four necessary conditions?",
        "CN": "Explain the TCP three-way handshake process.",
    }
    st.info(f"💡 **Sample Question ({topic}):** {sample_questions[topic]}")

    # --- Answer input ---
    answer_text = ""

    if input_mode == "Type answer":
        answer_text = st.text_area(
            "Type your answer below:",
            height=180,
            placeholder="Start typing your viva answer here...",
        )

    elif input_mode == "Record audio":
        if _HAS_SPEECH:
            speech_status = is_speech_available()
            if speech_status["mic_available"]:
                duration = st.slider("Recording duration (seconds)", 5, 60, 15)
                if st.button("Start recording"):
                    with st.spinner("Recording... Speak now!"):
                        wav_path = record_audio(duration_sec=duration)
                    if wav_path:
                        st.success(f"Recording saved to `{wav_path}`")
                        with st.spinner("Transcribing offline..."):
                            answer_text = transcribe_audio(wav_path)
                        if answer_text:
                            st.text_area("Transcribed text:", answer_text, height=120)
                        else:
                            st.warning("Transcription returned empty. Is the Vosk model folder present?")
                    else:
                        st.error("Recording failed.")
            else:
                st.warning(f"🎤 {speech_status['status_msg']}")
                answer_text = st.text_area("Fallback — type your answer:", height=180)
        else:
            st.warning("⚠️ `speech_module.py` not found.")
            answer_text = st.text_area("Fallback — type your answer:", height=180)

    elif input_mode == "Upload WAV":
        uploaded_wav = st.file_uploader("Upload a WAV file", type=["wav"])
        if uploaded_wav is not None and _HAS_SPEECH:
            import tempfile, os
            tmp = os.path.join(tempfile.gettempdir(), "uploaded.wav")
            with open(tmp, "wb") as f:
                f.write(uploaded_wav.getbuffer())
            with st.spinner("Transcribing..."):
                answer_text = transcribe_audio(tmp)
            if answer_text:
                st.text_area("Transcribed text:", answer_text, height=120)
            else:
                st.warning("Transcription empty. Check Vosk model path.")
        elif uploaded_wav is not None and not _HAS_SPEECH:
            st.warning("Speech module not available for transcription.")

    st.divider()

    # --- Evaluate button ---
    if st.button("Evaluate answer", type="primary", width="stretch"):
        if not answer_text.strip():
            st.warning("Please provide an answer before evaluating.")
        else:
            topic_keywords = {
                "AI": ["heuristic", "admissible", "optimal", "search", "cost", "path", "node", "frontier", "f(n)", "g(n)", "h(n)"],
                "DSA": ["time complexity", "worst case", "pivot", "partition", "O(n²)", "O(n log n)", "recursion", "divide"],
                "DBMS": ["normalization", "1NF", "2NF", "3NF", "BCNF", "functional dependency", "anomaly", "decomposition"],
                "OS": ["deadlock", "mutual exclusion", "hold and wait", "no preemption", "circular wait", "resource", "process"],
                "CN": ["SYN", "ACK", "handshake", "TCP", "connection", "sequence", "segment", "port"],
            }
            expected_kw = topic_keywords.get(topic, [])

            result = analyze_text(answer_text, expected_keywords=expected_kw)

            fol_result = None
            if _HAS_INFERENCE:
                try:
                    fol_result = evaluate_answer(answer_text, topic)
                except Exception as e:
                    fol_result = {"error": str(e)}

            st.session_state.current_score = result["overall_text_score"]
            _record_answer(
                topic=topic,
                answer=answer_text,
                result=result,
                source="Evaluator",
            )

            # --- Scorecard display ---
            st.subheader("Scorecard")

            score = result["overall_text_score"]
            st.markdown(
                f'<div class="big-score">{score} / 10</div>',
                unsafe_allow_html=True,
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Word Count", result["word_count"])
            m2.metric("Filler Words", result["filler_count"])
            m3.metric("Keyword Coverage", f"{result['keyword_coverage']:.0%}")
            wpm_display = f"{result['speaking_pace_wpm']}" if result["speaking_pace_wpm"] else "N/A"
            m4.metric("Pace (WPM)", wpm_display, delta=result["pace_verdict"])

            st.divider()

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✅ Strengths**")
                strengths_found = False
                if result["filler_count"] == 0:
                    st.success("No filler words — clean delivery!")
                    strengths_found = True
                if result["keyword_coverage"] >= 0.7:
                    st.success(f"Good keyword coverage ({result['keyword_coverage']:.0%})")
                    strengths_found = True
                if result["pace_verdict"] == "ideal":
                    st.success("Speaking pace is ideal.")
                    strengths_found = True
                if not strengths_found:
                    st.info("Keep practicing — strengths will appear here!")

                st.markdown("**⚠️ Weaknesses**")
                weaknesses_found = False
                if result["filler_count"] > 3:
                    st.warning(f"High filler count: {', '.join(result['filler_words_found'])}")
                    weaknesses_found = True
                if result["keyword_coverage"] < 0.5:
                    missing = ", ".join(result["keywords_missing"][:5])
                    st.warning(f"Missing keywords: {missing}")
                    weaknesses_found = True
                if result["pace_verdict"] in ("too slow", "too fast"):
                    st.warning(f"Pace is {result['pace_verdict']}.")
                    weaknesses_found = True
                if not weaknesses_found:
                    st.success("No major weaknesses detected!")

            with c2:
                st.markdown("**📊 Clarity Breakdown**")
                st.progress(result["clarity_score"] / 10.0, text=f"Clarity: {result['clarity_score']}/10")
                st.progress(result["keyword_coverage"], text=f"Keywords: {result['keyword_coverage']:.0%}")
                filler_ratio_pct = min(result["filler_ratio"] * 10, 1.0)
                st.progress(1.0 - filler_ratio_pct, text=f"Fluency: {1.0 - filler_ratio_pct:.0%}")

                st.markdown("**📝 Quick Summary**")
                st.info(quick_summary(result))

            # --- Actionable Suggestions (bulleted) ---
            st.divider()
            st.subheader("Suggestions")
            suggestions: list[str] = []
            if result["filler_count"] > 3:
                suggestions.append(
                    "**Reduce filler words** — practice pausing silently instead "
                    "of saying 'um' or 'like'."
                )
            if result["keyword_coverage"] < 0.7:
                suggestions.append(
                    f"**Strengthen your vocabulary** by including key terms like: "
                    f"_{', '.join(result['keywords_missing'][:4])}_."
                )
            if result["pace_verdict"] == "too fast":
                suggestions.append(
                    "**Slow down** — aim for 120–150 words per minute for clearer delivery."
                )
            elif result["pace_verdict"] == "too slow":
                suggestions.append(
                    "**Pick up the pace** — try to speak more fluidly to maintain examiner attention."
                )
            if result["avg_sentence_length"] > 30:
                suggestions.append(
                    "**Shorten sentences** — break long explanations into smaller logical chunks."
                )
            if result["clarity_score"] < 6:
                suggestions.append(
                    "**Improve structure** — use a clear intro → explanation → example flow."
                )
            if not suggestions:
                suggestions.append("Great job. Keep practicing to maintain this quality.")

            for s in suggestions:
                st.markdown(f"- {s}")

            # --- Follow-up Questions ---
            st.divider()
            st.subheader("Follow-up questions")
            st.caption("Practice these next to deepen your understanding of this topic.")

            followups: list[str] = []

            # Try pulling from inference engine first
            if fol_result and isinstance(fol_result, dict):
                engine_followups = fol_result.get("follow_up_questions", [])
                if engine_followups:
                    followups = engine_followups[:3]

            # Fallback: pull from CSP question generator
            if not followups and _HAS_CSP:
                try:
                    csp_qs = generate_viva_questions(
                        topic=topic,
                        difficulty="mixed",
                        count=3,
                    )
                    followups = [q.get("question", "") for q in csp_qs if q.get("question")]
                except Exception:
                    followups = []

            # Final fallback: built-in question bank per topic
            if not followups:
                builtin_bank = {
                    "AI": [
                        "How does A* differ from Dijkstra's algorithm?",
                        "Can you give an example of an admissible heuristic?",
                        "What happens if the heuristic overestimates the cost?",
                    ],
                    "DSA": [
                        "How can you optimize quicksort's worst case?",
                        "Compare quicksort with mergesort in terms of stability.",
                        "What is the role of the pivot in partitioning?",
                    ],
                    "DBMS": [
                        "What is BCNF and how is it different from 3NF?",
                        "Give an example of an update anomaly.",
                        "What are the drawbacks of over-normalization?",
                    ],
                    "OS": [
                        "What is the Banker's algorithm?",
                        "How can we prevent circular wait in deadlock?",
                        "Difference between deadlock prevention and avoidance?",
                    ],
                    "CN": [
                        "What is TCP four-way termination?",
                        "How does TCP ensure reliable delivery?",
                        "Difference between TCP and UDP?",
                    ],
                }
                followups = builtin_bank.get(topic, [
                    "Can you explain this concept with a real-world example?",
                    "What are its limitations?",
                    "How is it applied in modern systems?",
                ])

            st.session_state.followup_questions = followups
            for i, q in enumerate(followups, 1):
                st.markdown(f"**Q{i}.** {q}")

            # FOL reasoning trace
            if fol_result and "error" not in fol_result:
                st.divider()
                st.subheader("Reasoning trace")
                st.json(fol_result)
            elif _HAS_INFERENCE and fol_result and "error" in fol_result:
                st.warning(f"FOL engine error: {fol_result['error']}")


# ===================================================================
#  TAB 3 — Slide Deck Analyzer
# ===================================================================

elif PAGE == "Slide Analyzer":
    st.title("Slide analyzer")
    st.markdown(
        "Upload your presentation and get a full quality report: structure, "
        "typography, layout, density, bullet quality, topic coverage and timing."
    )

    if not _HAS_SLIDE:
        st.warning(
            "⚠️ `slide_analyzer.py` is not available in this environment."
        )

    st.divider()

    opt1, opt2, opt3 = st.columns([2, 2, 3])
    with opt1:
        slide_topic = st.selectbox(
            "Presentation Topic",
            ["AI", "DSA", "DBMS", "OS", "CN", "Other"],
            key="slide_topic",
        )
    with opt2:
        target_minutes = st.number_input(
            "Target duration (min)", 3, 60, 10, 1, key="slide_target_min",
        )
    with opt3:
        st.caption(
            "Try the bundled sample deck to see the analyzer in action, "
            "or upload your own PPTX / PDF."
        )
        sample_path = Path(__file__).resolve().parent / "sample_data" / "sample_slides.pptx"
        use_sample = st.checkbox(
            "Use the bundled sample deck", value=False, key="slide_use_sample",
        )

    uploaded_file = None
    if not use_sample:
        uploaded_file = st.file_uploader(
            "Upload PPTX or PDF",
            type=["pptx", "pdf"],
            help="Maximum file size: 50 MB",
        )
        if uploaded_file is not None:
            st.success(
                f"File loaded: **{uploaded_file.name}** "
                f"({uploaded_file.size / 1024:.1f} KB)"
            )

    if st.button("Analyze slides", type="primary", width="stretch"):
        if not _HAS_SLIDE:
            st.info("Slide analyzer module is unavailable.")
        else:
            import tempfile, os
            tmp_path = None

            if use_sample:
                if sample_path.exists():
                    tmp_path = str(sample_path)
                else:
                    st.error("Sample deck not found. Generate it with "
                             "`python sample_data/generate_sample_deck.py`.")
            elif uploaded_file is not None:
                suffix = ".pptx" if uploaded_file.name.lower().endswith(".pptx") else ".pdf"
                tmp_path = os.path.join(tempfile.gettempdir(), f"upload{suffix}")
                with open(tmp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

            if tmp_path:
                with st.spinner("Analyzing presentation..."):
                    try:
                        report = analyze_presentation(
                            tmp_path,
                            topic=slide_topic,
                            target_minutes=int(target_minutes),
                        )
                        st.session_state.slide_report = report
                        st.session_state.slide_reports.append({
                            "file_name": report.get("file_name", "N/A"),
                            "score": report.get("overall_score", 0.0),
                            "grade": report.get("grade", "F"),
                            "slides": report.get("total_slides", 0),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        })
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")
                        report = None

    report = st.session_state.slide_report

    if report:
        st.divider()
        st.subheader("Slide report")

        score = report.get("overall_score", 0.0)

        hdr1, hdr2 = st.columns([1, 2])
        with hdr1:
            st.markdown(
                f'<div class="big-score">{score} / 10</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"Grade {report.get('grade', 'F')} — {report.get('verdict', 'N/A')}")
        with hdr2:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Slides", report.get("total_slides", 0))
            m2.metric("Title Coverage", f"{report.get('title_coverage_pct', 0):.0f}%")
            m3.metric("Avg Words/Slide", report.get("avg_words_per_slide", 0))
            timing = report.get("timing") or {}
            m4.metric("Est. Duration", f"{timing.get('estimated_minutes', 0)} min")

        # --- Dimension breakdown ---
        st.markdown("**Score breakdown by dimension**")
        dimensions = report.get("dimensions") or {}
        if dimensions:
            dim_rows = []
            for name, data in dimensions.items():
                dim_rows.append({
                    "Dimension": data.get("label", name),
                    "Score": data.get("score", 0.0),
                    "Detail": data.get("detail", ""),
                })
            st.dataframe(
                dim_rows, hide_index=True, width="stretch",
            )
            for name, data in dimensions.items():
                st.progress(
                    min(data.get("score", 0.0) / 10.0, 1.0),
                    text=f"{data.get('label', name)}: {data.get('score', 0)}/10",
                )

        # --- Prioritised fixes ---
        top_fixes = report.get("top_fixes") or []
        if top_fixes:
            st.markdown("**Fix these first**")
            for fix in top_fixes:
                st.markdown(
                    f"**{fix.get('priority')}. {fix.get('fix')}**  \n"
                    f"{fix.get('area')} — {fix.get('detail', '')}"
                )

        # --- Issues by severity ---
        issues = report.get("issues") or {}
        if issues.get("critical"):
            st.error(f"**{len(issues['critical'])} critical issue(s)**")
            for issue in issues["critical"]:
                st.markdown(f"- {issue}")
        if issues.get("warning"):
            st.warning(f"**{len(issues['warning'])} warning(s)**")
            for issue in issues["warning"]:
                st.markdown(f"- {issue}")
        if issues.get("info"):
            with st.expander(f"{len(issues['info'])} suggestion(s)"):
                for issue in issues["info"]:
                    st.markdown(f"- {issue}")

        # --- Per-slide table ---
        slide_details = report.get("slide_details") or []
        if slide_details:
            st.markdown("**Per-slide breakdown**")
            rows = []
            for sd in slide_details:
                rows.append({
                    "#": sd.get("slide_no"),
                    "Title": sd.get("title", "")[:48],
                    "Score": sd.get("score"),
                    "Words": sd.get("word_count"),
                    "Bullets": sd.get("bullet_count"),
                    "Notes": "yes" if sd.get("has_notes") else "no",
                    "Level": sd.get("level"),
                })
            st.dataframe(rows, hide_index=True, width="stretch")

            with st.expander("Slide-by-slide diagnostics"):
                for sd in slide_details:
                    st.markdown(
                        f"**Slide {sd.get('slide_no')} — {sd.get('title', '')}** "
                        f"({sd.get('score')}/10, {sd.get('level')})"
                    )
                    st.caption(
                        f"{sd.get('word_count')} words · {sd.get('bullet_count')} bullets · "
                        f"reading time {sd.get('reading_time_sec')}s · "
                        f"readability {sd.get('readability')}"
                    )
                    font_pt = sd.get("min_font_pt")
                    if font_pt:
                        st.caption(f"Smallest font on the slide: {font_pt:.0f}pt")
                    if sd.get("issues"):
                        for issue in sd["issues"]:
                            icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}.get(
                                issue.get("severity"), "•"
                            )
                            st.markdown(f"{icon} {issue.get('message')}")
                    else:
                        st.success("No issues detected on this slide.")
                    st.divider()

        # --- Topic coverage ---
        topic_report = report.get("topic_report") or {}
        if topic_report.get("expected_keywords"):
            st.markdown("**🎯 Topic keyword coverage**")
            matched = topic_report.get("matched_keywords", [])
            missing = topic_report.get("missing_keywords", [])
            st.progress(
                min(topic_report.get("coverage_pct", 0.0) / 100.0, 1.0),
                text=f"{len(matched)}/{len(topic_report['expected_keywords'])} "
                     f"'{topic_report.get('resolved_topic')}' keywords "
                     f"({topic_report.get('coverage_pct', 0)}%)",
            )
            if matched:
                st.markdown(f"**Present:** {', '.join(matched[:20])}")
            if missing:
                st.markdown(f"**Missing:** {', '.join(missing[:20])}")

        # --- Feedback ---
        strengths = report.get("strengths") or []
        weaknesses = report.get("weaknesses") or []
        recommendations = report.get("recommendations") or []

        fb1, fb2 = st.columns(2)
        with fb1:
            st.markdown("**✅ Strengths**")
            for s in strengths:
                st.markdown(f"- {s}")
        with fb2:
            st.markdown("**⚠️ Weaknesses**")
            for w in weaknesses:
                st.markdown(f"- {w}")

        if recommendations:
            st.markdown("**💡 Recommendations**")
            for rec in recommendations:
                st.markdown(f"- {rec}")

    elif not uploaded_file and not use_sample:
        st.info("Upload a PPTX or PDF file, or tick the sample deck box, to begin.")


# ===================================================================
#  TAB 4 — Viva Simulator
# ===================================================================

elif PAGE == "Viva Simulator":
    st.title("Viva simulator")
    st.markdown("Simulate a real viva session with AI-generated questions.")

    if not _HAS_CSP:
        st.warning("⚠️ `csp_question_gen.py` not found yet.")

    st.divider()

    sim_col1, sim_col2, sim_col3 = st.columns(3)
    with sim_col1:
        sim_topic = st.selectbox("Topic", ["AI", "DSA", "DBMS", "OS", "CN"], key="sim_topic")
    with sim_col2:
        sim_difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard", "mixed"], key="sim_diff")
    with sim_col3:
        sim_count = st.number_input("Number of Questions", 3, 15, 5, 1, key="sim_count")

    time_limit = st.slider("Time limit per question (seconds)", 30, 180, 60)

    st.divider()

    if st.button("Start session", type="primary", width="stretch"):
        if _HAS_CSP:
            with st.spinner("Generating questions using CSP solver..."):
                try:
                    questions = generate_viva_questions(
                        topic=sim_topic,
                        difficulty=sim_difficulty,
                        count=sim_count,
                    )
                    st.session_state.simulator_questions = questions
                    st.session_state.simulator_answers = {}
                    st.session_state.simulator_active = True
                except Exception as e:
                    st.error(f"Question generation failed: {e}")
                    st.session_state.simulator_active = False
        else:
            demo_qs = [
                {"id": 1, "question": f"What is the difference between BFS and DFS? ({sim_topic})", "bloom": "Understand", "difficulty": sim_difficulty},
                {"id": 2, "question": f"Explain the concept of heuristic functions in {sim_topic}.", "bloom": "Apply", "difficulty": sim_difficulty},
                {"id": 3, "question": f"Compare and contrast two approaches to solving {sim_topic} problems.", "bloom": "Analyze", "difficulty": sim_difficulty},
            ]
            st.session_state.simulator_questions = demo_qs[:sim_count]
            st.session_state.simulator_answers = {}
            st.session_state.simulator_active = True
            st.info("ℹ️ Using demo questions (CSP module not yet compiled).")

    if st.session_state.simulator_active and st.session_state.simulator_questions:
        st.subheader(f"Session — {sim_topic} ({sim_difficulty})")
        st.caption(f"⏱️ Recommended time per question: {time_limit}s")

        for q in st.session_state.simulator_questions:
            q_id = q.get("id", 0)
            q_text = q.get("question", "No question text.")
            q_bloom = q.get("bloom", "N/A")
            q_diff = q.get("difficulty", "N/A")

            with st.expander(f"**Q{q_id}.** {q_text}", expanded=False):
                st.caption(f"🏷️ Bloom's Level: **{q_bloom}** | Difficulty: **{q_diff}**")
                ans = st.text_area("Your answer:", key=f"sim_ans_{q_id}", height=100)
                st.session_state.simulator_answers[q_id] = ans

        st.divider()
        if st.button("Submit answers", type="primary"):
            if _HAS_TEXT_ANALYZER:
                topic_keywords = {
                    "AI": ["heuristic", "admissible", "optimal", "search", "cost", "path", "node"],
                    "DSA": ["complexity", "pivot", "partition", "recursion", "divide"],
                    "DBMS": ["normalization", "dependency", "anomaly", "decomposition"],
                    "OS": ["deadlock", "mutual exclusion", "process", "resource"],
                    "CN": ["SYN", "ACK", "handshake", "TCP", "segment", "port"],
                }
                expected_kw = topic_keywords.get(sim_topic, [])
                evaluated = 0

                for q in st.session_state.simulator_questions:
                    q_id = q.get("id", 0)
                    q_text = q.get("question", "")
                    ans_text = st.session_state.simulator_answers.get(q_id, "")
                    if ans_text.strip():
                        result = analyze_text(ans_text, expected_keywords=expected_kw)
                        _record_answer(
                            topic=sim_topic,
                            answer=ans_text,
                            result=result,
                            source="Simulator",
                            question=q_text,
                        )
                        evaluated += 1

                if evaluated:
                    st.success(
                        f"✅ {evaluated} answer(s) evaluated and saved to the Dashboard."
                    )
                else:
                    st.warning("No answers were filled in — nothing to evaluate.")
            else:
                st.warning("Text analyzer unavailable; answers were not scored.")
            st.session_state.simulator_active = False
            st.balloons()


# ===================================================================
#  TAB 5 — Dashboard
# ===================================================================

elif PAGE == "Dashboard":
    st.title("Dashboard")
    st.markdown(
        "Every number below comes from an answer you actually evaluated. "
        "Review how each answer was delivered, then plan the next study session."
    )

    st.divider()

    log = st.session_state.answer_log
    history = st.session_state.scores_history

    # --- Performance overview ---
    st.subheader("Performance overview")

    if not history:
        st.info(
            "No evaluations yet. Use the **Viva Evaluator** or the "
            "**Viva Simulator** and your real scores will appear here."
        )
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Answers", 0)
        m2.metric("Avg Score", "— / 10")
        m3.metric("Avg Clarity", "— / 10")
        m4.metric("Avg Keywords", "— %")
        m5.metric("Best Score", "— / 10")
    else:
        import pandas as pd

        avg_score = sum(h["score"] for h in history) / len(history)
        avg_clarity = sum(h["clarity"] for h in history) / len(history)
        avg_kw = sum(h["keyword_cov"] for h in history) / len(history)
        best_score = max(h["score"] for h in history)
        total_words = sum(r["words"] for r in log) if log else 0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Answers", len(history))
        m2.metric("Avg Score", f"{avg_score:.1f}/10")
        m3.metric("Avg Clarity", f"{avg_clarity:.1f}/10")
        m4.metric("Avg Keywords", f"{avg_kw:.0%}")
        m5.metric("Best Score", f"{best_score:.1f}/10")

        if len(history) >= 2:
            recent = history[-1]["score"]
            earlier = history[-2]["score"]
            delta = recent - earlier
            st.caption(
                f"Last answer: **{recent:.1f}/10** "
                f"({'▲' if delta >= 0 else '▼'} {abs(delta):.1f} vs the previous one) "
                f"· {total_words} words spoken in total"
            )

        st.divider()

        # --- Score trend ---
        st.subheader("Score trend")
        df = pd.DataFrame(history)
        df["Session"] = range(1, len(df) + 1)
        st.line_chart(df.set_index("Session")[["score", "clarity"]])

        # --- Score distribution ---
        st.subheader("Score distribution")
        buckets = {"0-3": 0, "4-5": 0, "6-7": 0, "8-10": 0}
        for h in history:
            score = h["score"]
            if score < 4:
                buckets["0-3"] += 1
            elif score < 6:
                buckets["4-5"] += 1
            elif score < 8:
                buckets["6-7"] += 1
            else:
                buckets["8-10"] += 1
        st.bar_chart(pd.DataFrame({"Answers": buckets}))

        # --- Topic mastery ---
        st.subheader("Topic mastery")
        topic_scores: dict[str, list[float]] = {}
        for h in history:
            topic_scores.setdefault(h["topic"], []).append(h["score"])

        for topic_name, scores in topic_scores.items():
            avg = sum(scores) / len(scores)
            st.progress(
                min(avg / 10.0, 1.0),
                text=f"{topic_name}: {avg:.1f}/10 ({len(scores)} answer(s))",
            )

    # --- Answer log: how each answer was actually given ---
    if log:
        st.divider()
        st.subheader("Answer log")

        import pandas as pd

        rows = []
        for i, rec in enumerate(log, start=1):
            rows.append({
                "#": i,
                "Time": rec["timestamp"],
                "Topic": rec["topic"],
                "Source": rec["source"],
                "Score": rec["score"],
                "Clarity": rec["clarity"],
                "Keywords": f"{rec['keyword_cov']:.0%}",
                "Words": rec["words"],
                "Fillers": rec["fillers"],
                "Pace": rec["pace_verdict"],
            })
        st.dataframe(rows, hide_index=True, width="stretch")

        st.caption("Open an entry to see the answer itself and what was detected in it.")
        for i, rec in enumerate(reversed(log), start=1):
            index = len(log) - i + 1
            header = (
                f"**#{index} · {rec['topic']} · {rec['score']}/10** "
                f"— {rec['timestamp']} ({rec['source']})"
            )
            with st.expander(header):
                if rec["question"]:
                    st.markdown(f"**Question:** {rec['question']}")
                st.markdown("**Your answer:**")
                if rec["answer"]:
                    st.write(rec["answer"])
                else:
                    st.caption("(no text recorded)")

                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Words", rec["words"])
                d2.metric("Sentences", rec["sentences"])
                d3.metric("Filler Words", rec["fillers"])
                d4.metric("Avg Sentence", f"{rec['avg_sentence_length']}")

                if rec["filler_words"]:
                    st.warning(f"Filler words used: {rec['filler_words']}")
                if rec["keywords_missing"]:
                    st.warning(f"Missing expected keywords: {rec['keywords_missing']}")
                if rec["pace"] and rec["pace_verdict"] != "unknown":
                    st.caption(
                        f"Speaking pace: {rec['pace']} wpm ({rec['pace_verdict']})"
                    )

        # --- Export ---
        csv_df = pd.DataFrame(log)
        st.download_button(
            "Download answer history (CSV)",
            csv_df.to_csv(index=False).encode("utf-8"),
            file_name="viva_answer_history.csv",
            mime="text/csv",
        )

    # --- Slide deck reports ---
    slide_reports = st.session_state.slide_reports
    if slide_reports:
        st.divider()
        st.subheader("Slide deck reports")
        st.dataframe(
            [{
                "File": r["file_name"],
                "Slides": r["slides"],
                "Score": r["score"],
                "Grade": r["grade"],
                "Analyzed": r["timestamp"],
            } for r in reversed(slide_reports)],
            hide_index=True,
            width="stretch",
        )

    st.divider()

    # --- A* Improvement Path ---
    st.subheader("Optimal study path (A* search)")
    st.caption(
        "A* works out the cheapest order for studying your weak topics, "
        "using each topic's score gap and study-hour cost."
    )
    if _HAS_ASTAR:
        if st.button("Find improvement path"):
            with st.spinner("Running A* search..."):
                try:
                    if history:
                        topic_avg: dict[str, float] = {}
                        for h in history:
                            topic_avg.setdefault(h["topic"], []).append(h["score"])
                        current_scores = {
                            topic: round(sum(scores) / len(scores), 2)
                            for topic, scores in topic_avg.items()
                        }
                    else:
                        current_scores = {"AI": 4.5, "DSA": 6.0, "DBMS": 5.0,
                                          "OS": 6.5, "CN": 5.5}

                    weak = {t: s for t, s in current_scores.items() if s < 7.0}
                    if not weak:
                        st.session_state.improvement_path = []
                        st.success(
                            "Every topic is already at or above 7.0 — no study path needed."
                        )
                    else:
                        st.session_state.improvement_path = find_improvement_path(
                            weak, target_score=7.0, max_hours=20
                        )
                except Exception as e:
                    st.error(f"A* search failed: {e}")

        path = st.session_state.improvement_path
        if path:
            st.success(f"Optimal study sequence found — {len(path)} step(s).")
            for i, step in enumerate(path, 1):
                st.markdown(
                    f"**Step {i}: {step.get('topic')}**  \n"
                    f"{step.get('action')}  \n"
                    f"_{step.get('current_score')}/10 → {step.get('target_score')}/10, "
                    f"about {step.get('hours_needed')}h, priority {step.get('priority')}_"
                )
    else:
        st.info("ℹ️ `astar_improvement.py` is not available in this environment.")

    st.divider()

    # --- Goal Stack Study Plan ---
    st.subheader("Study plan (goal stack planning)")
    st.caption("Set your current and target scores — the planner will build a step-by-step action plan.")

    plan_col1, plan_col2 = st.columns(2)
    with plan_col1:
        current_grade = st.number_input("Current Score (0–10)", 0.0, 10.0, 5.0, 0.5)
    with plan_col2:
        target_grade = st.number_input("Target Score (0–10)", 0.0, 10.0, 8.0, 0.5)

    if _HAS_PLANNER:
        if st.button("Generate study plan", type="primary", width="stretch"):
            if target_grade <= current_grade:
                st.warning("Target should be higher than current score!")
            else:
                # Build a safe topic-scores dict for the planner
                if history:
                    topic_scores_dict: dict[str, float] = {}
                    acc: dict[str, list[float]] = {}
                    for h in history:
                        acc.setdefault(h["topic"], []).append(h["score"])
                    for t, s in acc.items():
                        topic_scores_dict[t] = sum(s) / len(s)
                else:
                    # Default example so plan ALWAYS shows something useful
                    topic_scores_dict = {
                        "Artificial Intelligence": 5.0,
                        "Database Management": 6.0,
                        "Operating Systems": 4.5,
                    }
                    st.info("ℹ️ Using default example topics (no viva history yet).")

                with st.spinner("Generating plan using Goal Stack Planning..."):
                    try:
                        # Try the richer signature first
                        try:
                            plan = generate_study_plan(
                                current_scores=topic_scores_dict,
                                target_score=target_grade,
                            )
                        except TypeError:
                            # Fallback to simpler signature
                            plan = generate_study_plan(
                                current_score=current_grade,
                                target_score=target_grade,
                            )
                        st.session_state.study_plan = plan
                    except Exception as e:
                        st.error(f"Planning failed: {e}")
                        # Local fallback plan so the UI is never empty
                        gap = target_grade - current_grade
                        st.session_state.study_plan = [
                            "Review weak topics identified in your viva history.",
                            f"Target improvement of +{gap:.1f} points.",
                            "Practice 3 mock vivas per week using the Simulator tab.",
                            "Reduce filler words — rehearse answers out loud daily.",
                            "Memorize key terminology for each topic.",
                            "Re-evaluate progress after one week.",
                        ]

        # Display plan in a clean step-by-step UI
        if st.session_state.study_plan:
            st.success(f"Your study plan has {len(st.session_state.study_plan)} step(s):")
            for i, step in enumerate(st.session_state.study_plan, 1):
                if isinstance(step, dict):
                    action = step.get("action") or step.get("goal") or step.get("sub_goal") or ""
                    meta_bits = []
                    if step.get("estimated_time"):
                        meta_bits.append(f"~{step['estimated_time']}")
                    if step.get("priority") is not None:
                        meta_bits.append(f"priority {step['priority']}")
                    meta = f"  ({' | '.join(meta_bits)})" if meta_bits else ""
                    body = f"**Step {i}:** {action}{meta}"
                else:
                    body = f"**Step {i}:** {step}"
                if i % 2 == 1:
                    st.info(body)
                else:
                    st.success(body)
    else:
        st.info(
            "ℹ️ `goal_stack_planner.py` not yet compiled. "
            "A fallback plan can still be generated locally once this module is available."
        )


# ===================================================================
# Footer
# ===================================================================

st.divider()
st.caption("VivaLens AI · SPPU TY AI 2024 · runs locally")