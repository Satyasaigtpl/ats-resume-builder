import pdfplumber
import re
import hashlib

def extract_text_from_bytes(file_bytes) -> str:
    """Extracts and compresses text from PDF bytes (for Streamlit file uploaders)."""
    try:
        text = []
        with pdfplumber.open(file_bytes) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text.append(extracted)
        raw = "\n".join(text)
        return compress_text(raw)
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def extract_text_from_upload(uploaded_file) -> str:
    """
    Reads text from an uploaded file.
    - .tex files: read directly as UTF-8 text (fastest, most accurate)
    - .pdf files: extract via pdfplumber + compress
    """
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    if name.endswith(".tex"):
        uploaded_file.seek(0)
        return uploaded_file.read().decode("utf-8", errors="replace")
    else:
        return extract_text_from_bytes(uploaded_file)


def extract_text_from_pdf(filepath: str) -> str:
    """Extracts and compresses text from a PDF file path."""
    try:
        text = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text.append(extracted)
        raw = "\n".join(text)
        return compress_text(raw)
    except Exception as e:
        return f"Error reading PDF: {str(e)}"


def compress_text(text: str) -> str:
    """
    Opt 1: Compress extracted text to reduce token usage.
    - Collapses multiple blank lines into one
    - Strips leading/trailing whitespace from each line
    - Removes lines that are only whitespace or repeated separators
    """
    lines = text.splitlines()
    cleaned = []
    prev_blank = False
    separator_pattern = re.compile(r'^[\s\-_=|*·•◦▪▸►▷>~]{3,}$')

    for line in lines:
        stripped = line.strip()
        # Skip pure separator/decorative lines
        if separator_pattern.match(stripped):
            continue
        if stripped == "":
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(stripped)
            prev_blank = False

    return "\n".join(cleaned).strip()

def file_hash(file_bytes) -> str:
    """Returns a short hash of file bytes for session-state caching keys."""
    file_bytes.seek(0)
    h = hashlib.md5(file_bytes.read()).hexdigest()[:12]
    file_bytes.seek(0)
    return h

def summarize_resume_for_context(full_text: str, max_chars: int = 1800) -> str:
    """
    Opt 3: Returns a condensed resume summary for use as cover letter context.
    Keeps the first `max_chars` characters — enough for name, experience titles,
    and key skills — without sending the full document.
    """
    if len(full_text) <= max_chars:
        return full_text
    # Try to cut at a newline boundary to avoid mid-sentence splits
    cut = full_text[:max_chars]
    last_newline = cut.rfind("\n")
    if last_newline > max_chars * 0.7:
        cut = cut[:last_newline]
    return cut + "\n[...resume truncated for token efficiency...]"
