from sqlalchemy.orm import Session

from app.models import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_shipment(self, shipment_id: int):
        return self.db.query(Document).filter(Document.shipment_id == shipment_id).all()
