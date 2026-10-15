"""ATS Resume Checker - Streamlit + Gemini Flash."""

import io
import json
import os
import re

import streamlit as st
from docx import Document
from google import genai
from google.genai import types
from pypdf import PdfReader

# ---------- Config ----------
DEFAULT_MODEL = "gemini-3.8-flash"
MAX_CHARS = 20000  # cap resume text sent to the model

st.set_page_config(page_title="ATS Resume Checker", page_icon="📄", layout="wide")


# ---------- Helpers ----------
def get_api_key(sidebar_key: str = "") -> str:
    """Priority: sidebar input > Streamlit secrets > environment variable."""
    if sidebar_key.strip():
        return sidebar_key.strip()
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def extract_text(uploaded_file) -> str:
    """Extract text from PDF, DOCX or TXT uploads."""
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts)
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    raise ValueError("Unsupported file type. Please upload a PDF, DOCX or TXT file.")


def build_prompt(resume_text: str, job_description: str) -> str:
    jd_block = (
        f"JOB DESCRIPTION:\n{job_description.strip()[:8000]}\n"
        if job_description.strip()
        else "JOB DESCRIPTION: none provided. Evaluate for general ATS-friendliness.\n"
    )
    return f"""You are an expert ATS (Applicant Tracking System) analyst and professional resume reviewer.
Analyze the resume below and return ONLY a JSON object (no markdown, no commentary) with exactly this schema:

{{
  "ats_score": <integer 0-100>,
  "summary": "<2-3 sentence overall assessment>",
  "section_scores": {{
    "formatting": <0-100>,
    "keywords": <0-100>,
    "experience_impact": <0-100>,
    "skills": <0-100>,
    "education": <0-100>,
    "readability": <0-100>
  }},
  "strengths": ["<string>", ...],
  "weaknesses": ["<string>", ...],
  "missing_keywords": ["<string>", ...],
  "improvements": [
    {{"priority": "High|Medium|Low", "section": "<resume section>", "issue": "<problem>", "suggestion": "<specific fix>"}}
  ],
  "rewrite_examples": [
    {{"original": "<weak bullet from the resume>", "improved": "<stronger version>"}}
  ]
}}

Scoring guidance: penalize missing contact info, missing standard sections, no quantified achievements,
weak action verbs, keyword stuffing, very long or very short resumes, and (if a job description is given)
poor keyword alignment. Be honest and realistic; most resumes score between 45 and 85.
Only reference content that actually appears in the resume. Do not invent facts.
Give 3-8 improvements and 2-4 rewrite examples. If a job description is given,
missing_keywords must come from it; otherwise list common keywords for the candidate's apparent field.

{jd_block}
RESUME:
\"\"\"
{resume_text[:MAX_CHARS]}
\"\"\"
"""


