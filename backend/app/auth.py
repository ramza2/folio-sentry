"""Single-owner authentication. Random opaque session IDs are only stored hashed."""
from dataclasses import dataclass
import hashlib
import hmac
import re
import secrets
import time

from argon2 import PasswordHasher, exceptions as argon_errors
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth_models import AuthSession, Owner
from app.config import get_settings
from app.database import get_engine

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
COOKIE_SECURE = "__Host-foliosentry_session"
COOKIE_DEV = "foliosentry_session_local"
SESSION_SECONDS = 8 * 60 * 60
IDLE_SECONDS = 30 * 60
MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{2,31}$")


@dataclass(frozen=True)
class AuthIdentity:
    username: str
    session_hash: str
    csrf_token: str


def cookie_name() -> str:
    return COOKIE_SECURE if get_settings().auth_cookie_secure else COOKIE_DEV


def _now() -> int:
    return int(time.time())


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_policy(password: str) -> None:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("비밀번호는 8~128자로 설정해야 합니다.")


def bootstrap_owner(username: str, password: str) -> None:
    """Explicit CLI-only initialization; NEVER called during app startup."""
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("사용자명은 영문자로 시작하는 영숫자/._- 조합 3~32자여야 합니다.")
    password_policy(password)
    digest = HASHER.hash(password)
    with Session(get_engine()) as db:
        with db.begin():
            if db.scalar(select(Owner.id).limit(1)) is not None:
                raise ValueError("소유자 계정이 이미 등록되었습니다.")
            db.add(Owner(id=1, username=username, password_hash=digest, failed_attempts=0))


def auth_ready() -> bool:
    """Readiness requires both auth schema tables and an initialized owner."""
    with Session(get_engine()) as db:
        owner_id = db.scalar(select(Owner.id).limit(1))
        db.scalar(select(AuthSession.id_hash).limit(1))
        return owner_id == 1


def authenticate(username: str, password: str) -> tuple[str, str, str]:
    """Rate limit invalid logins per the single account, returning token once."""
    now = _now()
    with Session(get_engine()) as db:
        with db.begin():
            owner = db.scalar(select(Owner).where(Owner.id == 1).with_for_update())
            if owner is None:
                raise HTTPException(status_code=503, detail="AUTH_NOT_INITIALIZED")
            if owner.locked_until is not None and owner.locked_until > now:
                raise HTTPException(status_code=429, detail="LOGIN_TEMPORARILY_LOCKED")
            try:
                verified = HASHER.verify(owner.password_hash, password)
            except (argon_errors.VerifyMismatchError, argon_errors.VerificationError, argon_errors.InvalidHashError):
                verified = False
            if not verified or not hmac.compare_digest(owner.username, username):
                owner.failed_attempts += 1
                if owner.failed_attempts >= MAX_ATTEMPTS:
                    owner.failed_attempts = 0
                    owner.locked_until = now + LOCK_SECONDS
                # Do not raise inside the transaction: the throttle must persist.
                success = False
            else:
                owner.failed_attempts = 0
                owner.locked_until = None
                token = secrets.token_urlsafe(32)
                csrf = secrets.token_urlsafe(32)
                db.add(AuthSession(
                    id_hash=_digest(token), owner_id=owner.id,
                    csrf_token=csrf, created_at=now, last_seen_at=now,
                    expires_at=now + SESSION_SECONDS,
                ))
                success = True
        if not success:
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
        return owner.username, token, csrf


def get_identity(token: str | None) -> AuthIdentity | None:
    if not token or len(token) > 256:
        return None
    now = _now()
    session_hash = _digest(token)
    with Session(get_engine()) as db:
        with db.begin():
            row = db.get(AuthSession, session_hash)
            if row is None:
                return None
            if row.expires_at <= now or now - row.last_seen_at > IDLE_SECONDS:
                db.delete(row)
                return None
            owner = db.get(Owner, row.owner_id)
            if owner is None:
                return None
            if now - row.last_seen_at >= 60:
                row.last_seen_at = now
            return AuthIdentity(username=owner.username, session_hash=session_hash, csrf_token=row.csrf_token)


def invalidate_session(session_hash: str) -> None:
    with Session(get_engine()) as db:
        with db.begin():
            db.execute(delete(AuthSession).where(AuthSession.id_hash == session_hash))


def csrf_matches(identity: AuthIdentity, submitted: str | None) -> bool:
    return bool(submitted) and hmac.compare_digest(identity.csrf_token, submitted)


def origin_allowed(origin: str | None) -> bool:
    allowed = {x.strip() for x in get_settings().auth_allowed_origins.split(",") if x.strip()}
    return bool(origin) and origin in allowed
