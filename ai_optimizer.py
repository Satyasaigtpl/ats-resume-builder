import google.generativeai as genai
from groq import Groq
import json
import re
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

# Free Low-Tier models on GitHub Models (150 req/day, 15 req/min)
GITHUB_FREE_MODELS = {
    "Llama 3.3 70B (Best Quality)": "Meta-Llama-3.3-70B-Instruct",
    "Phi-4 (Microsoft, Fast)": "Phi-4",
    "Mistral Small 3.1 (Fast)": "Mistral-small-3.1-24b-instruct",
    "DeepSeek-R1 (Reasoning)": "DeepSeek-R1",
    "Cohere Command R (Long Context)": "Cohere-command-r",
}

# ──────────────────────────────────────────────────────────────
# ── Template utilities ──
def strip_latex_comments(latex: str) -> str:
    """Removes full-line % comments and caps template at 4000 chars."""
    if not latex:
        return ""
    lines = latex.splitlines()
    cleaned = [l for l in lines if not l.strip().startswith("%")]
    result = "\n".join(cleaned)
    if len(result) > 4000:
        result = result[:4000] + "\n% [...template truncated...]"
    return result


def split_latex_template(tex: str):
    """
    Splits a LaTeX document into (preamble, body).
    preamble = everything up to and including \begin{document}
    body     = everything between \begin{document} and \end{document}
    Returns (preamble, body) or (None, tex) if no \begin{document} found.
    """
    import re
    m = re.search(r'(\\begin\{document\})', tex)
    if not m:
        return None, tex
    preamble = tex[:m.end()]
    rest = tex[m.end():]
    end_m = re.search(r'\\end\{document\}', rest)
    body = rest[:end_m.start()].strip() if end_m else rest.strip()
    return preamble, body


def splice_latex(preamble: str, body: str) -> str:
    """Reunites preamble + AI-generated body into a full compilable document."""
    body = body.strip()
    if not body.endswith(r'\end{document}'):
        body += "\n\\end{document}"
    return preamble + "\n" + body


def get_system_prompt(language="English"):
    lang_upper = language.upper()
    lang_instruction = (
        f"EVERY SINGLE WORD OF TEXT IN YOUR JSON VALUES AND LATEX CODE MUST BE WRITTEN IN {lang_upper}. "
        f"TRANSLATE EVERYTHING CITED FROM THE CONTEXT BEFORE OUTPUTTING."
        if language != "English" else "Output in English."
    )
    return f"""You are an Expert ATS Optimization Agent. Transform resumes and cover letters into high-scoring, job-specific LaTeX documents.

RULES:
1. OUTPUT ONLY VALID JSON matching the exact schema. No extra text.
2. LANGUAGE: {lang_instruction}
3. NO EM DASHES — use hyphens or colons.
4. Use standard ATS headings (Experience, Education, Skills) translated to {language}.
5. `latexCode` must be a fully compilable LaTeX document with \\documentclass and full preamble.
6. CUSTOM ENVIRONMENTS: If a Master Template is provided, you MUST use its custom environments (e.g. \\begin{{highlights}}, \\begin{{onecolentry}}, \\begin{{twocolentry}}, \\hrefWithoutArrow) EXACTLY as they appear in the template preamble. NEVER replace them with generic LaTeX (\\begin{{itemize}}, \\href, etc.).
7. PRESERVE THE ENTIRE PREAMBLE verbatim — every \\usepackage, \\definecolor, \\newenvironment, \\newcommand from the template must appear unchanged in your output.
8. Math symbols (e.g. \\cdot) MUST be in math mode ($\\cdot$). Escape &, %, $, #, _.
"""


