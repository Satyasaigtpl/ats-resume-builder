# 🎯 ResumeAI Pro

> **ATS-optimized resumes and cover letters, compiled locally with perfect formatting.**

ResumeAI Pro is a local, privacy-respecting resume optimization tool built with Streamlit. It takes your existing resume and cover letter, analyzes them against a job description using your choice of AI provider, and produces a polished, ATS-optimized PDF compiled directly from LaTeX — with your exact formatting preserved.

---

## ✨ Features

- **Multi-provider AI support** — plug in any of: GitHub Models (free), Gemini (Google), Groq, or a fully local Ollama instance
- **Two-call pipeline** — separate scoring/tips call from LaTeX generation for cost efficiency and higher quality
- **Preamble-splice optimization** — AI only rewrites the document body; your custom LaTeX preamble (custom environments, fonts, colors) is kept verbatim
- **Local PDF compilation** — uses your installed MiKTeX/XeLaTeX to compile directly on your machine; no document data sent to a compile server
- **ATS score dashboard** — weighted breakdown (Keywords 45%, Experience 25%, Skills 15%, Education 10%, Formatting 5%) with visual progress bars
- **Multilingual output** — generate in English or German (with automatic translation of all content)
- **Persistent templates** — save your master `.tex` templates to disk so they auto-load on every session
- **LaTeX review step** — inspect and hand-edit the AI output before compilation to fix any hallucinations
- **Download both PDF and `.tex` source** — keep full control of your documents

---

## 🏗️ Architecture

```
Resume builder/
├── app.py                  # Streamlit UI — all pages, state management, step flow
├── ai_optimizer.py         # AI provider abstraction & two-call pipeline
├── latex_utils.py          # LaTeX cleaning, escaping, and local compilation
├── pdf_utils.py            # PDF text extraction, compression, caching helpers
├── templates/
│   ├── resume_template.tex       # Your saved master resume template (LaTeX)
│   └── cover_letter_template.tex # Your saved master cover letter template (LaTeX)
├── requirements.txt        # Python dependencies
├── run_app.bat             # One-click launcher for Windows
└── INSTRUCTIONS.txt        # Plain-English guide for AI provider setup
```

### How it works

