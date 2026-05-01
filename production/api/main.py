"""
FlowSync Customer Success -- Main API Server
==============================================
FastAPI application that serves all channel endpoints.
"""

from __future__ import annotations

import logging
import sys
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ──────────────────────────────────────────────────────────────
# PATH SETUP
# ──────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_path = os.path.join(_project_root, "..", "src")
for p in [_src_path, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("flowsync.api")

# ──────────────────────────────────────────────────────────────
# LIFESPAN
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  FlowSync Customer Success API -- Starting")
    logger.info("=" * 60)

    # Database check
    try:
        from database import queries
        pool = await queries.get_db_pool()
        logger.info("  Database: Connected")
    except Exception as e:
        logger.warning("  Database: Not available (%s)", e)

    yield

    logger.info("Shutting down FlowSync API...")


# ──────────────────────────────────────────────────────────────
# APP CREATION
# ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="FlowSync Customer Success API",
        description="24/7 AI-powered customer support",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS Middleware - Yeh sahi jagah hai
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],                    # Development ke liye "*"
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Import and include routers ──
    from channels.web_form_handler import router as web_form_router
    app.include_router(web_form_router)

    # Root & Health endpoints
    @app.get("/", tags=["Health"])
    async def root():
        return {
            "service": "FlowSync Customer Success API",
            "status": "healthy",
            "docs": "/docs",
        }

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


# Create app instance
app = create_app()


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )