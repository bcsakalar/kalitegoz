import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .api import (
    admin,
    agents,
    ai_admin,
    analytics,
    assist_ws,
    auth,
    calibration,
    calls,
    chats,
    criteria,
    enterprise,
    events,
    ingest_api,
    knowledge,
    notifications,
    review,
    selfservice,
    targets,
    vision_assist,
    reports,
    stats,
    supervisor,
    workflow,
)
from .config import settings
from .db import Base, SessionLocal, engine
from .logging_setup import setup_logging

setup_logging(json_logs=True)
logger = logging.getLogger(__name__)

# --- Basit istek metrikleri (observability) ---
_METRICS = {"requests_total": 0, "errors_total": 0}
_LATENCY_MS: deque[float] = deque(maxlen=500)
# --- Basit IP bazli rate limit (sliding window, process ici) ---
_RATE: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))


def _check_production_readiness() -> None:
    """Guvensiz prod ayarlarini boot'ta belirgin sekilde uyar (sessiz deploy riskini onler).

    ENVIRONMENT=production iken bu ayarlar acikca tehlikelidir; log'a KRITIK uyari
    duser. On-prem/dev'de yalnizca bilgilendirir."""
    prod = getattr(settings, "environment", "development").lower() == "production"
    issues: list[str] = []
    if "CHANGE-IN-PROD" in settings.jwt_secret or len(settings.jwt_secret) < 32:
        issues.append("JWT_SECRET zayif/varsayilan — en az 32 karakterlik rastgele bir deger atayin.")
    if settings.demo_mode:
        issues.append("DEMO_MODE acik — parolasiz demo giris aktif; prod'da DEMO_MODE=false yapin.")
    if settings.cors_origin_list == ["*"]:
        issues.append("CORS_ORIGINS='*' — prod'da yalnizca kendi frontend alan adinizi verin.")
    if not issues:
        return
    header = "KRITIK GUVENLIK" if prod else "Guvenlik uyarisi (prod oncesi duzeltin)"
    logger.warning("=== %s ===", header)
    for i in issues:
        logger.warning("  ! %s", i)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from . import models  # noqa: F401 — tablolarin kaydolmasi icin
    from .migrations import run_light_migrations
    from .seed import seed_all

    Base.metadata.create_all(bind=engine)
    run_light_migrations(engine)  # mevcut tablolara eksik kolonlari idempotent ekle
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()

    settings.audio_dir.mkdir(parents=True, exist_ok=True)
    settings.transcript_dir.mkdir(parents=True, exist_ok=True)
    settings.watch_dir.mkdir(parents=True, exist_ok=True)
    _check_production_readiness()
    yield


app = FastAPI(
    title="KaliteGoz API",
    description="Cok kanalli, kurumsal cagri merkezi kalite yonetim platformu",
    version="2.0.0",
    lifespan=lifespan,
)

# ONEMLI middleware sirasi: Starlette'te EN SON eklenen middleware EN DISTA calisir.
# Rate-limit ara katmani ONCE tanimlanir, CORS EN SON eklenir; boylece CORS disarida
# olur ve rate-limit 429 / 5xx dahil TUM yanitlara Access-Control-Allow-Origin eklenir.
# Aksi halde 429 donunce tarayici CORS basligi goremez ve "Failed to fetch / CORS
# policy" hatasi verir (yanit aslinda API'ye ulasmistir ama tarayici bloklar).
@app.middleware("http")
async def observability_and_rate_limit(request: Request, call_next):
    path = request.url.path
    # CORS preflight (OPTIONS) ve health/metrics rate-limit'e GIRMEZ
    if request.method != "OPTIONS" and not path.startswith(("/api/health", "/metrics")):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = _RATE[ip]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_min:
            return JSONResponse({"detail": "Cok fazla istek, lutfen yavaslayin"}, status_code=429)
        bucket.append(now)

    start = time.perf_counter()
    _METRICS["requests_total"] += 1
    try:
        response = await call_next(request)
    except Exception:
        _METRICS["errors_total"] += 1
        raise
    elapsed = (time.perf_counter() - start) * 1000
    _LATENCY_MS.append(elapsed)
    if response.status_code >= 500:
        _METRICS["errors_total"] += 1
    response.headers["X-Response-Time-ms"] = f"{elapsed:.1f}"
    # --- Guvenlik basliklari (clickjacking / MIME-sniff / referrer sizinti onlemi) ---
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-XSS-Protection", "0")  # modern tarayici; CSP tercih edilir
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # HSTS yalnizca prod'da (dev'de HTTP ile calisilir; tarayiciyi HTTPS'e kilitlemesin)
    if getattr(settings, "environment", "development").lower() == "production":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# CORS EN SON eklenir -> en dista calisir -> hata/429 yanitlarina da CORS basligi eklenir
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(calls.router)
app.include_router(chats.router)
app.include_router(criteria.router)
app.include_router(agents.router)
app.include_router(stats.router)
app.include_router(admin.router)
app.include_router(knowledge.router)
app.include_router(calibration.router)
app.include_router(workflow.router)
app.include_router(supervisor.router)
app.include_router(reports.router)
app.include_router(events.router)
app.include_router(review.router)
app.include_router(analytics.router)
app.include_router(selfservice.router)
app.include_router(vision_assist.router)
app.include_router(assist_ws.router)
app.include_router(enterprise.router)
app.include_router(ingest_api.router)
app.include_router(ai_admin.router)
app.include_router(targets.router)
app.include_router(notifications.router)


@app.get("/api/health", tags=["health"])
def health():
    """Liveness — surec ayakta mi (bagimlilik kontrolu yok, hizli)."""
    return {"status": "ok", "app": settings.app_name, "version": "2.0.0"}


@app.get("/api/health/ready", tags=["health"])
def readiness():
    """Readiness — DB ve Redis erisilebilir mi. Yuk dengeleyici/orkestrator icin."""
    from sqlalchemy import text as _text

    checks: dict[str, str] = {}
    ok = True
    try:
        with engine.connect() as conn:
            conn.execute(_text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"; ok = False
    try:
        import redis  # type: ignore
        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"; ok = False
    body = {"status": "ready" if ok else "degraded", "checks": checks}
    return JSONResponse(body, status_code=200 if ok else 503)


@app.get("/metrics", response_class=PlainTextResponse, tags=["health"])
def metrics():
    """Prometheus tarzi basit metrikler."""
    avg_latency = sum(_LATENCY_MS) / len(_LATENCY_MS) if _LATENCY_MS else 0
    lines = [
        "# HELP kalitegoz_requests_total Toplam istek sayisi",
        "# TYPE kalitegoz_requests_total counter",
        f"kalitegoz_requests_total {_METRICS['requests_total']}",
        "# HELP kalitegoz_errors_total Toplam 5xx/exception sayisi",
        "# TYPE kalitegoz_errors_total counter",
        f"kalitegoz_errors_total {_METRICS['errors_total']}",
        "# HELP kalitegoz_request_latency_ms_avg Ortalama istek suresi (ms)",
        "# TYPE kalitegoz_request_latency_ms_avg gauge",
        f"kalitegoz_request_latency_ms_avg {avg_latency:.2f}",
    ]
    return "\n".join(lines) + "\n"
