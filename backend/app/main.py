"""Phase 0 API: health/readiness and fake instrument metadata only."""
from fastapi import FastAPI, Response

from app.contract import DemoOverviewDTO
from app.database import check_database
from app.demo_overview import get_demo_overview
from app.demo_data import DEMO_INSTRUMENTS, DemoInstrument

app = FastAPI(title="FolioSentry API", version="0.1.0")


@app.get("/api/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "folio-sentry"}


@app.get("/api/health/ready")
def ready(response: Response) -> dict[str, str]:
    database_ok = check_database()
    if not database_ok:
        response.status_code = 503
    return {
        "status": "ready" if database_ok else "unavailable",
        "database": "ok" if database_ok else "unavailable",
    }


@app.get("/api/v1/demo/instruments")
def demo_instruments() -> dict[str, str | list[DemoInstrument]]:
    return {"mode": "demo", "instruments": list(DEMO_INSTRUMENTS)}


@app.get("/api/v1/demo/overview", response_model=DemoOverviewDTO)
def demo_overview() -> DemoOverviewDTO:
    """Visual design fixture. No live quotes, holdings or signals."""
    return get_demo_overview()
