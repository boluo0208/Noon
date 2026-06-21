# Noon 订单下载模块 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零初始化 dubai_shipping_tool 项目，实现 Noon Directship 订单 CSV 自动下载、解析、前端展示的完整链路。

**Architecture:** FastAPI 后端通过后台任务管理器驱动 Playwright（Edge 浏览器），使用持久化上下文保存 Noon 登录状态。前端 Vue 3 + Element Plus 通过轮询任务状态展示实时进度，成功后展示订单数据表格。

**Tech Stack:** Python 3, FastAPI, Playwright (sync API), Pandas, Vue 3, TypeScript, Vite, Element Plus, Pinia, Axios

**Scope:** 本计划只实现订单下载 + 解析 + 前端展示。库存同步 (`inventory_client.py`) 和分配算法 (`allocator.py`) 不在本次范围内。

---

## File Structure Map

```
dubai_shipping_tool/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 应用入口，注册路由
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py        # 从 .env 读取配置 (pydantic-settings)
│   │   │   ├── paths.py         # 项目所有路径常量 (pathlib)
│   │   │   └── task_manager.py  # 后台任务状态管理 (内存 dict)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes_tasks.py  # POST /api/tasks/download-orders, GET /api/tasks/{id}, POST /api/tasks/{id}/continue
│   │   │   └── routes_data.py   # GET /api/data/orders/preview, GET /api/files/orders/latest
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── noon_downloader.py  # Playwright: 打开 Noon → 点击 Export → 等待下载 → 保存 CSV
│   │   │   └── order_parser.py     # Pandas: 读取 CSV → 清洗 → 提取三列 → 返回 JSON
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── task.py           # Pydantic: TaskStatus, TaskInfo, TaskCreateResponse
│   ├── requirements.txt
│   └── run.py                    # uvicorn 启动脚本
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts               # Vue 应用入口
│       ├── App.vue               # 根组件 + 侧边导航
│       ├── env.d.ts              # Vite 环境类型声明
│       ├── api/
│       │   └── index.ts          # Axios 实例 + 任务 API + 数据 API
│       ├── router/
│       │   └── index.ts          # Vue Router: /dashboard, /orders
│       ├── stores/
│       │   └── task.ts           # Pinia: 任务状态、轮询逻辑
│       ├── types/
│       │   └── task.ts           # TS 类型: TaskStatus, TaskInfo, OrderRow
│       └── views/
│           ├── DashboardView.vue # 操作按钮 + 任务进度卡片
│           └── OrdersView.vue    # 订单数据表格
├── data/
│   └── orders/
│       ├── current/
│       │   └── .gitkeep
│       └── archive/
│           └── .gitkeep
├── runtime/
│   ├── screenshots/
│   │   └── .gitkeep
│   └── .gitkeep
├── logs/
│   └── .gitkeep
├── scripts/
│   ├── setup.bat
│   └── start.bat
├── .env.example
├── .env
└── .gitignore
```

**Decomposition rationale:**
- `core/paths.py` — 所有路径集中管理，全项目引用它，零硬编码路径
- `core/config.py` — 从 .env 读取配置，前端/浏览器行为都可以通过环境变量控制
- `core/task_manager.py` — 内存任务状态管理，简单够用，不引入 SQLite（第一版仅订单下载不需要持久化任务）
- `services/noon_downloader.py` — Playwright 操作全部封装在此，暴露单一入口函数，方便测试和替换
- `services/order_parser.py` — CSV 解析独立于下载，输入是文件路径，输出是 DataFrame，可单独测试
- `schemas/task.py` — Pydantic 模型，前后端类型对齐
- 前端 `api/index.ts` — 所有后端 HTTP 调用集中在一个文件，组件不直接 import axios

---

### Task 1: 创建项目目录结构和根配置文件

**Files:**
- Create: `dubai_shipping_tool/.gitignore`
- Create: `dubai_shipping_tool/.env.example`
- Create: `dubai_shipping_tool/.env`
- Create: `dubai_shipping_tool/scripts/setup.bat`
- Create: `dubai_shipping_tool/scripts/start.bat`
- Create: all `.gitkeep` files for empty directories

- [ ] **Step 1: 创建所有目录**

