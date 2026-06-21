"""项目路径管理。所有路径以项目根目录为基准，禁止硬编码绝对路径。"""
from pathlib import Path


def _get_project_root() -> Path:
    """返回 dubai_shipping_tool/ 目录。"""
    return Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT: Path = _get_project_root()
DATA_DIR: Path = PROJECT_ROOT / "data"

# 订单
ORDERS_CURRENT_DIR: Path = DATA_DIR / "orders" / "current"
ORDERS_ARCHIVE_DIR: Path = DATA_DIR / "orders" / "archive"

# 库存
INVENTORY_CURRENT_DIR: Path = DATA_DIR / "inventory" / "current"
INVENTORY_ARCHIVE_DIR: Path = DATA_DIR / "inventory" / "archive"

RUNTIME_DIR: Path = PROJECT_ROOT / "runtime"
NOON_PROFILE_DIR: Path = RUNTIME_DIR / "noon_profile"
ERP_PROFILE_DIR: Path = RUNTIME_DIR / "erp_profile"
PROFILES_DIR: Path = RUNTIME_DIR / "profiles"
SCREENSHOT_DIR: Path = RUNTIME_DIR / "screenshots"
LOG_DIR: Path = PROJECT_ROOT / "logs"
ENV_FILE: Path = PROJECT_ROOT / ".env"

# 固定当前文件名
ORDERS_CURRENT_FILE: Path = ORDERS_CURRENT_DIR / "noon_pending_orders.csv"
INVENTORY_CURRENT_FILE: Path = INVENTORY_CURRENT_DIR / "dubai_inventory.xlsx"
INVENTORY_RAW_FILE: Path = INVENTORY_CURRENT_DIR / "inventory_raw.xlsx"
IN_TRANSIT_CURRENT_FILE: Path = INVENTORY_CURRENT_DIR / "dubai_in_transit.xlsx"
IN_TRANSIT_RAW_FILE: Path = INVENTORY_CURRENT_DIR / "in_transit_raw.xlsx"


def noon_profile_dir(account_id: str) -> Path:
    return PROFILES_DIR / "noon" / account_id


def erp_profile_dir(erp_account_id: str) -> Path:
    return PROFILES_DIR / "erp" / erp_account_id


def account_orders_current_dir(account_id: str) -> Path:
    return DATA_DIR / "accounts" / account_id / "orders" / "current"


def account_orders_archive_dir(account_id: str) -> Path:
    return DATA_DIR / "accounts" / account_id / "orders" / "archive"


def account_orders_current_file(account_id: str) -> Path:
    return account_orders_current_dir(account_id) / "noon_pending_orders.csv"


def warehouse_inventory_current_dir(warehouse_id: str) -> Path:
    return DATA_DIR / "warehouses" / warehouse_id / "inventory" / "current"


def warehouse_inventory_archive_dir(warehouse_id: str) -> Path:
    return DATA_DIR / "warehouses" / warehouse_id / "inventory" / "archive"


def warehouse_inventory_current_file(warehouse_id: str) -> Path:
    return warehouse_inventory_current_dir(warehouse_id) / "inventory.xlsx"


def warehouse_inventory_raw_file(warehouse_id: str) -> Path:
    return warehouse_inventory_current_dir(warehouse_id) / "inventory_raw.xlsx"


def warehouse_in_transit_current_file(warehouse_id: str) -> Path:
    return warehouse_inventory_current_dir(warehouse_id) / "in_transit.xlsx"


def warehouse_in_transit_raw_file(warehouse_id: str) -> Path:
    return warehouse_inventory_current_dir(warehouse_id) / "in_transit_raw.xlsx"


def ensure_directories() -> None:
    """项目启动时自动创建缺失目录。"""
    for d in [
        DATA_DIR,
        ORDERS_CURRENT_DIR,
        ORDERS_ARCHIVE_DIR,
        INVENTORY_CURRENT_DIR,
        INVENTORY_ARCHIVE_DIR,
        RUNTIME_DIR,
        NOON_PROFILE_DIR,
        ERP_PROFILE_DIR,
        PROFILES_DIR,
        SCREENSHOT_DIR,
        LOG_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
