"""
Grok Selenium Automation
Sử dụng Chrome đã cài trên máy với cách mở đơn giản (subprocess + remote debugging)
"""

import time
import os
import subprocess
import socket
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

# Chrome paths mặc định
DEFAULT_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
]

# Default Chrome User Data dir
DEFAULT_USER_DATA_DIRS = [
    r"C:\Users\{user}\AppData\Local\Google\Chrome\User Data",
    "~/.config/google-chrome",
    "~/Library/Application Support/Google/Chrome"
]


def find_free_port(start_port: int = 9222) -> int:
    """Tìm port trống để dùng cho remote debugging"""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return start_port


def get_default_user_data_dir() -> str:
    """Lấy thư mục User Data mặc định của Chrome"""
    import getpass
    user = getpass.getuser()

    for path_template in DEFAULT_USER_DATA_DIRS:
        path = path_template.format(user=user)
        path = os.path.expanduser(path)
        if os.path.exists(path):
            return path

    # Fallback
    return os.path.expanduser(DEFAULT_USER_DATA_DIRS[0].format(user=user))


@dataclass
class GrokVideoResult:
    """Kết quả tạo video"""
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


class GrokSeleniumAutomation:
    """Grok Automation sử dụng Selenium với cách mở Chrome đơn giản (subprocess + remote debugging)"""

    GROK_IMAGINE_URL = "https://grok.com/imagine"

    def __init__(
        self,
        chrome_path: str = None,
        profile_name: str = None,  # Tên profile Chrome, ví dụ "Profile 5"
        user_data_dir: str = None,  # Thư mục User Data của Chrome
        headless: bool = True,
        on_log: Optional[Callable[[str, str], None]] = None
    ):
        self.chrome_path = chrome_path
        self.profile_name = profile_name or "Default"
        self.user_data_dir = user_data_dir or get_default_user_data_dir()
        self.headless = headless
        self.on_log = on_log
        self.driver = None
        self.chrome_process = None  # Process Chrome được mở bằng subprocess
        self.debug_port = None  # Port remote debugging
        self._captured_video_url = None

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

    def _find_chrome_path(self) -> Optional[str]:
        """Tìm Chrome executable trên máy"""
        # Ưu tiên chrome_path được set
        if self.chrome_path and os.path.exists(self.chrome_path):
            return self.chrome_path

        # Tìm trong các path mặc định
        for path in DEFAULT_CHROME_PATHS:
            if os.path.exists(path):
                return path

        return None

    def _launch_chrome_subprocess(self) -> bool:
        """Mở Chrome bằng subprocess (như Windows Run) với remote debugging"""
        try:
            chrome_exe = self._find_chrome_path()
            if not chrome_exe:
                self.log_err("Không tìm thấy Chrome!")
                return False

            # Tìm port trống
            self.debug_port = find_free_port()

            # Build command - đơn giản như Windows Run
            cmd_parts = [
                f'"{chrome_exe}"',
                f'--remote-debugging-port={self.debug_port}',
                f'--profile-directory="{self.profile_name}"',
            ]

            # Thêm window size nếu cần
            if self.headless:
                cmd_parts.append('--window-size=400,300')
                cmd_parts.append('--window-position=-1000,-1000')  # Ẩn ra ngoài màn hình
            else:
                cmd_parts.append('--window-size=1200,800')

            cmd = ' '.join(cmd_parts)
            self.log(f"   Lệnh: {cmd}")

            # Mở Chrome bằng subprocess
            self.chrome_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.log(f"   Chrome đã mở (PID: {self.chrome_process.pid})")

            # Đợi Chrome khởi động
            time.sleep(3)
            return True

        except Exception as e:
            self.log_err(f"Lỗi mở Chrome subprocess: {e}")
            return False

    def setup_driver(self, download_dir: str = None, max_retries: int = 3) -> bool:
        """Setup Chrome driver - Dùng subprocess mở Chrome + Selenium connect vào"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.log(f"Thử lại lần {attempt + 1}...")
                    time.sleep(2)

                self.log("Đang khởi tạo Chrome...")
                self.log(f"   Chrome: {self._find_chrome_path()}")
                self.log(f"   Profile: {self.profile_name}")

                # Bước 1: Mở Chrome bằng subprocess
                if not self._launch_chrome_subprocess():
                    raise Exception("Không thể mở Chrome")

                # Bước 2: Selenium connect vào Chrome đang chạy
                self.log(f"   Connect vào Chrome (port {self.debug_port})...")

                options = Options()
                # CHỈ CẦN 1 DÒNG NÀY - connect vào Chrome đang chạy
                options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.debug_port}")

                # Download preferences (nếu cần)
                if download_dir:
                    self.download_dir = download_dir

                # Tải ChromeDriver và connect
                self.log("   Đang tải ChromeDriver...")
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)

                self.log_ok("Chrome đã sẵn sàng!")
                return True

            except Exception as e:
                self.log_err(f"Lỗi lần {attempt + 1}: {e}")
                self._cleanup_chrome()

                if attempt == max_retries - 1:
                    import traceback
                    self.log_err(traceback.format_exc())
                    return False

        return False

    def _cleanup_chrome(self):
        """Dọn dẹp Chrome process và driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

        if self.chrome_process:
            try:
                self.chrome_process.terminate()
            except:
                pass
            self.chrome_process = None

    def close_driver(self):
        """Close driver và Chrome process"""
        self._cleanup_chrome()

    def navigate_to_grok(self) -> bool:
        """Navigate to Grok Imagine"""
        try:
            self.driver.get(self.GROK_IMAGINE_URL)
            time.sleep(3)

            # Cài đặt fetch hook để bắt video URL
            self.install_video_hook()

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

    def install_video_hook(self):
        """Cài đặt fetch hook để tự động bắt video URL khi API trả về"""
        js_hook = '''
        (function() {
            if (window._grokVideoHook) return; // Đã cài rồi
            window._grokVideoHook = true;
            window._capturedVideoUrl = null;
            window._videoReady = false;

            const origFetch = window.fetch;
            window.fetch = function(url, opts) {
                const result = origFetch.apply(this, arguments);

                result.then(async res => {
                    try {
                        const cloned = res.clone();
                        const text = await cloned.text();

                        // Tìm video URL pattern của Grok: assets.grok.com/.../generated_video.mp4
                        const patterns = [
                            /https:\/\/assets\.grok\.com\/[^"'\s]+generated_video\.mp4[^"'\s]*/gi,
                            /https:\/\/assets\.grok\.com\/[^"'\s]+\.mp4[^"'\s]*/gi,
                            /"url":\s*"([^"]+\.mp4[^"]*)"/gi,
                            /"videoUrl":\s*"([^"]+)"/gi
                        ];

                        for (const pattern of patterns) {
                            const matches = text.matchAll(pattern);
                            for (const match of matches) {
                                let videoUrl = match[1] || match[0];
                                // Clean up URL
                                videoUrl = videoUrl.replace(/["\s]/g, '');
                                if (videoUrl && videoUrl.includes('.mp4')) {
                                    console.log('🎬 Grok Hook: Video URL!', videoUrl);
                                    window._capturedVideoUrl = videoUrl;
                                    window._videoReady = true;
                                }
                            }
                        }
                    } catch(e) {}
                }).catch(e => {});

                return result;
            };

            console.log('✅ Grok Video Hook đã cài đặt');
        })();
        '''
        try:
            self.driver.execute_script(js_hook)
            self.log("   Đã cài đặt video hook")
        except:
            pass

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
        """Upload ảnh - có retry cho headless mode"""
        try:
            image_path = Path(image_path).absolute()
            if not image_path.exists():
                self.log_err(f"Không tìm thấy ảnh: {image_path}")
                return False

            current_url = self.driver.current_url
            self.log(f"   URL trước upload: {current_url}")

            # Thử upload tối đa 3 lần (headless có thể cần retry)
            for attempt in range(3):
                if attempt > 0:
                    self.log(f"   Thử lại upload lần {attempt + 1}...")
                    time.sleep(2)
                    # Refresh nếu cần
                    if attempt == 2:
                        self.driver.refresh()
                        time.sleep(3)

                try:
                    # Click nút đính kèm
                    js_attach = '''
                    (function() {
                        var btns = document.querySelectorAll('button');
                        for (var b of btns) {
                            var label = b.getAttribute('aria-label') || '';
                            if (label.includes('Đính kèm') || label.includes('Attach')) {
                                b.click();
                                return 'clicked';
                            }
                        }
                        return 'not_found';
                    })();
                    '''
                    attach_result = self.driver.execute_script(js_attach)
                    self.log(f"   Attach button: {attach_result}")
                    time.sleep(1.5)  # Chờ menu mở

                    # Click menu Tải lên
                    js_upload = '''
                    (function() {
                        var items = document.querySelectorAll('div[role="menuitem"]');
                        for (var item of items) {
                            var text = item.textContent || '';
                            if (text.includes('Tải lên') || text.includes('Upload')) {
                                item.click();
                                return 'clicked';
                            }
                        }
                        return 'not_found';
                    })();
                    '''
                    upload_result = self.driver.execute_script(js_upload)
                    self.log(f"   Upload menu: {upload_result}")
                    time.sleep(1.5)  # Chờ file input xuất hiện

                    # Chờ file input với timeout
                    file_input = None
                    for wait in range(10):  # Chờ tối đa 10s
                        try:
                            file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                            if file_input:
                                break
                        except:
                            pass
                        time.sleep(1)

                    if not file_input:
                        self.log_warn("Không tìm thấy file input, thử lại...")
                        continue

                    # Gửi file
                    file_input.send_keys(str(image_path))
                    self.log_ok(f"Đã upload: {image_path.name}")

                    # Chờ redirect sang /imagine/post/
                    self.log("   Chờ redirect sang trang video...")
                    for i in range(30):
                        time.sleep(1)
                        new_url = self.driver.current_url
                        if '/imagine/post/' in new_url:
                            self.log_ok(f"   Đã redirect: {new_url}")
                            self.install_video_hook()
                            time.sleep(2)
                            return True
                        if i % 5 == 0 and i > 0:
                            self.log(f"   Chờ redirect... {i}s")

                    self.log_warn("Không thấy redirect, tiếp tục...")
                    return True

                except Exception as e:
                    self.log_warn(f"Lỗi lần {attempt + 1}: {e}")
                    if attempt == 2:
                        raise

            return False

        except Exception as e:
            self.log_err(f"Lỗi upload ảnh: {e}")
            return False

    def submit_and_wait(self, timeout: int = 90) -> bool:
        """Submit và chờ video tạo xong
        Logic:
        1. Nếu thấy % (0%-100%) = đang tạo video
        2. Nếu không thấy % và thấy icon film = video xong
        3. Chờ thêm 10s sau khi xong để đảm bảo
        """
        try:
            self.log("Đang chờ video được tạo (tối đa 90s)...")
            self.log("   - Đang tạo: có % tiến độ (0%-100%)")
            self.log("   - Đã xong: không có %, có icon film")
            start_time = time.time()

            while time.time() - start_time < timeout:
                elapsed = int(time.time() - start_time)

                # Check tiến độ và icon film
                js_check = '''
                // 1. Check xem có đang hiện % không (đang tạo video)
                var progressDiv = document.querySelector('div.tabular-nums');
                if (progressDiv) {
                    var text = progressDiv.textContent || '';
                    if (text.includes('%')) {
                        return 'progress|' + text.trim();
                    }
                }

                // 2. Không có % -> check icon film (class: lucide lucide-film size-4)
                var filmIcon = document.querySelector('svg.lucide-film');
                if (filmIcon) {
                    return 'film_ready|';
                }

                // 3. Check video src (backup)
                var video = document.querySelector('#sd-video');
                if (video && video.src && video.src.includes('.mp4')) {
                    return 'video_src|' + video.src;
                }

                return 'waiting|';
                '''

                try:
                    result = self.driver.execute_script(js_check)

                    if result and isinstance(result, str):
                        parts = result.split('|')
                        status = parts[0]
                        data = parts[1] if len(parts) > 1 else ''

                        # Log mỗi 5s hoặc khi có thay đổi
                        if elapsed % 5 == 0:
                            if status == 'progress':
                                self.log(f"   [{elapsed}s] Đang tạo: {data}")
                            else:
                                self.log(f"   [{elapsed}s] {status}")

                        if status == 'film_ready':
                            self.log_ok(f"Thấy icon film - Video đã xong! ({elapsed}s)")
                            self.log("   Chờ thêm 10s để video load hoàn toàn...")
                            time.sleep(10)
                            return True
                        elif status == 'video_src':
                            self.log_ok(f"Thấy video src! ({elapsed}s)")
                            self._captured_video_url = data
                            time.sleep(5)
                            return True
                        # progress hoặc waiting -> tiếp tục chờ
                    else:
                        if elapsed % 10 == 0:
                            self.log(f"   [{elapsed}s] JS result: {result}")

                except Exception as e:
                    if elapsed % 10 == 0:
                        self.log(f"   [{elapsed}s] JS error: {e}")

                time.sleep(2)

            self.log_warn(f"Timeout sau {timeout}s")
            return False

        except Exception as e:
            self.log_err(f"Lỗi chờ video: {e}")
            return False

    def download_video(self, output_path: str) -> bool:
        """Download video bằng cách click nút Download, thử lại nếu không có file"""
        try:
            import glob
            import shutil

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Các thư mục có thể chứa file download
            possible_dirs = []

            # 1. Download dir được set khi khởi tạo driver
            if hasattr(self, 'download_dir') and self.download_dir:
                possible_dirs.append(self.download_dir)

            # 2. Thư mục Downloads mặc định của hệ thống
            home = Path.home()
            possible_dirs.append(str(home / "Downloads"))
            possible_dirs.append(str(home / "downloads"))

            # 3. Thư mục output (nếu khác)
            possible_dirs.append(str(output_path.parent))

            self.log(f"   Sẽ tìm file mp4 trong: {possible_dirs}")

            # Ghi nhận thời gian trước khi click để lọc file mới
            before_click = time.time()

            js_click = '''
            var svg = document.querySelector('svg.lucide-download');
            if (svg) {
                var btn = svg.closest('button');
                if (btn) {
                    btn.click();
                    return 'clicked';
                }
            }
            var btn2 = document.querySelector('button[aria-label="Download"]');
            if (btn2) {
                btn2.click();
                return 'clicked_aria';
            }
            return 'not_found';
            '''

            # Thử click download tối đa 3 lần
            for attempt in range(3):
                self.log(f"   Click nút download (lần {attempt + 1})...")

                result = self.driver.execute_script(js_click)
                self.log(f"   Click result: {result}")

                if not result or not result.startswith('clicked'):
                    self.log_warn("Không tìm thấy nút download")
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    return False

                self.log_ok("Đã click download!")

                # Chờ file download (tối đa 20s mỗi lần click)
                for i in range(20):
                    time.sleep(1)

                    # Tìm trong tất cả các thư mục có thể
                    for dir_path in possible_dirs:
                        if not os.path.exists(dir_path):
                            continue

                        # Tìm file mp4 mới (sau thời điểm click)
                        files = glob.glob(f"{dir_path}/*.mp4")
                        for f in files:
                            try:
                                # Chỉ lấy file được tạo sau khi click
                                if os.path.getctime(f) > before_click - 5:  # -5s buffer
                                    file_size = os.path.getsize(f)
                                    if file_size > 10000:  # > 10KB
                                        self.log(f"   Tìm thấy: {f} ({file_size} bytes)")
                                        # Move về output_path
                                        shutil.move(f, output_path)
                                        self.log_ok(f"Đã lưu: {output_path}")
                                        return True
                                    elif i > 5:
                                        self.log(f"   File còn nhỏ ({file_size} bytes), chờ...")
                            except:
                                pass

                    if i % 5 == 0 and i > 0:
                        self.log(f"   Chờ file... {i}s")

                # Không thấy file sau 20s, thử click lại
                if attempt < 2:
                    self.log_warn(f"Không thấy file mp4 sau 20s, thử click lại...")
                    before_click = time.time()  # Reset thời gian
                    time.sleep(2)

            self.log_warn("Không tải được file sau 3 lần thử")
            return False

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
            # Reset URL đã bắt được
            self._captured_video_url = None

            # Setup driver if not exists
            if not self.driver:
                # Cấu hình download directory = thư mục output
                download_dir = str(Path(output_path).parent) if output_path else None
                if not self.setup_driver(download_dir=download_dir):
                    return GrokVideoResult(False, error="Không thể khởi tạo browser")

            # Navigate to Grok (sẽ cài hook tự động)
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

            # Submit and wait (90s timeout)
            self.log("4. Chờ video (tối đa 90s)...")
            if not self.submit_and_wait(timeout=90):
                return GrokVideoResult(False, error="Timeout chờ video")

            # Wait thêm 5s để video load hoàn toàn
            time.sleep(5)

            # Download
            self.log("5. Download video...")
            if output_path:
                if self.download_video(output_path):
                    # Verify
                    if self.verify_video_file(output_path):
                        self.log_ok(f"Video hợp lệ: {output_path}")
                        return GrokVideoResult(True, video_path=output_path)
                    else:
                        self.log_warn("File video không hợp lệ hoặc chưa download xong")
                        return GrokVideoResult(False, error="File video không hợp lệ")
                else:
                    return GrokVideoResult(False, error="Không thể download video")

            return GrokVideoResult(True, video_path="Downloads")

        except Exception as e:
            self.log_err(f"Exception: {e}")
            return GrokVideoResult(False, error=str(e))

    def reset_video_hook(self):
        """Reset trạng thái hook để chuẩn bị cho video mới"""
        self._captured_video_url = None
        if self.driver:
            try:
                self.driver.execute_script('''
                    window._capturedVideoUrl = null;
                    window._videoReady = false;
                ''')
            except:
                pass

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

                # Reset hook trước mỗi video
                self.reset_video_hook()

                result = self.create_video(
                    image_path=task.get("image", ""),
                    prompt=task.get("prompt", ""),
                    output_path=task.get("output", ""),
                    product_code=task.get("code", "")
                )
                results.append(result)

                # Open new tab for next video
                if i < total - 1:
                    self.log("   Mở tab mới...")
                    self.driver.execute_script("window.open('');")
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    time.sleep(2)

            if on_progress:
                on_progress(total, total, "Hoàn thành")

        finally:
            self.close_driver()

        return results
