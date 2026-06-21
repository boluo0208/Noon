"""Parse ERP inventory exports."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SKU_COLUMNS = ["SKU", "sku", "商品SKU", "商品编码", "商家SKU"]
STOCK_COLUMNS = ["当前库存", "可用库存", "库存", "数量", "stock", "quantity", "qty"]
WAREHOUSE_COLUMNS = ["仓库名称", "仓库", "仓库字段", "warehouse", "warehouse_name", "Warehouse"]


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    normalized = {str(col).strip().lower(): str(col).strip() for col in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def parse_inventory(file_path: Path, warehouse_name: str | None = None) -> pd.DataFrame:
    if not file_path.exists():
        raise FileNotFoundError(f"库存文件不存在: {file_path}")

    try:
        df = pd.read_excel(file_path, dtype=str)
    except Exception as e:
        raise ValueError(f"无法解析库存文件: {e}") from e

    df.columns = df.columns.astype(str).str.strip()
    sku_col = _first_existing_column(df, SKU_COLUMNS)
    stock_col = _first_existing_column(df, STOCK_COLUMNS)
    warehouse_col = _first_existing_column(df, WAREHOUSE_COLUMNS)

    missing = []
    if not sku_col:
        missing.append("SKU")
    if not stock_col:
        missing.append("当前库存")
    if missing:
        raise ValueError(f"库存文件缺少必要列: {missing}。实际列: {list(df.columns)}")

    if warehouse_name and warehouse_col:
        df = df[df[warehouse_col].astype(str).str.strip() == warehouse_name].copy()

    df = df[[sku_col, stock_col]].copy()
    df = df.rename(columns={sku_col: "SKU", stock_col: "当前库存"})
    df["SKU"] = df["SKU"].astype(str).str.strip()
    df = df[(df["SKU"] != "") & (df["SKU"].str.lower() != "nan")]
    df["当前库存"] = pd.to_numeric(df["当前库存"], errors="coerce").fillna(0).astype(int)
    df["当前库存"] = df["当前库存"].clip(lower=0)

    return df.groupby("SKU", as_index=False)["当前库存"].sum()


def parse_inventory_to_dicts(file_path: Path, warehouse_name: str | None = None) -> list[dict]:
    return parse_inventory(file_path, warehouse_name=warehouse_name).to_dict(orient="records")