```
Upload PDFs/TeX  →  Extract text  →  [Call 1] ATS Score + Tips
                                             ↓
                              [Call 2] LaTeX body generation
                                             ↓
                         Python splices preamble + AI body
                                             ↓
                       User reviews & edits LaTeX in browser
                                             ↓
                         Local XeLaTeX compilation → PDF
```

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/)
2. **MiKTeX** — [miktex.org](https://miktex.org/download) *(for local PDF compilation)*
   - During setup, set package installation to **"Install missing packages on the fly"**
   - After install, open MiKTeX Console and click **"Check for updates"** once
3. **An AI API key** *(or a running Ollama instance — see below)*

### Installation

```bash
# Clone or download this folder, then:
pip install -r requirements.txt
```

### Launch

Double-click **`run_app.bat`**, or run manually:

```bash
python -m streamlit run app.py
```

The app opens at [http://localhost:8501](http://localhost:8501).

---

## 🤖 AI Provider Setup

### Option A — GitHub Models *(Free, recommended)*

> **150 requests/day · 15 req/min** — enough for daily job applications at zero cost.

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Create a **Classic token** with the `models:read` scope
3. In the app sidebar, select **"GitHub Models (Free)"** and choose a model:

| Model | Best for |
|---|---|
| Llama 3.3 70B | Highest quality output |
| Phi-4 (Microsoft) | Fastest, good quality |
| Mistral Small 3.1 | Fast, instruction-following |
| DeepSeek-R1 | Deep reasoning / edge cases |
| Cohere Command R | Long job descriptions |

### Option B — Gemini (Google) *(Free tier)*

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Create an API key (free tier is generous for personal use)
3. Select **"Gemini (Google)"** in the sidebar and paste your key

### Option C — Groq *(Free & ultra-fast)*

1. Go to [console.groq.com/keys](https://console.groq.com/keys) and create a free account
2. Generate an API key
3. Select **"Groq"** in the sidebar and paste your key

### Option D — Ollama *(100% local, no data leaves your machine)*

1. Download and install [Ollama](https://ollama.com)
2. Pull a model: `ollama run llama3` *(first run downloads the model)*
3. Keep Ollama running in the background
4. Select **"Ollama (Local)"** in the sidebar and type your model name (e.g. `llama3`, `mistral`)

---

## 📋 Usage Walkthrough

### Step 1 — Upload & Analyze

1. Choose what to generate: **Both**, **Resume Only**, or **Cover Letter Only**
2. Upload your **master resume PDF** (or paste / upload a `.tex` file directly)
3. Optionally paste a **LaTeX template** to preserve your exact formatting
4. Paste the **job description** (or select "No JD — General Update" for a general refresh)
5. Click **⚡ Analyze & Optimize**

The AI will:
- Score your resume against the JD (with a breakdown by category)
- Generate 3–5 specific improvement tips
- Rewrite the resume body applying those tips with JD keywords woven in

### Step 2 — Review LaTeX

- The AI-generated LaTeX source appears in an editable text area
- Read through it — fix any hallucinated details, adjust tone, correct escaping
- Both resume and cover letter are shown side by side

### Step 3 — Compile & Download

- Click **🖨 Compile PDFs**
- XeLaTeX compiles locally; the PDF preview appears inline
- Download the **PDF** and/or the **`.tex` source** for your records

---

## 💡 Tips for Best Results

| Tip | Detail |
|---|---|
| **Use `.tex` as input** | Upload your `.tex` source directly — more accurate than OCR'd PDF text, and lets the AI reuse your exact environments |
| **Save your template** | Paste your master `.tex` and click "Save as Master Template" — it persists across sessions |
| **Review before compiling** | Always check the LaTeX for hallucinations (wrong company names, fabricated dates) |
| **Scanned PDFs won't work** | PDF must be text-selectable (not an image scan) |
| **German output** | Select "German (Deutsch)" in the sidebar — the entire resume is translated automatically |

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `pdfplumber` | PDF text extraction |
| `google-generativeai` | Gemini API client |
| `groq` | Groq API client |
| `azure-ai-inference` | GitHub Models API client |
| `requests` | Ollama HTTP calls |

Install all with:

```bash
pip install -r requirements.txt
```

---

## 🔒 Privacy

- Your documents are **never stored** — everything lives in Streamlit session state and is discarded when you close the browser tab
- PDF compilation happens **entirely on your machine** via MiKTeX — no file is uploaded to a compile server
- When using **Ollama**, the AI inference also runs locally — zero data leaves your computer
- When using cloud providers (Gemini, Groq, GitHub Models), your resume text and job description are sent to those APIs. Use their respective privacy policies for reference.

---

## 🐛 Troubleshooting

**PDF compilation fails**
- Open MiKTeX Console → check for updates → make sure "Install packages on the fly" is enabled
- Check that the MiKTeX `bin\x64` path in `latex_utils.py` matches your actual installation path
- Look at the error text shown in the app — XeLaTeX logs are included

**AI returns garbled LaTeX**
- Try a higher-quality model (e.g. Llama 3.3 70B instead of Phi-4)
- Paste a clean `.tex` template — it gives the AI a concrete structure to follow
- Edit the LaTeX manually in the review step before compiling

**Groq / GitHub Models rate limit**
- GitHub Models: 150 req/day, 15 req/min on the free tier
- Each optimization run uses 2 API calls (score + generate)
- Switch to Ollama for unlimited local runs

**`azure-ai-inference` not found**
```bash
pip install azure-ai-inference
```

---

## 📄 License

This project is for personal use. Keep your API keys private and review AI output before submitting applications.
