from pathlib import Path

from apps.analyzer.models import DocumentSet
from utils.file_metadata import build_file_metadata


def prepare_analysis_payload(document_set: DocumentSet) -> dict:
    """
    Prepares a structured payload for future OCR/analysis services.
    This keeps the view thin and business logic centralized.
    """

    pdf_meta = build_file_metadata(Path(document_set.pdf_file.path))
    images_meta = [
        build_file_metadata(Path(image.image_file.path))
        for image in document_set.image_files.all()
    ]
    return {
        "document_set_id": document_set.id,
        "status": document_set.status,
        "pdf": pdf_meta,
        "images": images_meta,
        "next_step": "ocr_extraction",
    }
