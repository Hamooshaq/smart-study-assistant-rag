from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import database as db
from .auth import login_user, logout_user, register_user, require_user
from .config import ensure_storage_dirs, settings
from .documents import create_document_record, delete_document, document_history, list_documents, process_document, save_upload_file
from .generation import (
    generate_flashcards,
    generate_quiz,
    generate_summary,
    public_quiz_items,
    read_saved_outputs,
    record_quiz_attempt,
)
from .progress import document_progress
from .rag import answer_question, retrieve_chunks


app = FastAPI(title=settings.app_name)


class AuthPayload(BaseModel):
    email: str
    password: str
    name: str | None = None


class ChatPayload(BaseModel):
    document_id: int
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=10)


class RetrievePayload(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)


class CountPayload(BaseModel):
    count: int = Field(default=10, ge=1, le=30)


class SettingsPayload(BaseModel):
    vlm_enabled: bool


class QuizAttemptPayload(BaseModel):
    answers: list[str] = Field(default_factory=list)


@app.on_event("startup")
def startup() -> None:
    ensure_storage_dirs()
    db.init_db()


if settings.frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=settings.frontend_dir), name="static")
if settings.assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=settings.assets_dir), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(settings.frontend_dir / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "vlm_default_enabled": settings.vlm_enabled,
        "vlm_model": settings.vlm_model,
        "ollama_model": settings.ollama_model,
    }


@app.post("/api/register")
def register(payload: AuthPayload, response: Response) -> dict:
    return {"user": register_user(payload.name or "", payload.email, payload.password, response)}


@app.post("/api/login")
def login(payload: AuthPayload, response: Response) -> dict:
    return {"user": login_user(payload.email, payload.password, response)}


@app.post("/api/logout")
def logout(
    response: Response,
    user: dict = Depends(require_user),
    study_session: str | None = Cookie(default=None, alias=settings.session_cookie),
) -> dict:
    logout_user(study_session, response)
    db.log_activity(int(user["id"]), "logout", "Logout")
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(require_user)) -> dict:
    return {"user": user}


@app.get("/api/settings")
def get_settings(user: dict = Depends(require_user)) -> dict:
    return {
        "vlm_enabled": bool(user.get("vlm_enabled")),
        "vlm_model": settings.vlm_model,
        "ollama_model": settings.ollama_model,
    }


@app.put("/api/settings")
def update_settings(payload: SettingsPayload, user: dict = Depends(require_user)) -> dict:
    user_id = int(user["id"])
    db.execute("UPDATE users SET vlm_enabled = ? WHERE id = ?", (int(payload.vlm_enabled), user_id))
    db.log_activity(
        user_id,
        "update_settings",
        "Analisis gambar dinyalakan" if payload.vlm_enabled else "Analisis gambar dimatikan",
    )
    return {
        "vlm_enabled": payload.vlm_enabled,
        "vlm_model": settings.vlm_model,
        "ollama_model": settings.ollama_model,
    }


@app.get("/api/activity")
def activity(user: dict = Depends(require_user)) -> dict:
    rows = db.fetch_all(
        "SELECT action, detail, document_id, created_at FROM activities WHERE user_id = ? ORDER BY created_at DESC LIMIT 25",
        (user["id"],),
    )
    return {"items": [dict(r) for r in rows]}


@app.get("/api/documents")
def documents(user: dict = Depends(require_user)) -> dict:
    return {"documents": list_documents(int(user["id"]))}


@app.post("/api/documents")
def upload_document(
    file: UploadFile = File(...),
    use_vision: bool | None = Form(default=None),
    user: dict = Depends(require_user),
) -> dict:
    user_id = int(user["id"])
    try:
        vision_enabled = bool(user.get("vlm_enabled")) if use_vision is None else bool(use_vision)
        saved_path, extension = save_upload_file(user_id, file)
        document_id = create_document_record(
            user_id,
            saved_path,
            file.filename or saved_path.name,
            extension,
            vision_enabled,
        )
        db.log_activity(user_id, "upload_document", f"Upload dokumen: {file.filename}", document_id)
        process_document(user_id, document_id, saved_path, extension, use_vision=vision_enabled)
        row = db.fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
        return {"document": dict(row)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/documents/{document_id}")
def remove_document(document_id: int, user: dict = Depends(require_user)) -> dict:
    try:
        delete_document(int(user["id"]), document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/documents/{document_id}/retrieve")
def retrieve(document_id: int, payload: RetrievePayload, user: dict = Depends(require_user)) -> dict:
    chunks = retrieve_chunks(int(user["id"]), document_id, payload.query, payload.top_k)
    return {"chunks": [{"id": c["id"], "source_label": c["source_label"], "score": round(float(c["score"]), 4), "content": c["content"]} for c in chunks]}


@app.post("/api/chat")
def chat(payload: ChatPayload, user: dict = Depends(require_user)) -> dict:
    return answer_question(int(user["id"]), payload.document_id, payload.question, payload.top_k)


@app.post("/api/documents/{document_id}/summary")
def summary(document_id: int, user: dict = Depends(require_user)) -> dict:
    return {"summary": generate_summary(int(user["id"]), document_id)}


@app.post("/api/documents/{document_id}/flashcards")
def flashcards(document_id: int, payload: CountPayload | None = None, user: dict = Depends(require_user)) -> dict:
    return {"flashcards": generate_flashcards(int(user["id"]), document_id, payload.count if payload else 10)}


@app.post("/api/documents/{document_id}/quiz")
def quiz(document_id: int, payload: CountPayload | None = None, user: dict = Depends(require_user)) -> dict:
    questions = generate_quiz(int(user["id"]), document_id, payload.count if payload else 5)
    return {"quiz": public_quiz_items(questions)}


@app.post("/api/documents/{document_id}/quiz/attempts")
def submit_quiz(document_id: int, payload: QuizAttemptPayload, user: dict = Depends(require_user)) -> dict:
    try:
        return record_quiz_attempt(int(user["id"]), document_id, payload.answers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/documents/{document_id}/outputs")
def outputs(document_id: int, user: dict = Depends(require_user)) -> dict:
    return read_saved_outputs(int(user["id"]), document_id)


@app.get("/api/documents/{document_id}/history")
def history(document_id: int, user: dict = Depends(require_user)) -> dict:
    return document_history(int(user["id"]), document_id)


@app.get("/api/documents/{document_id}/study-progress")
def study_progress(document_id: int, user: dict = Depends(require_user)) -> dict:
    try:
        return document_progress(int(user["id"]), document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
