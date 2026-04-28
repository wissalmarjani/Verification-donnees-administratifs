from sqlalchemy.orm import Session

from app.models import Shipment


class ShipmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, reference: str) -> Shipment:
        shipment = Shipment(reference=reference)
        self.db.add(shipment)
        self.db.commit()
        self.db.refresh(shipment)
        return shipment

    def get_by_reference(self, reference: str):
        return self.db.query(Shipment).filter(Shipment.reference == reference).first()

    def get_by_id(self, shipment_id: int):
        return self.db.query(Shipment).filter(Shipment.id == shipment_id).first()

    def list(self, page: int, page_size: int, status: str | None, q: str | None):
        query = self.db.query(Shipment)
        if status:
            query = query.filter(Shipment.status == status)
        if q:
            query = query.filter(Shipment.reference.ilike(f"%{q}%"))
        total = query.count()
        items = (
            query.order_by(Shipment.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total
