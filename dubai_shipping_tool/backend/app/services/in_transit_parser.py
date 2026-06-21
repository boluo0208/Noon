"""Parse ERP in-transit inventory exports."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

SKU_COLUMNS = ["SKU", "sku", "商品SKU", "商品编码", "商家SKU", "bizId", "BizId"]
QUANTITY_COLUMNS = ["数量", "在途库存", "当前库存", "库存", "quantity", "qty", "Quantity"]
CREATED_AT_COLUMNS = ["创建时间", "添加时间", "下单时间", "发货时间", "createdAt", "createTime"]
WAREHOUSE_COLUMNS = ["仓库名称", "仓库", "仓库字段", "warehouse", "warehouse_name", "Warehouse"]
MAX_AGE_DAYS = 10


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col).strip().lower(): str(col).strip() for col in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def parse_in_transit(file_path: Path, warehouse_name: str | None = None) -> pd.DataFrame:
    if not file_path.exists():
        raise FileNotFoundError(f"在途库存文件不存在: {file_path}")

    df = pd.read_excel(file_path, dtype=str)
    df.columns = df.columns.astype(str).str.strip()
    df = df.drop_duplicates()

    sku_col = _first_existing_column(df, SKU_COLUMNS)
    quantity_col = _first_existing_column(df, QUANTITY_COLUMNS)
    created_at_col = _first_existing_column(df, CREATED_AT_COLUMNS)
    warehouse_col = _first_existing_column(df, WAREHOUSE_COLUMNS)

    missing = []
    if not sku_col:
        missing.append("SKU")
    if not quantity_col:
        missing.append("数量")
    if missing:
        raise ValueError(f"在途库存文件缺少必要列: {missing}。实际列: {list(df.columns)}")

    if warehouse_name and warehouse_col:
        df = df[df[warehouse_col].astype(str).str.strip() == warehouse_name].copy()

    if created_at_col:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        def _in_recent_days(val: str | None) -> bool:
            if not val or pd.isna(val):
                return False
            dt = pd.to_datetime(val, errors="coerce")
            if pd.isna(dt):
                return False
            delta = today - dt.replace(tzinfo=None)
            return 0 <= delta.days <= MAX_AGE_DAYS

        df = df[df[created_at_col].apply(_in_recent_days)].copy()

    df = df[[sku_col, quantity_col]].copy()
    df = df.rename(columns={sku_col: "SKU", quantity_col: "在途库存"})
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df = df[(df["SKU"] != "") & (df["SKU"].str.lower() != "nan")]
    df["在途库存"] = pd.to_numeric(df["在途库存"], errors="coerce").fillna(0).astype(int)
    df["在途库存"] = df["在途库存"].clip(lower=0)

    return df.groupby("SKU", as_index=False)["在途库存"].sum()


def parse_in_transit_to_dicts(file_path: Path, warehouse_name: str | None = None) -> list[dict]:
    return parse_in_transit(file_path, warehouse_name=warehouse_name).to_dict(orient="records")