```bash
cd F:/Noon
mkdir -p dubai_shipping_tool/backend/app/core
mkdir -p dubai_shipping_tool/backend/app/api
mkdir -p dubai_shipping_tool/backend/app/services
mkdir -p dubai_shipping_tool/backend/app/schemas
mkdir -p dubai_shipping_tool/frontend/src/api
mkdir -p dubai_shipping_tool/frontend/src/router
mkdir -p dubai_shipping_tool/frontend/src/stores
mkdir -p dubai_shipping_tool/frontend/src/types
mkdir -p dubai_shipping_tool/frontend/src/views
mkdir -p dubai_shipping_tool/data/orders/current
mkdir -p dubai_shipping_tool/data/orders/archive
mkdir -p dubai_shipping_tool/runtime/screenshots
mkdir -p dubai_shipping_tool/logs
mkdir -p dubai_shipping_tool/scripts
```

- [ ] **Step 2: 创建 `.gitignore`**

```gitignore
.env

backend/.venv/
backend/__pycache__/
**/__pycache__/
*.pyc

frontend/node_modules/
frontend/dist/

runtime/
logs/

data/orders/current/
data/orders/archive/

*.csv
*.xlsx
*.json

.vscode/
.idea/
```

- [ ] **Step 3: 创建 `.env.example`**

```env
APP_NAME=Dubai Shipping Tool
APP_HOST=127.0.0.1
APP_PORT=8000

FRONTEND_ORIGIN=http://localhost:5173

NOON_HOME_URL=https://directship.noon.partners/
NOON_PENDING_URL=https://directship.noon.partners/en/orders/?project=PRJ408158&activeTab=pending&page=1&pageSize=10&whCode=W00178809AE
NOON_DOWNLOAD_TIMEOUT_SECONDS=300
NOON_HEADLESS=false

ORDER_TIMEZONE=Asia/Dubai
```

- [ ] **Step 4: 创建 `.env`（同 `.env.example` 内容）**

- [ ] **Step 5: 创建 `scripts/setup.bat`**

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo ============================================
echo   Dubai Shipping Tool - Setup
echo ============================================

echo.
echo [1/4] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)
python --version

echo.
echo [2/4] Setting up backend virtual environment...
cd backend
if not exist ".venv" (
    python -m venv .venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies.
    pause
    exit /b 1
)
python -m playwright install msedge
cd ..

echo.
echo [3/4] Installing frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Node.js dependencies.
    pause
    exit /b 1
)
cd ..

echo.
echo [4/4] Checking .env file...
if not exist ".env" (
    copy .env.example .env
    echo .env file created from .env.example.
) else (
    echo .env file already exists.
)

echo.
echo ============================================
echo   Setup complete!
echo ============================================
pause
```

- [ ] **Step 6: 创建 `scripts/start.bat`**

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo ============================================
echo   Dubai Shipping Tool - Start
echo ============================================

echo.
echo Starting backend...
start "Dubai Shipping Backend" cmd /c "cd /d "%cd%\backend" && .venv\Scripts\activate.bat && python run.py"

echo Starting frontend...
start "Dubai Shipping Frontend" cmd /c "cd /d "%cd%\frontend" && npm run dev"

echo.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo.
echo Waiting for services to start...
timeout /t 5 /nobreak >nul

start http://localhost:5173

echo.
echo Services started. Close this window to keep them running.
pause
```

- [ ] **Step 7: 创建所有 `.gitkeep` 文件**

```bash
cd F:/Noon/dubai_shipping_tool
touch data/orders/current/.gitkeep
touch data/orders/archive/.gitkeep
touch runtime/screenshots/.gitkeep
touch runtime/.gitkeep
touch logs/.gitkeep
```

---

### Task 2: 后端核心模块 — 配置和路径

**Files:**
- Create: `dubai_shipping_tool/backend/requirements.txt`
- Create: `dubai_shipping_tool/backend/app/__init__.py`
- Create: `dubai_shipping_tool/backend/app/core/__init__.py`
- Create: `dubai_shipping_tool/backend/app/core/config.py`
- Create: `dubai_shipping_tool/backend/app/core/paths.py`
- Create: `dubai_shipping_tool/backend/app/core/task_manager.py`

- [ ] **Step 1: 创建 `backend/requirements.txt`**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic-settings==2.7.1
python-dotenv==1.0.1
pandas==2.2.3
openpyxl==3.1.5
playwright==1.49.1
```

- [ ] **Step 2: 创建 `backend/app/core/paths.py`**

```python
"""项目路径管理。所有路径以项目根目录为基准，禁止硬编码绝对路径。"""
from pathlib import Path


def _get_project_root() -> Path:
    """返回 dubai_shipping_tool/ 目录。"""
    return Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT: Path = _get_project_root()
