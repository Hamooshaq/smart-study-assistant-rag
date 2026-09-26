from pathlib import Path
import json
import shutil
from uuid import uuid4

from fastapi import UploadFile

from . import database as db
from .chunking import chunk_sections
from .config import settings
from .extraction import extract_document_text
from .file_validation import validate_upload_filename
from .vector_store import build_document_index, delete_document_index
from .vision import extract_visual_sections


def save_upload_file(user_id: int, upload: UploadFile) -> tuple[Path, str]:
    extension = validate_upload_filename(upload.filename or "")
    user_dir = settings.upload_dir / f"user_{user_id}"
    user_dir.mkdir(parents=True, exist_ok=True)
    target = user_dir / f"{uuid4().hex}{extension}"
    total = 0
    with target.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            total += len(chunk)
            if total > settings.max_upload_bytes:
                target.unlink(missing_ok=True)
                raise ValueError(f"Ukuran file maksimal {settings.max_upload_mb} MB.")
            out.write(chunk)
    return target, extension


def create_document_record(
    user_id: int,
    path: Path,
    original_filename: str,
    extension: str,
    vision_enabled: bool = False,
) -> int:
    return db.execute(
        """
        INSERT INTO documents (user_id, filename, original_filename, file_type, status, vision_enabled, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, str(path), original_filename, extension.lstrip("."), "uploaded", int(vision_enabled), db.utc_now()),
    )


def mark_document_status(document_id: int, status: str, error: str | None = None) -> None:
    processed_at = db.utc_now() if status in {"ready", "failed"} else None
    db.execute(
        "UPDATE documents SET status = ?, error = ?, processed_at = COALESCE(?, processed_at) WHERE id = ?",
        (status, error, processed_at, document_id),
    )


def process_document(user_id: int, document_id: int, path: Path, extension: str, use_vision: bool = False) -> None:
    mark_document_status(document_id, "processing")
    try:
        text_error: Exception | None = None
        try:
            sections = extract_document_text(path, extension)
        except Exception as exc:
            sections = []
            text_error = exc
        if use_vision:
            sections.extend(extract_visual_sections(path, extension, user_id, document_id, enabled=True))
        if not sections and text_error:
            raise text_error
        chunks = chunk_sections(sections)
        if not chunks:
            raise ValueError("Tidak ada teks yang bisa diproses dari dokumen.")
        with db.get_connection() as conn:
            conn.execute("DELETE FROM chunks WHERE user_id = ? AND document_id = ?", (user_id, document_id))
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT INTO chunks (
                        user_id, document_id, chunk_index, content, source_type, source_label,
                        page_number, slide_number, token_count, is_visual
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        document_id,
                        chunk.chunk_index,
                        chunk.content,
                        chunk.source_type,
                        chunk.source_label,
                        chunk.page_number,
                        chunk.slide_number,
                        chunk.token_count,
                        int(chunk.is_visual),
                    ),
                )
        rows = db.fetch_all(
            "SELECT id, content FROM chunks WHERE user_id = ? AND document_id = ? ORDER BY chunk_index",
            (user_id, document_id),
        )
        build_document_index(user_id, document_id, [dict(r) for r in rows])
        mark_document_status(document_id, "ready")
        db.log_activity(user_id, "process_document", f"Dokumen diproses: {path.name}", document_id)
    except Exception as exc:
        mark_document_status(document_id, "failed", str(exc))
        raise


def list_documents(user_id: int) -> list[dict]:
    rows = db.fetch_all(
        """
        SELECT d.*, COUNT(c.id) AS chunk_count,
               COALESCE(SUM(CASE WHEN c.is_visual = 1 THEN 1 ELSE 0 END), 0) AS visual_chunk_count
        FROM documents d
        LEFT JOIN chunks c ON c.document_id = d.id
        WHERE d.user_id = ?
        GROUP BY d.id
        ORDER BY d.uploaded_at DESC
        """,
        (user_id,),
    )
    return [dict(r) for r in rows]


def delete_document(user_id: int, document_id: int) -> None:
    row = db.fetch_one("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    if not row:
        raise ValueError("Dokumen tidak ditemukan.")
    Path(row["filename"]).unlink(missing_ok=True)
    with db.get_connection() as conn:
        conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    delete_document_index(user_id, document_id)
    vision_dir = settings.vision_dir / f"user_{user_id}" / f"document_{document_id}"
    if vision_dir.exists():
        shutil.rmtree(vision_dir)
    db.log_activity(user_id, "delete_document", f"Dokumen dihapus: {row['original_filename']}", document_id)


def document_history(user_id: int, document_id: int) -> dict:
    rows = db.fetch_all(
        """
        SELECT question, answer, sources_json, created_at
        FROM chat_messages
        WHERE user_id = ? AND document_id = ?
        ORDER BY created_at DESC LIMIT 20
        """,
        (user_id, document_id),
    )
    return {"chat": [{**dict(r), "sources": json.loads(r["sources_json"])} for r in rows]}
