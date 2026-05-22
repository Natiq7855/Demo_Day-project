from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = "sqlite:///./curricula_dev.db"
    gemini_api_key: str = ""
    jwt_secret_key: str = "dev_change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    media_root: str = "storage"
    teacher_email: str = "teacher@curricula.ai"
    teacher_password: str = "Teacher@12345"
    frontend_origin: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
