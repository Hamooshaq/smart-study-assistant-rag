from datetime import datetime, timedelta, timezone
import json
from typing import Any

from . import database as db


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_count(value: str | None) -> int:
    if not value:
        return 0
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return 0
    return len(data) if isinstance(data, list) else 0


def _excerpt(value: str, limit: int = 140) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _daily_template() -> dict[str, int]:
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    return {day.isoformat(): 0 for day in days}


def _add_minutes(daily: dict[str, int], timestamp: str | None, minutes: int) -> None:
    parsed = _parse_time(timestamp)
    if not parsed:
        return
    key = parsed.date().isoformat()
    if key in daily:
        daily[key] += minutes


def document_progress(user_id: int, document_id: int) -> dict[str, Any]:
    document = db.fetch_one(
        """
        SELECT d.id, d.original_filename, d.file_type, d.status, d.vision_enabled,
               d.uploaded_at, d.processed_at, COUNT(c.id) AS chunk_count,
               COALESCE(SUM(CASE WHEN c.is_visual = 1 THEN 1 ELSE 0 END), 0) AS visual_chunk_count
        FROM documents d
        LEFT JOIN chunks c ON c.document_id = d.id
        WHERE d.user_id = ? AND d.id = ?
        GROUP BY d.id
        """,
        (user_id, document_id),
    )
    if not document:
        raise ValueError("Dokumen tidak ditemukan.")

    chat_rows = db.fetch_all(
        """
        SELECT question, answer, created_at
        FROM chat_messages
        WHERE user_id = ? AND document_id = ?
        ORDER BY created_at DESC
        """,
        (user_id, document_id),
    )
    summary = db.fetch_one(
        "SELECT content, updated_at FROM summaries WHERE user_id = ? AND document_id = ?",
        (user_id, document_id),
    )
    flashcards = db.fetch_one(
        "SELECT cards_json, updated_at FROM flashcards WHERE user_id = ? AND document_id = ?",
        (user_id, document_id),
    )
    quiz = db.fetch_one(
        "SELECT questions_json, updated_at FROM quizzes WHERE user_id = ? AND document_id = ?",
        (user_id, document_id),
    )
    attempts = db.fetch_all(
        """
        SELECT correct, total, created_at
        FROM quiz_attempts
        WHERE user_id = ? AND document_id = ?
        ORDER BY created_at DESC
        """,
        (user_id, document_id),
    )

    daily = _daily_template()
    estimated_total = 0

    for row in chat_rows:
        estimated_total += 2
        _add_minutes(daily, row["created_at"], 2)
    if summary:
        estimated_total += 4
        _add_minutes(daily, summary["updated_at"], 4)
    if flashcards:
        estimated_total += 5
        _add_minutes(daily, flashcards["updated_at"], 5)
    if quiz:
        estimated_total += 4
        _add_minutes(daily, quiz["updated_at"], 4)
    for attempt in attempts:
        minutes = max(3, int(attempt["total"] or 0))
        estimated_total += minutes
        _add_minutes(daily, attempt["created_at"], minutes)

    flashcard_count = _json_count(flashcards["cards_json"] if flashcards else None)
    quiz_question_count = _json_count(quiz["questions_json"] if quiz else None)
    scores = [
        round((int(row["correct"]) / int(row["total"])) * 100)
        for row in attempts
        if int(row["total"] or 0) > 0
    ]
    last_score = scores[0] if scores else None
    average_score = round(sum(scores) / len(scores)) if scores else None

    next_steps: list[str] = []
    if not summary:
        next_steps.append("Buat ringkasan untuk menangkap gambaran besar materi.")
    if flashcard_count < 5:
        next_steps.append("Buat flashcard untuk mengulang istilah dan konsep penting.")
    if quiz_question_count and not attempts:
        next_steps.append("Kerjakan quiz pertama untuk melihat pemahaman awal.")
    elif last_score is not None and last_score < 70:
        next_steps.append("Ulangi soal yang salah, lalu baca ulang sumber halaman atau slide terkait.")
    if not next_steps:
        next_steps.append("Lanjutkan dengan pertanyaan lanjutan atau quiz baru dari dokumen ini.")

    return {
        "document": dict(document),
        "metrics": {
            "estimated_minutes": estimated_total,
            "chat_count": len(chat_rows),
            "summary_ready": bool(summary),
            "flashcard_count": flashcard_count,
            "quiz_question_count": quiz_question_count,
            "quiz_attempt_count": len(attempts),
            "last_quiz_score": last_score,
            "average_quiz_score": average_score,
        },
        "daily_minutes": [
            {"date": date, "minutes": minutes}
            for date, minutes in daily.items()
        ],
        "recent_chat": [
            {
                "question": row["question"],
                "answer_excerpt": _excerpt(row["answer"]),
                "created_at": row["created_at"],
            }
            for row in chat_rows[:5]
        ],
        "next_steps": next_steps,
    }
