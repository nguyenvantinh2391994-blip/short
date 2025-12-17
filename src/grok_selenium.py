"""
Grok Selenium Automation - Hỗ trợ chạy ẩn (headless)
Sử dụng Selenium để điều khiển browser thay vì PyAutoGUI
"""

import time
import os
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from rich.console import Console

console = Console()


@dataclass
class GrokVideoResult:
    """Kết quả tạo video"""
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


class GrokSeleniumAutomation:
    """Grok Automation sử dụng Selenium - hỗ trợ chạy ẩn"""

    GROK_IMAGINE_URL = "https://grok.com/imagine"

    def __init__(
        self,
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = True,
        on_log: Optional[Callable[[str, str], None]] = None
    ):
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.headless = headless
        self.on_log = on_log
        self.driver: Optional[webdriver.Chrome] = None

    def log(self, msg: str, level: str = "info"):
        """Log message"""
        if self.on_log:
            self.on_log(msg, level)
        console.print(f"[cyan]{msg}[/]")

    def log_ok(self, msg: str):
        if self.on_log:
            self.on_log(msg, "success")
        console.print(f"[green]   ✓ {msg}[/]")

    def log_err(self, msg: str):
        if self.on_log:
            self.on_log(msg, "error")
        console.print(f"[red]   ✗ {msg}[/]")

    def log_warn(self, msg: str):
        if self.on_log:
            self.on_log(msg, "warning")
        console.print(f"[yellow]   ⚠ {msg}[/]")

    def setup_driver(self) -> bool:
        """Setup Chrome driver"""
        try:
            self.log("Đang khởi tạo Chrome driver...")
            options = Options()

            # Headless mode
            if self.headless:
                options.add_argument("--headless=new")
                self.log("   Chế độ ẩn (headless) đã bật")
            else:
                self.log("   Chế độ hiện browser")

            # Basic options
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--remote-debugging-port=0")  # Random port

            # Hide automation
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            # Profile path - Xử lý đúng format
            if self.profile_path:
                profile = Path(self.profile_path)
                self.log(f"   Profile path: {profile}")

                if profile.exists():
                    # Kiểm tra xem đây là User Data dir hay Profile dir
                    if (profile / "Default").exists() or (profile / "Local State").exists():
                        # Đây là User Data directory
                        options.add_argument(f"--user-data-dir={profile}")
                        self.log(f"   User data dir: {profile}")
                    else:
                        # Đây là Profile directory (vd: Profile 1)
                        options.add_argument(f"--user-data-dir={profile.parent}")
                        options.add_argument(f"--profile-directory={profile.name}")
                        self.log(f"   User data dir: {profile.parent}")
                        self.log(f"   Profile dir: {profile.name}")
                else:
                    self.log_warn(f"   Profile không tồn tại: {profile}")

            # Chrome binary path
            if self.chrome_path and Path(self.chrome_path).exists():
                options.binary_location = self.chrome_path
                self.log(f"   Chrome path: {self.chrome_path}")

            # Setup driver
            self.log("   Đang download/kiểm tra ChromeDriver...")
            service = Service(ChromeDriverManager().install())

            self.log("   Đang khởi động Chrome...")
            self.driver = webdriver.Chrome(service=service, options=options)

            # Hide webdriver flag
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            self.log_ok("Đã khởi tạo Chrome driver thành công!")
            return True

        except Exception as e:
            self.log_err(f"Lỗi khởi tạo driver: {e}")
            import traceback
            self.log_err(traceback.format_exc())
            return False

    def close_driver(self):
        """Close driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def navigate_to_grok(self) -> bool:
        """Navigate to Grok Imagine"""
        try:
            self.driver.get(self.GROK_IMAGINE_URL)
            time.sleep(5)  # Wait for page load

            # Check if logged in
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true'], .ProseMirror"))
                )
                self.log_ok("Đã vào trang Grok Imagine")
                return True
            except TimeoutException:
                self.log_warn("Có thể chưa đăng nhập Grok")
                return True  # Continue anyway

        except Exception as e:
            self.log_err(f"Lỗi truy cập Grok: {e}")
            return False

    def input_prompt(self, prompt: str) -> bool:
        """Nhập prompt vào ô input bằng JavaScript"""
        if not prompt:
            return True

        try:
            # Sử dụng JavaScript để nhập prompt
            js_code = f'''
            (function() {{
                // Tìm ô nhập
                var el = document.querySelector('.ProseMirror') ||
                         document.querySelector('div[contenteditable="true"]') ||
                         document.querySelector('p[data-placeholder]');
                if (el) {{
                    el.focus();
                    el.innerHTML = '<p>{prompt}</p>';
                    // Trigger input event
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }})();
            '''

            result = self.driver.execute_script(js_code)

            if result:
                self.log_ok(f"Đã nhập prompt: {prompt[:30]}...")
                return True
            else:
                self.log_warn("Không tìm thấy ô nhập prompt")
                return False

        except Exception as e:
            self.log_err(f"Lỗi nhập prompt: {e}")
            return False

    def upload_image(self, image_path: str) -> bool:
        """Upload ảnh bằng JavaScript + file input"""
        try:
            image_path = Path(image_path).absolute()
            if not image_path.exists():
                self.log_err(f"Không tìm thấy ảnh: {image_path}")
                return False

            # Click nút đính kèm bằng JS
            js_attach = '''
            (function() {
                var btns = document.querySelectorAll('button');
                for (var b of btns) {
                    var label = b.getAttribute('aria-label') || '';
                    if (label.includes('Đính kèm') || label.includes('Attach')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            })();
            '''
            self.driver.execute_script(js_attach)
            time.sleep(1)

            # Click menu Tải lên bằng JS
            js_upload = '''
            (function() {
                var items = document.querySelectorAll('div[role="menuitem"]');
                for (var item of items) {
                    var text = item.textContent || '';
                    if (text.includes('Tải lên') || text.includes('Upload')) {
                        item.click();
                        return true;
                    }
                }
                return false;
            })();
            '''
            self.driver.execute_script(js_upload)
            time.sleep(1)

            # Tìm file input và gửi file
            file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            file_input.send_keys(str(image_path))
            time.sleep(2)

            self.log_ok(f"Đã upload: {image_path.name}")
            return True

        except Exception as e:
            self.log_err(f"Lỗi upload ảnh: {e}")
            return False

    def submit_and_wait(self, timeout: int = 120) -> bool:
        """Submit và chờ video tạo xong bằng JavaScript"""
        try:
            # Không cần submit nữa vì đã upload ảnh rồi
            # Grok tự động tạo video sau khi upload
            self.log("Đang chờ video được tạo...")

            # Wait for video/download button
            start_time = time.time()

            while time.time() - start_time < timeout:
                elapsed = int(time.time() - start_time)

                # Check bằng JavaScript
                js_check = '''
                (function() {
                    // Check download button
                    var dlBtn = document.querySelector('button[aria-label="Tải xuống"]') ||
                                document.querySelector('button[aria-label="Download"]');
                    if (dlBtn) return 'download_ready';

                    // Check video element
                    var videos = document.querySelectorAll('video');
                    if (videos.length > 0) return 'video_found';

                    // Check nút Làm lại (done)
                    var btns = document.querySelectorAll('button');
                    for (var b of btns) {
                        var text = b.textContent || '';
                        if (text.includes('Làm lại') || text.includes('Redo')) {
                            return 'done';
                        }
                    }

                    return 'waiting';
                })();
                '''

                status = self.driver.execute_script(js_check)

                if status in ['download_ready', 'video_found', 'done']:
                    self.log_ok(f"Video sẵn sàng! ({elapsed}s) - {status}")
                    return True

                if elapsed % 15 == 0 and elapsed > 0:
                    self.log(f"   Đã chờ {elapsed}s...")

                time.sleep(3)

            self.log_warn(f"Timeout sau {timeout}s")
            return False

        except Exception as e:
            self.log_err(f"Lỗi submit: {e}")
            return False

    def download_video(self, output_path: str) -> bool:
        """Download video bằng JavaScript lấy URL + requests download"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Lấy video URL bằng JavaScript
            js_get_url = '''
            (function() {
                var video = document.querySelector('video');
                if (video && video.src) {
                    return video.src;
                }
                // Tìm trong source
                var source = document.querySelector('video source');
                if (source && source.src) {
                    return source.src;
                }
                return null;
            })();
            '''

            video_url = self.driver.execute_script(js_get_url)

            if video_url:
                self.log(f"   Tìm thấy video URL, đang download...")

                # Download video using requests
                import requests
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }

                # Get cookies from selenium
                cookies = {c['name']: c['value'] for c in self.driver.get_cookies()}

                response = requests.get(video_url, headers=headers, cookies=cookies, stream=True)

                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    self.log_ok(f"Đã lưu: {output_path}")
                    return True
                else:
                    self.log_warn(f"Download failed: HTTP {response.status_code}")

            # Fallback: click download button bằng JS
            self.log("   Thử click nút download...")
            js_click_download = '''
            document.querySelector('button[aria-label="Tải xuống"]').dispatchEvent(
                new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
            );
            '''
            self.driver.execute_script(js_click_download)
            time.sleep(3)

            self.log_ok("Đã click download button")
            return True

        except Exception as e:
            self.log_err(f"Lỗi download: {e}")
            return False

    def verify_video_file(self, file_path: str, min_size_kb: int = 100) -> bool:
        """Kiểm tra file video hợp lệ"""
        file_path = Path(file_path)

        if not file_path.exists():
            return False

        file_size = file_path.stat().st_size
        if file_size < min_size_kb * 1024:
            return False

        try:
            with open(file_path, "rb") as f:
                header = f.read(12)
                if b"ftyp" in header:
                    return True
        except:
            pass

        return False

    def create_video(
        self,
        image_path: str,
        prompt: str = "",
        output_path: str = "",
        product_code: str = ""
    ) -> GrokVideoResult:
        """Tạo video từ ảnh"""

        try:
            # Setup driver if not exists
            if not self.driver:
                if not self.setup_driver():
                    return GrokVideoResult(False, error="Không thể khởi tạo browser")

            # Navigate to Grok
            self.log("1. Mở trang Grok Imagine...")
            if not self.navigate_to_grok():
                return GrokVideoResult(False, error="Không thể truy cập Grok")

            # Input prompt
            if prompt:
                self.log(f"2. Nhập prompt...")
                self.input_prompt(prompt)

            # Upload image
            self.log(f"3. Upload ảnh: {Path(image_path).name}")
            if not self.upload_image(image_path):
                return GrokVideoResult(False, error="Không thể upload ảnh")

            # Submit and wait
            self.log("4. Gửi yêu cầu và chờ video...")
            if not self.submit_and_wait(timeout=120):
                return GrokVideoResult(False, error="Timeout chờ video")

            # Wait additional time
            self.log("   Chờ thêm 15s...")
            time.sleep(15)

            # Download
            self.log("5. Download video...")
            if output_path:
                self.download_video(output_path)

                # Verify
                if self.verify_video_file(output_path):
                    self.log_ok(f"Video hợp lệ: {output_path}")
                    return GrokVideoResult(True, video_path=output_path)
                else:
                    self.log_warn("File video không hợp lệ")
                    return GrokVideoResult(False, error="File video không hợp lệ")

            return GrokVideoResult(True, video_path="Downloads")

        except Exception as e:
            self.log_err(f"Exception: {e}")
            return GrokVideoResult(False, error=str(e))

    def create_video_batch(
        self,
        tasks: List[dict],
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> List[GrokVideoResult]:
        """Tạo nhiều video"""
        results = []
        total = len(tasks)

        try:
            # Setup driver once
            if not self.driver:
                if not self.setup_driver():
                    return [GrokVideoResult(False, error="Không thể khởi tạo browser")] * total

            for i, task in enumerate(tasks):
                if on_progress:
                    on_progress(i, total, f"Đang xử lý: {task.get('code', '')}")

                self.log(f"\n===== [{i+1}/{total}] Mã: {task.get('code', '')} =====")

                result = self.create_video(
                    image_path=task.get("image", ""),
                    prompt=task.get("prompt", ""),
                    output_path=task.get("output", ""),
                    product_code=task.get("code", "")
                )
                results.append(result)

                # Open new tab for next video
                if i < total - 1:
                    self.driver.execute_script("window.open('');")
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    time.sleep(1)

            if on_progress:
                on_progress(total, total, "Hoàn thành")

        finally:
            self.close_driver()

        return results
