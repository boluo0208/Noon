# ERP 库存同步模块 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 ERP 库存自动同步——Playwright 自动登录/下载 XLSX → Pandas 过滤汇总 → 前端展示库存数据。

**Architecture:** 沿用 Noon 订单下载模块的模式：`inventory_client.py`（Playwright 下载）与 `inventory_parser.py`（Pandas 清洗）分离，通过 `routes_tasks.py` 的后台任务线程连接，前端轮询任务状态。

**Tech Stack:** Python 3, Playwright (sync API), Pandas, openpyxl, FastAPI, Vue 3, Element Plus

**Scope:** 库存同步 + 解析 + 前端展示。分配算法（allocator.py）和结果导出不在本次范围内。

---

## File Structure Map

```
backend/app/
├── core/
│   ├── paths.py              ← 修改：新增 INVENTORY_CURRENT_DIR 等
│   └── config.py             ← 修改：新增 ERP 配置项
├── services/
│   ├── inventory_client.py   ← 新建：Playwright 下载库存 XLSX
│   └── inventory_parser.py   ← 新建：Pandas 过滤汇总
├── api/
│   ├── routes_tasks.py       ← 修改：新增 sync-inventory 端点
│   └── routes_data.py        ← 修改：新增库存预览 + 文件下载
└── schemas/
    └── task.py               ← 修改：新增 InventoryRow

frontend/src/
├── api/index.ts              ← 修改：新增库存 API
├── stores/task.ts            ← 修改：新增 triggerSyncInventory
├── router/index.ts           ← 修改：新增 /inventory 路由
├── App.vue                   ← 修改：侧栏新增菜单项
└── views/
    ├── DashboardView.vue     ← 修改：新增「同步库存」按钮
    └── InventoryView.vue     ← 新建：库存数据表格

.env / .env.example           ← 修改：新增 ERP_* 配置项
```

---

### Task 1: 更新路径配置和 ERP 配置

**Files:**
- Modify: `dubai_shipping_tool/backend/app/core/paths.py`
- Modify: `dubai_shipping_tool/backend/app/core/config.py`
- Modify: `dubai_shipping_tool/.env`
- Modify: `dubai_shipping_tool/.env.example`

- [ ] **Step 1: 更新 paths.py，新增库存路径和 ERP profile 目录**

Replace the entire file with:

```python
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
SCREENSHOT_DIR: Path = RUNTIME_DIR / "screenshots"
LOG_DIR: Path = PROJECT_ROOT / "logs"
ENV_FILE: Path = PROJECT_ROOT / ".env"

# 固定当前文件名
ORDERS_CURRENT_FILE: Path = ORDERS_CURRENT_DIR / "noon_pending_orders.csv"
INVENTORY_CURRENT_FILE: Path = INVENTORY_CURRENT_DIR / "dubai_inventory.xlsx"
INVENTORY_RAW_FILE: Path = INVENTORY_CURRENT_DIR / "inventory_raw.xlsx"


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
        SCREENSHOT_DIR,
        LOG_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: 更新 config.py，新增 ERP 配置项**

Replace the entire file with:

```python
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
    }


settings = Settings()
```

- [ ] **Step 3: 更新 .env 和 .env.example，新增 ERP 配置**

Read `.env` first, then append ERP settings:

```env
# ERP
ERP_BASE_URL=http://www.erpzd.com
ERP_USERNAME=
ERP_PASSWORD=
ERP_STOCK_PAGE_URL=http://www.erpzd.com/#/customer/box/stock/index
ERP_LOGIN_URL=http://www.erpzd.com/#/login?redirect=%2Fcustomer%2Fbox%2Fstock%2Findex
ERP_DOWNLOAD_TIMEOUT_SECONDS=120
ERP_HEADLESS=false
```

- [ ] **Step 4: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
.venv/Scripts/python -c "from app.core.paths import INVENTORY_CURRENT_DIR, ERP_PROFILE_DIR; print('INVENTORY_CURRENT_DIR:', INVENTORY_CURRENT_DIR); print('ERP_PROFILE_DIR:', ERP_PROFILE_DIR)"
```

