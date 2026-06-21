"""Priority result routes."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.core.accounts import accounts_for_warehouse, get_warehouse
from app.core.paths import (
    IN_TRANSIT_CURRENT_FILE,
    INVENTORY_CURRENT_FILE,
    ORDERS_CURRENT_FILE,
    account_orders_current_file,
    warehouse_in_transit_current_file,
    warehouse_inventory_current_file,
)
from app.services.allocator import allocate_to_dicts
from app.services.order_parser import parse_orders

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/results/priority")
def get_priority_results(
    keyword: str = Query(""),
    status_filter: str = Query("", alias="status"),
    warehouse_id: str | None = Query(None),
) -> dict:
    try:
        warehouse = get_warehouse(warehouse_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    order_files = [account_orders_current_file(a.id) for a in accounts_for_warehouse(warehouse.id)]
    order_files = [p for p in order_files if p.exists()]
    if not order_files and not warehouse_id and ORDERS_CURRENT_FILE.exists():
        order_files = [ORDERS_CURRENT_FILE]

    if not order_files:
        return {
            "total": 0,
            "data": [],
            "stats": {"selected": 0, "waiting_transit": 0, "shortage": 0, "no_stock": 0, "total_skus": 0},
        }

    try:
        inventory_file = warehouse_inventory_current_file(warehouse.id)
        in_transit_file = warehouse_in_transit_current_file(warehouse.id)
        if not inventory_file.exists() and not warehouse_id:
            inventory_file = INVENTORY_CURRENT_FILE
        if not in_transit_file.exists() and not warehouse_id:
            in_transit_file = IN_TRANSIT_CURRENT_FILE

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8-sig", newline="") as tmp:
            tmp_path = Path(tmp.name)

        try:
            merged_df = pd.concat([parse_orders(path) for path in order_files], ignore_index=True)
            merged_df.to_csv(tmp_path, index=False, encoding="utf-8-sig")
            all_rows = allocate_to_dicts(tmp_path, inventory_file, in_transit_file)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if keyword:
        kw = keyword.lower()
        all_rows = [
            r for r in all_rows
            if kw in str(r.get("订单号", "")).lower()
            or kw in str(r.get("SKU", "")).lower()
        ]

    if status_filter:
        all_rows = [r for r in all_rows if r.get("状态") == status_filter]

    stats = {
        "selected": sum(1 for r in all_rows if r.get("状态") == "建议发货"),
        "waiting_transit": sum(1 for r in all_rows if r.get("状态") == "等待在途"),
        "shortage": sum(1 for r in all_rows if r.get("状态") == "库存不足"),
        "no_stock": sum(1 for r in all_rows if r.get("状态") == "无库存"),
        "total_skus": len(set(r.get("SKU") for r in all_rows)),
    }

    return {"total": len(all_rows), "data": all_rows, "stats": stats}
