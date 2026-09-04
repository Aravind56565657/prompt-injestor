from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import attacks, reports, scans, targets
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("database initialized", url=settings.database_url.split("//")[-1].split(":")[0])
    yield


app = FastAPI(
    title="Prompt-Injection Tester",
    version="1.0.0",
    description="AI application security testing platform for prompt-injection vulnerabilities.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(targets.router, prefix="/api")
app.include_router(scans.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(attacks.router, prefix="/api")


@app.middleware("http")
async def enforce_max_body_size(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 2_000_000:
                    return JSONResponse(status_code=413, content={"detail": "Request body too large"})
            except ValueError:
                pass
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail} if settings.environment != "production" else {"detail": "Request failed"},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/")
async def root():
    return {"message": "Prompt-Injection Tester API", "docs": "/docs"}