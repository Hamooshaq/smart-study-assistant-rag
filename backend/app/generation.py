import json
import re
from typing import Any

from . import database as db
from .config import settings
from .ollama_client import chat_completion
from .rag import get_owned_document


def _document_context(user_id: int, document_id: int) -> str:
    get_owned_document(user_id, document_id)
    rows = db.fetch_all(
        "SELECT source_label, content FROM chunks WHERE user_id = ? AND document_id = ? ORDER BY chunk_index",
        (user_id, document_id),
    )
    text = "\n\n".join(f"[{r['source_label']}]\n{r['content']}" for r in rows)
    return text[: settings.summary_max_chars]


def _upsert(table: str, column: str, user_id: int, document_id: int, value: str) -> None:
    now = db.utc_now()
    db.execute(
        f"""
        INSERT INTO {table} (user_id, document_id, {column}, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, document_id) DO UPDATE SET
            {column} = excluded.{column},
            updated_at = excluded.updated_at
        """,
        (user_id, document_id, value, now, now),
    )


def generate_summary(user_id: int, document_id: int) -> str:
    content = chat_completion(
        [
            {"role": "system", "content": "Buat ringkasan hanya berdasarkan konteks dokumen."},
            {"role": "user", "content": f"Konteks:\n{_document_context(user_id, document_id)}\n\nBuat ringkasan belajar dalam bahasa Indonesia."},
        ]
    )
    _upsert("summaries", "content", user_id, document_id, content)
    db.log_activity(user_id, "generate_summary", "Ringkasan dibuat", document_id)
    return content


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            raise ValueError("Model tidak mengembalikan JSON array valid.")
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise ValueError("Output JSON harus berupa array.")
    return [item for item in data if isinstance(item, dict)]


def generate_flashcards(user_id: int, document_id: int, count: int = 10) -> list[dict[str, Any]]:
    raw = chat_completion(
        [
            {"role": "system", "content": "Buat flashcard hanya berdasarkan konteks. Output JSON array valid."},
            {"role": "user", "content": f"Konteks:\n{_document_context(user_id, document_id)}\n\nBuat {count} flashcard dengan format JSON: [{'{'}\"question\":\"...\",\"answer\":\"...\",\"source\":\"...\"{'}'}]."},
        ],
        temperature=0.1,
    )
    cards = _extract_json_array(raw)
    _upsert("flashcards", "cards_json", user_id, document_id, json.dumps(cards, ensure_ascii=False))
    db.log_activity(user_id, "generate_flashcards", f"{len(cards)} flashcard dibuat", document_id)
    return cards


def _answer_key(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"A", "B", "C", "D"}:
        return text
    match = re.match(r"^([A-D])[\.\)]\s+", text)
    return match.group(1) if match else ""


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _correct_answer(item: dict[str, Any]) -> str:
    options = [_clean_text(option) for option in item.get("options", []) if _clean_text(option)]
    answer = _clean_text(item.get("answer", ""))
    if answer in options:
        return answer

    key = _answer_key(answer)
    if key:
        index = ord(key) - ord("A")
        if 0 <= index < len(options):
            return options[index]
        for option in options:
            if _answer_key(option) == key:
                return option
    return answer


def _normalize_quiz_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        question = _clean_text(item.get("question"))
        options = [_clean_text(option) for option in item.get("options", []) if _clean_text(option)]
        answer = _correct_answer({**item, "options": options})
        if not question or len(options) < 2 or not answer:
            continue
        normalized.append(
            {
                "question": question,
                "options": options,
                "answer": answer,
                "source": _clean_text(item.get("source")),
            }
        )
    return normalized


def public_quiz_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": index,
            "question": item.get("question", ""),
            "options": item.get("options", []),
            "source": item.get("source", ""),
        }
        for index, item in enumerate(_normalize_quiz_items(items))
    ]


def grade_quiz_answers(items: list[dict[str, Any]], answers: list[str]) -> dict[str, Any]:
    questions = _normalize_quiz_items(items)
    results: list[dict[str, Any]] = []
    correct = 0

    for index, question in enumerate(questions):
        selected = _clean_text(answers[index] if index < len(answers) else "")
        answer = _correct_answer(question)
        selected_key = _answer_key(selected)
        answer_key = _answer_key(answer)
        is_correct = bool(selected) and (
            selected.casefold() == answer.casefold()
            or (bool(selected_key) and selected_key == answer_key)
        )
        correct += int(is_correct)
        results.append(
            {
                "question": question["question"],
                "options": question["options"],
                "selected_answer": selected,
                "correct_answer": answer,
                "is_correct": is_correct,
                "source": question.get("source", ""),
            }
        )

    total = len(questions)
    percent = round((correct / total) * 100) if total else 0
    return {"correct": correct, "total": total, "percent": percent, "results": results}


def generate_quiz(user_id: int, document_id: int, count: int = 5) -> list[dict[str, Any]]:
    raw = chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Buat quiz hanya berdasarkan konteks dokumen. Output harus JSON array valid tanpa markdown. "
                    "Setiap options harus berisi teks jawaban lengkap, dan answer harus sama persis dengan salah satu options."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Konteks:\n{_document_context(user_id, document_id)}\n\n"
                    f"Buat {count} soal pilihan ganda dalam bahasa Indonesia dengan format JSON: "
                    f"[{'{'}\"question\":\"...\",\"options\":[\"A. ...\",\"B. ...\",\"C. ...\",\"D. ...\"],"
                    f"\"answer\":\"A. ...\",\"source\":\"Halaman/Slide ...\"{'}'}]."
                ),
            },
        ],
        temperature=0.1,
    )
    questions = _normalize_quiz_items(_extract_json_array(raw))
    _upsert("quizzes", "questions_json", user_id, document_id, json.dumps(questions, ensure_ascii=False))
    db.log_activity(user_id, "generate_quiz", f"{len(questions)} soal quiz dibuat", document_id)
    return questions


def record_quiz_attempt(user_id: int, document_id: int, answers: list[str]) -> dict[str, Any]:
    get_owned_document(user_id, document_id)
    row = db.fetch_one("SELECT questions_json FROM quizzes WHERE user_id = ? AND document_id = ?", (user_id, document_id))
    if not row:
        raise ValueError("Quiz belum tersedia untuk dokumen ini.")
    graded = grade_quiz_answers(json.loads(row["questions_json"]), answers)
    db.execute(
        """
        INSERT INTO quiz_attempts (
            user_id, document_id, answers_json, results_json, correct, total, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            document_id,
            json.dumps(answers, ensure_ascii=False),
            json.dumps(graded["results"], ensure_ascii=False),
            graded["correct"],
            graded["total"],
            db.utc_now(),
        ),
    )
    db.log_activity(
        user_id,
        "submit_quiz",
        f"Quiz selesai: {graded['correct']}/{graded['total']}",
        document_id,
    )
    return graded


def read_saved_outputs(user_id: int, document_id: int) -> dict[str, Any]:
    summary = db.fetch_one("SELECT content FROM summaries WHERE user_id = ? AND document_id = ?", (user_id, document_id))
    flashcards = db.fetch_one("SELECT cards_json FROM flashcards WHERE user_id = ? AND document_id = ?", (user_id, document_id))
    quizzes = db.fetch_one("SELECT questions_json FROM quizzes WHERE user_id = ? AND document_id = ?", (user_id, document_id))
    return {
        "summary": summary["content"] if summary else None,
        "flashcards": json.loads(flashcards["cards_json"]) if flashcards else [],
        "quiz": public_quiz_items(json.loads(quizzes["questions_json"])) if quizzes else [],
    }
