"""
app.py — VivaLens AI
Sprint 5 (v2) | Agent: PRISM (UI/UX & Speech Engineer)

Main Streamlit multi-page application for VivaLens AI.
Provides 5 navigation tabs: Home, Viva Evaluator, Slide Analyzer,
Viva Simulator, and Analytics Dashboard.

v2 Updates:
    - Tab 1: Rebuilt as a professional product landing page
    - Tab 2: Added follow-up questions + bulleted suggestions
    - Tab 5: Robust study plan with default fallback + cleaner UI

Run:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st
import time
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
    /* Main background */
    .stApp {
        background-color: #0e1117;
    }
    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #1a1d24;
        border: 1px solid #2d3139;
        border-radius: 10px;
        padding: 15px;
    }
    /* Sidebar header */
    .sidebar-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.2rem;
    }
    .sidebar-sub {
        font-size: 0.85rem;
        color: #8b8fa3;
    }
    /* Score badge */
    .score-badge {
        display: inline-block;
        padding: 6px 18px;
        border-radius: 20px;
        font-size: 1.4rem;
        font-weight: 700;
        color: #fff;
    }
    .score-high   { background-color: #21c354; }
    .score-medium { background-color: #f5a623; }
    .score-low    { background-color: #e74c3c; }

    /* Native-style buttons */
    .stButton > button {
        background: #1c2030;
        color: #e6e9f2;
        font-weight: 500;
        border: 1px solid #30364a;
        border-radius: 8px;
        transition: background 0.15s ease, border-color 0.15s ease;
    }
    .stButton > button:hover {
        background: #242a3d;
        border-color: #4a5a7a;
        color: #ffffff;
    }

    /* ----- Landing page styling ----- */
    .hero-title {
        font-size: 3.2rem;
        font-weight: 800;
        color: #ffffff;
        text-align: center;
        margin-top: 1rem;
        margin-bottom: 0.3rem;
        letter-spacing: -1px;
    }
    .hero-sub {
        font-size: 1.15rem;
        color: #a0a5b8;
        text-align: center;
        margin-bottom: 2.5rem;
    }
    .feature-card {
        background: linear-gradient(145deg, #1a1d24, #22262f);
        border: 1px solid #2d3139;
        border-radius: 14px;
        padding: 24px 20px;
        min-height: 210px;
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .feature-card:hover {
        transform: translateY(-4px);
        border-color: #4a90e2;
    }
    .feature-icon {
        font-size: 2.4rem;
        margin-bottom: 10px;
    }
    .feature-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 8px;
    }
    .feature-desc {
        font-size: 0.9rem;
        color: #a0a5b8;
        line-height: 1.5;
    }
    .cta-banner {
        background: linear-gradient(90deg, #4a90e2, #6b5fbf);
        padding: 18px 24px;
        border-radius: 12px;
        text-align: center;
        color: #ffffff;
        font-size: 1rem;
        margin-top: 2rem;
    }

    /* ----- Study plan step styling ----- */
    .plan-step {
        background-color: #1a1d24;
        border-left: 4px solid #4a90e2;
        padding: 12px 18px;
        margin: 8px 0;
        border-radius: 6px;
        color: #e0e3eb;
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
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.markdown(
    '<p class="sidebar-title">🎓 VivaLens AI</p>'
    '<p class="sidebar-sub">Presentation & Viva Analyzer</p>',
    unsafe_allow_html=True,
)
st.sidebar.divider()

PAGE = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Home",
        "🎤 Viva Evaluator",
        "📊 Slide Analyzer",
        "❓ Viva Simulator",
        "📈 Dashboard",
    ],
    index=0,
)

st.sidebar.divider()
st.sidebar.caption("VivaLens AI v1.1 · 100% Free & Offline")


# ===================================================================
#  TAB 1 — 🏠 Home (Product Landing Page)
# ===================================================================

if PAGE == "🏠 Home":
    # --- Hero section ---
    st.markdown(
        '<p class="hero-title">Welcome to VivaLens AI</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="hero-sub">Your Personal AI-Powered Presentation and Viva Analyzer</p>',
        unsafe_allow_html=True,
    )

    # --- 4 Feature Cards ---
    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">🗣️</div>
            <div class="feature-title">Viva Evaluator</div>
            <div class="feature-desc">
                Speak or type your answers and get instant feedback on clarity,
                keywords, pace, and filler words.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📊</div>
            <div class="feature-title">Slide Analyzer</div>
            <div class="feature-desc">
                Upload your PPTX or PDF slides and receive a detailed quality
                report with actionable improvement tips.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">❓</div>
            <div class="feature-title">Viva Simulator</div>
            <div class="feature-desc">
                Practice with AI-generated questions tailored to your topic,
                difficulty level, and Bloom's taxonomy coverage.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class="feature-card">
            <div class="feature-icon">📈</div>
            <div class="feature-title">Smart Study Planner</div>
            <div class="feature-desc">
                Get a personalized step-by-step study plan to reach your
                target score, built using intelligent planning algorithms.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- Call-to-action banner ---
    st.markdown("""
    <div class="cta-banner">
        🚀 <b>Ready to boost your viva performance?</b> &nbsp;
        Pick a tool from the left sidebar and start practicing — it's 100% free and runs offline.
    </div>
    """, unsafe_allow_html=True)

    # --- Quick stats ---
    st.markdown("")
    st.markdown("")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Topics Covered", "5+")
    s2.metric("AI Algorithms", "7")
    s3.metric("Offline Ready", "✅ Yes")
    s4.metric("Cost", "Free")


# ===================================================================
#  TAB 2 — 🎤 Viva Answer Evaluator
# ===================================================================

elif PAGE == "🎤 Viva Evaluator":
    st.title("🎤 Viva Answer Evaluator")
    st.markdown("Speak or type your answer and get instant AI-powered feedback.")

    if not _HAS_TEXT_ANALYZER:
        st.error("❌ `text_analyzer.py` not found. Please compile the Sprint 2 files first.")
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
            ["✍️ Type Answer", "🎙️ Record Audio", "📁 Upload WAV"],
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

    if input_mode == "✍️ Type Answer":
        answer_text = st.text_area(
            "Type your answer below:",
            height=180,
            placeholder="Start typing your viva answer here...",
        )

    elif input_mode == "🎙️ Record Audio":
        if _HAS_SPEECH:
            speech_status = is_speech_available()
            if speech_status["mic_available"]:
                duration = st.slider("Recording duration (seconds)", 5, 60, 15)
                if st.button("🔴 Start Recording"):
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

    elif input_mode == "📁 Upload WAV":
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
    if st.button("🔍 Evaluate Answer", type="primary", use_container_width=True):
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
            st.session_state.scores_history.append({
                "topic": topic,
                "score": result["overall_text_score"],
                "clarity": result["clarity_score"],
                "keyword_cov": result["keyword_coverage"],
            })

            # --- Scorecard display ---
            st.subheader("📋 Scorecard")

            score = result["overall_text_score"]
            badge_class = "score-high" if score >= 7 else "score-medium" if score >= 4 else "score-low"
            st.markdown(
                f'<span class="score-badge {badge_class}">{score} / 10</span>',
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
            st.subheader("💡 Actionable Suggestions")
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
                suggestions.append("Great job! Keep practicing to maintain this quality. 🎉")

            for s in suggestions:
                st.markdown(f"- {s}")

            # --- Follow-up Questions ---
            st.divider()
            st.subheader("🔁 Recommended Follow-up Questions")
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
                st.subheader("🧠 FOL Reasoning Trace")
                st.json(fol_result)
            elif _HAS_INFERENCE and fol_result and "error" in fol_result:
                st.warning(f"FOL engine error: {fol_result['error']}")


# ===================================================================
#  TAB 3 — 📊 Slide Deck Analyzer  (unchanged)
# ===================================================================

elif PAGE == "📊 Slide Analyzer":
    st.title("📊 Slide Deck Analyzer")
    st.markdown("Upload your presentation slides and get an instant quality report.")

    if not _HAS_SLIDE:
        st.warning(
            "⚠️ `slide_analyzer.py` not found yet. "
            "This module will be available once the Bonus Module is compiled."
        )

    st.divider()

    slide_topic = st.selectbox(
        "Presentation Topic",
        ["AI", "DSA", "DBMS", "OS", "CN", "Other"],
        key="slide_topic",
    )

    uploaded_file = st.file_uploader(
        "Upload PPTX or PDF",
        type=["pptx", "pdf"],
        help="Maximum file size: 50 MB",
    )

    if uploaded_file is not None:
        st.success(f"📎 File loaded: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

        if st.button("🔍 Analyze Slides", type="primary", use_container_width=True):
            if _HAS_SLIDE:
                import tempfile, os
                suffix = ".pptx" if uploaded_file.name.endswith(".pptx") else ".pdf"
                tmp_path = os.path.join(tempfile.gettempdir(), f"upload{suffix}")
                with open(tmp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                with st.spinner("Analyzing presentation..."):
                    try:
                        report = analyze_presentation(tmp_path, topic=slide_topic)
                        st.session_state.slide_report = report
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")
                        report = None

                if report:
                    st.subheader("📋 Slide Report")
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.metric("Overall Score", f"{report.get('overall_score', 'N/A')}/10")
                    sc2.metric("Title Coverage", f"{report.get('title_coverage', 0):.0%}")
                    sc3.metric("Total Slides", report.get("slide_count", "N/A"))

                    if report.get("overloaded_slides"):
                        st.warning(
                            f"⚠️ Overloaded slides (too much text): "
                            f"{', '.join(map(str, report['overloaded_slides']))}"
                        )
                    if report.get("recommendations"):
                        st.markdown("**💡 Recommendations:**")
                        for rec in report["recommendations"]:
                            st.markdown(f"- {rec}")
            else:
                st.info("🔄 Slide analyzer module pending.")
    else:
        st.info("👆 Upload a PPTX or PDF file to begin analysis.")


# ===================================================================
#  TAB 4 — ❓ Interactive Viva Simulator  (unchanged)
# ===================================================================

elif PAGE == "❓ Viva Simulator":
    st.title("❓ Interactive Viva Simulator")
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

    if st.button("🚀 Start Viva Session", type="primary", use_container_width=True):
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
        st.subheader(f"📝 Viva Session — {sim_topic} ({sim_difficulty})")
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
        if st.button("✅ Submit All Answers", type="primary"):
            st.success("Answers submitted! Check the 📈 Dashboard for your scores.")
            if _HAS_TEXT_ANALYZER:
                for q in st.session_state.simulator_questions:
                    q_id = q.get("id", 0)
                    ans_text = st.session_state.simulator_answers.get(q_id, "")
                    if ans_text.strip():
                        result = analyze_text(ans_text)
                        st.session_state.scores_history.append({
                            "topic": sim_topic,
                            "score": result["overall_text_score"],
                            "clarity": result["clarity_score"],
                            "keyword_cov": result["keyword_coverage"],
                        })
            st.session_state.simulator_active = False
            st.balloons()


# ===================================================================
#  TAB 5 — 📈 Analytics & Study Planner  (overhauled)
# ===================================================================

elif PAGE == "📈 Dashboard":
    st.title("📈 Analytics & Study Planner")
    st.markdown("Track your progress and get an AI-generated study plan.")

    st.divider()

    # --- Performance overview ---
    st.subheader("📊 Performance Overview")
    history = st.session_state.scores_history

    if not history:
        st.info("No evaluations yet — showing demo metrics. Take a viva to see your real stats.")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sessions", 0)
        m2.metric("Avg Score", "— / 10")
        m3.metric("Avg Clarity", "— / 10")
        m4.metric("Avg Keywords", "— %")
    else:
        avg_score = sum(h["score"] for h in history) / len(history)
        avg_clarity = sum(h["clarity"] for h in history) / len(history)
        avg_kw = sum(h["keyword_cov"] for h in history) / len(history)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sessions", len(history))
        m2.metric("Avg Score", f"{avg_score:.1f}/10")
        m3.metric("Avg Clarity", f"{avg_clarity:.1f}/10")
        m4.metric("Avg Keywords", f"{avg_kw:.0%}")

        st.divider()

        # Bar chart of scores over time
        st.subheader("📉 Score Trend")
        import pandas as pd
        df = pd.DataFrame(history)
        df["Session"] = range(1, len(df) + 1)
        st.bar_chart(df.set_index("Session")[["score", "clarity"]])

        # Topic mastery bars (grouped by topic)
        st.subheader("🎯 Topic Mastery")
        topic_scores: dict[str, list[float]] = {}
        for h in history:
            topic_scores.setdefault(h["topic"], []).append(h["score"])

        for topic_name, scores in topic_scores.items():
            avg = sum(scores) / len(scores)
            st.progress(min(avg / 10.0, 1.0), text=f"{topic_name}: {avg:.1f}/10 ({len(scores)} session(s))")

    st.divider()

    # --- A* Improvement Path ---
    st.subheader("🧭 Optimal Study Path (A* Search)")
    if _HAS_ASTAR:
        if st.button("🔍 Find Improvement Path"):
            with st.spinner("Running A* search..."):
                try:
                    # Use real weak topics if available, else sensible defaults
                    if history:
                        topic_avg: dict[str, float] = {}
                        for h in history:
                            topic_avg.setdefault(h["topic"], []).append(h["score"])  # type: ignore
                        weak_topics = [t for t, s in topic_avg.items()
                                       if (sum(s) / len(s)) < 7.0]
                        if not weak_topics:
                            weak_topics = ["AI", "DBMS"]
                    else:
                        weak_topics = ["AI", "DBMS", "OS"]

                    path = find_improvement_path(weak_topics)
                    st.session_state.improvement_path = path
                except Exception as e:
                    st.error(f"A* search failed: {e}")

        if st.session_state.improvement_path:
            st.success("Optimal study sequence found!")
            for i, step in enumerate(st.session_state.improvement_path, 1):
                st.markdown(f"**Step {i}:** {step}")
    else:
        st.info("ℹ️ `astar_improvement.py` not yet compiled.")

    st.divider()

    # --- Goal Stack Study Plan ---
    st.subheader("📋 Personalized Study Plan (Goal Stack Planning)")
    st.caption("Set your current and target scores — the planner will build a step-by-step action plan.")

    plan_col1, plan_col2 = st.columns(2)
    with plan_col1:
        current_grade = st.number_input("Current Score (0–10)", 0.0, 10.0, 5.0, 0.5)
    with plan_col2:
        target_grade = st.number_input("Target Score (0–10)", 0.0, 10.0, 8.0, 0.5)

    if _HAS_PLANNER:
        if st.button("📝 Generate Study Plan", type="primary", use_container_width=True):
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
            st.success(f"✅ Your personalized plan has {len(st.session_state.study_plan)} step(s):")
            for i, step in enumerate(st.session_state.study_plan, 1):
                # Alternate st.info / st.success for visual rhythm
                step_text = step if isinstance(step, str) else str(step)
                if i % 2 == 1:
                    st.info(f"**Step {i}:** {step_text}")
                else:
                    st.success(f"**Step {i}:** {step_text}")
    else:
        st.info(
            "ℹ️ `goal_stack_planner.py` not yet compiled. "
            "A fallback plan can still be generated locally once this module is available."
        )


# ===================================================================
# Footer
# ===================================================================

st.divider()
st.caption("🎓 VivaLens AI · SPPU TY AI 2024 · 100% Free & Offline")