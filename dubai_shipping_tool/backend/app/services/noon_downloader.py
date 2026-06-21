"""Download Noon Directship pending orders with Playwright."""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout, sync_playwright

from app.core.accounts import NoonAccountConfig, get_noon_account
from app.core.config import settings
from app.core.paths import (
    NOON_PROFILE_DIR,
    SCREENSHOT_DIR,
    account_orders_archive_dir,
    account_orders_current_dir,
    account_orders_current_file,
    noon_profile_dir,
)
from app.core.task_manager import TaskInfo, TaskStatus


def _log(message: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [NoonDownloader] {message}", flush=True)


def _log_error(message: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [NoonDownloader] [ERROR] {message}", file=sys.stderr, flush=True)


def _check_profile_lock(profile_dir: Path = NOON_PROFILE_DIR) -> None:
    for lock_file in [
        profile_dir / "SingletonLock",
        profile_dir / "SingletonSocket",
        profile_dir / "Lockfile",
    ]:
        if not lock_file.exists():
            continue
        try:
            lock_file.unlink()
        except PermissionError as exc:
            raise RuntimeError(
                f"Cannot remove browser lock file {lock_file}.\n"
                f"Another Edge instance may be using profile {profile_dir}.\n"
                "Close the related Edge window and retry."
            ) from exc


def _is_edge_available() -> bool:
    checks = [
        ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"],
        ["where", "msedge"],
    ]
    for command in checks:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return True
        except Exception:
            pass
    return False


def _screenshot(page: Page, name: str) -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def _archive_account_csv(source_id: str) -> None:
    current_file = account_orders_current_file(source_id)
    if not current_file.exists():
        return
    archive_dir = account_orders_archive_dir(source_id)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"noon_pending_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    shutil.move(str(current_file), str(archive_dir / archive_name))


def _is_login_page(page: Page) -> bool:
    try:
        url = page.url.lower()
        title = page.title().lower()
        return "login" in url or "signin" in url or "login" in title or "sign in" in title
    except Exception:
        return False


def _find_export_button(page: Page, timeout: int = 10) -> bool:
    try:
        if page.get_by_role("button", name="Export", exact=True).is_visible(timeout=timeout * 1000):
            return True
    except Exception:
        pass
    try:
        return page.locator("button:visible").filter(has_text="Export").first.is_visible(timeout=3_000)
    except Exception:
        return False


def _try_fill_noon_email(page: Page, account: NoonAccountConfig) -> bool:
    if not account.email:
        return False
    selectors = [
        "input[type='email']",
        "input[name*='email' i]",
        "input[placeholder*='email' i]",
        "input[autocomplete='email']",
        "input:visible",
    ]
    for selector in selectors:
        try:
            field = page.locator(selector).first
            if field.is_visible(timeout=2_000):
                field.fill(account.email)
                try:
                    field.press("Enter")
                except Exception:
                    pass
                return True
        except Exception:
            continue
    return False


def _wait_for_login_complete(page: Page, task: TaskInfo, timeout: int = 600) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        elapsed = int(time.time() - (task.started_at or time.time()))
        remaining = int(deadline - time.time())
        task.message = (
            "Please complete Noon login in the Edge browser.\n"
            f"Waited {elapsed}s, {remaining}s remaining."
        )
        try:
            if not _is_login_page(page):
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                if _find_export_button(page, timeout=5):
                    return True
            if _find_export_button(page, timeout=1):
                return True
        except Exception:
            pass
        time.sleep(4)
    return False


def _wait_for_export_button(page: Page, task: TaskInfo, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task.message = "Waiting for Noon Export button..."
        if _find_export_button(page, timeout=5):
            return True
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
    return False


def _select_project_if_prompted(page: Page, task: TaskInfo) -> bool:
    """Select the first available Noon project if a project picker blocks the page."""
    try:
        body_text = page.locator("body").inner_text(timeout=3_000)
    except Exception:
        return False

    prompt_markers = [
        "Select a pro",
        "Search for your project",
        "PROJECT NAME",
        "You do not have sufficient permissions",
    ]
    if not any(marker in body_text for marker in prompt_markers):
        return False

    task.message = "Noon is asking for a project; selecting the first available project..."
    clicked = page.evaluate(
        """() => {
            const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const bad = [
                'Search for your project',
                'You do not have sufficient permissions',
                'PROJECT NAME',
                'PROJECT ID',
                'ORGANIZATION',
                'Manage Projects',
                'Close'
            ];
            const candidates = Array.from(document.querySelectorAll('[role="dialog"] * , body *'))
                .filter((el) => visible(el))
                .map((el) => ({ el, text: (el.innerText || '').trim(), rect: el.getBoundingClientRect() }))
                .filter((x) => x.text.length > 10 && x.text.length < 240)
                .filter((x) => !bad.some((b) => x.text.includes(b)))
                .filter((x) => /PRJ\\d+|PROJECT|shenzhen|shan|hang|GoHappy/i.test(x.text))
                .sort((a, b) => {
                    const aScore = (a.text.match(/PRJ\\d+/) ? 0 : 10) + a.rect.top / 1000 + a.text.length / 10000;
                    const bScore = (b.text.match(/PRJ\\d+/) ? 0 : 10) + b.rect.top / 1000 + b.text.length / 10000;
                    return aScore - bScore;
                });
            if (!candidates.length) return false;
            candidates[0].el.click();
            return true;
        }"""
    )
    if not clicked:
        return False

    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    page.wait_for_timeout(1_000)
    return True


def _page_has_target_warehouse(page: Page, account: NoonAccountConfig) -> bool:
    target_code = account.noon_warehouse_code.strip()
    target_name = account.noon_warehouse_name.strip()
    try:
        body_text = page.locator("body").inner_text(timeout=3_000)
    except Exception:
        return False
    if target_code and target_code in body_text:
        return True
    return bool(target_name and target_name in body_text and not target_code)


def _click_current_warehouse_switcher(page: Page) -> None:
    selectors = [
        "button:has-text('GP-UAE')",
        "button:has-text('PLT-KSA')",
        "button:has-text('PL-UAE')",
        "button:has-text('ETWAREHOUSE')",
        "[role='button']:has-text('GP-UAE')",
        "[role='button']:has-text('PLT-KSA')",
        "[role='button']:has-text('PL-UAE')",
        "[role='button']:has-text('ETWAREHOUSE')",
    ]
    for selector in selectors:
        try:
            item = page.locator(selector).first
            if item.is_visible(timeout=1_000):
                item.click()
                return
        except Exception:
            continue

    clicked = page.evaluate(
        """() => {
            const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const pattern = /W\\d{6,}[A-Z]{2}/;
            const candidates = Array.from(document.querySelectorAll('button,[role="button"],div,span'))
                .filter((el) => visible(el) && pattern.test(el.innerText || ''))
                .map((el) => ({ el, len: (el.innerText || '').length, top: el.getBoundingClientRect().top }))
                .filter((x) => x.len < 140)
                .sort((a, b) => a.top - b.top || a.len - b.len);
            if (!candidates.length) return false;
            candidates[0].el.click();
            return true;
        }"""
    )
    if not clicked:
        raise RuntimeError("Cannot find Noon warehouse/country switcher")


def _click_target_warehouse_option(page: Page, account: NoonAccountConfig) -> None:
    labels = [x for x in [account.noon_warehouse_code.strip(), account.noon_warehouse_name.strip()] if x]
    for label in labels:
        try:
            option = page.get_by_text(label, exact=False).last
            option.wait_for(state="visible", timeout=8_000)
            option.click()
            return
        except Exception:
            continue

    target = labels[0] if labels else ""
    clicked = page.evaluate(
        """(target) => {
            const visible = (el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
            };
            const matches = Array.from(document.querySelectorAll('button,[role="button"],div,span'))
                .filter((el) => visible(el) && (el.innerText || '').includes(target))
                .sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
            if (!matches.length) return false;
            matches[0].click();
            return true;
        }""",
        target,
    )
    if not clicked:
        raise RuntimeError(f"Cannot find Noon warehouse option: {target}")


def _select_noon_warehouse(page: Page, task: TaskInfo, account: NoonAccountConfig) -> None:
    if not account.noon_warehouse_code and not account.noon_warehouse_name:
        return

    target = account.noon_warehouse_name or account.noon_warehouse_code
    task.message = f"Switching Noon warehouse/country to {target}..."
    if _page_has_target_warehouse(page, account):
        return

    _click_current_warehouse_switcher(page)
    page.wait_for_timeout(500)
    _click_target_warehouse_option(page, account)
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass
    page.wait_for_timeout(1_000)

    if not _page_has_target_warehouse(page, account):
        raise RuntimeError(f"Noon warehouse switch did not reach target: {target}")


def run_noon_download(task: TaskInfo, account_id: str | None = None) -> None:
    _log("=" * 50)
    _log(f"Task {task.task_id} started")
    try:
        account = get_noon_account(account_id)
    except ValueError as exc:
        task.status = TaskStatus.FAILED
        task.error_detail = str(exc)
        task.finished_at = time.time()
        return

    profile_dir = noon_profile_dir(account.noon_account_id)
    orders_dir = account_orders_current_dir(account.id)
    orders_file = account_orders_current_file(account.id)

    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        _log(f"ProactorEventLoop set in thread {threading.current_thread().name}")

    task.status = TaskStatus.RUNNING
    task.started_at = time.time()
    task.message = "Checking runtime environment..."

    if not _is_edge_available():
        task.status = TaskStatus.FAILED
        task.error_detail = "Microsoft Edge was not found. Please install Edge or run: python -m playwright install msedge"
        task.finished_at = time.time()
        return

    try:
        _check_profile_lock(profile_dir)
    except RuntimeError as exc:
        task.status = TaskStatus.FAILED
        task.error_detail = str(exc)
        task.finished_at = time.time()
        return

    pw = None
    context: BrowserContext | None = None
    page: Page | None = None

    try:
        task.message = "Starting Edge browser..."
        pw = sync_playwright().start()
        context = pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="msedge",
            headless=settings.noon_headless,
            accept_downloads=True,
            args=["--disable-extensions", "--no-first-run", "--no-default-browser-check"],
        )

        task.message = "Opening Noon pending orders page..."
        page = context.new_page()
        page.goto(account.pending_url, wait_until="domcontentloaded", timeout=60_000)
        try:
            page.wait_for_load_state("networkidle", timeout=30_000)
        except PlaywrightTimeout:
            pass
        _select_project_if_prompted(page, task)

        if _is_login_page(page):
            task.status = TaskStatus.WAITING_LOGIN
            filled = _try_fill_noon_email(page, account)
            task.message = (
                f"{account.name} requires Noon login.\n"
                + ("Email was filled automatically; enter the OTP and finish login.\n" if filled else "Enter email/OTP and finish login in Edge.\n")
                + "The program will continue after login is detected."
            )
            if not _wait_for_login_complete(page, task, timeout=600):
                task.status = TaskStatus.FAILED
                task.error_detail = "Timed out waiting for Noon login."
                task.finished_at = time.time()
                return
            _select_project_if_prompted(page, task)
        else:
            _select_project_if_prompted(page, task)

        if not _wait_for_export_button(page, task, timeout=30):
            screenshot_path = _screenshot(page, "no_export_button")
            task.status = TaskStatus.FAILED
            task.error_detail = f"Logged in, but Export button was not found. Screenshot: {screenshot_path}"
            task.finished_at = time.time()
            return

        try:
            _select_noon_warehouse(page, task, account)
        except Exception as exc:
            screenshot_path = _screenshot(page, "warehouse_switch_failed")
            task.status = TaskStatus.FAILED
            task.error_detail = (
                f"Noon warehouse/country switch failed: {exc}\n"
                f"Target: {account.noon_warehouse_name or account.noon_warehouse_code}\n"
                f"Screenshot: {screenshot_path}"
            )
            task.finished_at = time.time()
            return

        if not _wait_for_export_button(page, task, timeout=30):
            screenshot_path = _screenshot(page, "no_export_after_switch")
            task.status = TaskStatus.FAILED
            task.error_detail = f"Export button not found after warehouse switch. Screenshot: {screenshot_path}"
            task.finished_at = time.time()
            return

        task.status = TaskStatus.RUNNING
        task.message = "Exporting Noon orders..."
        export_button = page.get_by_role("button", name="Export", exact=True)
        try:
            if not export_button.is_visible(timeout=5_000):
                export_button = page.locator("button:visible").filter(has_text="Export").first
                export_button.wait_for(state="visible", timeout=5_000)
        except Exception:
            screenshot_path = _screenshot(page, "no_export_button_final")
            task.status = TaskStatus.FAILED
            task.error_detail = f"Export button is unavailable. Screenshot: {screenshot_path}"
            task.finished_at = time.time()
            return

        with page.expect_download(timeout=settings.noon_download_timeout_seconds * 1000) as download_info:
            export_button.click()
        download = download_info.value

        task.message = "Saving Noon orders file..."
        _archive_account_csv(account.id)
        original_name = download.suggested_filename
        suffix = Path(original_name).suffix or ".csv"
        save_path = orders_dir / f"noon_pending_orders{suffix}"
        orders_dir.mkdir(parents=True, exist_ok=True)
        download.save_as(str(save_path))
        if suffix.lower() not in (".xlsx", ".xls") and save_path != orders_file:
            shutil.move(str(save_path), str(orders_file))

        task.status = TaskStatus.SUCCESS
        task.message = f"{account.name} orders were saved."
        task.finished_at = time.time()
        _log("Task completed")

    except PlaywrightTimeout as exc:
        screenshot_path = _screenshot(page, "timeout") if page else None
        task.status = TaskStatus.FAILED
        task.error_detail = f"Operation timed out: {exc}\nScreenshot: {screenshot_path}\n\n{traceback.format_exc()}"
        task.finished_at = time.time()
    except Exception as exc:
        screenshot_path = None
        if page:
            try:
                screenshot_path = _screenshot(page, "error")
            except Exception:
                pass
        task.status = TaskStatus.FAILED
        task.error_detail = f"Download failed: {exc}\nScreenshot: {screenshot_path}\n\n{traceback.format_exc()}"
        task.finished_at = time.time()
    finally:
        if context:
            try:
                context.close()
            except Exception as exc:
                _log_error(f"Failed to close browser context: {exc}")
        if pw:
            try:
                pw.stop()
            except Exception as exc:
                _log_error(f"Failed to stop Playwright: {exc}")
