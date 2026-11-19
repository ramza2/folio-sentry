"""FolioSentry private API; all /api/v1/* data is deny-by-default."""
from typing import Annotated

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.exc import SQLAlchemyError

from app import auth
from app.contract import DemoOverviewDTO
from app.database import check_database
from app.demo_data import DEMO_INSTRUMENTS, DemoInstrument
from app.demo_overview import get_demo_overview
from app.portfolio_api import router as portfolio_router

app = FastAPI(
    title="FolioSentry API", version="0.1.0",
    docs_url=None, redoc_url=None, openapi_url=None,
)


def api_error(status: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": "접근할 수 없습니다.", "request_id": None}},
        headers={"Cache-Control": "no-store"},
    )


@app.middleware("http")
async def protect_api(request: Request, call_next):
    path = request.url.path
    is_private_api = path.startswith("/api/") and path not in {
        "/api/health/live", "/api/health/ready",
    }
    if is_private_api:
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if (request.headers.get("sec-fetch-site") == "cross-site" or
                    not auth.origin_allowed(request.headers.get("origin"))):
                return api_error(403, "ORIGIN_REJECTED")

        # Every new /api/* endpoint is protected without the author adding
        # another dependency. Only the login endpoint is public.
        if not (path == "/api/v1/auth/login" and request.method == "POST"):
            try:
                identity = auth.get_identity(request.cookies.get(auth.cookie_name()))
            except SQLAlchemyError:
                return api_error(503, "AUTH_BACKEND_UNAVAILABLE")
            if identity is None:
                return api_error(401, "AUTH_REQUIRED")
            request.state.auth_identity = identity
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if not auth.csrf_matches(identity, request.headers.get("x-csrf-token")):
                    return api_error(403, "CSRF_REJECTED")

    response = await call_next(request)
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Vary"] = "Cookie"
    return response


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr


@app.post("/api/v1/auth/login")
def login(payload: LoginInput):
    try:
        username, token, csrf = auth.authenticate(username=payload.username, password=payload.password.get_secret_value())
    except SQLAlchemyError:
        return api_error(503, "AUTH_BACKEND_UNAVAILABLE")
    response = JSONResponse(content={"authenticated": True, "username": username, "csrf_token": csrf},
                            headers={"Cache-Control": "no-store"})
    response.set_cookie(
        key=auth.cookie_name(), value=token, max_age=auth.SESSION_SECONDS,
        httponly=True, secure=auth.get_settings().auth_cookie_secure,
        samesite="strict", path="/",
    )
    return response


@app.get("/api/v1/auth/me")
def me(request: Request):
    identity = request.state.auth_identity
    return {"authenticated": True, "username": identity.username, "csrf_token": identity.csrf_token}


@app.post("/api/v1/auth/logout")
def logout(request: Request):
    identity = request.state.auth_identity
    try:
        auth.invalidate_session(identity.session_hash)
    except SQLAlchemyError:
        return api_error(503, "AUTH_BACKEND_UNAVAILABLE")
    response = JSONResponse(content={"authenticated": False}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        key=auth.cookie_name(), path="/",
        secure=auth.get_settings().auth_cookie_secure, httponly=True, samesite="strict",
    )
    return response


@app.get("/api/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "folio-sentry"}


@app.get("/api/health/ready")
def ready(response: Response) -> dict[str, str]:
    db_ok = check_database()
    try:
        owner_ok = db_ok and auth.auth_ready()
    except SQLAlchemyError:
        owner_ok = False
    if not owner_ok:
        response.status_code = 503
    return {
        "status": "ready" if owner_ok else "unavailable",
        "database": "ok" if db_ok else "unavailable",
        "auth": "ready" if owner_ok else "unavailable",
    }


@app.get("/api/v1/demo/instruments")
def demo_instruments() -> dict[str, str | list[DemoInstrument]]:
    return {"mode": "demo", "instruments": list(DEMO_INSTRUMENTS)}


@app.get("/api/v1/demo/overview", response_model=DemoOverviewDTO)
def demo_overview() -> DemoOverviewDTO:
    """Visual design fixture. No live quotes, holdings or signals."""
    return get_demo_overview()


# All routes inherit the existing global Origin/CSRF/session middleware.
app.include_router(portfolio_router)
