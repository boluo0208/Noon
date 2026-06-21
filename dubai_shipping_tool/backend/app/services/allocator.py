"""Priority allocation based on orders, stock, and in-transit stock."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from app.services.in_transit_parser import parse_in_transit
from app.services.inventory_parser import parse_inventory
from app.services.order_parser import parse_orders

ALLOCATION_STATUS = {
    "SELECTED": "建议发货",
    "WAITING_TRANSIT": "等待在途",
    "SHORTAGE": "库存不足",
    "NO_STOCK": "无库存",
}


def _format_time(iso_str: str | None) -> str:
    if not iso_str or pd.isna(iso_str):
        return "-"
    try:
        return datetime.fromisoformat(str(iso_str)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(iso_str)


def allocate(orders_file: Path, inventory_file: Path, in_transit_file: Path | None = None) -> pd.DataFrame:
    if not orders_file.exists():
        raise FileNotFoundError(f"订单文件不存在: {orders_file}")

    orders_df = parse_orders(orders_file)

    inventory_map: dict[str, int] = {}
    if inventory_file.exists():
        inv_df = parse_inventory(inventory_file)
        inventory_map = dict(zip(inv_df["SKU"], inv_df["当前库存"]))
        inventory_map = {k: max(0, int(v)) for k, v in inventory_map.items()}

    in_transit_map: dict[str, int] = {}
    if in_transit_file and in_transit_file.exists():
        transit_df = parse_in_transit(in_transit_file)
        in_transit_map = dict(zip(transit_df["SKU"], transit_df["在途库存"]))
        in_transit_map = {k: max(0, int(v)) for k, v in in_transit_map.items()}

    sku_order_count = orders_df.groupby("partner_sku").size().to_dict()
    results = []

    for sku, group in orders_df.groupby("partner_sku"):
        group = group.copy()
        stock = inventory_map.get(sku, 0)
        transit_stock = in_transit_map.get(sku, 0)
        demand_count = int(sku_order_count.get(sku, len(group)))
        total_visible_stock = stock + transit_stock
        shortage_gap = max(demand_count - total_visible_stock, 0)

        group = group.sort_values(["target_shipped_at", "order_nr"], ascending=[True, True])
        group["库存"] = stock
        group["出单数"] = demand_count
        group["在途库存"] = transit_stock
        group["现货+在途"] = total_visible_stock
        group["缺口"] = shortage_gap
        group["priority_rank"] = range(1, len(group) + 1)

        def _status(rank: int) -> str:
            if rank <= stock:
                return ALLOCATION_STATUS["SELECTED"]
            if rank <= total_visible_stock:
                return ALLOCATION_STATUS["WAITING_TRANSIT"]
            if total_visible_stock <= 0:
                return ALLOCATION_STATUS["NO_STOCK"]
            return ALLOCATION_STATUS["SHORTAGE"]

        group["状态"] = group["priority_rank"].apply(_status)
        results.append(group)

    if not results:
        return pd.DataFrame(columns=[
            "订单号", "SKU", "库存", "出单数", "在途库存", "现货+在途", "缺口", "最晚处理时间", "状态"
        ])

    result = pd.concat(results, ignore_index=True)
    result = result.rename(columns={
        "order_nr": "订单号",
        "partner_sku": "SKU",
        "target_shipped_at": "最晚处理时间",
    })
    result["最晚处理时间"] = result["最晚处理时间"].apply(_format_time)

    return result[["订单号", "SKU", "库存", "出单数", "在途库存", "现货+在途", "缺口", "最晚处理时间", "状态"]]


def allocate_to_dicts(orders_file: Path, inventory_file: Path, in_transit_file: Path | None = None) -> list[dict]:
    return allocate(orders_file, inventory_file, in_transit_file).to_dict(orient="records")
