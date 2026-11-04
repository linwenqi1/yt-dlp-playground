from fastapi import APIRouter

from app.api import health, info, jobs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(info.router)
api_router.include_router(jobs.router)
