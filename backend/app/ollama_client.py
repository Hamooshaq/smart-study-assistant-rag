import requests

from .config import settings


class OllamaError(RuntimeError):
    pass


def chat_completion(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        response = requests.post(f"{settings.ollama_url.rstrip('/')}/api/chat", json=payload, timeout=120)
    except requests.RequestException as exc:
        raise OllamaError("Ollama belum bisa dihubungi. Jalankan Ollama dan pull model Qwen.") from exc
    if response.status_code >= 400:
        raise OllamaError(f"Ollama error {response.status_code}: {response.text[:300]}")
    content = response.json().get("message", {}).get("content", "").strip()
    if not content:
        raise OllamaError("Ollama tidak mengembalikan jawaban.")
    return content
