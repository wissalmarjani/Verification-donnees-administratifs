from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.auth_repository import AuthRepository


class AuthService:
    def __init__(self, repo: AuthRepository):
        self.repo = repo

    def ensure_seed_admin(self):
        if not self.repo.get_by_username("admin"):
            self.repo.create_user("admin", hash_password("admin123"), "admin")

    def login(self, username: str, password: str):
        user = self.repo.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            return None
        token = create_access_token(user.username, user.role)
        return {"access_token": token, "role": user.role}
