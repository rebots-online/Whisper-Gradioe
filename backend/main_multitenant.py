"""
Main FastAPI application with multi-tenant support.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import time
import threading

from backend.db.db_instance import init_db
from backend.routers.transcription.router import transcription_router, get_pipeline
from backend.routers.vad.router import get_vad_model, vad_router
from backend.routers.bgm_separation.router import get_bgm_separation_inferencer, bgm_separation_router
from backend.routers.task.router import task_router
from backend.common.config_loader import read_env, load_server_config
from backend.common.cache_manager import cleanup_old_files
from modules.utils.paths import SERVER_CONFIG_PATH, BACKEND_CACHE_DIR

# Import multi-tenant components
from backend.middleware.tenant_context import TenantContextMiddleware
from backend.routers.auth.router import auth_router
from backend.routers.tenant.router import tenant_router
from backend.routers.reseller.router import reseller_router
from backend.routers.workflow.router import workflow_router
from backend.routers.job import job_router
from backend.routers.websocket import websocket_router
from backend.job_queue import start_job_queue, stop_job_queue
from backend.job_queue.handlers import register_handlers


def clean_cache_thread(ttl: int, frequency: int) -> threading.Thread:
    def clean_cache(_ttl: int, _frequency: int):
        while True:
            cleanup_old_files(cache_dir=BACKEND_CACHE_DIR, ttl=_ttl)
            time.sleep(_frequency)

    return threading.Thread(
        target=clean_cache,
        args=(ttl, frequency),
        daemon=True
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Basic setup initialization
    server_config = load_server_config()
    read_env("DB_URL")  # Place .env file into /configs/.env
    init_db()

    # Inferencer initialization
    transcription_pipeline = get_pipeline()
    vad_inferencer = get_vad_model()
    bgm_separation_inferencer = get_bgm_separation_inferencer()

    # Thread initialization
    cache_thread = clean_cache_thread(server_config["cache"]["ttl"], server_config["cache"]["frequency"])
    cache_thread.start()

    # Start job queue
    start_job_queue()

    # Register job handlers
    register_handlers()

    yield

    # Stop job queue
    stop_job_queue()

    # Release VRAM when server shutdown
    transcription_pipeline = None
    vad_inferencer = None
    bgm_separation_inferencer = None


app = FastAPI(
    title="Whisper-WebUI-Backend",
    description=f"""
    REST API for Whisper-WebUI with multi-tenant support.
    Swagger UI is available via /docs or root URL with redirection. Redoc is available via /redoc.
    """,
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Authentication endpoints for multi-tenant support."
        },
        {
            "name": "Tenants",
            "description": "Tenant management endpoints for multi-tenant support."
        },
        {
            "name": "Resellers",
            "description": "Reseller management endpoints for multi-tenant support."
        },
        {
            "name": "Workflows",
            "description": "Workflow management endpoints for multi-tenant support."
        },
        {
            "name": "Transcription",
            "description": "Transcription endpoints for audio processing."
        },
        {
            "name": "VAD",
            "description": "Voice Activity Detection endpoints."
        },
        {
            "name": "BGM Separation",
            "description": "Cached files for /bgm-separation are generated in the `backend/cache` directory,"
                           " you can set TLL for these files in `backend/configs/config.yaml`."
        },
        {
            "name": "Tasks",
            "description": "Task management endpoints for tracking job progress."
        },
        {
            "name": "Jobs",
            "description": "Job management endpoints for processing transcription jobs."
        },
        {
            "name": "WebSockets",
            "description": "WebSocket endpoints for real-time job updates."
        }
    ]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],  # Disable DELETE
    allow_headers=["*"],
)

# Add tenant context middleware
app.add_middleware(TenantContextMiddleware)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(tenant_router, prefix="/api/tenants", tags=["Tenants"])
app.include_router(reseller_router, prefix="/api/resellers", tags=["Resellers"])
app.include_router(workflow_router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(transcription_router, tags=["Transcription"])
app.include_router(vad_router, tags=["VAD"])
app.include_router(bgm_separation_router, tags=["BGM Separation"])
app.include_router(task_router, tags=["Tasks"])
app.include_router(job_router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(websocket_router, tags=["WebSockets"])


@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def index():
    """
    Redirect to the documentation. Defaults to Swagger UI.
    You can also check the /redoc with redoc style: https://github.com/Redocly/redoc
    """
    return "/docs"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