Expected: 输出两个路径，均在 `F:\Noon\dubai_shipping_tool\` 下。

```bash
.venv/Scripts/python -c "from app.core.config import settings; print('ERP_BASE_URL:', settings.erp_base_url); print('ERP_USERNAME:', repr(settings.erp_username))"
```

Expected: `ERP_BASE_URL: http://www.erpzd.com`, `ERP_USERNAME: ''`

---

### Task 2: 库存解析服务 — inventory_parser.py

**Files:**
- Create: `dubai_shipping_tool/backend/app/services/inventory_parser.py`

- [ ] **Step 1: 创建 inventory_parser.py**

```python
"""库存 XLSX 解析模块。

读取 ERP 导出的原始 XLSX，过滤箱号含中文的行，只保留迪拜仓，
提取 SKU + 当前库存两列，按 SKU 汇总。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def parse_inventory(file_path: Path) -> pd.DataFrame:
    """读取 ERP 导出的库存 XLSX，清洗后返回 SKU + 当前库存 汇总表。

    Args:
        file_path: 原始 XLSX 文件路径。

    Returns:
        DataFrame，包含 SKU 和 当前库存 两列，按 SKU 汇总。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 缺少必需列或无法解析。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"库存文件不存在: {file_path}")

    df = pd.read_excel(file_path, dtype=str)

    # 去除列名前后的空格
    df.columns = df.columns.str.strip()

    # 记录原始行数
    original_rows = len(df)

    # 1. 移除箱号含中文的行
    if '箱号' in df.columns:
        # 匹配任何中文字符（Unicode CJK 范围）
        pattern = r'[一-鿿㐀-䶿]'
        df = df[~df['箱号'].fillna('').str.contains(pattern, regex=True)]
        removed_chinese = original_rows - len(df)
    else:
        removed_chinese = 0

    before_warehouse = len(df)

    # 2. 只保留迪拜仓
    if '仓库名称' in df.columns:
        df = df[df['仓库名称'] == '迪拜仓']
        removed_warehouse = before_warehouse - len(df)
    else:
        removed_warehouse = 0

    # 3. 检查必需列
    required = ['SKU', '当前库存']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"库存文件缺少必要列: {missing}。实际列名: {list(df.columns)}"
        )

    # 4. 提取两列
    df = df[['SKU', '当前库存']].copy()

    # 5. 清洗 SKU（去空格，移除空值）
    df['SKU'] = df['SKU'].astype(str).str.strip()
    df = df[df['SKU'] != '']
    df = df[df['SKU'] != 'nan']

    # 6. 当前库存转数值，非数字 → 0
    df['当前库存'] = pd.to_numeric(df['当前库存'], errors='coerce').fillna(0).astype(int)

    # 7. 按 SKU 汇总
    result = df.groupby('SKU', as_index=False)['当前库存'].sum()

    return result


def parse_inventory_to_dicts(file_path: Path) -> list[dict]:
    """解析库存文件并返回 dict 列表，供 API 直接返回 JSON。"""
    df = parse_inventory(file_path)
    return df.to_dict(orient="records")
```

