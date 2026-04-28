import re
import os
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
import pytesseract


if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")


def _ocr_page_with_tesseract(page: fitz.Page) -> str:
    """
    OCR one PDF page by rendering it as an image.
    """
    matrix = fitz.Matrix(2, 2)  # Better OCR quality than default rendering
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    img = Image.open(BytesIO(pix.tobytes("png")))
    return (pytesseract.image_to_string(img) or "").strip()


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract and clean text from a PDF file using PyMuPDF.
    """

    chunks: list[str] = []
    with fitz.open(file_path) as doc:
        for page in doc:
            page_text = (page.get_text("text") or "").strip()
            if not page_text:
                # Fallback for scanned/image-based PDFs.
                try:
                    page_text = _ocr_page_with_tesseract(page)
                except Exception:
                    # Keep pipeline alive if OCR dependency is unavailable.
                    page_text = ""
            chunks.append(page_text)

    raw_text = "\n".join(chunks)
    # Basic cleanup for easier downstream processing.
    cleaned = re.sub(r"\r\n?", "\n", raw_text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
