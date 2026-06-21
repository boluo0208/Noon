"""应用配置，从 .env 文件和环境变量读取。"""
from pydantic_settings import BaseSettings
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Dubai Shipping Tool"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    # Noon
    noon_home_url: str = "https://directship.noon.partners/"
    noon_pending_url: str = (
        "https://directship.noon.partners/en/orders/"
        "?project=PRJ408158&activeTab=pending&page=1&pageSize=10&whCode=W00178809AE"
    )
    noon_download_timeout_seconds: int = 300
    noon_headless: bool = False

    # ERP
    erp_base_url: str = "http://www.erpzd.com"
    erp_username: str = ""
    erp_password: str = ""
    erp_stock_page_url: str = "http://www.erpzd.com/#/customer/box/stock/index"
    erp_login_url: str = "http://www.erpzd.com/#/login?redirect=%2Fcustomer%2Fbox%2Fstock%2Findex"
    erp_download_timeout_seconds: int = 120
    erp_headless: bool = False

    order_timezone: str = "Asia/Dubai"

    model_config = {
        "env_file": str(_project_root / ".env"),
        "env_file_encoding": "utf-8",
        "env_ignore_empty": True,
    }


settings = Settings()


def load_settings() -> Settings:
    """Return a fresh Settings instance so runtime .env edits are picked up."""
    return Settings()
