from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:password@localhost:5432/crm_db"
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Database settings
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    postgres_db: str = "crm_db"

    # API keys
    google_api_key: Optional[str] = None
    youtube_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # AI models
    model: str = "gpt-4o-mini"
    model_translate: str = "gpt-4o-transcribe"

    # AWS/S3 settings
    s3_bucket_name: Optional[str] = None
    aws_region: str = "us-east-1"
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None

    # App settings
    app_env: str = "development"
    debug: str = "0"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
