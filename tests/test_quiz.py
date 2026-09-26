from backend.app.generation import grade_quiz_answers, public_quiz_items


QUESTIONS = [
    {
        "question": "Apa tujuan retrieval dalam sistem RAG?",
        "options": [
            "A. Mengambil konteks yang relevan",
            "B. Menghapus seluruh dokumen",
            "C. Mengubah password pengguna",
            "D. Mengganti format file",
        ],
        "answer": "A",
        "source": "Halaman 2",
    }
]


def test_public_quiz_items_hide_answer():
    public_items = public_quiz_items(QUESTIONS)
    assert public_items[0]["question"] == QUESTIONS[0]["question"]
    assert "answer" not in public_items[0]


def test_grade_quiz_answers_accepts_option_text():
    result = grade_quiz_answers(QUESTIONS, ["A. Mengambil konteks yang relevan"])
    assert result["correct"] == 1
    assert result["percent"] == 100
    assert result["results"][0]["correct_answer"] == "A. Mengambil konteks yang relevan"