# ──────────────────────────────────────────────────────────────
# Provider-aware token limits
# Groq free tier: 8000 TPM total (input + output combined)
# GitHub Models free: 8000 input / 4000 output per request
# Gemini: generous, no tight limits
# ──────────────────────────────────────────────────────────────
PROVIDER_LIMITS = {
    "Groq":           {"max_tokens": 2500, "max_resume_chars": 3000, "max_jd_chars": 4000},
    "GitHub Models":  {"max_tokens": 3500, "max_resume_chars": 5000, "max_jd_chars": 6000},
    "Gemini (Google)":{"max_tokens": 7000, "max_resume_chars": 8000, "max_jd_chars": 12000},
    "Ollama (Local)": {"max_tokens": 7000, "max_resume_chars": 8000, "max_jd_chars": 12000},
}

def _get_limits(api_provider: str) -> dict:
    for key in PROVIDER_LIMITS:
        if api_provider.startswith(key):
            return PROVIDER_LIMITS[key]
    return PROVIDER_LIMITS["Gemini (Google)"]

def _cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    nl = cut.rfind("\n")
    return (cut[:nl] if nl > max_chars * 0.7 else cut) + "\n[...truncated...]"


def _extract_latex(text: str) -> dict:
    """
    Extracts LaTeX code from model response.
    Tries (in order): JSON parse → delimiter markers → code fences → raw fallback.
    """
    stripped = text.strip()

    # 1. Model returned JSON {"latexCode": "..."} despite being asked for markers
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict) and "latexCode" in parsed:
            return {"latexCode": parsed["latexCode"]}
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Explicit delimiter markers
    if "<<<LATEX_START>>>" in stripped:
        inner = stripped.split("<<<LATEX_START>>>", 1)[1]
        if "<<<LATEX_END>>>" in inner:
            inner = inner.split("<<<LATEX_END>>>", 1)[0]
        return {"latexCode": inner.strip()}

    # 3. Markdown code fences
    for fence in ["```latex", "```"]:
        if fence in stripped:
            inner = stripped.split(fence, 1)[1]
            if "```" in inner:
                inner = inner.split("```", 1)[0]
            return {"latexCode": inner.strip()}

    # 4. Fallback: treat whole response as LaTeX
    return {"latexCode": stripped}

# Call 1: score + tips (cheap, no LaTeX generation)
# Call 2: LaTeX generation only (uses condensed context)
# ──────────────────────────────────────────────────────────────

def score_resume(api_provider, api_key, master_text, jd_text, language="English"):
    """Call 1 — ATS scoring and tips only. No LaTeX output = very cheap."""
    lim = _get_limits(api_provider)
    master_text = _cap(master_text, lim["max_resume_chars"])
    jd_text     = _cap(jd_text,     lim["max_jd_chars"])
    system_prompt = get_system_prompt(language)
    translation_note = (
        f"Tips must be in {language.upper()}."
        if language != "English" else ""
    )
    user_prompt = f"""Resume:
{master_text}

Job Description:
{jd_text}

Task: Evaluate this resume against the JD using the ATS formula below. Score each 0-100.
ATS = (keywordMatch×0.45) + (experienceRelevance×0.25) + (skillsMatch×0.15) + (education×0.10) + (formatting×0.05)
Give 3-5 specific improvement tips. {translation_note}

JSON SCHEMA:
{{
  "atsBreakdown": {{"keywordMatch": 80, "experienceRelevance": 75, "skillsMatch": 70, "education": 85, "formatting": 90}},
  "atsScore": 79,
  "atsTips": ["Tip 1", "Tip 2", "Tip 3"]
}}"""
    return _call_llm(api_provider, api_key, system_prompt, user_prompt)