DATA_DIR: Path = PROJECT_ROOT / "data"
ORDERS_CURRENT_DIR: Path = DATA_DIR / "orders" / "current"
ORDERS_ARCHIVE_DIR: Path = DATA_DIR / "orders" / "archive"
RUNTIME_DIR: Path = PROJECT_ROOT / "runtime"
NOON_PROFILE_DIR: Path = RUNTIME_DIR / "noon_profile"
SCREENSHOT_DIR: Path = RUNTIME_DIR / "screenshots"
LOG_DIR: Path = PROJECT_ROOT / "logs"
ENV_FILE: Path = PROJECT_ROOT / ".env"

# 固定当前文件名
ORDERS_CURRENT_FILE: Path = ORDERS_CURRENT_DIR / "noon_pending_orders.csv"


def ensure_directories() -> None:
    """项目启动时自动创建缺失目录。"""
    for d in [
        DATA_DIR,
        ORDERS_CURRENT_DIR,
        ORDERS_ARCHIVE_DIR,
        RUNTIME_DIR,
        NOON_PROFILE_DIR,
        SCREENSHOT_DIR,
        LOG_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: 创建 `backend/app/core/config.py`**

```python
"""应用配置，从 .env 文件和环境变量读取。"""
from pydantic_settings import BaseSettings
from pathlib import Path
import sys

# 注入项目根目录以定位 .env
_project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_project_root))


class Settings(BaseSettings):
    app_name: str = "Dubai Shipping Tool"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    noon_home_url: str = "https://directship.noon.partners/"
    noon_pending_url: str = (
        "https://directship.noon.partners/en/orders/"
        "?project=PRJ408158&activeTab=pending&page=1&pageSize=10&whCode=W00178809AE"
    )
    noon_download_timeout_seconds: int = 300
    noon_headless: bool = False

    order_timezone: str = "Asia/Dubai"

    model_config = {
        "env_file": str(_project_root / ".env"),
        "env_file_encoding": "utf-8",
    }


settings = Settings()
```

- [ ] **Step 4: 创建 `backend/app/core/task_manager.py`**

```python
"""后台任务管理器。第一版使用内存 dict，不依赖 SQLite。"""
from __future__ import annotations

import uuid
import time
import threading
from enum import Enum
from typing import Callable, Optional


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_LOGIN = "WAITING_LOGIN"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TaskInfo:
    def __init__(self, task_type: str) -> None:
        self.task_id: str = uuid.uuid4().hex[:12]
        self.task_type: str = task_type
        self.status: TaskStatus = TaskStatus.PENDING
        self.message: str = ""
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.error_detail: Optional[str] = None
        self._login_event: threading.Event = threading.Event()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_detail": self.error_detail,
        }

    def wait_for_continue(self, timeout: float = 600) -> bool:
        """等待前端调用 /continue，返回 True 表示收到继续信号。"""
        return self._login_event.wait(timeout=timeout)

    def signal_continue(self) -> None:
        """前端调用 /continue 时触发。"""
        self._login_event.set()


class TaskManager:
    """内存任务注册表。"""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskInfo] = {}

    def create_task(self, task_type: str) -> TaskInfo:
        task = TaskInfo(task_type)
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict]:
        return [t.to_dict() for t in self._tasks.values()]


task_manager = TaskManager()
```

- [ ] **Step 5: 验证 Python 语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
python -c "from app.core.paths import PROJECT_ROOT, ensure_directories; ensure_directories(); print('PROJECT_ROOT:', PROJECT_ROOT)"
```

Expected: 输出 `PROJECT_ROOT: F:\Noon\dubai_shipping_tool` 并创建所有缺失目录。

---

### Task 3: Noon 订单下载服务

**Files:**
- Create: `dubai_shipping_tool/backend/app/services/__init__.py`
- Create: `dubai_shipping_tool/backend/app/services/noon_downloader.py`

- [ ] **Step 1: 创建 `backend/app/services/noon_downloader.py`**

```python
"""Noon Directship 订单 CSV 下载模块。

使用 Playwright 同步 API，在线程中运行以避免阻塞 FastAPI 事件循环。
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.core.config import settings
from app.core.paths import (
    NOON_PROFILE_DIR,
    SCREENSHOT_DIR,
    ORDERS_CURRENT_DIR,
    ORDERS_CURRENT_FILE,
    ORDERS_ARCHIVE_DIR,
)
from app.core.task_manager import TaskInfo, TaskStatus


def _screenshot(page: Page, name: str) -> Path:
    """保存当前页面截图并返回路径。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{ts}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def _archive_current_csv() -> None:
    """将旧的 current CSV 移动到 archive 并添加时间戳。"""
    if ORDERS_CURRENT_FILE.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"noon_pending_orders_{ts}.csv"
        ORDERS_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ORDERS_CURRENT_FILE), str(ORDERS_ARCHIVE_DIR / archive_name))


