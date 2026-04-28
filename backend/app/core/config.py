from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Document Consistency Analyzer API"
    database_url: str = "sqlite:///./smart_docs.db"
    upload_dir: str = "./uploads"
    tesseract_cmd: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    secret_key: str = "change_this_in_production"
    access_token_expire_minutes: int = 120
    redis_url: str = "redis://redis:6379/0"
    celery_eager: int = 0
    max_upload_size_mb: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
