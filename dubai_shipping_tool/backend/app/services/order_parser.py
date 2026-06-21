"""订单 CSV/XLSX 解析模块。

自动识别 CSV/Excel 格式，提取 order_nr、partner_sku、target_shipped_at 三列。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


REQUIRED_COLUMNS = ["order_nr", "partner_sku", "target_shipped_at"]


def parse_orders(file_path: Path) -> pd.DataFrame:
    """读取订单文件并提取三列核心字段。

    Args:
        file_path: CSV 或 XLSX 文件路径。

    Returns:
        DataFrame，只包含 order_nr, partner_sku, target_shipped_at 三列。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 缺少必要列或无法解析。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"订单文件不存在: {file_path}")

    suffix = file_path.suffix.lower()

    # 读取文件
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        # CSV: 尝试多种编码
        df = _read_csv_with_fallback(file_path)

    # 去除列名前后的空格
    df.columns = df.columns.str.strip()

    # 检查必需列
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"订单文件缺少必要列: {missing}。实际列名: {list(df.columns)}"
        )

    # 只保留三列
    df = df[REQUIRED_COLUMNS].copy()

    # 清洗数据
    df["order_nr"] = df["order_nr"].astype(str).str.strip()
    df["partner_sku"] = df["partner_sku"].astype(str).str.strip()
    df["target_shipped_at"] = df["target_shipped_at"].astype(str).str.strip()

    # 删除空行
    before = len(df)
    df = df[
        (df["order_nr"] != "")
        & (df["order_nr"] != "nan")
        & (df["partner_sku"] != "")
        & (df["partner_sku"] != "nan")
        & (df["target_shipped_at"] != "")
        & (df["target_shipped_at"] != "nan")
    ]
    dropped = before - len(df)

    # 解析时间
    df["parsed_time"] = pd.to_datetime(
        df["target_shipped_at"], errors="coerce", utc=False
    )
    invalid_time = df["parsed_time"].isna()
    if invalid_time.any():
        # 将无法解析时间的行标记，但不删除
        pass

    df["target_shipped_at"] = df["parsed_time"].apply(
        lambda x: x.isoformat() if pd.notna(x) else None
    )

    return df.drop(columns=["parsed_time"])


def _read_csv_with_fallback(file_path: Path) -> pd.DataFrame:
    """尝试多种编码读取 CSV。"""
    for encoding in ["utf-8-sig", "utf-8", "gb18030", "latin-1"]:
        try:
            return pd.read_csv(file_path, dtype=str, encoding=encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法识别 CSV 文件编码: {file_path}")


def parse_orders_to_dicts(file_path: Path) -> list[dict]:
    """解析订单文件并返回 dict 列表，供 API 直接返回 JSON。"""
    df = parse_orders(file_path)
    return df.to_dict(orient="records")
