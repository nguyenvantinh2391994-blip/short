"""
VE3 Tool - Chrome Token Extractor
=================================
Tự động lấy Bearer Token từ Google Flow bằng Chrome profile.

Sử dụng Selenium với Chrome DevTools Protocol (CDP) để capture
Authorization header từ network requests.
"""

import json
import time
import threading
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from datetime import datetime


class ChromeTokenExtractor:
    """
    Tự động mở Chrome và lấy Bearer Token từ Google Flow.

    Sử dụng Chrome profile của user để bypass login.
    """

    FLOW_URL = "https://labs.google/fx/tools/flow"

    def __init__(
        self,
        chrome_path: str,
        profile_path: str,
        headless: bool = False,
        timeout: int = 60,
        debug_port: int = None
    ):
        """
        Khởi tạo extractor.

        Args:
            chrome_path: Đường dẫn đến chrome.exe
            profile_path: Đường dẫn đến Chrome User Data
            headless: Chạy ẩn không hiện UI
            timeout: Timeout cho việc lấy token (giây)
            debug_port: Port cho Chrome DevTools (mặc định random 9222-9322)
        """
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.headless = headless
        self.timeout = timeout

        import random
        self.debug_port = debug_port or random.randint(9222, 9322)

        self.driver = None
        self.bearer_token = None
        self.project_id = None

        profile_path_obj = Path(profile_path)
        default_folder = profile_path_obj / "Default"

        is_tool_profile = "chrome_profiles" in str(profile_path_obj).lower()

        if is_tool_profile or default_folder.exists() or not (profile_path_obj.parent / "Local State").exists():
            self.user_data_dir = str(profile_path_obj)
            self.profile_name = None
        else:
            self.profile_name = profile_path_obj.name
            self.user_data_dir = str(profile_path_obj.parent)

    def _create_driver(self):
        """Tạo Chrome WebDriver với CDP enabled và anti-detection."""
        try:
            import undetected_chromedriver as uc
            self._create_driver_undetected(uc)
            return
        except ImportError:
            pass

        self._create_driver_selenium()

    def _create_driver_undetected(self, uc):
        """Tạo driver với undetected-chromedriver."""
        options = uc.ChromeOptions()

        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        if self.profile_name:
            options.add_argument(f"--profile-directory={self.profile_name}")

        options.binary_location = self.chrome_path

        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--remote-debugging-port={self.debug_port}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-extensions")

        self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=None)
        self._setup_cdp_network_capture()
        self._inject_stealth_scripts()

    def _create_driver_selenium(self):
        """Fallback: Tạo driver với Selenium."""
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options

        options = Options()

        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        if self.profile_name:
            options.add_argument(f"--profile-directory={self.profile_name}")

        options.binary_location = self.chrome_path

        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--remote-debugging-port={self.debug_port}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except ImportError:
            service = Service()

        self.driver = webdriver.Chrome(service=service, options=options)
        self._setup_cdp_network_capture()
        self._inject_stealth_scripts()

    def _setup_cdp_network_capture(self):
        """Setup CDP network capture."""
        self._captured_requests = []
        self.driver.execute_cdp_cmd("Network.enable", {})

        intercept_js = """
        window.__ve3_captured_tokens__ = [];

        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            const [url, options] = args;
            if (url && url.includes('aisandbox-pa.googleapis.com') && url.includes('flowMedia')) {
                const headers = options?.headers || {};
                const auth = headers['Authorization'] || headers['authorization'];
                if (auth && auth.startsWith('Bearer ')) {
                    window.__ve3_captured_tokens__.push({
                        token: auth.substring(7),
                        url: url,
                        timestamp: Date.now()
                    });
                }
            }
            return originalFetch.apply(this, args);
        };

        const originalXHROpen = XMLHttpRequest.prototype.open;
        const originalXHRSetHeader = XMLHttpRequest.prototype.setRequestHeader;

        XMLHttpRequest.prototype.open = function(method, url) {
            this.__ve3_url__ = url;
            return originalXHROpen.apply(this, arguments);
        };

        XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
            if (this.__ve3_url__ &&
                this.__ve3_url__.includes('aisandbox-pa.googleapis.com') &&
                this.__ve3_url__.includes('flowMedia') &&
                (name.toLowerCase() === 'authorization') &&
                value.startsWith('Bearer ')) {
                window.__ve3_captured_tokens__.push({
                    token: value.substring(7),
                    url: this.__ve3_url__,
                    timestamp: Date.now()
                });
            }
            return originalXHRSetHeader.apply(this, arguments);
        };
        """
        try:
            self.driver.execute_script(intercept_js)
        except Exception:
            pass

    def _inject_stealth_scripts(self):
        """Inject JavaScript to hide automation fingerprints."""
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });

        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ];
                plugins.length = 3;
                return plugins;
            }
        });

        Object.defineProperty(navigator, 'languages', {
            get: () => ['vi-VN', 'vi', 'en-US', 'en']
        });

        if (!window.chrome) {
            window.chrome = {};
        }
        window.chrome.runtime = window.chrome.runtime || {};
        window.chrome.loadTimes = function() {};
        window.chrome.csi = function() {};
        window.chrome.app = window.chrome.app || { isInstalled: false };
        """
        try:
            self.driver.execute_script(stealth_js)
        except Exception:
            pass

    def _extract_token_from_logs(self) -> Tuple[Optional[str], Optional[str]]:
        """Extract Bearer Token từ JavaScript captured tokens."""
        try:
            tokens = self.driver.execute_script("return window.__ve3_captured_tokens__ || [];")

            if tokens and len(tokens) > 0:
                latest = tokens[-1]
                self.bearer_token = latest.get("token")
                url = latest.get("url", "")

                if "/projects/" in url:
                    parts = url.split("/projects/")[1]
                    self.project_id = parts.split("/")[0]

                if self.bearer_token:
                    return self.bearer_token, self.project_id

        except Exception:
            pass

        return None, None

    def _trigger_image_generation(self):
        """Trigger một request tạo ảnh để capture token."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            time.sleep(3)

            selectors = [
                "button[aria-label*='Generate']",
                "button[aria-label*='Create']",
                "button:contains('Generate')",
                "[data-test='generate-button']",
                ".generate-button",
                "button.primary",
            ]

            for selector in selectors:
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    element.click()
                    return True
                except:
                    continue

            try:
                textarea = self.driver.find_element(By.TAG_NAME, "textarea")
                textarea.send_keys("test image for token extraction")
                textarea.submit()
                return True
            except:
                pass

            return False

        except Exception as e:
            print(f"Error triggering generation: {e}")
            return False

    def extract_token(self, callback=None) -> Tuple[Optional[str], Optional[str], str]:
        """
        Mở Chrome và lấy Bearer Token.

        Args:
            callback: Function để cập nhật progress (optional)

        Returns:
            Tuple[bearer_token, project_id, error_message]
        """
        error = ""

        try:
            if callback:
                callback("Đang khởi động Chrome...")

            self._create_driver()

            if callback:
                callback("Đang mở Google Flow...")

            self.driver.get(self.FLOW_URL)
            time.sleep(5)

            self._setup_cdp_network_capture()
            self._inject_stealth_scripts()

            if callback:
                callback("Đang chờ đăng nhập (nếu cần)...")

            current_url = self.driver.current_url
            if "accounts.google.com" in current_url:
                if callback:
                    callback("Vui lòng đăng nhập Google trong cửa sổ Chrome...")

                for _ in range(120):
                    time.sleep(1)
                    if "labs.google" in self.driver.current_url:
                        break
                else:
                    return None, None, "Timeout waiting for login"

            if callback:
                callback("Đang capture token...")

            start_time = time.time()
            while time.time() - start_time < 10:
                token, project_id = self._extract_token_from_logs()
                if token:
                    if callback:
                        callback("Đã lấy được token!")
                    return token, project_id, ""
                time.sleep(1)

            if callback:
                callback("Đang trigger request để lấy token...")

            self._trigger_image_generation()

            start_time = time.time()
            while time.time() - start_time < self.timeout:
                token, project_id = self._extract_token_from_logs()
                if token:
                    if callback:
                        callback("Đã lấy được token!")
                    return token, project_id, ""
                time.sleep(1)

            error = "Không thể capture được token. Thử tạo một ảnh thủ công trên trang Flow."

        except ImportError as e:
            error = f"Thiếu thư viện: {e}. Chạy: pip install selenium webdriver-manager"
        except Exception as e:
            error = f"Lỗi: {str(e)}"
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass

        return None, None, error

    def extract_token_async(self, callback=None, on_complete=None):
        """Lấy token trong background thread."""
        def worker():
            token, project_id, error = self.extract_token(callback)
            if on_complete:
                on_complete(token, project_id, error)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread


if __name__ == "__main__":
    import sys

    print("Chrome Token Extractor Test")
    print("=" * 50)

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    profile_path = r"C:\Users\admin\AppData\Local\Google\Chrome\User Data\Profile 2"

    if len(sys.argv) >= 3:
        chrome_path = sys.argv[1]
        profile_path = sys.argv[2]

    print(f"Chrome: {chrome_path}")
    print(f"Profile: {profile_path}")

    def progress(msg):
        print(f"[Progress] {msg}")

    extractor = ChromeTokenExtractor(
        chrome_path=chrome_path,
        profile_path=profile_path,
        headless=False
    )

    token, project_id, error = extractor.extract_token(callback=progress)

    if token:
        print(f"\nSuccess!")
        print(f"Token: {token[:50]}...")
        print(f"Project ID: {project_id}")
    else:
        print(f"\nFailed: {error}")
