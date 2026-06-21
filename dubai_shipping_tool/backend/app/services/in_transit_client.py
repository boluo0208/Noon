"""在途库存下载模块。

使用 Playwright 同步 API，复用 ERP 持久化上下文，
打开物流页面 → 点「查询SKU明细」→ 点「下载表格数据」→ 保存 XLSX。
"""
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from app.core.config import settings
from app.core.accounts import get_erp_account
from app.core.paths import (
    ERP_PROFILE_DIR,
    SCREENSHOT_DIR,
    INVENTORY_CURRENT_DIR,
    INVENTORY_ARCHIVE_DIR,
    IN_TRANSIT_CURRENT_FILE,
    IN_TRANSIT_RAW_FILE,
    erp_profile_dir,
    warehouse_in_transit_current_file,
    warehouse_in_transit_raw_file,
    warehouse_inventory_archive_dir,
    warehouse_inventory_current_dir,
)
from app.core.task_manager import TaskInfo, TaskStatus
from app.services.inventory_client import _do_erp_login
from app.services.in_transit_parser import parse_in_transit


def _screenshot(page: Page, name: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{ts}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def _archive_current_raw(raw_file: Path = IN_TRANSIT_RAW_FILE, archive_dir: Path = INVENTORY_ARCHIVE_DIR) -> None:
    if raw_file.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"in_transit_raw_{ts}.xlsx"
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(raw_file), str(archive_dir / archive_name))


def _archive_current_in_transit(current_file: Path = IN_TRANSIT_CURRENT_FILE, archive_dir: Path = INVENTORY_ARCHIVE_DIR) -> None:
    if current_file.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"dubai_in_transit_{ts}.xlsx"
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current_file), str(archive_dir / archive_name))


def _is_erp_login_page(page: Page) -> bool:
    try:
        if "login" in page.url.lower():
            return True
        return page.locator("input[type='password']").first.is_visible(timeout=1_000)
    except Exception:
        return False


def run_in_transit_sync(task: TaskInfo, warehouse_id: str | None = None) -> None:
    """在线程中执行在途库存下载。

    复用 ERP 持久化上下文，打开物流管理页面，
    点击「查询SKU明细」→「下载表格数据」→ 保存 XLSX。
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
    current_file = warehouse_in_transit_current_file(warehouse.id)
    raw_file = warehouse_in_transit_raw_file(warehouse.id)

    logistics_url = "http://www.erpzd.com/#/customer/wuliu/index"

    with sync_playwright() as p:
        context: BrowserContext = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="msedge",
            headless=settings.erp_headless,
            accept_downloads=True,
        )

        page: Page = context.new_page()

        try:
            # 0. 清空 SPA 缓存，防止旧查询数据残留
            page.goto("about:blank", wait_until="domcontentloaded", timeout=5_000)
            page.evaluate("() => { try { localStorage.clear(); sessionStorage.clear(); } catch(e) {} }")

            # 1. 打开物流管理页面
            task.message = "正在打开物流管理页面..."
            page.goto(logistics_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_load_state("networkidle", timeout=15_000)

            if _is_erp_login_page(page):
                task.message = "检测到需要登录 ERP..."
                if not _do_erp_login(page, task, erp_account):
                    return
                task.message = "登录完成，跳转到物流管理页面..."
                page.goto(logistics_url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_load_state("networkidle", timeout=15_000)

            # 2. 点击查询按钮（适配多种文本变体）
            task.message = "正在查找查询按钮..."

            query_btn = None
            # 按优先级尝试：精确 → 部分 → 模糊
            selectors = [
                ("button", "查询SKU明细"),
                ("button", "SKU明细"),
                ("button", "查询明细"),
                ("button", "查询"),
                ("a", "查询SKU明细"),
                ("a", "SKU明细"),
                ("a", "查询"),
                ("*[role='button']", "查询"),
            ]
            for tag, text in selectors:
                if tag == "*[role='button']":
                    candidate = page.locator(tag).filter(has_text=text).first
                else:
                    candidate = page.get_by_role("button", name=text) if tag == "button" else page.locator(tag).filter(has_text=text).first
                    if tag == "button":
                        try:
                            if not candidate.is_visible(timeout=2_000):
                                candidate = page.locator(tag).filter(has_text=text).first
                        except Exception:
                            candidate = page.locator(tag).filter(has_text=text).first
                try:
                    if candidate and candidate.is_visible(timeout=2_000):
                        query_btn = candidate
                        break
                except Exception:
                    continue

            if not query_btn:
                # 获取页面上所有按钮文本，帮助排查
                all_btns = page.locator("button").all()
                btn_texts = []
                for b in all_btns[:20]:
                    try:
                        t = b.inner_text(timeout=500)
                        if t.strip():
                            btn_texts.append(t.strip())
                    except Exception:
                        pass
                _screenshot(page, "no_query_sku_button")
                task.status = TaskStatus.FAILED
                task.error_detail = f"找不到查询按钮。页面可见按钮: {btn_texts}"
                task.finished_at = time.time()
                context.close()
                return

            query_btn.click()
            task.message = "已点击查询按钮，等待数据加载..."
            page.wait_for_timeout(3000)  # 等查询结果加载

            # 3. 点击下载按钮
            task.message = "正在查找下载按钮..."

            download_btn = None
            dl_selectors = [
                ("下载表格数据",),
                ("表格数据",),
                ("下载",),
                ("导出",),
            ]
            for texts in dl_selectors:
                for text in texts:
                    candidate = page.locator("button").filter(has_text=text).first
                    try:
                        if candidate.is_visible(timeout=2_000):
                            download_btn = candidate
                            break
                    except Exception:
                        continue
                if download_btn:
                    break

            if not download_btn:
                all_btns = page.locator("button").all()
                btn_texts = []
                for b in all_btns[:20]:
                    try:
                        t = b.inner_text(timeout=500)
                        if t.strip():
                            btn_texts.append(t.strip())
                    except Exception:
                        pass
                _screenshot(page, "no_download_button")
                task.status = TaskStatus.FAILED
                task.error_detail = f"找不到下载按钮。页面可见按钮: {btn_texts}"
                task.finished_at = time.time()
                context.close()
                return

            task.message = "正在下载在途库存文件..."
            with page.expect_download(timeout=120_000) as download_info:
                download_btn.click()

            download = download_info.value
            task.message = "正在保存在途库存文件..."

            _archive_current_raw(raw_file, archive_dir)
            _archive_current_in_transit(current_file, archive_dir)

            original_name = download.suggested_filename
            suffix = Path(original_name).suffix or ".xlsx"
            current_dir.mkdir(parents=True, exist_ok=True)
            save_path = current_dir / f"in_transit_raw{suffix}"
            download.save_as(str(save_path))

            if save_path != raw_file:
                shutil.move(str(save_path), str(raw_file))

            cleaned_df = parse_in_transit(raw_file)
            cleaned_df.to_excel(current_file, index=False)

            task.message = f"{warehouse.name} 在途库存文件已下载并生成，共 {len(cleaned_df)} 个 SKU。"
            task.status = TaskStatus.SUCCESS
            task.finished_at = time.time()

        except PlaywrightTimeout as e:
            _screenshot(page, "in_transit_timeout")
            task.status = TaskStatus.FAILED
            task.error_detail = f"操作超时: {e}"
            task.finished_at = time.time()
        except Exception as e:
            import traceback
            _screenshot(page, "in_transit_error")
            task.status = TaskStatus.FAILED
            task.error_detail = f"在途库存同步失败: {e}\n{traceback.format_exc()}"
            task.finished_at = time.time()
        finally:
            try:
                context.close()
            except Exception:
                pass
