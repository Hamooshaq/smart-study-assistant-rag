from pathlib import Path

from .config import ALLOWED_EXTENSIONS


def get_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def validate_upload_filename(filename: str) -> str:
    extension = get_extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Format file tidak didukung. Gunakan: {allowed}.")
    return extension
