"""
AURA — Personal AI Assistant
Core settings and configuration
"""

from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    # App
    aura_host: str = "127.0.0.1"
    aura_port: int = 8000
    aura_secret_key: str = "dev-secret-key"
    aura_data_path: str = "./data"

    # Ollama / LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"

    # Instagram
    instagram_username: str = ""
    instagram_password: str = ""

    # Email
    email_imap_host: str = "imap.gmail.com"
    email_imap_port: int = 993
    email_address: str = ""
    email_password: str = ""

    # Google
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    google_calendar_id: str = "primary"

    # Network
    network_scan_range: str = "192.168.1.0/24"
    network_scan_interval: int = 300

    # ChromaDB
    chroma_db_path: str = "./data/chromadb"

    # File watching
    watched_folders: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Ensure data directories exist
Path(settings.aura_data_path).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_db_path).mkdir(parents=True, exist_ok=True)
Path(f"{settings.aura_data_path}/logs").mkdir(parents=True, exist_ok=True)
