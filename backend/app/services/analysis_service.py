import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import ExtractedField
from app.services.extraction_service import _tesseract_available
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.rules.engine import load_rules
from app.services.extraction_service import extract_raw_text, extract_text_for_doc_type, parse_fields
from app.services.validation_service import validate_consistency

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.analysis_repo = AnalysisRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.shipment_repo = ShipmentRepository(db)

    def run_analysis(self, shipment_id: int, rules: list[dict] | None = None):
        shipment = self.shipment_repo.get_by_id(shipment_id)
        if not shipment:
            raise ValueError("Shipment not found")
        documents = self.doc_repo.list_by_shipment(shipment_id)
        if not documents:
            raise ValueError("No documents uploaded")

        self.db.query(ExtractedField).filter(ExtractedField.document_id.in_([d.id for d in documents])).delete(
            synchronize_session=False
        )
        self.db.commit()

        file_text_cache: dict[str, str] = {}
        for doc in documents:
            try:
                if doc.file_path not in file_text_cache:
                    file_text_cache[doc.file_path] = extract_raw_text(doc.file_path)
                raw_text = file_text_cache[doc.file_path]
            except Exception as exc:
                logger.exception("raw text extraction failed for document_id=%s", doc.id)
                raw_text = ""
                self.db.add(
                    ExtractedField(
                        document_id=doc.id,
                        field_name="_extraction_error",
                        field_value=str(exc),
                        source="system",
                        confidence=0.0,
                    )
                )
            scoped_text = extract_text_for_doc_type(raw_text, doc.doc_type)
            doc.raw_text = scoped_text
            fields = parse_fields(scoped_text, doc.doc_type)
            doc.consignee = fields.get("consignee") or ""
            doc.packages = fields.get("packages")
            doc.gross_weight = fields.get("gross_weight")
            doc.commercial_weight = fields.get("commercial_weight")
            doc.transport_unit_number = fields.get("transport_unit_number") or ""
            doc.incoterm = fields.get("incoterm") or ""
            doc.destination = fields.get("destination") or ""
            doc.transport_type = fields.get("transport_type") or ""
            for field_name, field_value in fields.items():
                self.db.add(
                    ExtractedField(
                        document_id=doc.id,
                        field_name=field_name,
                        field_value="" if field_value is None else str(field_value),
                        source="regex",
                        confidence=0.85 if field_value else 0.2,
                    )
                )
        self.db.commit()

        non_empty_text_docs = sum(1 for d in documents if (d.raw_text or "").strip())
        if non_empty_text_docs == 0:
            has_pdf = any(Path(d.file_path).suffix.lower() == ".pdf" for d in documents)
            if has_pdf and not _tesseract_available():
                logger.warning(
                    "No text extracted from PDFs for shipment_id=%s; OCR unavailable. "
                    "Continuing with empty extraction to return a structured inconsistency report.",
                    shipment_id,
                )
            else:
                logger.warning(
                    "No text extracted for shipment_id=%s; continuing to produce an inconsistency report.",
                    shipment_id,
                )

        analysis = validate_consistency(documents, rules or load_rules())
        shipment.status = analysis["status"]
        self.db.commit()
        run = self.analysis_repo.create_run(shipment_id, analysis)
        logger.info(json.dumps({"event": "analysis_completed", "shipment_id": shipment_id, "status": analysis["status"]}))
        return run, analysis, documents