def run_noon_download(task: TaskInfo) -> None:
    """在线程中执行 Noon 订单下载。

    此函数由 TaskManager 在后台线程中调用，task 的状态会被实时更新。
    前端通过 GET /api/tasks/{task_id} 轮询状态。
    """
    task.status = TaskStatus.RUNNING
    task.started_at = time.time()
    task.message = "正在启动浏览器..."

    with sync_playwright() as p:
        # 使用持久化上下文保存登录状态
        context: BrowserContext = p.chromium.launch_persistent_context(
            user_data_dir=str(NOON_PROFILE_DIR),
            channel="msedge",
            headless=settings.noon_headless,
            accept_downloads=True,
        )

        page: Page = context.new_page()

        try:
            # 打开 Pending 页面
            task.message = "正在打开 Noon Pending 页面..."
            page.goto(settings.noon_pending_url, wait_until="domcontentloaded", timeout=60_000)

            # 检查是否需要登录（页面标题或 URL 包含 login）
            page.wait_for_load_state("networkidle", timeout=30_000)
            current_url = page.url.lower()
            if "login" in current_url or "signin" in current_url:
                task.status = TaskStatus.WAITING_LOGIN
                task.message = "请在浏览器中手动登录 Noon，登录完成后点击前端「继续」按钮。"
                # 等待前端 /continue 信号，最长等 10 分钟
                if task.wait_for_continue(timeout=600):
                    # 用户登录后刷新到 Pending 页面
                    task.status = TaskStatus.RUNNING
                    task.message = "登录完成，跳转到 Pending 页面..."
                    page.goto(
                        settings.noon_pending_url,
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )
                    page.wait_for_load_state("networkidle", timeout=30_000)
                else:
                    task.status = TaskStatus.FAILED
                    task.error_detail = "等待登录超时。"
                    context.close()
                    return

            # 定位 Export 按钮并点击下载
            task.message = "正在寻找 Export 按钮..."
            export_button = page.get_by_role("button", name="Export", exact=True)
            if not export_button.is_visible(timeout=10_000):
                # 备用：使用可见按钮文本匹配
                export_button = page.locator("button:visible").filter(has_text="Export").first
                if not export_button.is_visible(timeout=5_000):
                    screenshot_path = _screenshot(page, "no_export_button")
                    task.status = TaskStatus.FAILED
                    task.error_detail = (
                        f"找不到 Export 按钮。页面截图已保存: {screenshot_path}"
                    )
                    context.close()
                    return

            task.message = "正在导出订单数据，等待 Noon 生成文件..."
            with page.expect_download(timeout=settings.noon_download_timeout_seconds * 1000) as download_info:
                export_button.click()

            download = download_info.value
            task.message = "正在保存订单文件..."

            # 归档旧文件
            _archive_current_csv()

            # 保存下载的文件，保留原始后缀
            original_name = download.suggested_filename
            suffix = Path(original_name).suffix or ".csv"
            save_path = ORDERS_CURRENT_DIR / f"noon_pending_orders{suffix}"
            download.save_as(str(save_path))

            # 如果是 xlsx，也更新固定文件名引用
            if suffix.lower() in (".xlsx", ".xls"):
                task.message = f"订单文件已保存: {save_path}（实际格式: XLSX）"
            else:
                # 如果后缀不同，重命名为固定的 csv 名
                if save_path != ORDERS_CURRENT_FILE:
                    shutil.move(str(save_path), str(ORDERS_CURRENT_FILE))
                task.message = "订单文件已保存。"

            task.status = TaskStatus.SUCCESS
            task.finished_at = time.time()

        except PlaywrightTimeout as e:
            screenshot_path = _screenshot(page, "timeout")
            task.status = TaskStatus.FAILED
            task.error_detail = f"操作超时: {e}. 页面截图: {screenshot_path}"
        except Exception as e:
            screenshot_path = _screenshot(page, "error")
            task.status = TaskStatus.FAILED
            task.error_detail = f"下载失败: {e}. 页面截图: {screenshot_path}"
        finally:
            context.close()
```

- [ ] **Step 2: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
python -c "from app.services.noon_downloader import run_noon_download; print('Import OK')"
```

Expected: `Import OK`（可能需要先 `pip install -r requirements.txt`）

---

### Task 4: 订单解析服务

**Files:**
- Create: `dubai_shipping_tool/backend/app/services/order_parser.py`

- [ ] **Step 1: 创建 `backend/app/services/order_parser.py`**

```python
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
```

