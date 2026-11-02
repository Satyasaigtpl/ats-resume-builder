import re
import os
import subprocess
import tempfile
import shutil

def clean_latex_code(text: str) -> str:
    """Strips common AI hallucination artifacts that break LaTeX compilation."""
    if not text or not text.strip():
        return text

    # Do not escape LaTeX globally: %, &, $, and _ are syntax in many valid
    # commands and environments. JSON decoding already handles escaped newlines;
    # only decode conservative line/tab markers left by an unparsed model reply.
    text = re.sub(r'\\n(?=[ \t]|\\|$)', '\n', text)
    text = re.sub(r'\\t(?=[ \t]|\\|$)', '\t', text)

    # Remove leading/trailing quotes models sometimes add.
    text = text.strip().strip('"').strip("'")

    # Remove markdown code fences.
    text = re.sub(r'^```latex\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)

    # Strip everything before/after the document when a model returned prose.
    doc_match = re.search(r'(\\documentclass)', text)
    if doc_match:
        text = text[doc_match.start():]
    end_match = re.search(r'(\\end\{document\})', text)
    if end_match:
        text = text[:end_match.end()]

    # Remove stray punctuation immediately after \documentclass{...}.
    text = re.sub(r'(\\documentclass(?:\[.*?\])?\{.*?\})[.,;]+', r'\1', text)
    return text.strip()

def _find_latex_engine() -> str | None:
    """Find a usable LaTeX engine without depending on one machine's path."""
    requested = os.environ.get("LATEX_ENGINE")
    candidates = [requested] if requested else []
    candidates.extend(["xelatex", "pdflatex"])
    candidates.extend([
        r"C:\Users\Satya Sai\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe",
        r"C:\Program Files\MiKTeX\miktex\bin\x64\xelatex.exe",
    ])
    for candidate in candidates:
        if candidate and (os.path.isabs(candidate) and os.path.isfile(candidate)
                          or shutil.which(candidate)):
            return candidate
    return None


def _asset_placeholder(match: re.Match[str], missing_assets: list[str]) -> str:
    """Replace an unavailable image with a compile-safe placeholder."""
    options = match.group("options") or ""
    filename = match.group("filename")
    missing_assets.append(filename)

    width = re.search(r"width\s*=\s*([0-9.]+(?:cm|in|pt|mm))", options)
    height = re.search(r"height\s*=\s*([0-9.]+(?:cm|in|pt|mm))", options)
    width_value = width.group(1) if width else "2cm"
    height_value = height.group(1) if height else "2cm"
    return (
        r"\fbox{\rule{0pt}{"
        + height_value
        + r"}\rule{"
        + width_value
        + r"}{0pt}}"
    )


def _stage_assets(latex_code: str, tmp_dir: str) -> tuple[str, list[str]]:
    """Copy local graphics next to the .tex file or create placeholders."""
    missing_assets: list[str] = []
    search_dirs = [
        os.getcwd(),
        os.path.dirname(__file__),
        os.path.join(os.path.dirname(__file__), "templates"),
    ]
    pattern = re.compile(
        r"\\includegraphics(?:\[(?P<options>[^\]]*)\])?"
        r"\{(?P<filename>[^}]+)\}"
    )

    def stage(match: re.Match[str]) -> str:
        filename = match.group("filename")
        source = next(
            (os.path.join(directory, filename) for directory in search_dirs
             if os.path.isfile(os.path.join(directory, filename))),
            None,
        )
        if source:
            destination = os.path.join(tmp_dir, os.path.basename(filename))
            shutil.copy2(source, destination)
            return match.group(0)
        return _asset_placeholder(match, missing_assets)

    return pattern.sub(stage, latex_code), missing_assets


def compile_latex_to_pdf(latex_code: str):
    """
    Compiles LaTeX to PDF using the first available XeLaTeX or pdfLaTeX engine.
    Returns: (success_boolean, result_bytes_or_error_str)
    """
    clean_latex = clean_latex_code(latex_code)
    engine = _find_latex_engine()
    if not engine:
        return (
            False,
            "LaTeX Error: No LaTeX engine found. Install MiKTeX/TeX Live "
            "and ensure xelatex or pdflatex is on PATH.",
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        clean_latex, missing_assets = _stage_assets(clean_latex, tmp_dir)
        tex_file_path = os.path.join(tmp_dir, "resume.tex")
        pdf_file_path = os.path.join(tmp_dir, "resume.pdf")

        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(clean_latex)

        env = os.environ.copy()
        command = [
            engine,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
        ]
        if "miktex" in engine.lower():
            command.append("--enable-installer")
        command.append("resume.tex")
        try:
            process = subprocess.run(
                command,
                cwd=tmp_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=400,
            )

            if process.returncode == 0 and os.path.isfile(pdf_file_path):
                with open(pdf_file_path, "rb") as f:
                    pdf_data = f.read()
                return True, pdf_data

            warning = ""
            if missing_assets:
                warning = (
                    "\n\nMissing image assets replaced with placeholders: "
                    + ", ".join(sorted(set(missing_assets)))
                )
            error_msg = (
                f"LaTeX Error: compilation failed (exit code {process.returncode})."
                f"{warning}\n\nLOG:\n{process.stdout[-2500:]}\n\n"
                f"STDERR:\n{process.stderr[-1000:]}"
            )
            return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "LaTeX Error: Compilation timed out. Please try again."
        except OSError as exc:
            return False, f"LaTeX Error: Unable to start '{engine}': {exc}"
