import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from jose import JWTError, jwt

JWT_SECRET = os.getenv("JWT_SECRET", "snoopi-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 8

_users_file = Path(__file__).parent / "users.json"
_users: list[dict] = json.loads(_users_file.read_text())


def authenticate(username: str, password: str) -> dict | None:
    """Return user dict (without hash) if credentials are valid, else None."""
    for user in _users:
        if user["username"] == username:
            if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
                return {"username": user["username"], "display_name": user["display_name"]}
            return None
    return None


def create_token(username: str, display_name: str) -> str:
    """Create a JWT token that expires in JWT_EXPIRE_HOURS."""
    payload = {
        "sub": username,
        "display_name": display_name,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """Decode and verify a JWT token. Returns user dict or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"username": payload["sub"], "display_name": payload["display_name"]}
    except JWTError:
        return None