- [ ] **Step 2: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
.venv/Scripts/python -c "from app.services.inventory_parser import parse_inventory, parse_inventory_to_dicts; print('Import OK')"
```

Expected: `Import OK`

---

### Task 3: 库存下载服务 — inventory_client.py

**Files:**
- Create: `dubai_shipping_tool/backend/app/services/inventory_client.py`

- [ ] **Step 1: 创建 inventory_client.py**

```python
"""ERP 库存 XLSX 下载模块。

使用 Playwright 同步 API，在线程中运行以避免阻塞 FastAPI 事件循环。
自动填账号密码登录（持久化上下文），点击「查看所有库存」→ 弹窗 → 点击「下载」。
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.core.config import settings
from app.core.paths import (
    ERP_PROFILE_DIR,
    SCREENSHOT_DIR,
    INVENTORY_CURRENT_DIR,
    INVENTORY_RAW_FILE,
    INVENTORY_ARCHIVE_DIR,
)
from app.core.task_manager import TaskInfo, TaskStatus


def _screenshot(page: Page, name: str) -> Path:
    """保存当前页面截图并返回路径。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{ts}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def _archive_current_raw() -> None:
    """将旧的 raw XLSX 移动到 archive 并添加时间戳。"""
    if INVENTORY_RAW_FILE.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"inventory_raw_{ts}.xlsx"
        INVENTORY_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(INVENTORY_RAW_FILE), str(INVENTORY_ARCHIVE_DIR / archive_name))


def _do_erp_login(page: Page, task: TaskInfo) -> bool:
    """在 ERP 登录页自动填账号密码并登录。返回 True 表示登录成功。"""
    task.message = "正在 ERP 登录页填写账号密码..."

    # 等待登录表单加载
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeout:
        pass

    # 尝试定位用户名输入框
    username_input = page.locator("input[type='text']").first
    password_input = page.locator("input[type='password']").first

    if not username_input.is_visible(timeout=5_000):
        # 备用：尝试通过 placeholder 定位
        username_input = page.locator("input[placeholder*='用户'], input[placeholder*='账号'], input[placeholder*='手机']").first
        if not username_input.is_visible(timeout=3_000):
            # 再次备用：通过 label 文本定位
            username_input = page.locator("input").filter(has_text="").first

    try:
        username_input.wait_for(state="visible", timeout=5_000)
    except PlaywrightTimeout:
        pass

    if not settings.erp_username or not settings.erp_password:
        task.status = TaskStatus.FAILED
        task.error_detail = "ERP 账号密码未配置，请在 .env 中设置 ERP_USERNAME 和 ERP_PASSWORD。"
        return False

    username_input.fill(settings.erp_username)
    password_input.fill(settings.erp_password)

    task.message = "正在点击登录按钮..."

    # 查找登录按钮
    login_button = page.locator("button").filter(has_text="登录").first
    if not login_button.is_visible(timeout=3_000):
        login_button = page.locator("button").filter(has_text="登 录").first
    if not login_button.is_visible(timeout=2_000):
        login_button = page.locator("button[type='submit']").first

    login_button.click()

    # 等待登录完成（URL 不再包含 login）
    try:
        page.wait_for_url("**/customer/box/**", timeout=15_000)
        task.message = "ERP 登录成功。"
        return True
    except PlaywrightTimeout:
        _screenshot(page, "erp_login_failed")
        task.status = TaskStatus.FAILED
        task.error_detail = "ERP 登录失败，请检查账号密码是否正确。"
        return False


