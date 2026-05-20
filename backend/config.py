import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    MODEL_NAME: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    CHROMA_DB_DIR: str = str(PROJECT_ROOT / "chroma_db")
    DATABASE_URL: str = f"sqlite:///{(PROJECT_ROOT / 'mace_chatbot.db').as_posix()}"
    DATA_DIR: str = str(PROJECT_ROOT / "data")
    PORT: int = 8000
    # Semicolon-separated for Windows paths with commas unlikely; comma-separated origins
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    # If True (recommended for local dev): allow any Origin; disables cookie credentials on CORS
    CORS_ALLOW_ALL: bool = True

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()


def _resolve_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return str(path)


def _resolve_database_url(url: str) -> str:
    if url.startswith("sqlite:///./"):
        db_file = (PROJECT_ROOT / url.removeprefix("sqlite:///./")).resolve()
        return f"sqlite:///{db_file.as_posix()}"
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        raw = url.removeprefix("sqlite:///")
        if not Path(raw).is_absolute():
            db_file = (PROJECT_ROOT / raw).resolve()
            return f"sqlite:///{db_file.as_posix()}"
    return url


# Resolve relative .env paths against project root (not shell cwd)
settings.CHROMA_DB_DIR = _resolve_path(settings.CHROMA_DB_DIR)
settings.DATA_DIR = _resolve_path(settings.DATA_DIR)
settings.DATABASE_URL = _resolve_database_url(settings.DATABASE_URL)

os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
os.makedirs(settings.DATA_DIR, exist_ok=True)
