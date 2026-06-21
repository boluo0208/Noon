"""任务相关 API 路由。"""
from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.task_manager import task_manager, TaskStatus
from app.schemas.task import TaskCreateResponse, TaskInfoResponse
from app.services.noon_downloader import run_noon_download
from app.services.inventory_client import run_inventory_sync
from app.services.in_transit_client import run_in_transit_sync

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class DownloadOrdersRequest(BaseModel):
    account_id: str | None = None


class WarehouseTaskRequest(BaseModel):
    warehouse_id: str | None = None


@router.post("/download-orders", response_model=TaskCreateResponse)
def start_download_orders(payload: DownloadOrdersRequest | None = None) -> TaskCreateResponse:
    """创建后台任务下载 Noon 订单。"""
    task = task_manager.create_task("download-orders")
    # 在后台线程中运行 Playwright
    t = threading.Thread(target=run_noon_download, args=(task, payload.account_id if payload else None), daemon=True)
    t.start()
    return TaskCreateResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value,
        message=task.message,
    )


@router.post("/sync-inventory", response_model=TaskCreateResponse)
def start_sync_inventory(payload: WarehouseTaskRequest | None = None) -> TaskCreateResponse:
    """创建后台任务同步 ERP 库存。"""
    task = task_manager.create_task("sync-inventory")
    t = threading.Thread(target=run_inventory_sync, args=(task, payload.warehouse_id if payload else None), daemon=True)
    t.start()
    return TaskCreateResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value,
        message=task.message,
    )


@router.post("/sync-in-transit", response_model=TaskCreateResponse)
def start_sync_in_transit(payload: WarehouseTaskRequest | None = None) -> TaskCreateResponse:
    """创建后台任务同步在途库存。"""
    task = task_manager.create_task("sync-in-transit")
    t = threading.Thread(target=run_in_transit_sync, args=(task, payload.warehouse_id if payload else None), daemon=True)
    t.start()
    return TaskCreateResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value,
        message=task.message,
    )


@router.get("/{task_id}", response_model=TaskInfoResponse)
def get_task(task_id: str) -> TaskInfoResponse:
    """查询任务状态。前端轮询此接口。"""
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskInfoResponse(**task.to_dict())


@router.post("/{task_id}/continue")
def continue_task(task_id: str) -> dict:
    """用户完成手动登录后继续执行任务。"""
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != TaskStatus.WAITING_LOGIN:
        raise HTTPException(status_code=400, detail="任务不在等待登录状态")
    task.signal_continue()
    return {"status": "ok", "message": "任务继续执行"}