- [ ] **Step 2: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
python -c "from app.services.order_parser import parse_orders_to_dicts; print('Import OK')"
```

Expected: `Import OK`

---

### Task 5: Pydantic Schemas

**Files:**
- Create: `dubai_shipping_tool/backend/app/schemas/__init__.py`
- Create: `dubai_shipping_tool/backend/app/schemas/task.py`

- [ ] **Step 1: 创建 `backend/app/schemas/task.py`**

```python
"""Pydantic 模型，前后端类型对齐。"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class TaskCreateResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    message: str


class TaskInfoResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    message: str
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error_detail: Optional[str] = None


class OrderRow(BaseModel):
    order_nr: str
    partner_sku: str
    target_shipped_at: Optional[str] = None


class OrdersPreviewResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[OrderRow]
```

---

### Task 6: FastAPI 路由

**Files:**
- Create: `dubai_shipping_tool/backend/app/api/__init__.py`
- Create: `dubai_shipping_tool/backend/app/api/routes_tasks.py`
- Create: `dubai_shipping_tool/backend/app/api/routes_data.py`

- [ ] **Step 1: 创建 `backend/app/api/routes_tasks.py`**

```python
"""任务相关 API 路由。"""
from __future__ import annotations

import threading

from fastapi import APIRouter, HTTPException

from app.core.task_manager import task_manager, TaskStatus
from app.schemas.task import TaskCreateResponse, TaskInfoResponse
from app.services.noon_downloader import run_noon_download

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/download-orders", response_model=TaskCreateResponse)
def start_download_orders() -> TaskCreateResponse:
    """创建后台任务下载 Noon 订单。"""
    task = task_manager.create_task("download-orders")
    # 在后台线程中运行 Playwright
    t = threading.Thread(target=run_noon_download, args=(task,), daemon=True)
    t.start()
    return TaskCreateResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value,
        message=task.message,
    )


@router.get("/{task_id}", response_model=TaskInfoResponse)
def get_task(task_id: str) -> TaskInfoResponse:
    """查询任务状态。前端轮询此接口。"""
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskInfoResponse(**task.to_dict())


@router.post("/{task_id}/continue")
def continue_task(task_id: str) -> dict:
    """用户完成手动登录后继续执行任务。"""
    task = task_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != TaskStatus.WAITING_LOGIN:
        raise HTTPException(status_code=400, detail="任务不在等待登录状态")
    task.signal_continue()
    return {"status": "ok", "message": "任务继续执行"}
```

- [ ] **Step 2: 创建 `backend/app/api/routes_data.py`**

```python
"""数据预览与文件下载路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.paths import ORDERS_CURRENT_FILE
from app.services.order_parser import parse_orders_to_dicts
from app.schemas.task import OrdersPreviewResponse, OrderRow

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/data/orders/preview")
def preview_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: str = Query(""),
) -> dict:
    """分页返回订单数据。"""
    if not ORDERS_CURRENT_FILE.exists():
        return {"total": 0, "page": page, "page_size": page_size, "data": []}

    try:
        all_rows = parse_orders_to_dicts(ORDERS_CURRENT_FILE)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 关键词过滤
    if keyword:
        kw = keyword.lower()
        all_rows = [
            r
            for r in all_rows
            if kw in str(r.get("order_nr", "")).lower()
            or kw in str(r.get("partner_sku", "")).lower()
        ]

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
def download_latest_orders() -> FileResponse:
    """下载最新订单文件。"""
    if not ORDERS_CURRENT_FILE.exists():
        raise HTTPException(status_code=404, detail="暂无订单文件")
    return FileResponse(
        path=str(ORDERS_CURRENT_FILE),
        filename=ORDERS_CURRENT_FILE.name,
        media_type="text/csv",
    )
