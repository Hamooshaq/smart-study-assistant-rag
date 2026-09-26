from datetime import datetime, timedelta, timezone
import re

from fastapi import Cookie, HTTPException, Response, status

from . import database as db
from .config import settings
from .security import hash_password, new_token, verify_password


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=settings.session_days)).isoformat(timespec="seconds")


def _public_user(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "vlm_enabled": bool(row["vlm_enabled"]) if "vlm_enabled" in row.keys() else False,
    }


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie,
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_days * 24 * 60 * 60,
    )


def create_session(user_id: int) -> str:
    token = new_token()
    db.execute(
        "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, user_id, _expires_at(), db.utc_now()),
    )
    return token


def register_user(name: str, email: str, password: str, response: Response) -> dict:
    name, email = name.strip(), email.strip().lower()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Nama minimal 2 karakter.")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email tidak valid.")
    try:
        user_id = db.execute(
            "INSERT INTO users (name, email, password_hash, created_at, vlm_enabled) VALUES (?, ?, ?, ?, ?)",
            (name, email, hash_password(password), db.utc_now(), int(settings.vlm_enabled)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Email sudah digunakan.") from exc
    user = db.fetch_one("SELECT id, name, email, vlm_enabled FROM users WHERE id = ?", (user_id,))
    _set_cookie(response, create_session(int(user["id"])))
    db.log_activity(int(user["id"]), "register", "Akun dibuat")
    return _public_user(user)


def login_user(email: str, password: str, response: Response) -> dict:
    row = db.fetch_one("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau password salah.")
    _set_cookie(response, create_session(int(row["id"])))
    db.log_activity(int(row["id"]), "login", "Login berhasil")
    return _public_user(row)


def logout_user(token: str | None, response: Response) -> None:
    if token:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    response.delete_cookie(settings.session_cookie)


def require_user(study_session: str | None = Cookie(default=None, alias=settings.session_cookie)) -> dict:
    if not study_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Belum login.")
    row = db.fetch_one(
        """
        SELECT u.id, u.name, u.email, s.expires_at
             , u.vlm_enabled
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token = ?
        """,
        (study_session,),
    )
    if not row:
        raise HTTPException(status_code=401, detail="Session tidak valid.")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        db.execute("DELETE FROM sessions WHERE token = ?", (study_session,))
        raise HTTPException(status_code=401, detail="Session sudah kedaluwarsa.")
    return _public_user(row)
