"""Shared API response models."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TaskCreateResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    message: str


class TaskInfoResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    message: str
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error_detail: Optional[str] = None


class OrderRow(BaseModel):
    order_nr: str
    partner_sku: str
    target_shipped_at: Optional[str] = None


class InventoryRow(BaseModel):
    SKU: str
    当前库存: int


class InTransitRow(BaseModel):
    SKU: str
    在途库存: int
