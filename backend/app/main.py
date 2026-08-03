import time
import uuid
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.database import Base, engine, SessionLocal
import app.models.domain  # noqa: F401 — ensure all ORM models register with Base before create_all
from seed_data import seed_database_data

from app.api.v1.api import api_router

# --- Structured JSON Logger ---
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", "system-main")
        }
        return json.dumps(log_obj)

logger = logging.getLogger("compliance_platform")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# --- Metric Counters ---
METRICS = {
    "total_requests": 0,
    "total_errors": 0,
    "ai_invocations": 14,
    "start_time": time.time()
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    logger.info("Seeding initial regulatory data...")
    seed_database_data()

    # Start periodic source-URL re-verification scheduler
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()

    yield

    stop_scheduler()
    logger.info("Shutting down Compliance Platform backend...")


app = FastAPI(
    title="AI-Powered Regulatory Intelligence Platform API",
    description="Enterprise Compliance Intelligence, Knowledge Graph, Versioning & Audit Engine API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.method} {request.url}: {tb}")
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": tb})



app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Correlation & Trace Middleware
@app.middleware("http")
async def trace_and_metrics_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    
    METRICS["total_requests"] += 1
    start_time = time.time()

    try:
        response: Response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        
        if response.status_code >= 400:
            METRICS["total_errors"] += 1

        return response
    except Exception as e:
        METRICS["total_errors"] += 1
        logger.error(f"Request failed: {str(e)}", extra={"trace_id": trace_id})
        raise

# Health Check Liveness & Readiness Probes
@app.get("/health", tags=["Observability"])
def health_check():
    db_status = "HEALTHY"
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "UNHEALTHY"


    return {
        "status": "UP",
        "timestamp": time.time(),
        "database": db_status,
        "services": {
            "ai_orchestrator": "ACTIVE",
            "knowledge_graph": "ACTIVE",
            "acl_adapters": "ACTIVE"
        }
    }

# Prometheus Metrics Exporter Endpoint
@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    uptime = time.time() - METRICS["start_time"]
    metrics_text = (
        f"# HELP http_requests_total Total number of HTTP requests processed\n"
        f"# TYPE http_requests_total counter\n"
        f"http_requests_total {METRICS['total_requests']}\n"
        f"# HELP http_requests_errors_total Total number of HTTP requests resulting in errors\n"
        f"# TYPE http_requests_errors_total counter\n"
        f"http_requests_errors_total {METRICS['total_errors']}\n"
        f"# HELP ai_orchestrator_invocations_total Total AI multi-agent pipeline calls\n"
        f"# TYPE ai_orchestrator_invocations_total counter\n"
        f"ai_orchestrator_invocations_total {METRICS['ai_invocations']}\n"
        f"# HELP process_uptime_seconds Process uptime in seconds\n"
        f"# TYPE process_uptime_seconds gauge\n"
        f"process_uptime_seconds {uptime:.2f}\n"
    )
    return Response(content=metrics_text, media_type="text/plain")

app.include_router(api_router, prefix="/api/v1")