def parse_json_response(text: str) -> dict:
    """Parse model output into a dict, tolerating code fences or extra text."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def clamp_score(value) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def normalize(result: dict) -> dict:
    """Make sure every expected key exists with a sane type."""
    result = result if isinstance(result, dict) else {}
    sections = result.get("section_scores") or {}
    keys = ["formatting", "keywords", "experience_impact", "skills", "education", "readability"]
    return {
        "ats_score": clamp_score(result.get("ats_score")),
        "summary": str(result.get("summary", "")),
        "section_scores": {k: clamp_score(sections.get(k)) for k in keys},
        "strengths": [str(x) for x in result.get("strengths") or []],
        "weaknesses": [str(x) for x in result.get("weaknesses") or []],
        "missing_keywords": [str(x) for x in result.get("missing_keywords") or []],
        "improvements": [x for x in result.get("improvements") or [] if isinstance(x, dict)],
        "rewrite_examples": [x for x in result.get("rewrite_examples") or [] if isinstance(x, dict)],
    }


def analyze_resume(api_key: str, model: str, resume_text: str, job_description: str) -> dict:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=build_prompt(resume_text, job_description),
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    return normalize(parse_json_response(response.text))


def score_label(score: int) -> str:
    if score >= 80:
        return "🟢 Excellent"
    if score >= 65:
        return "🟡 Good - room to improve"
    if score >= 50:
        return "🟠 Needs work"
    return "🔴 Poor - major improvements needed"


def build_report(result: dict) -> str:
    lines = [f"ATS SCORE: {result['ats_score']}/100", "", result["summary"], "", "SECTION SCORES"]
    lines += [f"- {k.replace('_', ' ').title()}: {v}/100" for k, v in result["section_scores"].items()]
    lines += ["", "STRENGTHS"] + [f"- {s}" for s in result["strengths"]]
    lines += ["", "WEAKNESSES"] + [f"- {s}" for s in result["weaknesses"]]
    lines += ["", "MISSING KEYWORDS", ", ".join(result["missing_keywords"]) or "None", "", "IMPROVEMENTS"]
    for i in result["improvements"]:
        lines.append(
            f"- [{i.get('priority', '')}] {i.get('section', '')}: {i.get('issue', '')} -> {i.get('suggestion', '')}"
        )
    lines += ["", "REWRITE EXAMPLES"]
    for r in result["rewrite_examples"]:
        lines.append(f"Before: {r.get('original', '')}\nAfter:  {r.get('improved', '')}\n")
    return "\n".join(lines)


# ---------- UI ----------
st.title("📄 ATS Resume Checker")
st.caption("Upload your resume to get an ATS score and specific suggestions to improve it.")

with st.sidebar:
    st.header("Settings")
    sidebar_key = st.text_input(
        "Gemini API key",
        type="password",
        help="Leave empty if the key is set in Streamlit secrets or the GEMINI_API_KEY env variable.",
    )
    model_name = st.text_input("Model", value=os.getenv("GEMINI_MODEL", DEFAULT_MODEL))
    st.markdown("Get a free key at [Google AI Studio](https://aistudio.google.com/apikey).")
    st.info("Your resume is sent to Google's Gemini API for analysis and is not stored by this app.")

col_left, col_right = st.columns(2)
with col_left:
    uploaded = st.file_uploader("Upload resume (PDF, DOCX or TXT)", type=["pdf", "docx", "txt"])
with col_right:
    job_desc = st.text_area(
        "Job description (optional, for a targeted score)",
        height=180,
        placeholder="Paste the job description here to check keyword match...",
    )

if st.button("Analyze resume", type="primary", disabled=uploaded is None):
    api_key = get_api_key(sidebar_key)
    if not api_key:
        st.error("Please provide a Gemini API key in the sidebar or in Streamlit secrets.")
        st.stop()

    try:
        with st.spinner("Reading resume..."):
            text = extract_text(uploaded)
    except Exception as e:
        st.error(f"Could not read the file: {e}")
        st.stop()

    if len(text.strip()) < 100:
        st.error(
            "Very little text was found. If your resume is a scanned image, "
            "upload a text-based PDF or DOCX instead."
        )
        st.stop()

    try:
        with st.spinner("Analyzing with Gemini..."):
            st.session_state["result"] = analyze_resume(api_key, model_name.strip(), text, job_desc)
    except json.JSONDecodeError:
        st.error("The AI returned an unreadable response. Please try again.")
        st.stop()
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        st.stop()

result = st.session_state.get("result")
if result:
    st.divider()
    score = result["ats_score"]
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("ATS Score", f"{score}/100")
        st.progress(score / 100)
        st.subheader(score_label(score))
    with c2:
        st.write(result["summary"])

    st.subheader("Section scores")
    cols = st.columns(len(result["section_scores"]))
    for col, (name, val) in zip(cols, result["section_scores"].items()):
        col.metric(name.replace("_", " ").title(), val)

    s_col, w_col = st.columns(2)
    with s_col:
        st.subheader("✅ Strengths")
        for s in result["strengths"] or ["None identified."]:
            st.markdown(f"- {s}")
    with w_col:
        st.subheader("⚠️ Weaknesses")
        for w in result["weaknesses"] or ["None identified."]:
            st.markdown(f"- {w}")

    st.subheader("🔑 Missing keywords")
    if result["missing_keywords"]:
        st.write(" ".join(f"`{k}`" for k in result["missing_keywords"]))
    else:
        st.write("No major keyword gaps found.")

    st.subheader("🛠️ Recommended improvements")
    order = {"high": 0, "medium": 1, "low": 2}
    for imp in sorted(result["improvements"], key=lambda x: order.get(str(x.get("priority", "")).lower(), 3)):
        with st.expander(f"[{imp.get('priority', '-')}] {imp.get('section', 'General')}: {imp.get('issue', '')}"):
            st.write(imp.get("suggestion", ""))

    if result["rewrite_examples"]:
        st.subheader("✍️ Example rewrites")
        for ex in result["rewrite_examples"]:
            st.markdown(f"**Before:** {ex.get('original', '')}")
            st.markdown(f"**After:** {ex.get('improved', '')}")
            st.write("")

    st.download_button("Download report (.txt)", build_report(result), file_name="ats_report.txt")