```

---

### Task 7: FastAPI 应用入口

**Files:**
- Create: `dubai_shipping_tool/backend/app/main.py`
- Create: `dubai_shipping_tool/backend/run.py`

- [ ] **Step 1: 创建 `backend/app/main.py`**

```python
"""FastAPI 应用入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.paths import ensure_directories
from app.api.routes_tasks import router as tasks_router
from app.api.routes_data import router as data_router

# 启动时自动创建目录
ensure_directories()

app = FastAPI(title=settings.app_name, version="1.0.0")

# CORS: 允许前端开发服务器
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(data_router)


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok", "app": settings.app_name}
```

- [ ] **Step 2: 创建 `backend/run.py`**

```python
"""项目启动脚本。"""
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
```

- [ ] **Step 3: 启动后端验证**

```bash
cd F:/Noon/dubai_shipping_tool/backend
# 先安装依赖
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install msedge
# 启动
.venv\Scripts\python run.py
```

Expected: 后端在 `http://127.0.0.1:8000` 启动，访问 `/api/health` 返回 `{"status":"ok","app":"Dubai Shipping Tool"}`。

---

### Task 8: 前端脚手架

**Files:**
- Create: `dubai_shipping_tool/frontend/package.json`
- Create: `dubai_shipping_tool/frontend/index.html`
- Create: `dubai_shipping_tool/frontend/vite.config.ts`
- Create: `dubai_shipping_tool/frontend/tsconfig.json`
- Create: `dubai_shipping_tool/frontend/tsconfig.node.json`
- Create: `dubai_shipping_tool/frontend/src/env.d.ts`
- Create: `dubai_shipping_tool/frontend/src/main.ts`
- Create: `dubai_shipping_tool/frontend/src/App.vue`
- Create: `dubai_shipping_tool/frontend/src/router/index.ts`
- Create: `dubai_shipping_tool/frontend/src/types/task.ts`
- Create: `dubai_shipping_tool/frontend/src/api/index.ts`
- Create: `dubai_shipping_tool/frontend/src/stores/task.ts`

- [ ] **Step 1: 创建 `frontend/package.json`**

```json
{
  "name": "dubai-shipping-tool",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
    "pinia": "^2.3.0",
    "axios": "^1.7.9",
    "element-plus": "^2.9.1"
  },
  "devDependencies": {
    "typescript": "^5.7.2",
    "vite": "^6.0.5",
    "@vitejs/plugin-vue": "^5.2.1",
    "vue-tsc": "^2.2.0"
  }
}
```

- [ ] **Step 2: 创建 `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: 创建 `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dubai Shipping Tool</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 4: 创建 `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "noEmit": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 5: 创建 `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 6: 创建 `frontend/src/env.d.ts`**

```typescript
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
```

- [ ] **Step 7: 创建 `frontend/src/types/task.ts`**

```typescript
export type TaskStatus = 'PENDING' | 'RUNNING' | 'WAITING_LOGIN' | 'SUCCESS' | 'FAILED'

export interface TaskInfo {
  task_id: string
  task_type: string
  status: TaskStatus
  message: string
  started_at: number | null
  finished_at: number | null
  error_detail: string | null
}

export interface OrderRow {
  order_nr: string
  partner_sku: string
  target_shipped_at: string | null
}

export interface OrdersPreview {
  total: number
  page: number
  page_size: number
  data: OrderRow[]
}
```

- [ ] **Step 8: 创建 `frontend/src/api/index.ts`**

```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ====== 任务 API ======

export function startDownloadOrders() {
  return api.post<{ task_id: string; task_type: string; status: string; message: string }>('/tasks/download-orders')
}

export function getTask(taskId: string) {
  return api.get<{
    task_id: string
    task_type: string
    status: string
    message: string
    started_at: number | null
    finished_at: number | null
    error_detail: string | null
  }>(`/tasks/${taskId}`)
}

export function continueTask(taskId: string) {
  return api.post<{ status: string; message: string }>(`/tasks/${taskId}/continue`)
}

// ====== 数据 API ======

export function getOrdersPreview(params: { page?: number; page_size?: number; keyword?: string } = {}) {
  return api.get<{ total: number; page: number; page_size: number; data: any[] }>('/data/orders/preview', { params })
}

export function getOrdersFileUrl() {
  return '/api/files/orders/latest'
}
```

- [ ] **Step 9: 创建 `frontend/src/stores/task.ts`**

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TaskInfo, TaskStatus } from '@/types/task'
import { startDownloadOrders, getTask, continueTask } from '@/api/index'

export const useTaskStore = defineStore('task', () => {
  const currentTask = ref<TaskInfo | null>(null)
  const isPolling = ref(false)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  function startPolling(taskId: string) {
    isPolling.value = true
    pollTimer = setInterval(async () => {
      try {
        const { data } = await getTask(taskId)
        currentTask.value = data
        if (['SUCCESS', 'FAILED'].includes(data.status)) {
          stopPolling()
        }
      } catch {
        stopPolling()
      }
    }, 2000)
  }

  function stopPolling() {
    isPolling.value = false
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function triggerDownload() {
    const { data } = await startDownloadOrders()
    currentTask.value = {
      task_id: data.task_id,
      task_type: data.task_type,
      status: data.status as TaskStatus,
      message: data.message,
      started_at: null,
      finished_at: null,
      error_detail: null,
    }
    startPolling(data.task_id)
  }

  async function triggerContinue() {
    if (!currentTask.value) return
    await continueTask(currentTask.value.task_id)
  }

  return {
    currentTask,
    isPolling,
    triggerDownload,
    triggerContinue,
    startPolling,
    stopPolling,
  }
})
```

- [ ] **Step 10: 创建 `frontend/src/router/index.ts`**

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('@/views/OrdersView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
```

- [ ] **Step 11: 创建 `frontend/src/main.ts`**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
```

- [ ] **Step 12: 创建 `frontend/src/App.vue`**

```vue
<template>
  <el-container style="min-height: 100vh">
    <el-aside width="200px" style="background: #304156">
      <div style="padding: 16px; color: #fff; font-size: 16px; font-weight: bold; text-align: center">
        迪拜仓发货工具
      </div>
      <el-menu
        :default-active="route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/dashboard">
          <span>控制台</span>
        </el-menu-item>
        <el-menu-item index="/orders">
          <span>订单数据</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
```

- [ ] **Step 13: 安装前端依赖并验证**

```bash
cd F:/Noon/dubai_shipping_tool/frontend
npm install
npm run dev
```

Expected: 前端在 `http://localhost:5173` 启动，显示侧边导航的空白页面。

---

### Task 9: 前端视图 — Dashboard

**Files:**
- Create: `dubai_shipping_tool/frontend/src/views/DashboardView.vue`

- [ ] **Step 1: 创建 `frontend/src/views/DashboardView.vue`**

```vue
<template>
  <div>
    <h2 style="margin-bottom: 20px">控制台</h2>

    <!-- 操作按钮 -->
    <el-card style="margin-bottom: 20px">
      <template #header>
        <span>操作</span>
      </template>
      <el-button
        type="primary"
        size="large"
        :loading="taskStore.isPolling && taskStore.currentTask?.status === 'RUNNING'"
        :disabled="taskStore.isPolling && taskStore.currentTask?.status === 'RUNNING'"
        @click="taskStore.triggerDownload()"
      >
        下载 Noon 订单
      </el-button>
      <el-button
        v-if="taskStore.currentTask?.status === 'WAITING_LOGIN'"
        type="success"
        size="large"
        @click="taskStore.triggerContinue()"
      >
        已完成登录，继续执行
      </el-button>
    </el-card>

    <!-- 任务状态 -->
    <el-card v-if="taskStore.currentTask" style="margin-bottom: 20px">
      <template #header>
        <span>任务状态</span>
      </template>

      <el-steps :active="stepIndex" finish-status="success" process-status="process" align-center>
        <el-step title="准备" />
        <el-step title="打开Noon" />
        <el-step title="导出订单" />
        <el-step title="完成" />
      </el-steps>

      <div style="margin-top: 16px">
        <el-tag
          :type="statusTagType"
          size="large"
        >
          {{ taskStore.currentTask.status }}
        </el-tag>
        <span style="margin-left: 12px; color: #606266">{{ taskStore.currentTask.message }}</span>
      </div>

      <div
        v-if="taskStore.currentTask.status === 'WAITING_LOGIN'"
        style="margin-top: 16px"
      >
        <el-alert
          title="需要手动登录"
          type="warning"
          description="浏览器窗口已打开 Noon 登录页面。请在浏览器中手动输入账号密码登录，登录完成后回到此页面点击「已完成登录，继续执行」按钮。"
          show-icon
          :closable="false"
        />
      </div>

      <div
        v-if="taskStore.currentTask.status === 'FAILED'"
        style="margin-top: 16px"
      >
        <el-alert
          title="任务失败"
          type="error"
          :description="taskStore.currentTask.error_detail || '未知错误'"
          show-icon
          :closable="false"
        />
      </div>

      <div
        v-if="taskStore.currentTask.status === 'SUCCESS'"
        style="margin-top: 16px"
      >
        <el-alert
          title="订单下载完成"
          type="success"
          description="订单文件已保存，请前往「订单数据」页面查看。"
          show-icon
          :closable="false"
        />
      </div>
    </el-card>

    <!-- 文件状态 -->
    <el-card>
      <template #header>
        <span>文件状态</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="订单文件">
          {{ orderFileExists ? '已存在' : '暂无' }}
          <el-button
            v-if="orderFileExists"
            size="small"
            type="primary"
            link
            @click="downloadOrderFile"
          >
            下载
          </el-button>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useTaskStore } from '@/stores/task'
import { getOrdersFileUrl } from '@/api/index'

const taskStore = useTaskStore()
const orderFileExists = ref(false)

onMounted(async () => {
  try {
    const { default: api } = await import('@/api/index')
    const res = await api.getOrdersPreview({ page: 1, page_size: 1 })
    orderFileExists.value = res.data.total > 0
  } catch {
    orderFileExists.value = false
  }
})

const stepIndex = computed(() => {
  const status = taskStore.currentTask?.status
  const map: Record<string, number> = {
    PENDING: 0,
    RUNNING: 1,
    WAITING_LOGIN: 1,
    SUCCESS: 4,
    FAILED: -1,
  }
  return map[status || 'PENDING'] ?? 0
})

const statusTagType = computed(() => {
  const map: Record<string, string> = {
    PENDING: 'info',
    RUNNING: 'warning',
    WAITING_LOGIN: 'warning',
    SUCCESS: 'success',
    FAILED: 'danger',
  }
  return map[taskStore.currentTask?.status || 'PENDING'] || 'info'
})

function downloadOrderFile() {
  window.open(getOrdersFileUrl(), '_blank')
}
</script>
```

---

### Task 10: 前端视图 — 订单数据页

**Files:**
- Create: `dubai_shipping_tool/frontend/src/views/OrdersView.vue`

- [ ] **Step 1: 创建 `frontend/src/views/OrdersView.vue`**

```vue
<template>
  <div>
    <h2 style="margin-bottom: 20px">订单数据</h2>

    <!-- 搜索栏 -->
    <el-card style="margin-bottom: 20px">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索订单号或 SKU"
            clearable
            @keyup.enter="searchOrders"
          />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="searchOrders">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 数据表格 -->
    <el-card>
      <template #header>
        <span>订单列表（共 {{ total }} 条）</span>
      </template>

      <el-table
        :data="orders"
        border
        stripe
        v-loading="loading"
        empty-text="暂无订单数据，请先下载订单"
        style="width: 100%"
      >
        <el-table-column prop="order_nr" label="订单号 (order_nr)" min-width="180" />
        <el-table-column prop="partner_sku" label="SKU (partner_sku)" min-width="150" />
        <el-table-column prop="target_shipped_at" label="最晚发货时间" min-width="200">
          <template #default="{ row }">
            {{ row.target_shipped_at || '-' }}
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadOrders"
          @current-change="loadOrders"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getOrdersPreview } from '@/api/index'
import type { OrderRow } from '@/types/task'

const orders = ref<OrderRow[]>([])
const total = ref(0)
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(50)
const searchKeyword = ref('')

async function loadOrders() {
  loading.value = true
  try {
    const { data } = await getOrdersPreview({
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: searchKeyword.value,
    })
    orders.value = data.data
    total.value = data.total
  } catch {
    orders.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function searchOrders() {
  currentPage.value = 1
  loadOrders()
}

function resetSearch() {
  searchKeyword.value = ''
  currentPage.value = 1
  loadOrders()
}

onMounted(() => {
  loadOrders()
})
</script>
```

---

### Task 11: 端到端验证

- [ ] **Step 1: 启动后端**

```bash
cd F:/Noon/dubai_shipping_tool
scripts\start.bat
```

- [ ] **Step 2: 验证检查清单**

在浏览器 `http://localhost:5173` 中验证：

1. 页面正常加载，左侧显示导航栏，右侧显示"控制台"。
2. 点击"下载 Noon 订单"按钮。
3. Edge 浏览器窗口弹出，打开 Noon Pending 页面。
4. 若未登录，前端显示"需要手动登录"提示和"已完成登录，继续执行"按钮。
5. 在浏览器中手动登录后，点击"已完成登录，继续执行"。
6. 程序自动点击 Export 按钮，等待导出完成。
7. 任务状态变为 SUCCESS。
8. 切换到"订单数据"页面，表格展示订单数据。
9. 搜索和分页功能正常工作。

- [ ] **Step 3: 修复验证中发现的问题**

---

## 验证策略

- **后端单元测试**（后续任务）：`order_parser.py` 的 CSV 解析逻辑（多种编码、缺少列、空值处理）
- **后端集成测试**（后续任务）：API 端点 `/api/health`、`/api/tasks/*`、`/api/data/orders/preview`
- **前端 E2E**：手动按上述检查清单逐项验证

## 已知未覆盖项（后续迭代）

- `inventory_client.py` — ERP 库存接口调用
- `allocator.py` — 库存分配算法
- `result_exporter.py` — 结果 Excel 导出
- `routes_config.py` — 设置页面 API
- `SettingsView.vue` — 设置页面
- `InventoryView.vue` — 库存数据页面
- `ResultsView.vue` — 分配结果页面
- SQLite 持久化任务记录
- `clean_runtime.bat` 清理脚本
- Playwright 无头模式调优
