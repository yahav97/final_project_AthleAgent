"""
Configuration management for AthleAgent backend.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # When False, the app does not import SQLAlchemy, Postgres, or legacy JWT auth routes.
    ENABLE_LEGACY_AUTH_DB: bool = False

    # sklearn model artifact (default: backend/injury_model.pkl)
    MODEL_PATH: str = str(Path(__file__).resolve().parent / "injury_model.pkl")

    # Database (only used if ENABLE_LEGACY_AUTH_DB is True)
    DATABASE_URL: str = "postgresql://postgres:Michal09@localhost:5432/athleagent"
    
    # JWT Authentication
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "your-secret-key-change-this-in-production-min-32-chars"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")

    # Firebase Admin / Firestore
    FIREBASE_SERVICE_ACCOUNT_KEY: Optional[str] = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    
    # Gemini AI
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    
    # File Uploads
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads/images")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AthleAgent API"
    VERSION: str = "1.0.0"
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Create upload directory if it doesn't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

