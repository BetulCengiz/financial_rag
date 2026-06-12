import pdfplumber
from pathlib import Path
from loguru import logger


def extract_text(pdf_path: str | Path) -> str:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    texts = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text:
                texts.append(text)
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    cleaned = [str(c).strip() if c else "" for c in row]
                    texts.append(" | ".join(cleaned))

    return "\n\n".join(texts)


def extract_with_metadata(pdf_path: str | Path) -> dict:
    path = Path(pdf_path)
    text = extract_text(path)
    return {
        "text": text,
        "source": str(path),
        "filename": path.name,
        "char_count": len(text),
    }