"""
Autentykacja JWT dla panelu sterowania.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

from config.settings import get_settings

settings      = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
ALGORITHM     = "HS256"
USERS_FILE    = Path("data/users.json")


class Token(BaseModel):
    access_token: str
    token_type:   str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire    = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


# ── Baza użytkowników ─────────────────────────────────────────────────────────

def _load_users() -> dict:
    try:
        if USERS_FILE.exists():
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_users(users: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")


def register_user(username: str, password: str) -> tuple[bool, str]:
    """Rejestruje nowe konto — wymaga zatwierdzenia przez admina."""
    if len(username) < 3:
        return False, "Login musi mieć min. 3 znaki"
    if len(password) < 6:
        return False, "Hasło musi mieć min. 6 znaków"
    if not username.isalnum():
        return False, "Login może zawierać tylko litery i cyfry"
    if username in (settings.panel_username, "viewer"):
        return False, "Zarezerwowana nazwa użytkownika"
    users = _load_users()
    if username in users:
        u = users[username]
        if u.get("approved"):
            return False, "Użytkownik już istnieje"
        else:
            return False, "Konto czeka na zatwierdzenie przez admina"
    users[username] = {
        "password_hash": hash_password(password),
        "role":          "viewer",
        "approved":      False,
        "created_at":    datetime.utcnow().isoformat(),
    }
    _save_users(users)
    return True, "Konto utworzone — czeka na zatwierdzenie przez admina"


def approve_user(username: str) -> tuple[bool, str]:
    users = _load_users()
    if username not in users:
        return False, "Użytkownik nie istnieje"
    users[username]["approved"] = True
    _save_users(users)
    return True, f"Zatwierdzono {username}"


def reject_user(username: str) -> tuple[bool, str]:
    users = _load_users()
    if username not in users:
        return False, "Użytkownik nie istnieje"
    del users[username]
    _save_users(users)
    return True, f"Odrzucono i usunięto {username}"


def delete_user(username: str) -> tuple[bool, str]:
    if username in (settings.panel_username, "viewer"):
        return False, "Nie można usunąć wbudowanych kont"
    users = _load_users()
    if username not in users:
        return False, "Użytkownik nie istnieje"
    del users[username]
    _save_users(users)
    return True, f"Usunięto {username}"


def list_users() -> list[dict]:
    users = _load_users()
    result = [
        {
            "username":   settings.panel_username,
            "role":       "admin",
            "approved":   True,
            "created_at": "",
            "builtin":    True,
        },
        {
            "username":   "viewer",
            "role":       "viewer",
            "approved":   True,
            "created_at": "",
            "builtin":    True,
        },
    ]
    for u, d in users.items():
        result.append({
            "username":   u,
            "role":       d.get("role", "viewer"),
            "approved":   d.get("approved", False),
            "created_at": d.get("created_at", ""),
            "builtin":    False,
        })
    return result


def get_user_role(username: str) -> str:
    if username == settings.panel_username:
        return "admin"
    users = _load_users()
    return users.get(username, {}).get("role", "viewer")


def authenticate_user(username: str, password: str) -> bool:
    # Wbudowany admin
    if username == settings.panel_username:
        if password == settings.emergency_stop_password:
            return True
        if settings.panel_password_hash:
            return verify_password(password, settings.panel_password_hash)
        return False
    # Wbudowany viewer
    if username == "viewer" and password == settings.viewer_password:
        return True
    # Użytkownicy z pliku — tylko zatwierdzeni
    users = _load_users()
    user = users.get(username)
    if user and user.get("approved") and user.get("password_hash"):
        return verify_password(password, user["password_hash"])
    return False


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nieprawidłowy token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exc
        return username
    except JWTError:
        raise credentials_exc


async def get_current_role(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload.get("role", "viewer")
    except Exception:
        return "viewer"
