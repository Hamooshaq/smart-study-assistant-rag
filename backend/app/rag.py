import json
from typing import Any

from . import database as db
from .config import settings
from .ollama_client import chat_completion
from .vector_store import build_document_index, search_document_index


SYSTEM_PROMPT = (
    "Kamu adalah asisten belajar untuk mahasiswa. Jawab hanya berdasarkan konteks dokumen yang diberikan. "
    "Jika konteks tidak cukup untuk menjawab, katakan bahwa informasi tersebut tidak ditemukan pada dokumen. "
    "Jangan mengarang jawaban."
)


def get_owned_document(user_id: int, document_id: int) -> dict[str, Any]:
    row = db.fetch_one("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
    if not row:
        raise ValueError("Dokumen tidak ditemukan.")
    return dict(row)


def rebuild_index_from_db(user_id: int, document_id: int) -> None:
    rows = db.fetch_all(
        "SELECT id, content FROM chunks WHERE user_id = ? AND document_id = ? ORDER BY chunk_index",
        (user_id, document_id),
    )
    build_document_index(user_id, document_id, [dict(row) for row in rows])


def retrieve_chunks(user_id: int, document_id: int, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("Pertanyaan tidak boleh kosong.")
    get_owned_document(user_id, document_id)
    limit = top_k or settings.rag_top_k
    try:
        matches = search_document_index(user_id, document_id, query, limit)
    except RuntimeError:
        rebuild_index_from_db(user_id, document_id)
        matches = search_document_index(user_id, document_id, query, limit)
    score_by_id = {chunk_id: score for chunk_id, score in matches}
    results: list[dict[str, Any]] = []
    for chunk_id, _ in matches:
        row = db.fetch_one(
            "SELECT * FROM chunks WHERE id = ? AND user_id = ? AND document_id = ?",
            (chunk_id, user_id, document_id),
        )
        if row:
            item = dict(row)
            item["score"] = score_by_id[chunk_id]
            results.append(item)
    return results


def build_context(chunks: list[dict[str, Any]]) -> str:
    return "\n\n".join(f"[Sumber {i}: {c['source_label']}]\n{c['content']}" for i, c in enumerate(chunks, 1))


def answer_question(user_id: int, document_id: int, question: str, top_k: int | None = None) -> dict[str, Any]:
    chunks = retrieve_chunks(user_id, document_id, question, top_k)
    if not chunks:
        answer = "Informasi tersebut tidak ditemukan pada dokumen."
        sources: list[dict[str, Any]] = []
    else:
        answer = chat_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Konteks dokumen:\n{build_context(chunks)}\n\n"
                        f"Pertanyaan: {question}\n\n"
                        "Jawab ringkas, jelas, dan sebutkan sumber halaman/slide yang dipakai."
                    ),
                },
            ]
        )
        sources = [
            {"chunk_id": c["id"], "source_label": c["source_label"], "score": round(float(c["score"]), 4)}
            for c in chunks
        ]
    db.execute(
        """
        INSERT INTO chat_messages (user_id, document_id, question, answer, sources_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, document_id, question, answer, json.dumps(sources), db.utc_now()),
    )
    db.log_activity(user_id, "chat", "Pertanyaan dokumen dijawab", document_id)
    return {"answer": answer, "sources": sources}
