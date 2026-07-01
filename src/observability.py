import json
import logging
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import Request
from fastapi.responses import Response

try:
    from prometheus_client import Counter, Gauge, Histogram, CONTENT_TYPE_LATEST, generate_latest
except Exception:  # pragma: no cover - fallback when prometheus_client is unavailable
    Counter = Gauge = Histogram = None
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None

from src.config import LOG_DIR

REQUEST_COUNT = Counter(
    "capstone_http_requests_total",
    "Total number of HTTP requests handled by the API",
    ["method", "path", "status"],
) if Counter else None

REQUEST_LATENCY = Histogram(
    "capstone_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
) if Histogram else None

ACTIVE_REQUESTS = Gauge(
    "capstone_http_active_requests",
    "Current number of in-flight HTTP requests",
) if Gauge else None

PLAN_EVENTS = Counter(
    "capstone_plan_events_total",
    "Day plan lifecycle events grouped by profession and event type",
    ["profession", "event_type"],
) if Counter else None

PLAN_ADHERENCE = Counter(
    "capstone_plan_adherence_signals_total",
    "Signals that help compare how professions follow their plans",
    ["profession", "signal"],
) if Counter else None

_LOGGER_NAME = "capstone"


class JsonLineFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if hasattr(record, "method"):
            payload["method"] = record.method
        if hasattr(record, "path"):
            payload["path"] = record.path
        if hasattr(record, "status_code"):
            payload["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms
        if hasattr(record, "client_ip"):
            payload["client_ip"] = record.client_ip
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging():
    logger = logging.getLogger(_LOGGER_NAME)
    if getattr(logger, "_configured", False):
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = JsonLineFormatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        LOG_DIR / "capstone.jsonl",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger._configured = True  # type: ignore[attr-defined]
    return logger


def setup_observability(app):
    logger = _configure_logging()

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "-"
        start = time.perf_counter()

        if ACTIVE_REQUESTS:
            ACTIVE_REQUESTS.inc()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start
            duration_ms = round(duration * 1000, 2)

            if REQUEST_COUNT:
                REQUEST_COUNT.labels(method=method, path=path, status=str(status_code)).inc()
            if REQUEST_LATENCY:
                REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
            if ACTIVE_REQUESTS:
                ACTIVE_REQUESTS.dec()

            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )

        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/metrics")
    def metrics():
        if generate_latest is None:
            return Response("prometheus_client is not installed", media_type="text/plain")
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    logger.info("observability_initialized")


def record_plan_event(profession: str | None, event_type: str, signal: str | None = None):
    profession_label = (profession or "Unknown").strip() or "Unknown"
    event_label = (event_type or "generated").strip() or "generated"
    if PLAN_EVENTS:
        PLAN_EVENTS.labels(profession=profession_label, event_type=event_label).inc()
    if signal and PLAN_ADHERENCE:
        PLAN_ADHERENCE.labels(profession=profession_label, signal=signal).inc()
