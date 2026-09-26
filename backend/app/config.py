import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Smart Study Assistant"
    database_path: Path = Path(os.getenv("APP_DB_PATH", ROOT_DIR / "storage" / "app.db"))
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", ROOT_DIR / "storage" / "uploads"))
    index_dir: Path = Path(os.getenv("INDEX_DIR", ROOT_DIR / "storage" / "indexes"))
    vision_dir: Path = Path(os.getenv("VISION_DIR", ROOT_DIR / "storage" / "vision"))
    frontend_dir: Path = ROOT_DIR / "frontend"
    assets_dir: Path = ROOT_DIR / "assets"
    session_cookie: str = "study_session"
    session_days: int = int(os.getenv("SESSION_DAYS", "7"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    vlm_enabled: bool = os.getenv("VLM_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    vlm_model: str = os.getenv("VLM_MODEL", "llava:7b")
    vlm_max_images_per_document: int = int(os.getenv("VLM_MAX_IMAGES_PER_DOCUMENT", "12"))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "75"))
    summary_max_chars: int = int(os.getenv("SUMMARY_MAX_CHARS", "12000"))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
ALLOWED_EXTENSIONS = {".pdf", ".ppt", ".pptx"}


def ensure_storage_dirs() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    settings.vision_dir.mkdir(parents=True, exist_ok=True)