def generate_resume_latex(api_provider, api_key, master_text, jd_text, language="English", master_latex="", improvement_tips=None):
    """Call 2 — LaTeX generation. Outputs document body only if template provided; preamble is spliced back in Python."""
    lim = _get_limits(api_provider)
    master_text = _cap(master_text, lim["max_resume_chars"])
    jd_text     = _cap(jd_text,     lim["max_jd_chars"])
    system_prompt = get_system_prompt(language)
    translation_instruction = (
        f"TRANSLATION REQUIRED: All content must be in {language.upper()}."
        if language != "English" else ""
    )

    tips_block = ""
    if improvement_tips:
        tips_str = "\n".join(f"  - {t}" for t in improvement_tips)
        tips_block = f"\nIMPROVEMENT REQUIREMENTS (apply ALL):\n{tips_str}\n"

    # If we have a master template, split preamble/body and only ask AI for body
    preamble, old_body = split_latex_template(master_latex) if master_latex else (None, "")

    if preamble:
        # Body-only mode: saves ~1000 output tokens, preamble is spliced back locally
        body_example = _cap(old_body, 1500)  # send only a short body excerpt as example
        user_prompt = f"""ORIGINAL RESUME CONTENT (document body only):
{master_text}

TARGET JOB DESCRIPTION:
{jd_text}
{tips_block}
EXAMPLE BODY STRUCTURE (use these exact custom environments):
{body_example}

INSTRUCTIONS:
1. Output ONLY the content that goes BETWEEN \\begin{{document}} and \\end{{document}}.
2. Do NOT include \\documentclass or any \\usepackage lines — the preamble is handled separately.
3. Use the EXACT same custom environments shown above (\\begin{{highlights}}, \\begin{{twocolentry}}, \\hrefWithoutArrow, etc.).
4. Integrate EXACT keywords from the JD into bullets. Quantify achievements.
5. Apply every improvement listed. Preserve all personal details.
6. {translation_instruction if translation_instruction else 'Output in English.'}

Wrap the body between:
<<<LATEX_START>>>
...body content here (no preamble)...
<<<LATEX_END>>>"""
        ok, result = _call_llm(api_provider, api_key, system_prompt, user_prompt, latex_mode=True)
        if ok:
            body = result.get("latexCode", "")
            result["latexCode"] = splice_latex(preamble, body)
        return ok, result

    else:
        # No template: ask for full document
        user_prompt = f"""ORIGINAL RESUME:
{master_text}

TARGET JOB DESCRIPTION:
{jd_text}
{tips_block}
INSTRUCTIONS:
1. Rewrite resume integrating JD keywords. Quantify achievements.
2. Apply every improvement listed. Preserve personal details.
3. {translation_instruction if translation_instruction else 'Output in English.'}

Output ONLY raw compilable LaTeX. Wrap between:
<<<LATEX_START>>>
...full latex...
<<<LATEX_END>>>"""
        return _call_llm(api_provider, api_key, system_prompt, user_prompt, latex_mode=True)



def optimize_resume(api_provider, api_key, master_text, jd_text, language="English", master_latex=""):
    """
    Two-call pipeline:
    Call 1: Score and get improvement tips
    Call 2: Generate LaTeX USING those tips as explicit requirements
    """
    # Call 1: scoring + tips
    ok1, result1 = score_resume(api_provider, api_key, master_text, jd_text, language)
    if not ok1:
        return False, result1

    tips = result1.get("atsTips", [])

    # Call 2: LaTeX generation — tips are passed in to direct improvements
    ok2, result2 = generate_resume_latex(
        api_provider, api_key, master_text, jd_text, language, master_latex,
        improvement_tips=tips
    )
    if not ok2:
        return False, result2

    merged = {**result1, **result2}
    return True, merged


