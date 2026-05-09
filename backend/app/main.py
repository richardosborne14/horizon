"""
FastAPI application entry point for Horizon.

This module creates the FastAPI app instance, configures CORS,
registers all routers, and sets up the health endpoint.
"""
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler. Minimal for Sprint 0."""
    print(f"🚀 Starting Horizon API [{settings.app_env}]")
    yield
    print("👋 Shutting down Horizon API")


app = FastAPI(
    title="Horizon API",
    description="API for Horizon — multi-decade wealth planning engine for French freelancers",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)


# CORS — allow requests from the SvelteKit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)


# Routers — all prefixed with /api, registered in app/routers/__init__.py
app.include_router(api_router, prefix="/api")


@app.get("/api/health", tags=["system"])
async def health_check():
    """Health check endpoint. Returns service status, timestamp, and version."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "environment": settings.app_env,
    }