def run_inventory_sync(task: TaskInfo) -> None:
    """在线程中执行 ERP 库存同步。

    此函数由 TaskManager 在后台线程中调用，task 的状态会被实时更新。
    前端通过 GET /api/tasks/{task_id} 轮询状态。
    """
    task.status = TaskStatus.RUNNING
    task.started_at = time.time()
    task.message = "正在启动浏览器..."

    with sync_playwright() as p:
        context: BrowserContext = p.chromium.launch_persistent_context(
            user_data_dir=str(ERP_PROFILE_DIR),
            channel="msedge",
            headless=settings.erp_headless,
            accept_downloads=True,
        )

        page: Page = context.new_page()

        try:
            # 1. 打开库存管理页面
            task.message = "正在打开 ERP 库存管理页面..."
            page.goto(settings.erp_stock_page_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_load_state("networkidle", timeout=15_000)

            # 2. 检查是否需要登录
            current_url = page.url.lower()
            if "login" in current_url:
                task.message = "检测到需要登录 ERP..."
                if not _do_erp_login(page, task):
                    context.close()
                    return
                # 登录后重新导航到库存页面
                task.message = "登录完成，跳转到库存管理页面..."
                page.goto(settings.erp_stock_page_url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_load_state("networkidle", timeout=15_000)

            # 3. 点击「查看所有库存」按钮
            task.message = "正在查找「查看所有库存」按钮..."

            view_all_btn = page.get_by_role("button", name="查看所有库存")
            if not view_all_btn.is_visible(timeout=5_000):
                view_all_btn = page.locator("button").filter(has_text="查看所有库存").first
            if not view_all_btn.is_visible(timeout=3_000):
                view_all_btn = page.locator("button").filter(has_text="所有库存").first

            if not view_all_btn.is_visible(timeout=3_000):
                _screenshot(page, "no_view_all_button")
                task.status = TaskStatus.FAILED
                task.error_detail = "找不到「查看所有库存」按钮。"
                context.close()
                return

            view_all_btn.click()
            task.message = "已点击「查看所有库存」，等待弹窗出现..."

            # 4. 等待弹窗/对话框出现
            page.wait_for_timeout(2000)  # 给弹窗动画时间

            # 5. 在弹窗中点击「下载」按钮
            task.message = "正在查找「下载」按钮..."

            download_btn = page.get_by_role("button", name="下载")
            if not download_btn.is_visible(timeout=5_000):
                download_btn = page.locator("button").filter(has_text="下载").first
            if not download_btn.is_visible(timeout=3_000):
                download_btn = page.locator("button").filter(has_text="导出").first

            if not download_btn.is_visible(timeout=3_000):
                _screenshot(page, "no_download_button")
                task.status = TaskStatus.FAILED
                task.error_detail = "找不到「下载」按钮。"
                context.close()
                return

            # 6. 监听下载并点击
            task.message = "正在下载库存文件..."
            with page.expect_download(timeout=settings.erp_download_timeout_seconds * 1000) as download_info:
                download_btn.click()

            download = download_info.value
            task.message = "正在保存库存文件..."

            # 归档旧文件
            _archive_current_raw()

            # 保存下载的文件
            original_name = download.suggested_filename
            suffix = Path(original_name).suffix or ".xlsx"
            save_path = INVENTORY_CURRENT_DIR / f"inventory_raw{suffix}"
            download.save_as(str(save_path))

            # 如果后缀不是 xlsx，重命名为固定的 xlsx 名
            if save_path != INVENTORY_RAW_FILE:
                shutil.move(str(save_path), str(INVENTORY_RAW_FILE))

            task.message = "库存文件已下载。"
            task.status = TaskStatus.SUCCESS
            task.finished_at = time.time()

        except PlaywrightTimeout as e:
            _screenshot(page, "erp_timeout")
            task.status = TaskStatus.FAILED
            task.error_detail = f"操作超时: {e}"
        except Exception as e:
            _screenshot(page, "erp_error")
            task.status = TaskStatus.FAILED
            task.error_detail = f"库存同步失败: {e}"
        finally:
            context.close()
```

- [ ] **Step 2: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
.venv/Scripts/python -c "from app.services.inventory_client import run_inventory_sync; print('Import OK')"
```

Expected: `Import OK`

---

### Task 4: 新增 InventoryRow Schema

**Files:**
- Modify: `dubai_shipping_tool/backend/app/schemas/task.py`

- [ ] **Step 1: 在 task.py 末尾追加 InventoryRow**

Add after the existing `OrderRow` class:

```python
class InventoryRow(BaseModel):
    SKU: str
    当前库存: int
```

- [ ] **Step 2: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
.venv/Scripts/python -c "from app.schemas.task import InventoryRow; print('Import OK')"
```

Expected: `Import OK`

---

### Task 5: 新增 sync-inventory 任务路由

**Files:**
- Modify: `dubai_shipping_tool/backend/app/api/routes_tasks.py`

- [ ] **Step 1: 在 routes_tasks.py 新增 sync-inventory 端点**

Add import for `run_inventory_sync` at the top, and add the new endpoint before `get_task`:

```python
from app.services.inventory_client import run_inventory_sync
```

Add new endpoint after `start_download_orders`:

```python
@router.post("/sync-inventory", response_model=TaskCreateResponse)
def start_sync_inventory() -> TaskCreateResponse:
    """创建后台任务同步 ERP 库存。"""
    task = task_manager.create_task("sync-inventory")
    t = threading.Thread(target=run_inventory_sync, args=(task,), daemon=True)
    t.start()
    return TaskCreateResponse(
        task_id=task.task_id,
        task_type=task.task_type,
        status=task.status.value,
        message=task.message,
    )
```

- [ ] **Step 2: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
.venv/Scripts/python -c "from app.api.routes_tasks import router; print('Routes OK')"
```

Expected: `Routes OK`

---

### Task 6: 新增库存数据预览和文件下载路由

**Files:**
- Modify: `dubai_shipping_tool/backend/app/api/routes_data.py`

- [ ] **Step 1: 在 routes_data.py 新增库存相关端点**

Add imports and two new endpoints:

```python
from app.core.paths import ORDERS_CURRENT_FILE, INVENTORY_CURRENT_FILE
from app.services.inventory_parser import parse_inventory_to_dicts
from app.schemas.task import OrderRow, InventoryRow
```

Add after `download_latest_orders`:

```python
@router.get("/data/inventory/preview")
def preview_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    keyword: str = Query(""),
) -> dict:
    """分页返回库存数据。"""
    if not INVENTORY_CURRENT_FILE.exists():
        return {"total": 0, "page": page, "page_size": page_size, "data": []}

    try:
        all_rows = parse_inventory_to_dicts(INVENTORY_CURRENT_FILE)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 关键词过滤（按 SKU）
    if keyword:
        kw = keyword.lower()
        all_rows = [
            r for r in all_rows
            if kw in str(r.get("SKU", "")).lower()
        ]

    total = len(all_rows)
    start = (page - 1) * page_size
    end = start + page_size
    data = [InventoryRow(**r) for r in all_rows[start:end]]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [d.model_dump() for d in data],
    }


@router.get("/files/inventory/latest")
def download_latest_inventory() -> FileResponse:
    """下载最新库存文件。"""
    if not INVENTORY_CURRENT_FILE.exists():
        raise HTTPException(status_code=404, detail="暂无库存文件")
    return FileResponse(
        path=str(INVENTORY_CURRENT_FILE),
        filename=INVENTORY_CURRENT_FILE.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

- [ ] **Step 2: 验证语法**

```bash
cd F:/Noon/dubai_shipping_tool/backend
.venv/Scripts/python -c "from app.api.routes_data import router; print('Routes OK')"
```

Expected: `Routes OK`

---

### Task 7: 前端 API 层 — 新增库存 API

**Files:**
- Modify: `dubai_shipping_tool/frontend/src/api/index.ts`

- [ ] **Step 1: 新增库存相关 API 函数**

Add after the existing orders API functions:

```typescript
// ====== 库存 API ======

export function startSyncInventory() {
  return api.post<{ task_id: string; task_type: string; status: string; message: string }>('/tasks/sync-inventory')
}

export function getInventoryPreview(params: { page?: number; page_size?: number; keyword?: string } = {}) {
  return api.get<{ total: number; page: number; page_size: number; data: { SKU: string; 当前库存: number }[] }>('/data/inventory/preview', { params })
}

export function getInventoryFileUrl() {
  return '/api/files/inventory/latest'
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd F:/Noon/dubai_shipping_tool/frontend
npx vue-tsc --noEmit src/api/index.ts
```

---

### Task 8: 前端 Store — 新增同步库存操作

**Files:**
- Modify: `dubai_shipping_tool/frontend/src/stores/task.ts`

- [ ] **Step 1: 新增 triggerSyncInventory 函数**

Add import for `startSyncInventory` at the top, and add the new function:

```typescript
import { startDownloadOrders, startSyncInventory, getTask, continueTask } from '@/api/index'
```

Add `triggerSyncInventory` function after `triggerDownload`:

```typescript
  async function triggerSyncInventory() {
    const { data } = await startSyncInventory()
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
```

Add `triggerSyncInventory` to the return object:

```typescript
  return {
    currentTask,
    isPolling,
    triggerDownload,
    triggerSyncInventory,
    triggerContinue,
    startPolling,
    stopPolling,
  }
```

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd F:/Noon/dubai_shipping_tool/frontend
npx vue-tsc --noEmit
```

---

### Task 9: DashboardView — 新增「同步库存」按钮和库存状态

**Files:**
- Modify: `dubai_shipping_tool/frontend/src/views/DashboardView.vue`

- [ ] **Step 1: 新增「同步库存」按钮**

Add after the 「下载 Noon 订单」button in the operations card:

```vue
      <el-button
        type="success"
        size="large"
        style="margin-left: 12px"
        :loading="taskStore.isPolling && taskStore.currentTask?.task_type === 'sync-inventory' && (taskStore.currentTask?.status === 'RUNNING' || taskStore.currentTask?.status === 'PENDING')"
        :disabled="taskStore.isPolling && taskStore.currentTask?.status !== 'SUCCESS' && taskStore.currentTask?.status !== 'FAILED' && taskStore.currentTask?.task_type !== 'sync-inventory'"
        @click="taskStore.triggerSyncInventory()"
      >
        同步 ERP 库存
      </el-button>
```

- [ ] **Step 2: 新增库存文件状态**

Add after the `订单文件` description item:

```vue
        <el-descriptions-item label="库存文件">
          {{ inventoryFileExists ? '已存在' : '暂无' }}
          <el-button
            v-if="inventoryFileExists"
            size="small"
            type="primary"
            link
            @click="downloadInventoryFile"
          >
            下载
          </el-button>
        </el-descriptions-item>
```

- [ ] **Step 3: 更新 script 部分**

Add imports and state:

```typescript
import { getOrdersPreview, getOrdersFileUrl, getInventoryPreview, getInventoryFileUrl } from '@/api/index'

const inventoryFileExists = ref(false)
```

Update onMounted:

```typescript
onMounted(async () => {
  try {
    const [orderRes, inventoryRes] = await Promise.all([
      getOrdersPreview({ page: 1, page_size: 1 }),
      getInventoryPreview({ page: 1, page_size: 1 }),
    ])
    orderFileExists.value = orderRes.data.total > 0
    inventoryFileExists.value = inventoryRes.data.total > 0
  } catch {
    orderFileExists.value = false
    inventoryFileExists.value = false
  }
})
```

Add download function:

```typescript
function downloadInventoryFile() {
  window.open(getInventoryFileUrl(), '_blank')
}
```

---

### Task 10: InventoryView — 库存数据表格页面

**Files:**
- Create: `dubai_shipping_tool/frontend/src/views/InventoryView.vue`

- [ ] **Step 1: 创建 InventoryView.vue**

```vue
<template>
  <div>
    <h2 style="margin-bottom: 20px">库存数据</h2>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card>
          <template #header><span>SKU 数量</span></template>
          <div style="font-size: 28px; font-weight: bold; color: #409EFF">{{ total }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header><span>总库存件数</span></template>
          <div style="font-size: 28px; font-weight: bold; color: #67C23A">{{ totalQuantity }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header><span>操作</span></template>
          <el-button type="primary" @click="downloadInventory">下载库存 Excel</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索栏 -->
    <el-card style="margin-bottom: 20px">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索 SKU"
            clearable
            @keyup.enter="searchInventory"
          />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="searchInventory">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 数据表格 -->
    <el-card>
      <template #header>
        <span>库存列表（共 {{ total }} 条）</span>
      </template>

      <el-table
        :data="inventory"
        border
        stripe
        v-loading="loading"
        empty-text="暂无库存数据，请先同步库存"
        style="width: 100%"
      >
        <el-table-column prop="SKU" label="SKU" min-width="200" />
        <el-table-column prop="当前库存" label="当前库存" min-width="150" sortable />
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadInventory"
          @current-change="loadInventory"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getInventoryPreview, getInventoryFileUrl } from '@/api/index'

interface InventoryRow {
  SKU: string
  当前库存: number
}

const inventory = ref<InventoryRow[]>([])
const total = ref(0)
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(50)
const searchKeyword = ref('')

const totalQuantity = computed(() => {
  return inventory.value.reduce((sum, row) => sum + row.当前库存, 0)
})

async function loadInventory() {
  loading.value = true
  try {
    const { data } = await getInventoryPreview({
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: searchKeyword.value,
    })
    inventory.value = data.data
    total.value = data.total
  } catch {
    inventory.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function searchInventory() {
  currentPage.value = 1
  loadInventory()
}

function resetSearch() {
  searchKeyword.value = ''
  currentPage.value = 1
  loadInventory()
}

function downloadInventory() {
  window.open(getInventoryFileUrl(), '_blank')
}

onMounted(() => {
  loadInventory()
})
</script>
```

---

### Task 11: 更新路由和导航

**Files:**
- Modify: `dubai_shipping_tool/frontend/src/router/index.ts`
- Modify: `dubai_shipping_tool/frontend/src/App.vue`

- [ ] **Step 1: 新增 /inventory 路由**

In `router/index.ts`, add the inventory route after the orders route:

```typescript
  {
    path: '/inventory',
    name: 'Inventory',
    component: () => import('@/views/InventoryView.vue'),
  },
```

- [ ] **Step 2: 侧栏新增菜单项**

In `App.vue`, add after the orders menu item:

```vue
        <el-menu-item index="/inventory">
          <span>库存数据</span>
        </el-menu-item>
```

- [ ] **Step 3: 验证前端编译**

```bash
cd F:/Noon/dubai_shipping_tool/frontend
npx vue-tsc --noEmit
```

Expected: No errors.

---

### Task 12: 端到端验证

- [ ] **Step 1: 配置 ERP 账号密码**

在 `.env` 中填入真实的 ERP 用户名密码：
```env
ERP_USERNAME=你的ERP用户名
ERP_PASSWORD=你的ERP密码
```

- [ ] **Step 2: 启动后端**

```bash
cd F:/Noon/dubai_shipping_tool/backend
.venv/Scripts/python run.py
```

Expected: 后端在 `http://127.0.0.1:8000` 启动。

- [ ] **Step 3: 启动前端**

```bash
cd F:/Noon/dubai_shipping_tool/frontend
npm run dev
```

Expected: 前端在 `http://localhost:5173` 启动。

- [ ] **Step 4: 验证清单**

1. 打开 `http://localhost:5173`
2. 侧栏显示「库存数据」菜单
3. 控制台页面出现「同步 ERP 库存」按钮
4. 点击「同步 ERP 库存」→ Edge 浏览器打开 ERP → 自动登录 → 跳转库存页 → 点击查看所有库存 → 点击下载
5. 任务状态变为 SUCCESS
6. 切换到「库存数据」页面 → 表格显示 SKU + 当前库存
7. 搜索 SKU、分页正常
8. 点击「下载库存 Excel」可下载文件
9. 验证箱号含中文的行已被过滤
10. 验证只保留迪拜仓数据
11. 验证同 SKU 库存已汇总

---

## 验证策略

- **后端验证**: 每个 Python 文件单独验证语法和 import
- **前端验证**: `vue-tsc --noEmit` 检查类型
- **E2E**: 手动按 Task 12 检查清单逐项验证

## 已知未覆盖项（后续迭代）

- ERP 登录失败时的「手动登录」fallback（类似 Noon 的 WAITING_LOGIN 机制）
- Token 过期自动检测和重新登录
- `POST /api/tasks/run-all` 一键运行全部
- `routes_config.py` 设置页面 API
- `SettingsView.vue` 设置页面
