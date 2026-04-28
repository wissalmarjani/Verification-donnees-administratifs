import logging

from apps.analyzer.models import DocumentSet
from services.document_pipeline import prepare_analysis_payload
from services.exceptions import ExtractionError, ValidationError
from services.extraction_service import extract_structured_data
from services.ocr_service import extract_text_from_image
from services.pdf_service import extract_text_from_pdf
from services.validation_service import compare_data

logger = logging.getLogger("analyzer.pipeline")


def run_document_pipeline(document_set: DocumentSet) -> dict:
    """
    Orchestrates the full extraction + validation workflow.
    Keeps business logic out of HTTP views.
    """

    try:
        pdf_text = extract_text_from_pdf(document_set.pdf_file.path)
    except Exception as exc:
        logger.exception("PDF extraction failed for document_set=%s", document_set.id)
        raise ExtractionError("Failed to extract text from PDF.") from exc
    if not pdf_text.strip():
        logger.warning(
            "No text extracted from PDF document_set=%s. "
            "If file is scanned, ensure Tesseract is installed/configured.",
            document_set.id,
        )

    image_text_chunks = []
    for image in document_set.image_files.all():
        try:
            text = extract_text_from_image(image.image_file.path)
            if text:
                image_text_chunks.append(text)
        except Exception:
            logger.exception("OCR failed for image=%s", image.id)
    image_text = "\n\n".join(image_text_chunks).strip()

    pdf_data = extract_structured_data(pdf_text)
    image_data = extract_structured_data(image_text)

    try:
        validation = compare_data(pdf_data, image_data)
    except Exception as exc:
        logger.exception("Validation compare failed for document_set=%s", document_set.id)
        raise ValidationError("Failed to validate extracted data.") from exc

    document_set.pdf_extracted_text = pdf_text
    document_set.image_extracted_text = image_text
    document_set.pdf_structured_data = pdf_data
    document_set.image_structured_data = image_data
    document_set.validation_result = validation
    document_set.status = validation.get("status", "ERROR")
    document_set.save(
        update_fields=[
            "pdf_extracted_text",
            "image_extracted_text",
            "pdf_structured_data",
            "image_structured_data",
            "validation_result",
            "status",
            "updated_at",
        ]
    )

    prepare_analysis_payload(document_set)
    logger.info("Pipeline completed for document_set=%s status=%s", document_set.id, document_set.status)
    return validation
