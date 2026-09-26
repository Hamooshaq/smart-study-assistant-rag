import json
import shutil
from pathlib import Path

from .config import settings
from .embedding import embed_query, embed_texts


def _import_faiss():
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError("faiss-cpu belum terpasang. Jalankan pip install -r requirements.txt.") from exc
    return faiss


def _document_index_dir(user_id: int, document_id: int) -> Path:
    return settings.index_dir / f"user_{user_id}" / f"document_{document_id}"


def build_document_index(user_id: int, document_id: int, chunk_rows: list[dict]) -> None:
    if not chunk_rows:
        raise ValueError("Tidak ada chunk untuk dibuat index.")
    faiss = _import_faiss()
    embeddings = embed_texts([row["content"] for row in chunk_rows])
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    index_dir = _document_index_dir(user_id, document_id)
    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / "index.faiss"))
    (index_dir / "chunk_ids.json").write_text(
        json.dumps([int(row["id"]) for row in chunk_rows]), encoding="utf-8"
    )


def search_document_index(user_id: int, document_id: int, query: str, top_k: int) -> list[tuple[int, float]]:
    faiss = _import_faiss()
    index_dir = _document_index_dir(user_id, document_id)
    index_path = index_dir / "index.faiss"
    ids_path = index_dir / "chunk_ids.json"
    if not index_path.exists() or not ids_path.exists():
        raise RuntimeError("FAISS index belum tersedia untuk dokumen ini.")
    index = faiss.read_index(str(index_path))
    chunk_ids = json.loads(ids_path.read_text(encoding="utf-8"))
    scores, positions = index.search(embed_query(query), min(top_k, len(chunk_ids)))
    results: list[tuple[int, float]] = []
    for pos, score in zip(positions[0].tolist(), scores[0].tolist()):
        if pos >= 0:
            results.append((int(chunk_ids[pos]), float(score)))
    return results


def delete_document_index(user_id: int, document_id: int) -> None:
    index_dir = _document_index_dir(user_id, document_id)
    if index_dir.exists():
        shutil.rmtree(index_dir)
