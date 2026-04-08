import io
import re
import os
import subprocess
import tempfile
import shutil

def auto_escape_latex(text: str) -> str:
    """Automatically escapes common characters that LLMs forget to escape."""
    text = re.sub(r'(?<!\\\\)%', r'\\%', text)
    text = re.sub(r'(?<!\\\\)&', r'\\&', text)
    text = re.sub(r'(?<!\\\\)\\$', r'\\$', text)
    return text

def clean_latex_code(text: str) -> str:
    """Strips common AI hallucination artifacts that break LaTeX compilation."""
    if not text or not text.strip():
        return text
    # 1. Decode literal \n \t sequences models sometimes serialize as escaped text
    text = text.replace('\\n', '\n').replace('\\t', '\t')
    # 2. Remove leading/trailing quotes models sometimes add
    text = text.strip().strip('"').strip("'")
    # 3. Remove markdown code fences
    text = re.sub(r'^```latex\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
    # 4. Strip EVERYTHING before \documentclass (text before it = nullfont crash)
    doc_match = re.search(r'(\\documentclass)', text)
    if doc_match:
        text = text[doc_match.start():]
    # 5. Strip EVERYTHING after \end{document}
    end_match = re.search(r'(\\end\{document\})', text)
    if end_match:
        text = text[:end_match.end()]
    # 6. Remove stray chars immediately after \documentclass{...}
    text = re.sub(r'(\\documentclass(?:\[.*?\])?\{.*?\})[.,;]+', r'\1', text)
    return text.strip()

def compile_latex_to_pdf(latex_code: str):
    """
    Compiles LaTeX to PDF locally using a MiKTeX installation.
    Returns: (success_boolean, result_bytes_or_error_str)
    """
    clean_latex = clean_latex_code(auto_escape_latex(latex_code))
    
    # Path to your local MiKTeX installation
    miktex_bin = r"C:\Users\Satya Sai\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
    
    # Create a temporary directory for compilation
    with tempfile.TemporaryDirectory() as tmp_dir:
        tex_file_path = os.path.join(tmp_dir, "resume.tex")
        pdf_file_path = os.path.join(tmp_dir, "resume.pdf")
        
        # Write the LaTeX code to a file
        with open(tex_file_path, "w", encoding="utf-8") as f:
            f.write(clean_latex)
            
        # Add MiKTeX to the system's PATH for the subprocess
        env = os.environ.copy()
        env["PATH"] = miktex_bin + os.pathsep + env.get("PATH", "")
        
        # Run xelatex (MiKTeX auto-downloads missing packages on the fly!)
        try:
            xelatex_path = os.path.join(miktex_bin, "xelatex.exe")
            process = subprocess.run(
                [xelatex_path, "-interaction=nonstopmode", "--enable-installer", "resume.tex"],
                cwd=tmp_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=400 # Give plenty of time for first-run package downloads
            )
            
            if os.path.exists(pdf_file_path):
                with open(pdf_file_path, "rb") as f:
                    pdf_data = f.read()
                return True, pdf_data
            else:
                # Return the last 1500 characters of the log to help debug
                error_msg = f"LaTeX Error: PDF not generated.\n\nSTDOUT:\n{process.stdout[-1500:]}\n\nSTDERR:\n{process.stderr[-500:]}"
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "LaTeX Error: Compilation timed out. Please try again."
        except Exception as e:
            return False, f"Unexpected Local LaTeX Error: {str(e)}"
