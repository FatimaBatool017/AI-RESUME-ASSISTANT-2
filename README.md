# AI-RESUME-ASSISTANT-2
# 📄 ATS Resume Checker

A Streamlit app that scores a resume for ATS (Applicant Tracking System) compatibility and gives concrete improvement suggestions, powered by Google's Gemini Flash model.

## Features
- Upload a resume as **PDF, DOCX or TXT**
- Optional **job description** for a targeted keyword match
- ATS score (0-100) plus section scores (formatting, keywords, impact, skills, education, readability)
- Strengths, weaknesses, missing keywords, prioritized improvements and example bullet rewrites
- Downloadable text report

## Run locally
```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey), then either:

- paste it into the app sidebar, **or**
- set it as an environment variable (`export GEMINI_API_KEY="your_key"`), **or**
- create `.streamlit/secrets.toml` containing:
  ```toml
  GEMINI_API_KEY = "your_key"
  ```

```bash
streamlit run app.py
```

## Deploy on Streamlit Community Cloud
1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **Create app**, choose the repo, branch `main`, main file `app.py`.
4. Open **Advanced settings → Secrets** and add: `GEMINI_API_KEY = "your_key"`
5. Click **Deploy**.

## Configuration
| Setting | Where | Default |
|---|---|---|
| `GEMINI_API_KEY` | Streamlit secrets / env var / sidebar | none |
| `GEMINI_MODEL` | env var or sidebar field | `gemini-2.5-flash` |

## Notes
- Scanned (image-only) PDFs have no extractable text; use a text-based PDF or DOCX.
- The ATS score is an AI estimate, not the output of a real ATS. Use it as guidance.
- Never commit your API key. `.gitignore` already excludes `.streamlit/secrets.toml` and `.env`.
