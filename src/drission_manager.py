"""
DrissionPage Manager - Quản lý browser dùng DrissionPage
Thay thế cho chrome_manager.py và undetected-chromedriver

DrissionPage là thư viện Python mạnh mẽ cho browser automation:
- Tự động chống phát hiện bot
- Hỗ trợ Chrome profiles
- Có thể chạy ẩn hoặc hiện
- Tốc độ nhanh hơn Selenium
"""

import time
from pathlib import Path
from typing import Optional, List, Any
from dataclasses import dataclass

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    from DrissionPage.errors import ElementNotFoundError
    HAS_DRISSION = True
except ImportError:
    HAS_DRISSION = False
    ChromiumPage = None
    ChromiumOptions = None

from rich.console import Console

console = Console()


@dataclass
class BrowserProfile:
    """Cấu hình Chrome profile"""
    name: str
    chrome_path: str
    profile_path: str
    rate_limited: bool = False


class DrissionManager:
    """
    Manager cho DrissionPage - dùng chung cho tất cả tính năng.
    Hỗ trợ nhiều profiles để xử lý rate limit.
    """

    def __init__(
        self,
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = False,
        on_log: Optional[callable] = None,
    ):
        """
        Args:
            chrome_path: Đường dẫn Chrome executable
            profile_path: Đường dẫn Chrome profile (user data dir)
            headless: Chạy ẩn browser
            on_log: Callback để log
        """
        self.chrome_path = chrome_path or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.profile_path = profile_path
        self.headless = headless
        self.on_log = on_log

        self.page: Optional[ChromiumPage] = None
        self._is_hidden = False

    def log(self, msg: str, level: str = "info"):
        """Log message"""
        if self.on_log:
            self.on_log(msg, level)

        if level == "success":
            console.print(f"[green]   ✓ {msg}[/]")
        elif level == "error":
            console.print(f"[red]   ✗ {msg}[/]")
        elif level == "warning":
            console.print(f"[yellow]   ⚠ {msg}[/]")
        else:
            console.print(f"[cyan]{msg}[/]")

    def is_available(self) -> bool:
        """Kiểm tra DrissionPage đã được cài đặt chưa"""
        return HAS_DRISSION

    def setup(self, download_dir: str = None, max_retries: int = 3) -> bool:
        """
        Khởi tạo browser với DrissionPage

        Args:
            download_dir: Thư mục download mặc định
            max_retries: Số lần thử lại nếu lỗi

        Returns:
            True nếu thành công
        """
        if not HAS_DRISSION:
            self.log("DrissionPage chưa được cài đặt. Chạy: pip install DrissionPage", "error")
            return False

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.log(f"Thử lại lần {attempt + 1}...", "warning")
                    time.sleep(2)

                self.log("Đang khởi tạo Chrome với DrissionPage...")

                # Cấu hình ChromiumOptions
                options = ChromiumOptions()

                # Browser path
                if self.chrome_path:
                    options.set_browser_path(self.chrome_path)

                # Profile path (user data dir)
                if self.profile_path:
                    profile = Path(self.profile_path)
                    profile.mkdir(parents=True, exist_ok=True)
                    options.set_user_data_path(str(profile))
                    self.log(f"   Profile: {profile}")

                # Tối ưu options
                options.set_argument("--no-first-run")
                options.set_argument("--no-default-browser-check")
                options.set_argument("--disable-popup-blocking")
                options.set_argument("--disable-infobars")
                options.set_argument("--disable-dev-shm-usage")

                # Tắt Safe Browsing để không bị chặn download
                options.set_argument("--safebrowsing-disable-download-protection")
                options.set_argument("--disable-features=SafeBrowsingEnhancedProtection")

                # Window size
                if self.headless:
                    options.set_argument("--window-size=800,600")
                    options.set_argument("--window-position=-2000,-2000")
                else:
                    options.set_argument("--window-size=1920,1080")
                    options.set_argument("--start-maximized")

                # Download preferences
                if download_dir:
                    options.set_download_path(download_dir)

                # Khởi tạo page
                self.page = ChromiumPage(options)

                # Ẩn window nếu cần
                if self.headless:
                    self._hide_window()

                self.log("Chrome đã sẵn sàng!", "success")
                return True

            except Exception as e:
                self.log(f"Lỗi lần {attempt + 1}: {e}", "error")
                self.close()

                if attempt == max_retries - 1:
                    import traceback
                    self.log(traceback.format_exc(), "error")
                    return False

        return False

    def close(self):
        """Đóng browser"""
        if self.page:
            try:
                self.page.quit()
            except:
                pass
            self.page = None

    def is_running(self) -> bool:
        """Kiểm tra browser có đang chạy không"""
        return self.page is not None

    def _hide_window(self):
        """Ẩn browser window bằng cách đẩy ra ngoài màn hình"""
        if not self.page:
            return
        try:
            self.page.set.window.position(-2000, -2000)
            self._is_hidden = True
            self.log("   Đã ẩn Chrome window")
        except Exception as e:
            self.log(f"   Lỗi ẩn window: {e}", "warning")

    def show_window(self):
        """Hiện browser window"""
        if not self.page:
            return
        try:
            self.page.set.window.position(100, 100)
            self.page.set.window.size(1200, 800)
            self._is_hidden = False
            self.log("   Đã hiện Chrome window")
        except Exception as e:
            self.log(f"   Lỗi hiện window: {e}", "warning")

    def toggle_visibility(self):
        """Toggle ẩn/hiện browser"""
        if self._is_hidden:
            self.show_window()
        else:
            self._hide_window()

    # =========================================================================
    # NAVIGATION & INTERACTION
    # =========================================================================

    def navigate(self, url: str, wait: float = 3) -> bool:
        """
        Điều hướng đến URL

        Args:
            url: URL cần mở
            wait: Thời gian chờ sau khi load (giây)

        Returns:
            True nếu thành công
        """
        if not self.page:
            return False
        try:
            self.page.get(url)
            if wait > 0:
                time.sleep(wait)
            return True
        except Exception as e:
            self.log(f"Lỗi navigate: {e}", "error")
            return False

    def run_js(self, script: str, as_expr: bool = False) -> Any:
        """
        Chạy JavaScript

        Args:
            script: Code JavaScript
            as_expr: True nếu là expression cần return value

        Returns:
            Kết quả từ JS (nếu có)
        """
        if not self.page:
            return None
        try:
            return self.page.run_js(script, as_expr=as_expr)
        except Exception as e:
            self.log(f"Lỗi run_js: {e}", "warning")
            return None

    def run_js_return(self, script: str) -> Any:
        """Chạy JS và trả về kết quả"""
        return self.run_js(script, as_expr=True)

    def get_element(self, locator: str, timeout: float = 10):
        """
        Tìm element bằng CSS selector

        Args:
            locator: CSS selector
            timeout: Thời gian chờ tối đa

        Returns:
            Element hoặc None
        """
        if not self.page:
            return None
        try:
            return self.page.ele(locator, timeout=timeout)
        except ElementNotFoundError:
            return None
        except Exception as e:
            self.log(f"Lỗi get_element: {e}", "warning")
            return None

    def get_elements(self, locator: str) -> List:
        """Tìm nhiều elements bằng CSS selector"""
        if not self.page:
            return []
        try:
            return self.page.eles(locator)
        except:
            return []

    def click(self, locator: str, timeout: float = 10) -> bool:
        """Click vào element"""
        el = self.get_element(locator, timeout)
        if el:
            try:
                el.click()
                return True
            except:
                pass
        return False

    def input_text(self, locator: str, text: str, clear: bool = True, timeout: float = 10) -> bool:
        """Nhập text vào input/textarea"""
        el = self.get_element(locator, timeout)
        if el:
            try:
                if clear:
                    el.clear()
                el.input(text)
                return True
            except:
                pass
        return False

    def wait_for(self, locator: str, timeout: float = 30) -> bool:
        """Chờ element xuất hiện"""
        el = self.get_element(locator, timeout)
        return el is not None

    def get_page_source(self) -> str:
        """Lấy HTML của trang"""
        if not self.page:
            return ""
        try:
            return self.page.html
        except:
            return ""

    def get_current_url(self) -> str:
        """Lấy URL hiện tại"""
        if not self.page:
            return ""
        try:
            return self.page.url
        except:
            return ""

    def scroll(self, direction: str = "down", amount: int = 500):
        """
        Scroll trang

        Args:
            direction: "up" hoặc "down"
            amount: Số pixels
        """
        if not self.page:
            return
        try:
            if direction == "down":
                self.page.scroll.down(amount)
            else:
                self.page.scroll.up(amount)
        except:
            pass

    def new_tab(self, url: str = None) -> bool:
        """Mở tab mới"""
        if not self.page:
            return False
        try:
            self.page.new_tab(url)
            return True
        except:
            return False

    def close_tab(self):
        """Đóng tab hiện tại"""
        if not self.page:
            return
        try:
            self.page.close()
        except:
            pass

    def get_tabs_count(self) -> int:
        """Đếm số tabs đang mở"""
        if not self.page:
            return 0
        try:
            return len(self.page.tab_ids)
        except:
            return 0

    def close_extra_tabs(self):
        """Đóng tất cả tab thừa, chỉ giữ 1 tab"""
        if not self.page:
            return
        try:
            tab_ids = self.page.tab_ids
            if len(tab_ids) > 1:
                self.log(f"   Đóng {len(tab_ids) - 1} tab thừa...")
                main_tab = tab_ids[0]
                for tab_id in tab_ids[1:]:
                    self.page.close_tabs(tab_id)
                self.page.to_tab(main_tab)
        except Exception as e:
            self.log(f"Lỗi đóng tab: {e}", "warning")

    # =========================================================================
    # FILE UPLOAD
    # =========================================================================

    def upload_file(self, file_input_locator: str, file_path: str, timeout: float = 10) -> bool:
        """
        Upload file thông qua input[type=file]

        Args:
            file_input_locator: CSS selector của input file
            file_path: Đường dẫn file cần upload
            timeout: Thời gian chờ

        Returns:
            True nếu thành công
        """
        if not self.page:
            return False
        try:
            file_input = self.get_element(file_input_locator, timeout)
            if file_input:
                file_input.input(file_path)
                return True
        except Exception as e:
            self.log(f"Lỗi upload file: {e}", "error")
        return False

    # =========================================================================
    # DOWNLOAD
    # =========================================================================

    def set_download_path(self, path: str):
        """Đặt thư mục download"""
        if not self.page:
            return
        try:
            self.page.set.download_path(path)
        except:
            pass

    def wait_download(self, timeout: float = 60) -> Optional[str]:
        """
        Chờ file download hoàn thành

        Args:
            timeout: Thời gian chờ tối đa

        Returns:
            Đường dẫn file đã download hoặc None
        """
        if not self.page:
            return None
        try:
            return self.page.wait.download_begin(timeout=timeout)
        except:
            return None


# =========================================================================
# SINGLETON INSTANCE (Optional - để dùng như chrome_manager cũ)
# =========================================================================

_manager_instance = None


def get_manager(
    chrome_path: str = None,
    profile_path: str = None,
    headless: bool = False,
) -> DrissionManager:
    """
    Lấy singleton instance của DrissionManager

    Args:
        chrome_path: Đường dẫn Chrome
        profile_path: Đường dẫn profile
        headless: Chạy ẩn

    Returns:
        DrissionManager instance
    """
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = DrissionManager(
            chrome_path=chrome_path,
            profile_path=profile_path,
            headless=headless,
        )
    elif chrome_path or profile_path:
        # Update cấu hình nếu được truyền vào
        if chrome_path:
            _manager_instance.chrome_path = chrome_path
        if profile_path:
            _manager_instance.profile_path = profile_path
        _manager_instance.headless = headless

    return _manager_instance


def reset_manager():
    """Reset singleton instance"""
    global _manager_instance
    if _manager_instance:
        _manager_instance.close()
    _manager_instance = None
