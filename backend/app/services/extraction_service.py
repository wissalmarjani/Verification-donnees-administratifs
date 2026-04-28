import re
import unicodedata
import uuid
import logging
from pathlib import Path
from typing import Dict, Optional

import pdfplumber
import pytesseract
from PIL import Image, ImageOps, ImageFilter
from pdfplumber.utils.exceptions import PdfminerException
import pypdfium2 as pdfium

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

from app.core.config import settings
from app.services.extraction.llm_fallback import extract_with_llm
from app.services.extraction.template_registry import get_template

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

logger = logging.getLogger(__name__)

DOC_TYPE_SECTION_MARKERS = {
    "INVOICE": [r"\binvoice\b", r"\bfacture\b"],
    "CC": [r"\bcertificate\s+of\s+conformity\b", r"\bcertificate\b", r"\bcertificat\b", r"\bconformity\b"],
    "BC": [r"\bpurchase\s+order\b", r"\bbon\s+de\s+commande\b", r"\bcommande\b"],
    "PHYTO": [r"\bphytosanitary\b", r"\bphytosanitaire\b", r"\bphyto\b"],
}


def _tesseract_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _preprocess_for_ocr(image: Image.Image) -> Image.Image:
    # OpenCV (if available): grayscale + denoise + adaptive threshold.
    if cv2 is not None and np is not None:
        bgr = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, None, 12, 7, 21)
        bw = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 8
        )
        return Image.fromarray(bw)

    # Fallback: high-contrast black/white preprocessing via PIL only.
    gray = ImageOps.grayscale(image)
    denoised = gray.filter(ImageFilter.MedianFilter(size=3))
    bw = denoised.point(lambda x: 255 if x > 170 else 0)
    return bw


def _ocr_pdf_page_with_pdfium(file_path: str, page_index: int, temp_dir: Path) -> str:
    temp_img_path = temp_dir / f"ocr_{uuid.uuid4().hex}.png"
    pdf = pdfium.PdfDocument(file_path)
    try:
        if page_index >= len(pdf):
            return ""
        page = pdf[page_index]
        bitmap = page.render(scale=300 / 72)
        pil_image = bitmap.to_pil()
        processed = _preprocess_for_ocr(pil_image)
        processed.save(str(temp_img_path), format="PNG")
        try:
            return pytesseract.image_to_string(Image.open(str(temp_img_path)), config="--oem 3 --psm 6") or ""
        except Exception:
            return ""
    finally:
        pdf.close()
        if temp_img_path.exists():
            temp_img_path.unlink()


def _extract_text_from_pdf(file_path: str) -> str:
    chunks = []
    temp_dir = Path(settings.upload_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        with pdfplumber.open(file_path) as pdf:
            tesseract_ok = _tesseract_available()
            for page_index, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if not text.strip() and tesseract_ok:
                    # OCR fallback for scanned PDFs rendered via pypdfium2 (more stable on Windows).
                    text = _ocr_pdf_page_with_pdfium(file_path, page_index, temp_dir)
                page_block = text.strip()
                if page_block:
                    chunks.append(f"--- PAGE {page_index + 1} ---\n{page_block}")
            if not tesseract_ok:
                logger.warning("Tesseract OCR is unavailable; scanned PDF pages may produce empty text")
    except (PdfminerException, ValueError, OSError) as exc:
        logger.warning("Failed to parse PDF '%s': %s", file_path, exc)
        return ""
    return "\n".join(chunks)


def _extract_text_from_image(file_path: str) -> str:
    image = Image.open(file_path)
    try:
        processed = _preprocess_for_ocr(image)
        return pytesseract.image_to_string(processed, config="--oem 3 --psm 6")
    except Exception:
        return ""


def extract_raw_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        text = _extract_text_from_pdf(file_path)
        if text.strip():
            return text
        return ""
    if ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}:
        return _extract_text_from_image(file_path)
    return ""


