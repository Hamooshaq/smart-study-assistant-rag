from functools import lru_cache

import numpy as np

from .config import settings


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("sentence-transformers belum terpasang. Jalankan pip install -r requirements.txt.") from exc
    return SentenceTransformer(settings.embedding_model)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return (vectors / norms).astype("float32")


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.empty((0, 0), dtype="float32")
    model = _load_model()
    vectors = model.encode(texts, batch_size=8, show_progress_bar=False)
    return _normalize(np.asarray(vectors, dtype="float32"))


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])
