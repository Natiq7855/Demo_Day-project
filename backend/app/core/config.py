from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./curricula_dev.db"
    groq_api_key: str = "demo"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = 0.2
    groq_max_tokens: int = 900
    jwt_secret_key: str = "dev_change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    media_root: str = "storage"
    teacher_email: str = "teacher@curricula.ai"
    teacher_password: str = "Teacher@12345"

    class Config:
        env_file = ".env"


settings = Settings()
