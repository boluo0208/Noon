"""FastAPI 应用入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.paths import ensure_directories
from app.api.routes_tasks import router as tasks_router
from app.api.routes_data import router as data_router
from app.api.routes_results import router as results_router
from app.api.routes_config import router as config_router

# 启动时自动创建目录
ensure_directories()

app = FastAPI(title=settings.app_name, version="1.0.0")

# CORS: 允许前端开发服务器
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(data_router)
app.include_router(results_router)
app.include_router(config_router)


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok", "app": settings.app_name}