def _search(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def _search_float(pattern: str, text: str) -> Optional[float]:
    value = _search(pattern, text)
    if not value:
        return None
    cleaned = value.replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _search_int(pattern: str, text: str) -> Optional[int]:
    value = _search(pattern, text)
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return int(digits) if digits else None


def _normalize_text(text: str) -> str:
    # Normalize accents to improve FR/EN matching stability.
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def parse_fields(raw_text: str, doc_type: str = "") -> Dict[str, Optional[str]]:
    # Lecture ligne par ligne: on scanne chaque ligne et on prend la première occurrence.
    fields: Dict[str, Optional[str]] = {
        "consignee": None,
        "packages": None,
        "gross_weight": None,
        "commercial_weight": None,
        "transport_unit_number": None,
        "incoterm": None,
        "destination": None,
        "transport_type": None,
        "exporter_name": None,
        "importer_name": None,
        "product_name": None,
        "botanical_variety": None,
        "net_weight": None,
    }

    normalized_text = _normalize_text(raw_text)

    for raw_line, norm_line in zip(raw_text.splitlines(), normalized_text.splitlines()):
        line = raw_line.strip()
        normalized_line = norm_line.strip()
        if not line:
            continue
        if not fields["consignee"]:
            fields["consignee"] = (
                _search(r"(?:consignee|consigne|notify|client)\s*[:\-]\s*(.+)", line)
                or _search(r"(?:consignee|consigne|notify|client)\s*[:\-]\s*(.+)", normalized_line)
            )
        if fields["packages"] is None:
            fields["packages"] = (
                _search_int(r"(?:number\s+of\s+packages|packages|nombre\s+de\s+colis|nb\s*colis)\s*[:\-]?\s*([0-9\., ]+)", line)
                or _search_int(r"(?:number\s+of\s+packages|packages|nombre\s+de\s+colis|nb\s*colis)\s*[:\-]?\s*([0-9\., ]+)", normalized_line)
            )
        if fields["gross_weight"] is None:
            fields["gross_weight"] = (
                _search_float(r"(?:gross\s+weight|poids\s+brut)\s*[:\-]?\s*([0-9\., ]+)", line)
                or _search_float(r"(?:gross\s+weight|poids\s+brut)\s*[:\-]?\s*([0-9\., ]+)", normalized_line)
            )
        if fields["commercial_weight"] is None:
            fields["commercial_weight"] = (
                _search_float(r"(?:commercial\s+weight|net\s+weight|poids\s+commercial|poids\s+net)\s*[:\-]?\s*([0-9\., ]+)", line)
                or _search_float(r"(?:commercial\s+weight|net\s+weight|poids\s+commercial|poids\s+net)\s*[:\-]?\s*([0-9\., ]+)", normalized_line)
            )
        if not fields["transport_unit_number"]:
            fields["transport_unit_number"] = _search(
                r"(?:transport\s+unit\s+number|container\s+number|truck\s+number|n[°o]\s*de\s*l[' ]?unite\s*de\s*transport|numero\s*unite\s*transport|immatriculation)\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
                line,
            ) or _search(
                r"(?:transport\s+unit\s+number|container\s+number|truck\s+number|n[°o]\s*de\s*l[' ]?unite\s*de\s*transport|numero\s*unite\s*transport|immatriculation)\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
                normalized_line,
            )
        if not fields["incoterm"]:
            fields["incoterm"] = _search(r"(?:incoterm)\s*[:\-]?\s*([A-Za-z]{3})", line) or _search(
                r"(?:incoterm)\s*[:\-]?\s*([A-Za-z]{3})", normalized_line
            )
        if not fields["destination"]:
            fields["destination"] = _search(r"(?:destination)\s*[:\-]?\s*([A-Za-z0-9 ,\-/]+)", line) or _search(
                r"(?:destination)\s*[:\-]?\s*([A-Za-z0-9 ,\-/]+)", normalized_line
            )
        if not fields["transport_type"]:
            fields["transport_type"] = _search(
                r"(?:transport\s+type|moyen\s+de\s+transport|mode\s+de\s+transport)\s*[:\-]?\s*(truck|container|camion|conteneur)",
                normalized_line,
            )
        if not fields["exporter_name"]:
            fields["exporter_name"] = _search(
                r"(?:exporter|shipper|consignor|expediteur)\s*[:\-]?\s*(.+)",
                normalized_line,
            )
        if not fields["importer_name"]:
            fields["importer_name"] = _search(
                r"(?:importer|importateur|consignee|notify)\s*[:\-]?\s*(.+)",
                normalized_line,
            )
        if not fields["product_name"]:
            fields["product_name"] = _search(
                r"(?:product|products|commodity|goods|description|produit)\s*[:\-]?\s*(.+)",
                normalized_line,
            )
        if not fields["botanical_variety"]:
            fields["botanical_variety"] = _search(
                r"\b(citrus\s+clementina|nadorcott|mandarines?|clementines?)\b",
                normalized_line,
            )
        if fields["net_weight"] is None:
            fields["net_weight"] = _search_float(
                r"(?:net\s+weight|poids\s+net)\s*[:\-]?\s*([0-9\., ]+)",
                normalized_line,
            )

    # Heuristic fallback: if strict "field: value" patterns fail, look for useful lines.
    if not fields["incoterm"]:
        fields["incoterm"] = _search(r"\b(EXW|FCA|CPT|CIP|DAP|DPU|DDP|FAS|FOB|CFR|CIF)\b", normalized_text)
    if not fields["transport_type"]:
        transport = _search(r"\b(truck|container|camion|conteneur)\b", normalized_text)
        if transport:
            fields["transport_type"] = "container" if transport.lower() in {"container", "conteneur"} else "truck"
    if not fields["botanical_variety"]:
        fields["botanical_variety"] = _search(r"\b(citrus\s+clementina|nadorcott|mandarines?|clementines?)\b", normalized_text)
    template = get_template(doc_type)
    for field_name, patterns in template.items():
        if not fields.get(field_name):
            for pattern in patterns:
                value = _search(pattern, raw_text)
                if value:
                    fields[field_name] = value
                    break

    if sum(1 for value in fields.values() if value not in (None, "")) < 2:
        # Keep fallback optional and non-blocking.
        llm_fields = extract_with_llm(raw_text)
        if isinstance(llm_fields, dict):
            for field_name in fields.keys():
                if fields.get(field_name) not in (None, ""):
                    continue
                llm_value = llm_fields.get(field_name)
                if llm_value in (None, ""):
                    continue
                if field_name in {"packages"}:
                    try:
                        fields[field_name] = int(float(str(llm_value).replace(",", ".")))
                    except ValueError:
                        continue
                elif field_name in {"gross_weight", "commercial_weight"}:
                    try:
                        fields[field_name] = float(str(llm_value).replace(",", "."))
                    except ValueError:
                        continue
                else:
                    fields[field_name] = str(llm_value).strip()
    return fields


def extract_text_for_doc_type(raw_text: str, doc_type: str) -> str:
    target = (doc_type or "").upper()
    markers = DOC_TYPE_SECTION_MARKERS.get(target, [])
    if not markers:
        return raw_text

    lines = raw_text.splitlines()
    if not lines:
        return raw_text

    heading_hits = []
    for index, line in enumerate(lines):
        normalized_line = _normalize_text(line.lower())
        for candidate_type, candidate_patterns in DOC_TYPE_SECTION_MARKERS.items():
            if any(re.search(pattern, normalized_line, re.IGNORECASE) for pattern in candidate_patterns):
                heading_hits.append((index, candidate_type))
                break

    if not heading_hits:
        return raw_text

    heading_hits.sort(key=lambda hit: hit[0])
    extracted_blocks = []
    for hit_index, hit_type in enumerate(heading_hits):
        start_index, current_type = hit_type
        if current_type != target:
            continue
        end_index = len(lines)
        if hit_index + 1 < len(heading_hits):
            end_index = heading_hits[hit_index + 1][0]
        block = "\n".join(lines[start_index:end_index]).strip()
        if block:
            extracted_blocks.append(block)

    if extracted_blocks:
        return "\n\n".join(extracted_blocks)
    return raw_text
