import streamlit as st
from pdf_utils import extract_text_from_bytes, extract_text_from_upload, file_hash, summarize_resume_for_context
from latex_utils import compile_latex_to_pdf
from ai_optimizer import optimize_resume, optimize_cover_letter, GITHUB_FREE_MODELS
import base64
import os

# ── Template persistence ──
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
CV_TEMPLATE_PATH = os.path.join(TEMPLATE_DIR, "resume_template.tex")
CL_TEMPLATE_PATH = os.path.join(TEMPLATE_DIR, "cover_letter_template.tex")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

def load_template(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def save_template(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def display_pdf(pdf_bytes):
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}#toolbar=0" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

st.set_page_config(page_title="ResumeAI Pro", page_icon="🎯", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp {
    background-color: #0a0a0f !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Hide streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 3rem !important; max-width: 1400px !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0d0d18 !important;
    border-right: 1px solid #1e1e3a !important;
}
[data-testid="stSidebar"] * { color: #94a3b8 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label { color: #64748b !important; font-size: 0.75rem !important; letter-spacing: 0.08em !important; text-transform: uppercase !important; }

/* Hero header */
.hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #38bdf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.25rem 0;
    line-height: 1.1;
}
.hero-sub {
    color: #475569;
    font-size: 0.9rem;
    font-weight: 400;
    margin-bottom: 2.5rem;
    letter-spacing: 0.01em;
}

/* Step chips */
.step-row {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 2rem;
    align-items: center;
}
.step-chip {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.9rem;
    border-radius: 100px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid #1e1e3a;
    color: #475569;
    background: #0d0d18;
    transition: all 0.2s;
}
.step-chip.active {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    border-color: transparent;
    color: #fff;
    box-shadow: 0 0 20px rgba(99,102,241,0.35);
}
.step-chip.done {
    border-color: #10b981;
    color: #10b981;
    background: rgba(16,185,129,0.07);
}
.step-divider {
    width: 24px;
    height: 1px;
    background: #1e1e3a;
}

/* Cards */
.card {
    background: #0d0d18;
    border: 1px solid #1e1e3a;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
}
.card:hover { border-color: #2d2d5a; }
.card-title {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #475569;
    margin-bottom: 1rem;
}

/* Mode selector pills */
div[data-testid="stRadio"] > div { gap: 0.5rem !important; }
div[data-testid="stRadio"] label {
    background: #0d0d18 !important;
    border: 1px solid #1e1e3a !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-size: 0.82rem !important;
    color: #64748b !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
}
div[data-testid="stRadio"] label:hover { border-color: #4f46e5 !important; color: #818cf8 !important; }

/* Score badge */
.score-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 90px;
    height: 90px;
    border-radius: 50%;
    font-size: 1.6rem;
    font-weight: 700;
    border: 3px solid;
    margin-bottom: 0.5rem;
}
.score-badge.high { border-color: #10b981; color: #10b981; background: rgba(16,185,129,0.08); box-shadow: 0 0 24px rgba(16,185,129,0.2); }
.score-badge.mid  { border-color: #f59e0b; color: #f59e0b; background: rgba(245,158,11,0.08); box-shadow: 0 0 24px rgba(245,158,11,0.2); }
.score-badge.low  { border-color: #ef4444; color: #ef4444; background: rgba(239,68,68,0.08); box-shadow: 0 0 24px rgba(239,68,68,0.2); }

/* Tips */
.tip-item {
    display: flex;
    gap: 0.75rem;
    padding: 0.6rem 0;
    border-bottom: 1px solid #12122a;
    font-size: 0.84rem;
    color: #94a3b8;
    align-items: flex-start;
}
.tip-item:last-child { border-bottom: none; }
.tip-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #818cf8;
    margin-top: 6px;
    flex-shrink: 0;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.02em !important;
    padding: 0.65rem 1.5rem !important;
    transition: all 0.2s !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.3) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 28px rgba(99,102,241,0.45) !important;
}

/* Download buttons */
.stDownloadButton > button {
    background: transparent !important;
    border: 1px solid #1e1e3a !important;
    border-radius: 8px !important;
    color: #94a3b8 !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    transition: all 0.2s !important;
}
.stDownloadButton > button:hover {
    border-color: #4f46e5 !important;
    color: #818cf8 !important;
    background: rgba(79,70,229,0.08) !important;
}

/* Text areas */
.stTextArea textarea {
    background: #070710 !important;
    border: 1px solid #1e1e3a !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    resize: vertical !important;
}
.stTextArea textarea:focus { border-color: #4f46e5 !important; box-shadow: 0 0 0 2px rgba(79,70,229,0.2) !important; }
.stTextArea label { color: #475569 !important; font-size: 0.72rem !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; font-weight: 600 !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: #070710 !important;
    border: 1px dashed #1e1e3a !important;
    border-radius: 10px !important;
    transition: border-color 0.2s !important;
}
[data-testid="stFileUploader"]:hover { border-color: #4f46e5 !important; }
[data-testid="stFileUploader"] label { color: #475569 !important; font-size: 0.72rem !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; font-weight: 600 !important; }
[data-testid="stFileUploader"] p { color: #334155 !important; font-size: 0.78rem !important; }

/* Selectbox */
.stSelectbox > div > div {
    background: #0d0d18 !important;
    border: 1px solid #1e1e3a !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}
.stSelectbox label { color: #475569 !important; font-size: 0.72rem !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; font-weight: 600 !important; }

/* Text input */
.stTextInput input {
    background: #0d0d18 !important;
    border: 1px solid #1e1e3a !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
    font-size: 0.84rem !important;
}
.stTextInput input:focus { border-color: #4f46e5 !important; }
.stTextInput label { color: #475569 !important; font-size: 0.72rem !important; text-transform: uppercase !important; letter-spacing: 0.08em !important; font-weight: 600 !important; }

/* Divider */
hr { border-color: #1e1e3a !important; margin: 2rem 0 !important; }

/* Spinner */
.stSpinner > div { border-color: #4f46e5 transparent transparent !important; }

/* Error / success */
.stAlert { border-radius: 8px !important; border: 1px solid !important; font-size: 0.83rem !important; }

/* Metric */
[data-testid="stMetric"] { background: transparent !important; }

/* Section label */
.section-label {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #334155;
    margin-bottom: 0.75rem;
}

/* Subheader override */
h2, h3 {
    color: #e2e8f0 !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-label">⚙ Configuration</div>', unsafe_allow_html=True)
    api_provider_base = st.selectbox("API Provider", [
        "GitHub Models (Free)",
        "Gemini (Google)",
        "Groq",
        "Ollama (Local)",
    ])

    api_provider = api_provider_base  # will be overridden for GitHub Models

    if api_provider_base == "GitHub Models (Free)":
        model_label = st.selectbox("Model", list(GITHUB_FREE_MODELS.keys()))
        api_provider = f"GitHub Models — {model_label}"
        st.caption("[Get a free GitHub PAT](https://github.com/settings/tokens) with `models:read` permission")
        api_key = st.text_input("GitHub PAT", type="password", placeholder="ghp_...")
        st.caption("🟠 Free tier: 150 req/day · 15 req/min")
    elif api_provider_base == "Ollama (Local)":
        st.caption("Make sure Ollama is running locally")
        api_key = st.text_input("Model Name", value="llama3")
    else:
        if api_provider_base == "Gemini (Google)":
            st.caption("[Get Gemini Key](https://aistudio.google.com/app/apikey)")
        else:
            st.caption("[Get Groq Key](https://console.groq.com/keys)")
        api_key = st.text_input("API Key", type="password")

    st.divider()
    language = st.selectbox("Output Language", ["English", "German (Deutsch)"])

# ──────────────────────────────────────────────
# HERO
# ──────────────────────────────────────────────
has_results = 'results' in st.session_state and st.session_state['results']
has_pdfs    = 'rendered_pdfs' in st.session_state and st.session_state['rendered_pdfs']

st.markdown('<div class="hero-title">Resume · AI Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">ATS-optimized documents, compiled with your exact formatting.</div>', unsafe_allow_html=True)

# Step tracker
s1 = "active"
s2 = "done" if has_results else ("active" if False else "")
s3 = "done" if has_pdfs else ""
st.markdown(f"""
<div class="step-row">
  <div class="step-chip {"done" if has_results or has_pdfs else "active"}">① Upload &amp; Analyze</div>
  <div class="step-divider"></div>
  <div class="step-chip {"done" if has_pdfs else ("active" if has_results else "")}">② Review LaTeX</div>
  <div class="step-divider"></div>
  <div class="step-chip {"active" if has_pdfs else ""}">③ Compile &amp; Download</div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# STEP 1: INPUTS
# ──────────────────────────────────────────────
st.markdown('<div class="section-label">What to generate</div>', unsafe_allow_html=True)
generation_mode = st.radio("", ["Both (Resume + Cover Letter)", "Resume Only", "Cover Letter Only"], horizontal=True, label_visibility="collapsed")

col1, col2 = st.columns(2, gap="large")
with col1:
    st.markdown('<div class="section-label">Master Documents</div>', unsafe_allow_html=True)
    # Defaults — overridden below depending on generation mode
    cv_file, cl_file = None, None
    cv_latex = st.session_state.get("cv_latex_saved", "")
    cl_latex = st.session_state.get("cl_latex_saved", "")

    # Load saved templates from disk on first run
    if "cv_latex_saved" not in st.session_state:
        st.session_state["cv_latex_saved"] = load_template(CV_TEMPLATE_PATH)
    if "cl_latex_saved" not in st.session_state:
        st.session_state["cl_latex_saved"] = load_template(CL_TEMPLATE_PATH)

    if generation_mode in ["Both (Resume + Cover Letter)", "Resume Only"]:
        cv_file  = st.file_uploader("Resume (PDF or .tex)", type=["pdf", "tex"])
        cv_latex = st.text_area(
            "Resume LaTeX Template",
            value=st.session_state["cv_latex_saved"],
            height=130,
            placeholder="Paste your master .tex source here… (auto-saved once you click Save below)",
            key="cv_latex_input"
        )
        if cv_latex != st.session_state["cv_latex_saved"]:
            if st.button("💾  Save as Master Resume Template", key="save_cv"):
                save_template(CV_TEMPLATE_PATH, cv_latex)
                st.session_state["cv_latex_saved"] = cv_latex
                st.success("Resume template saved permanently!")
    elif generation_mode == "Cover Letter Only":
        cv_file = st.file_uploader("Resume (PDF or .tex, for context)", type=["pdf", "tex"])
        cv_latex = st.session_state.get("cv_latex_saved", "")

    if generation_mode in ["Both (Resume + Cover Letter)", "Cover Letter Only"]:
        cl_file  = st.file_uploader("Cover Letter (PDF or .tex)", type=["pdf", "tex"])
        cl_latex = st.text_area(
            "Cover Letter LaTeX Template",
            value=st.session_state["cl_latex_saved"],
            height=130,
            placeholder="Paste your master .tex source here… (auto-saved once you click Save below)",
            key="cl_latex_input"
        )
        if cl_latex != st.session_state["cl_latex_saved"]:
            if st.button("💾  Save as Master Cover Letter Template", key="save_cl"):
                save_template(CL_TEMPLATE_PATH, cl_latex)
                st.session_state["cl_latex_saved"] = cl_latex
                st.success("Cover letter template saved permanently!")

with col2:
    st.markdown('<div class="section-label">Job Description</div>', unsafe_allow_html=True)
    jd_options = st.radio("", ["Paste Text", "No JD — General Update"], label_visibility="collapsed")
    jd_text = ""
    if jd_options == "Paste Text":
        jd_text = st.text_area("Job Description", height=280, placeholder="Paste the full job description here…", label_visibility="collapsed")

if st.button("⚡  Analyze & Optimize", use_container_width=True):
    if not api_key:
        st.error("Enter your API Key or Model Name in the sidebar.")
    elif generation_mode == "Both (Resume + Cover Letter)" and (not cv_file or not cl_file):
        st.error("Upload both a Resume and Cover Letter PDF.")
    elif generation_mode == "Resume Only" and not cv_file:
        st.error("Upload your Master Resume PDF.")
    elif generation_mode == "Cover Letter Only" and (not cv_file or not cl_file):
        st.error("Upload both a Cover Letter PDF and a Resume PDF (for context).")
    elif (cv_file and cv_file.size > 10 * 1024 * 1024) or (cl_file and cl_file.size > 10 * 1024 * 1024):
        st.error("File size exceeds 10 MB limit.")
    elif jd_text and len(jd_text) > 20000:
        st.error("Job Description exceeds maximum length (20 000 chars).")
    else:
        st.session_state['results'] = None
        st.session_state['rendered_pdfs'] = None

        # OPT 5: Cache extracted text keyed by file hash to avoid re-extraction
        def get_cached_text(uploaded_file):
            if uploaded_file is None:
                return ""
            key = f"pdf_text_{file_hash(uploaded_file)}"
            if key not in st.session_state:
                st.session_state[key] = extract_text_from_upload(uploaded_file)
            return st.session_state[key]

        with st.spinner("Reading documents…"):
            cv_text = get_cached_text(cv_file)
            cl_text = get_cached_text(cl_file)

        progress_bar = st.progress(0, text="Starting AI agent…")
        safe_jd = jd_text[:15000]
        results_dict = {"cv_score": 0, "cv_tips": [], "cv_latex": "", "cl_latex": ""}

        if generation_mode in ["Both (Resume + Cover Letter)", "Resume Only"]:
            progress_bar.progress(10, text="Analyzing JD and optimizing resume…")
            ok, cv_result = optimize_resume(api_provider, api_key, cv_text, safe_jd, language, cv_latex)
            progress_bar.progress(55)
            if not ok:
                st.error(f"Resume Error: {cv_result.get('error')}")
                st.stop()
            results_dict.update({
                "cv_score":     cv_result.get("atsScore", 0),
                "cv_tips":      cv_result.get("atsTips", []),
                "cv_latex":     cv_result.get("latexCode", ""),
                "cv_breakdown": cv_result.get("atsBreakdown", {}),
            })

        if generation_mode in ["Both (Resume + Cover Letter)", "Cover Letter Only"]:
            progress_bar.progress(60, text="Drafting cover letter…")
            # OPT 3: Send a condensed resume summary as context, not the full text
            cv_summary = summarize_resume_for_context(cv_text) if cv_text else ""
            ok, cl_result = optimize_cover_letter(api_provider, api_key, cl_text, safe_jd, language, cv_summary, cl_latex)
            progress_bar.progress(100)
            if not ok:
                st.error(f"Cover Letter Error: {cl_result.get('error')}")
                st.stop()
            results_dict["cl_latex"] = cl_result.get("latexCode", "")

        st.session_state['results'] = results_dict
        st.rerun()

# ──────────────────────────────────────────────
# STEP 2: REVIEW
# ──────────────────────────────────────────────
if has_results:
    results = st.session_state['results']
    st.divider()

    # ATS Score + tips
    score = results.get('cv_score', 0)
    breakdown = results.get('cv_breakdown', {})
    score_class = "high" if score >= 75 else ("mid" if score >= 50 else "low")
    tips_html = "".join(f'<div class="tip-item"><div class="tip-dot"></div><span>{t}</span></div>' for t in results.get('cv_tips', []))

    if score > 0:
        # Recalculate weighted score from breakdown if available
        if breakdown:
            calculated = (
                breakdown.get('keywordMatch', score) * 0.45 +
                breakdown.get('experienceRelevance', score) * 0.25 +
                breakdown.get('skillsMatch', score) * 0.15 +
                breakdown.get('education', score) * 0.10 +
                breakdown.get('formatting', score) * 0.05
            )
            score = round(calculated)
            score_class = "high" if score >= 75 else ("mid" if score >= 50 else "low")

        bd_rows = ""
        if breakdown:
            components = [
                ("Keywords",    breakdown.get('keywordMatch', 0),       0.45, "#818cf8"),
                ("Experience",  breakdown.get('experienceRelevance', 0), 0.25, "#c084fc"),
                ("Skills",      breakdown.get('skillsMatch', 0),         0.15, "#38bdf8"),
                ("Education",   breakdown.get('education', 0),           0.10, "#34d399"),
                ("Formatting",  breakdown.get('formatting', 0),          0.05, "#f59e0b"),
            ]
            for label, val, weight, color in components:
                bar_pct = max(0, min(val, 100))
                bd_rows += f"""
                <div style="margin-bottom:0.6rem;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
                    <span style="font-size:0.72rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;">{label}</span>
                    <span style="font-size:0.72rem;color:#475569;">×{weight:.2f} &nbsp;<b style="color:{color};">{val}</b></span>
                  </div>
                  <div style="background:#12122a;border-radius:4px;height:5px;overflow:hidden;">
                    <div style="width:{bar_pct}%;height:100%;background:{color};border-radius:4px;transition:width 0.6s ease;"></div>
                  </div>
                </div>"""

        c1, c2, c3 = st.columns([1, 2, 3], gap="large")
        with c1:
            st.markdown(f"""
            <div style="text-align:center;padding:1rem 0;">
              <div class="score-badge {score_class}">{score}</div>
              <div style="font-size:0.68rem;color:#334155;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;margin-top:0.4rem;">ATS Score</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            if bd_rows:
                st.markdown(f'<div class="section-label">Score Breakdown</div>{bd_rows}', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="section-label">Improvement Tips</div><div>{tips_html}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label" style="margin-top:1.5rem;">Edit LaTeX Source</div>', unsafe_allow_html=True)
    st.caption("Review and tweak the AI output before compiling. Fix any hallucinations or adjust the tone here.")

    colA, colB = st.columns(2, gap="large")
    edited_cv_latex = ""
    edited_cl_latex = ""
    with colA:
        if results.get('cv_latex'):
            edited_cv_latex = st.text_area("Resume LaTeX", results['cv_latex'], height=420, label_visibility="collapsed")
    with colB:
        if results.get('cl_latex'):
            edited_cl_latex = st.text_area("Cover Letter LaTeX", results['cl_latex'], height=420, label_visibility="collapsed")

    if st.button("🖨  Compile PDFs", use_container_width=True):
        rpdfs = {}
        if edited_cv_latex:
            with st.spinner("Compiling resume…"):
                ok, res = compile_latex_to_pdf(edited_cv_latex)
                rpdfs.update({"success_cv": ok, "pdf_cv": res, "tex_cv": edited_cv_latex})
        if edited_cl_latex:
            with st.spinner("Compiling cover letter…"):
                ok, res = compile_latex_to_pdf(edited_cl_latex)
                rpdfs.update({"success_cl": ok, "pdf_cl": res, "tex_cl": edited_cl_latex})
        st.session_state['rendered_pdfs'] = rpdfs
        st.rerun()

# ──────────────────────────────────────────────
# STEP 3: DOWNLOAD + PREVIEW
# ──────────────────────────────────────────────
if has_pdfs:
    rpdfs = st.session_state['rendered_pdfs']
    st.divider()
    st.markdown('<div class="section-label">Downloads &amp; Preview</div>', unsafe_allow_html=True)

    col_dl_1, col_dl_2 = st.columns(2, gap="large")
    with col_dl_1:
        if 'tex_cv' in rpdfs:
            st.markdown('<div class="section-label">Resume</div>', unsafe_allow_html=True)
            if rpdfs.get('success_cv'):
                st.download_button("↓ PDF", data=rpdfs['pdf_cv'], file_name="Resume_Optimized.pdf", mime="application/pdf", use_container_width=True)
                st.download_button("↓ .tex source", data=rpdfs['tex_cv'], file_name="Resume.tex", use_container_width=True)
                display_pdf(rpdfs['pdf_cv'])
            else:
                st.error(rpdfs['pdf_cv'])

    with col_dl_2:
        if 'tex_cl' in rpdfs:
            st.markdown('<div class="section-label">Cover Letter</div>', unsafe_allow_html=True)
            if rpdfs.get('success_cl'):
                st.download_button("↓ PDF", data=rpdfs['pdf_cl'], file_name="CoverLetter_Optimized.pdf", mime="application/pdf", use_container_width=True)
                st.download_button("↓ .tex source", data=rpdfs['tex_cl'], file_name="CoverLetter.tex", use_container_width=True)
                display_pdf(rpdfs['pdf_cl'])
            else:
                st.error(rpdfs['pdf_cl'])
