import os
import uuid
from pathlib import Path

from fastapi import UploadFile
import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document


ALLOWED_DOC_TYPES = {"CC", "INVOICE", "BC", "PHYTO", "AUTO"}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def ensure_upload_dir() -> Path:
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def save_document_file(shipment_id: int, upload_file: UploadFile) -> str:
    root = ensure_upload_dir()
    shipment_dir = root / str(shipment_id)
    shipment_dir.mkdir(parents=True, exist_ok=True)

    extension = os.path.splitext(upload_file.filename or "")[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        ext_display = extension or "missing extension"
        raise ValueError(f"Unsupported file type: {ext_display}. Allowed: {allowed}")
    target_name = f"{uuid.uuid4().hex}{extension}"
    target_path = shipment_dir / target_name

    with target_path.open("wb") as f:
        f.write(upload_file.file.read())

    if extension == ".pdf":
        try:
            with pdfplumber.open(str(target_path)) as pdf:
                _ = len(pdf.pages)
        except (PdfminerException, ValueError, OSError):
            if target_path.exists():
                target_path.unlink()
            raise ValueError("Invalid or corrupted PDF file")
    return str(target_path)


def create_document(db: Session, shipment_id: int, doc_type: str, upload_file: UploadFile) -> Document:
    if doc_type not in ALLOWED_DOC_TYPES:
        raise ValueError(f"Invalid doc type: {doc_type}. Allowed: {sorted(ALLOWED_DOC_TYPES)}")

    file_path = save_document_file(shipment_id, upload_file)
    document = Document(
        shipment_id=shipment_id,
        doc_type=doc_type,
        filename=upload_file.filename or "unknown",
        file_path=file_path,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def create_documents_for_upload(db: Session, shipment_id: int, doc_type: str, upload_file: UploadFile) -> list[Document]:
    # AUTO mode: one dossier PDF can contain CC/INVOICE/BC/PHYTO.
    if doc_type == "AUTO":
        file_path = save_document_file(shipment_id, upload_file)
        created: list[Document] = []
        for target_type in ("CC", "INVOICE", "BC", "PHYTO"):
            document = Document(
                shipment_id=shipment_id,
                doc_type=target_type,
                filename=f"{target_type}_{upload_file.filename or 'unknown'}",
                file_path=file_path,
            )
            db.add(document)
            created.append(document)
        db.commit()
        for document in created:
            db.refresh(document)
        return created

    return [create_document(db, shipment_id, doc_type, upload_file)]
