"""
Configuration settings for the application.
"""

import os
from pydantic import BaseSettings
import uuid


class Settings(BaseSettings):
    """
    Application settings.
    """
    # JWT settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_REFRESH_SECRET_KEY: str = os.getenv("JWT_REFRESH_SECRET_KEY", "your-refresh-secret-key")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///backend/records.db")
    
    # Default tenant settings
    DEFAULT_TENANT_ID: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    
    # Storage settings
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "storage")
    
    # Whisper settings
    WHISPER_MODEL_DIR: str = os.getenv("WHISPER_MODEL_DIR", "models/whisper")
    FASTER_WHISPER_MODEL_DIR: str = os.getenv("FASTER_WHISPER_MODEL_DIR", "models/faster-whisper")
    INSANELY_FAST_WHISPER_MODEL_DIR: str = os.getenv("INSANELY_FAST_WHISPER_MODEL_DIR", "models/insanely-fast-whisper")
    
    # VAD settings
    VAD_MODEL_DIR: str = os.getenv("VAD_MODEL_DIR", "models/vad")
    
    # BGM separation settings
    UVR_MODEL_DIR: str = os.getenv("UVR_MODEL_DIR", "models/uvr")
    
    # Output settings
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "outputs")
    
    # Cache settings
    CACHE_DIR: str = os.getenv("CACHE_DIR", "backend/cache")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "86400"))  # 24 hours
    CACHE_FREQUENCY: int = int(os.getenv("CACHE_FREQUENCY", "3600"))  # 1 hour
    
    # Server settings
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    
    # RevenueCat settings
    REVENUECAT_API_KEY: str = os.getenv("REVENUECAT_API_KEY", "")
    REVENUECAT_WEBHOOK_SECRET: str = os.getenv("REVENUECAT_WEBHOOK_SECRET", "")
    
    class Config:
        env_file = ".env"


settings = Settings()
