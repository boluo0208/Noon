"""Account, store, order-source, and warehouse configuration."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.paths import PROJECT_ROOT


class WarehouseConfig(BaseModel):
    id: str
    name: str
    market: str
    erp_account_id: str
    erp_warehouse_name: str
    order_timezone: str = "Asia/Dubai"


class NoonLoginAccountConfig(BaseModel):
    id: str
    name: str
    email: str = ""


class NoonOrderSourceConfig(BaseModel):
    id: str
    name: str
    market: str
    warehouse_id: str
    noon_account_id: str
    store_id: str = ""
    project_id: str = ""
    email: str = ""
    noon_warehouse_name: str = ""
    noon_warehouse_code: str = ""
    pending_url: str = ""


class ErpAccountConfig(BaseModel):
    id: str
    name: str
    username: str = ""
    password: str = ""


class AccountsConfig(BaseModel):
    default_noon_account_id: str = "noon_primary_ae"
    default_warehouse_id: str = "dubai"
    warehouses: list[WarehouseConfig] = Field(default_factory=list)
    noon_login_accounts: list[NoonLoginAccountConfig] = Field(default_factory=list)
    noon_accounts: list[NoonOrderSourceConfig] = Field(default_factory=list)
    erp_accounts: list[ErpAccountConfig] = Field(default_factory=list)


NoonAccountConfig = NoonOrderSourceConfig


def _config_path() -> Path:
    return PROJECT_ROOT / "config" / "accounts.json"


def _fallback_config() -> AccountsConfig:
    return AccountsConfig(
        default_noon_account_id="noon_primary_ae",
        default_warehouse_id="dubai",
        warehouses=[
            WarehouseConfig(
                id="dubai",
                name="迪拜仓",
                market="AE",
                erp_account_id="erp_ae",
                erp_warehouse_name="迪拜仓",
                order_timezone=settings.order_timezone,
            )
        ],
        noon_login_accounts=[
            NoonLoginAccountConfig(id="noon_primary", name="Noon账号1"),
        ],
        noon_accounts=[
            NoonOrderSourceConfig(
                id="noon_primary_ae",
                name="Noon账号-店铺408158-迪拜订单",
                market="AE",
                warehouse_id="dubai",
                noon_account_id="noon_primary",
                store_id="408158",
                project_id="PRJ408158",
                noon_warehouse_name="GP-UAE",
                noon_warehouse_code="W00178809AE",
                pending_url=settings.noon_pending_url,
            )
        ],
        erp_accounts=[
            ErpAccountConfig(
                id="erp_ae",
                name="ERP迪拜账号",
                username=settings.erp_username,
                password=settings.erp_password,
            )
        ],
    )


def _upgrade_legacy_config(data: dict) -> dict:
    if "noon_login_accounts" in data:
        return data

    login_accounts: list[dict] = []
    order_sources: list[dict] = []
    seen_login_ids: set[str] = set()
    for source in data.get("noon_accounts", []):
        login_id = source.get("noon_account_id") or source.get("login_account_id") or source.get("id")
        if login_id not in seen_login_ids:
            login_accounts.append({
                "id": login_id,
                "name": source.get("login_name") or source.get("name") or login_id,
                "email": source.get("email", ""),
            })
            seen_login_ids.add(login_id)
        order_sources.append({**source, "noon_account_id": login_id})

    data = {**data}
    data["noon_login_accounts"] = login_accounts
    data["noon_accounts"] = order_sources
    return data


def load_accounts_config() -> AccountsConfig:
    path = _config_path()
    if not path.exists():
        return _fallback_config()
    data = json.loads(path.read_text(encoding="utf-8"))
    config = AccountsConfig(**_upgrade_legacy_config(data))
    if not config.warehouses or not config.noon_accounts or not config.erp_accounts:
        return _fallback_config()
    return config


def _login_account_map(config: AccountsConfig) -> dict[str, NoonLoginAccountConfig]:
    return {account.id: account for account in config.noon_login_accounts}


def _source_with_effective_email(
    source: NoonOrderSourceConfig,
    login_accounts: dict[str, NoonLoginAccountConfig],
) -> NoonOrderSourceConfig:
    if source.email:
        return source
    login_account = login_accounts.get(source.noon_account_id)
    if not login_account or not login_account.email:
        return source
    return source.model_copy(update={"email": login_account.email})


def list_accounts_summary() -> dict:
    config = load_accounts_config()
    login_accounts = _login_account_map(config)
    return {
        "default_noon_account_id": config.default_noon_account_id,
        "default_warehouse_id": config.default_warehouse_id,
        "warehouses": [w.model_dump() for w in config.warehouses],
        "noon_login_accounts": [
            a.model_dump() | {"has_email": bool(a.email)}
            for a in config.noon_login_accounts
        ],
        "noon_accounts": [
            _source_with_effective_email(source, login_accounts).model_dump(exclude={"pending_url"})
            | {"has_pending_url": bool(source.pending_url)}
            for source in config.noon_accounts
        ],
        "erp_accounts": [
            a.model_dump(exclude={"password"}) | {"has_password": bool(a.password)}
            for a in config.erp_accounts
        ],
    }


def get_warehouse(warehouse_id: str | None = None) -> WarehouseConfig:
    config = load_accounts_config()
    wanted = warehouse_id or config.default_warehouse_id
    for warehouse in config.warehouses:
        if warehouse.id == wanted:
            return warehouse
    raise ValueError(f"未知仓库: {wanted}")


def get_noon_login_account(account_id: str) -> NoonLoginAccountConfig:
    config = load_accounts_config()
    for account in config.noon_login_accounts:
        if account.id == account_id:
            return account
    raise ValueError(f"未知 Noon 登录账号: {account_id}")


def get_noon_account(account_id: str | None = None) -> NoonOrderSourceConfig:
    config = load_accounts_config()
    login_accounts = _login_account_map(config)
    wanted = account_id or config.default_noon_account_id
    for source in config.noon_accounts:
        if source.id == wanted:
            if not source.pending_url:
                raise ValueError(f"Noon订单来源 {source.name} 未配置 pending_url")
            if source.noon_account_id not in login_accounts:
                raise ValueError(f"Noon订单来源 {source.name} 绑定的登录账号不存在: {source.noon_account_id}")
            return _source_with_effective_email(source, login_accounts)
    raise ValueError(f"未知 Noon 订单来源: {wanted}")


def get_erp_account(warehouse_id: str | None = None) -> tuple[WarehouseConfig, ErpAccountConfig]:
    config = load_accounts_config()
    warehouse = get_warehouse(warehouse_id)
    for account in config.erp_accounts:
        if account.id == warehouse.erp_account_id:
            return warehouse, account
    raise ValueError(f"仓库 {warehouse.name} 绑定的 ERP 账号不存在: {warehouse.erp_account_id}")


def accounts_for_warehouse(warehouse_id: str) -> list[NoonOrderSourceConfig]:
    config = load_accounts_config()
    login_accounts = _login_account_map(config)
    return [
        _source_with_effective_email(source, login_accounts)
        for source in config.noon_accounts
        if source.warehouse_id == warehouse_id and source.pending_url
    ]
