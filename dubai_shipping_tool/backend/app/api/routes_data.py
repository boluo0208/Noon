"""Data preview and file routes."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.accounts import accounts_for_warehouse, get_noon_account, get_warehouse
from app.core.paths import (
    IN_TRANSIT_CURRENT_FILE,
    INVENTORY_CURRENT_FILE,
    ORDERS_CURRENT_FILE,
    account_orders_current_file,
    warehouse_in_transit_current_file,
    warehouse_inventory_current_file,
)
from app.schemas.task import InTransitRow, InventoryRow, OrderRow
from app.services.in_transit_parser import parse_in_transit_to_dicts
from app.services.inventory_parser import parse_inventory_to_dicts
from app.services.order_parser import parse_orders_to_dicts

router = APIRouter(prefix="/api", tags=["data"])

ORDER_FRESH_SECONDS = 3600


def _file_meta(path: Path) -> dict:
    if not path.exists():
        return {
            "exists": False,
            "updated_at": None,
            "age_seconds": None,
            "is_stale": True,
            "size": 0,
        }
    updated_at = path.stat().st_mtime
    age_seconds = max(0, int(time.time() - updated_at))
    return {
        "exists": True,
        "updated_at": updated_at,
        "age_seconds": age_seconds,
        "is_stale": age_seconds > ORDER_FRESH_SECONDS,
        "size": path.stat().st_size,
    }


def _filter_order_rows(rows: list[dict], keyword: str) -> list[dict]:
    if not keyword:
        return rows
    kw = keyword.lower()
    return [
        row for row in rows
        if kw in str(row.get("order_nr", "")).lower()
        or kw in str(row.get("partner_sku", "")).lower()
        or kw in str(row.get("store_id", "")).lower()
    ]


def _sort_order_rows(rows: list[dict]) -> list[dict]:
    store_order = {"408158": 0, "442609": 1}
    return sorted(
        rows,
        key=lambda row: (
            store_order.get(str(row.get("store_id", "")), 99),
            str(row.get("target_shipped_at") or ""),
            str(row.get("order_nr") or ""),
        ),
    )


@router.get("/data/orders/warehouse")
def preview_orders_by_warehouse(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: str = Query(""),
    warehouse_id: str | None = Query(None),
) -> dict:
    try:
        warehouse = get_warehouse(warehouse_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    sources = accounts_for_warehouse(warehouse.id)
    all_rows: list[dict] = []
    source_statuses: list[dict] = []
    update_times: list[float] = []

    for source in sources:
        orders_file = account_orders_current_file(source.id)
        meta = _file_meta(orders_file)
        if meta["updated_at"]:
            update_times.append(float(meta["updated_at"]))

        source_status = {
            "id": source.id,
            "name": source.name,
            "store_id": source.store_id,
            "project_id": source.project_id,
            "warehouse_id": source.warehouse_id,
            **meta,
        }

        row_count = 0
        if orders_file.exists():
            try:
                rows = parse_orders_to_dicts(orders_file)
            except (FileNotFoundError, ValueError) as e:
                source_status["error"] = str(e)
                rows = []
            for row in rows:
                row["source_id"] = source.id
                row["source_name"] = source.name
                row["store_id"] = source.store_id
                row["project_id"] = source.project_id
                row["warehouse_id"] = source.warehouse_id
            row_count = len(rows)
            all_rows.extend(rows)
        source_status["row_count"] = row_count
        source_statuses.append(source_status)

    max_update_gap_seconds = 0
    if len(update_times) >= 2:
        max_update_gap_seconds = int(max(update_times) - min(update_times))

    freshness = {
        "fresh_seconds": ORDER_FRESH_SECONDS,
        "has_missing": any(not s["exists"] for s in source_statuses),
        "has_stale": any(s["is_stale"] for s in source_statuses),
        "max_update_gap_seconds": max_update_gap_seconds,
        "has_update_gap": max_update_gap_seconds > ORDER_FRESH_SECONDS,
        "needs_refresh": (
            any(not s["exists"] for s in source_statuses)
            or any(s["is_stale"] for s in source_statuses)
            or max_update_gap_seconds > ORDER_FRESH_SECONDS
        ),
    }

    all_rows = _sort_order_rows(_filter_order_rows(all_rows, keyword))
    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "warehouse": warehouse.model_dump(),
        "sources": source_statuses,
        "freshness": freshness,
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": all_rows[start:end],
    }


@router.get("/data/orders/preview")
def preview_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: str = Query(""),
    account_id: str | None = Query(None),
) -> dict:
    try:
        orders_file = account_orders_current_file(get_noon_account(account_id).id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not orders_file.exists() and not account_id:
        orders_file = ORDERS_CURRENT_FILE
    if not orders_file.exists():
        return {"total": 0, "page": page, "page_size": page_size, "data": []}

    try:
        all_rows = parse_orders_to_dicts(orders_file)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    all_rows = _filter_order_rows(all_rows, keyword)
    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    data = [OrderRow(**r) for r in all_rows[start:end]]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [d.model_dump() for d in data],
    }


@router.get("/files/orders/latest")
def download_latest_orders(account_id: str | None = Query(None)) -> FileResponse:
    try:
        orders_file = account_orders_current_file(get_noon_account(account_id).id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not orders_file.exists() and not account_id:
        orders_file = ORDERS_CURRENT_FILE
    if not orders_file.exists():
        raise HTTPException(status_code=404, detail="暂无订单文件")
    return FileResponse(path=str(orders_file), filename=orders_file.name, media_type="text/csv")


@router.get("/data/inventory/preview")
def preview_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: str = Query(""),
    warehouse_id: str | None = Query(None),
) -> dict:
    try:
        warehouse = get_warehouse(warehouse_id)
        inventory_file = warehouse_inventory_current_file(warehouse.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not inventory_file.exists() and not warehouse_id:
        inventory_file = INVENTORY_CURRENT_FILE
    if not inventory_file.exists():
        return {"total": 0, "page": page, "page_size": page_size, "data": []}

    try:
        all_rows = parse_inventory_to_dicts(inventory_file, warehouse_name=warehouse.erp_warehouse_name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if keyword:
        kw = keyword.lower()
        all_rows = [r for r in all_rows if kw in str(r.get("SKU", "")).lower()]

    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    data = [InventoryRow(**r) for r in all_rows[start:end]]

    return {"total": total, "page": page, "page_size": page_size, "data": [d.model_dump() for d in data]}


@router.get("/files/inventory/latest")
def download_latest_inventory(warehouse_id: str | None = Query(None)) -> FileResponse:
    try:
        inventory_file = warehouse_inventory_current_file(get_warehouse(warehouse_id).id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not inventory_file.exists() and not warehouse_id:
        inventory_file = INVENTORY_CURRENT_FILE
    if not inventory_file.exists():
        raise HTTPException(status_code=404, detail="暂无库存文件")
    return FileResponse(
        path=str(inventory_file),
        filename=inventory_file.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/data/in-transit/preview")
def preview_in_transit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: str = Query(""),
    warehouse_id: str | None = Query(None),
) -> dict:
    try:
        warehouse = get_warehouse(warehouse_id)
        in_transit_file = warehouse_in_transit_current_file(warehouse.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not in_transit_file.exists() and not warehouse_id:
        in_transit_file = IN_TRANSIT_CURRENT_FILE
    if not in_transit_file.exists():
        return {"total": 0, "page": page, "page_size": page_size, "data": []}

    try:
        all_rows = parse_in_transit_to_dicts(in_transit_file, warehouse_name=warehouse.erp_warehouse_name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if keyword:
        kw = keyword.lower()
        all_rows = [r for r in all_rows if kw in str(r.get("SKU", "")).lower()]

    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    data = [InTransitRow(**r) for r in all_rows[start:end]]

    return {"total": total, "page": page, "page_size": page_size, "data": [d.model_dump() for d in data]}


@router.get("/files/in-transit/latest")
def download_latest_in_transit(warehouse_id: str | None = Query(None)) -> FileResponse:
    try:
        in_transit_file = warehouse_in_transit_current_file(get_warehouse(warehouse_id).id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not in_transit_file.exists() and not warehouse_id:
        in_transit_file = IN_TRANSIT_CURRENT_FILE
    if not in_transit_file.exists():
        raise HTTPException(status_code=404, detail="暂无在途库存文件")
    return FileResponse(
        path=str(in_transit_file),
        filename=in_transit_file.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
