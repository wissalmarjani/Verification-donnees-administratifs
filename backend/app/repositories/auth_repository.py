from sqlalchemy.orm import Session

from app.models import User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str):
        return self.db.query(User).filter(User.username == username).first()

    def create_user(self, username: str, password_hash: str, role: str):
        user = User(username=username, password_hash=password_hash, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
