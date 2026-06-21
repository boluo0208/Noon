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

from app.core.config import load_settings, settings
from app.core.accounts import ErpAccountConfig, get_erp_account
from app.core.paths import (
    ERP_PROFILE_DIR,
    SCREENSHOT_DIR,
    INVENTORY_CURRENT_DIR,
    INVENTORY_CURRENT_FILE,
    INVENTORY_RAW_FILE,
    INVENTORY_ARCHIVE_DIR,
    erp_profile_dir,
    warehouse_inventory_archive_dir,
    warehouse_inventory_current_dir,
    warehouse_inventory_current_file,
    warehouse_inventory_raw_file,
)
from app.core.task_manager import TaskInfo, TaskStatus
from app.services.inventory_parser import parse_inventory


def _screenshot(page: Page, name: str) -> Path:
    """保存当前页面截图并返回路径。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{ts}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def _archive_current_raw(raw_file: Path = INVENTORY_RAW_FILE, archive_dir: Path = INVENTORY_ARCHIVE_DIR) -> None:
    """将旧的 raw XLSX 移动到 archive 并添加时间戳。"""
    if raw_file.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"inventory_raw_{ts}.xlsx"
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(raw_file), str(archive_dir / archive_name))


def _archive_current_inventory(current_file: Path = INVENTORY_CURRENT_FILE, archive_dir: Path = INVENTORY_ARCHIVE_DIR) -> None:
    """将旧的清洗后库存文件移动到 archive 并添加时间戳。"""
    if current_file.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"dubai_inventory_{ts}.xlsx"
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current_file), str(archive_dir / archive_name))


def _do_erp_login(page: Page, task: TaskInfo, erp_account: ErpAccountConfig | None = None) -> bool:
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
            username_input = page.locator("input").filter(has_text="").first

    current_settings = load_settings()
    username = erp_account.username if erp_account else current_settings.erp_username
    password = erp_account.password if erp_account else current_settings.erp_password
    if not username or not password:
        task.status = TaskStatus.FAILED
        task.error_detail = "ERP 账号密码未配置，请在账号配置中设置 ERP username/password。"
        task.finished_at = time.time()
        return False

    username_input.fill(username)
    password_input.fill(password)

    task.message = "正在点击登录按钮..."

    # Find the login button. ERP currently renders it as "Login".
    login_button = page.get_by_role("button", name="Login")
    if not login_button.is_visible(timeout=3_000):
        login_button = page.locator("button").filter(has_text="Login").first
    if not login_button.is_visible(timeout=2_000):
        login_button = page.locator("button").filter(has_text="登录").first
    if not login_button.is_visible(timeout=2_000):
        login_button = page.locator("button[type='submit']").first

    if not login_button.is_visible(timeout=3_000):
        _screenshot(page, "erp_login_button_not_found")
        task.status = TaskStatus.FAILED
        task.error_detail = "找不到登录按钮。"
        task.finished_at = time.time()
        return False

    login_button.click()

    # 等待登录完成（URL 不再包含 login，进入任意 customer 页面）
    try:
        page.wait_for_url(lambda url: "login" not in url.lower() and "/customer/" in url.lower(), timeout=15_000)
        task.message = "ERP 登录成功。"
        return True
    except PlaywrightTimeout:
        _screenshot(page, "erp_login_failed")
        task.status = TaskStatus.FAILED
        task.error_detail = "ERP 登录失败，请检查账号密码是否正确。"
        task.finished_at = time.time()
        return False


def run_inventory_sync(task: TaskInfo, warehouse_id: str | None = None) -> None:
    """在线程中执行 ERP 库存同步。

    此函数由 TaskManager 在后台线程中调用，task 的状态会被实时更新。
    前端通过 GET /api/tasks/{task_id} 轮询状态。
    """
    task.status = TaskStatus.RUNNING
    task.started_at = time.time()
    task.message = "正在启动浏览器..."

    try:
        warehouse, erp_account = get_erp_account(warehouse_id)
    except ValueError as e:
        task.status = TaskStatus.FAILED
        task.error_detail = str(e)
        task.finished_at = time.time()
        return

    profile_dir = erp_profile_dir(erp_account.id)
    current_dir = warehouse_inventory_current_dir(warehouse.id)
    archive_dir = warehouse_inventory_archive_dir(warehouse.id)
    current_file = warehouse_inventory_current_file(warehouse.id)
    raw_file = warehouse_inventory_raw_file(warehouse.id)

    with sync_playwright() as p:
        context: BrowserContext = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
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
                if not _do_erp_login(page, task, erp_account):
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
                task.finished_at = time.time()
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
                task.finished_at = time.time()
                return

            # 6. 监听下载并点击
            task.message = "正在下载库存文件..."
            with page.expect_download(timeout=settings.erp_download_timeout_seconds * 1000) as download_info:
                download_btn.click()

            download = download_info.value
            task.message = "正在保存库存文件..."

            # 归档旧文件
            _archive_current_raw(raw_file, archive_dir)
            _archive_current_inventory(current_file, archive_dir)

            # 保存下载的文件
            original_name = download.suggested_filename
            suffix = Path(original_name).suffix or ".xlsx"
            current_dir.mkdir(parents=True, exist_ok=True)
            save_path = current_dir / f"inventory_raw{suffix}"
            download.save_as(str(save_path))

            # 如果后缀不是 xlsx，重命名为固定的 xlsx 名
            if save_path != raw_file:
                shutil.move(str(save_path), str(raw_file))

            cleaned_df = parse_inventory(raw_file, warehouse_name=warehouse.erp_warehouse_name)
            cleaned_df.to_excel(current_file, index=False)

            task.message = f"{warehouse.name} 库存文件已下载并生成，共 {len(cleaned_df)} 个 SKU。"
            task.status = TaskStatus.SUCCESS
            task.finished_at = time.time()

        except PlaywrightTimeout as e:
            _screenshot(page, "erp_timeout")
            task.status = TaskStatus.FAILED
            task.error_detail = f"操作超时: {e}"
            task.finished_at = time.time()
        except Exception as e:
            import traceback
            _screenshot(page, "erp_error")
            task.status = TaskStatus.FAILED
            task.error_detail = f"库存同步失败: {e}\n{traceback.format_exc()}"
            task.finished_at = time.time()
        finally:
            try:
                context.close()
            except Exception:
                pass