def optimize_cover_letter(api_provider, api_key, master_cl_text, jd_text,
                          language="English", master_resume_text="", master_latex=""):
    """Uses preamble-split so only the body is generated by AI."""
    lim = _get_limits(api_provider)
    master_cl_text    = _cap(master_cl_text,    lim["max_resume_chars"])
    jd_text           = _cap(jd_text,           lim["max_jd_chars"])
    master_resume_text = _cap(master_resume_text, 1200)
    system_prompt = get_system_prompt(language)
    translation_instruction = (
        f"TRANSLATION REQUIRED: All content must be in {language.upper()}."
        if language != "English" else ""
    )

    resume_block = f"\nApplicant Resume (summary):\n{master_resume_text}\n" if master_resume_text else ""
    preamble, old_body = split_latex_template(master_latex) if master_latex else (None, "")

    if preamble:
        body_example = _cap(old_body, 1000)
        user_prompt = f"""ORIGINAL COVER LETTER CONTENT:
{master_cl_text}

JOB DESCRIPTION:
{jd_text}
{resume_block}
EXAMPLE BODY STRUCTURE:
{body_example}

INSTRUCTIONS:
1. Output ONLY the content between \\begin{{document}} and \\end{{document}}. NO preamble.
2. Tailor to the JD, aligning with the resume context above.
3. {translation_instruction if translation_instruction else 'Output in English.'}

Wrap between:
<<<LATEX_START>>>
...body only...
<<<LATEX_END>>>"""
        ok, result = _call_llm(api_provider, api_key, system_prompt, user_prompt, latex_mode=True)
        if ok:
            result["latexCode"] = splice_latex(preamble, result.get("latexCode", ""))
        return ok, result
    else:
        user_prompt = f"""MASTER COVER LETTER:
{master_cl_text}

JOB DESCRIPTION:
{jd_text}
{resume_block}
Task: Write tailored cover letter. {translation_instruction}
Output ONLY raw compilable LaTeX. Wrap between:
<<<LATEX_START>>>
...full latex...
<<<LATEX_END>>>"""
        return _call_llm(api_provider, api_key, system_prompt, user_prompt, latex_mode=True)


def _call_llm(api_provider, api_key, system_prompt, user_prompt, latex_mode=False):
    """latex_mode=True: skip json_object format, extract LaTeX via markers."""
    lim = _get_limits(api_provider)
    max_tok = lim["max_tokens"]
    try:
        if api_provider == "Gemini (Google)":
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_prompt)
            cfg = genai.GenerationConfig(max_output_tokens=max_tok)
            if latex_mode:
                response = model.generate_content(user_prompt, generation_config=cfg)
                return True, _extract_latex(response.text)
            response = model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(response_mime_type="application/json", max_output_tokens=max_tok)
            )
            return True, json.loads(response.text)

        elif api_provider == "Groq":
            client = Groq(api_key=api_key)
            kwargs = dict(
                model="openai/gpt-oss-120b",
                max_tokens=max_tok,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ]
            )
            if not latex_mode:
                kwargs["response_format"] = {"type": "json_object"}
            completion = client.chat.completions.create(**kwargs)
            raw = completion.choices[0].message.content
            if latex_mode:
                return True, _extract_latex(raw)
            return True, json.loads(raw)

        elif api_provider == "Ollama (Local)":
            import requests
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": api_key,
                    "options": {"num_predict": max_tok},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt}
                    ],
                    "stream": False,
                    "format": "json" if not latex_mode else None
                }
            )
            if response.status_code == 200:
                raw = response.json()["message"]["content"]
                if latex_mode:
                    return True, _extract_latex(raw)
                return True, json.loads(raw)
            return False, {"error": f"Ollama HTTP {response.status_code}: {response.text}"}

        elif api_provider.startswith("GitHub Models"):
            model_label = api_provider.split(" — ", 1)[1] if " — " in api_provider else "Phi-4 (Microsoft, Fast)"
            model_id = GITHUB_FREE_MODELS.get(model_label, "Phi-4")
            client = ChatCompletionsClient(
                endpoint="https://models.inference.ai.azure.com",
                credential=AzureKeyCredential(api_key)
            )
            extra = {} if latex_mode else {"response_format": {"type": "json_object"}}
            response = client.complete(
                messages=[
                    SystemMessage(content=system_prompt),
                    UserMessage(content=user_prompt)
                ],
                model=model_id,
                max_tokens=max_tok,
                **extra
            )
            raw = response.choices[0].message.content
            if latex_mode:
                return True, _extract_latex(raw)
            return True, json.loads(raw)

        return False, {"error": "Invalid API Provider."}

    except Exception as e:
        return False, {"error": str(e)}
