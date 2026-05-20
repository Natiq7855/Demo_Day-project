from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    groq_api_key: str
    groq_model: str = "llama-3.1-70b-versatile"
    groq_temperature: float = 0.2
    groq_max_tokens: int = 900
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    media_root: str = "storage"

    class Config:
        env_file = ".env"


settings = Settings()
