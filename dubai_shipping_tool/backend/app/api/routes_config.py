"""账号和仓库配置 API。"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.accounts import list_accounts_summary

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/accounts")
def get_accounts() -> dict:
    """返回可选 Noon 账号、ERP 账号和仓库配置。"""
    return list_accounts_summary()
