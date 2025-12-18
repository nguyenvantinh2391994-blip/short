"""
Grok Selenium Automation - Hỗ trợ chạy ẩn (headless)
Sử dụng undetected-chromedriver để tránh bị phát hiện bot
"""

import time
import os
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass

# Sử dụng undetected-chromedriver thay vì selenium thường
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
        self.driver: Optional[uc.Chrome] = None
        self._captured_video_url = None  # URL video bắt được từ hook

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

    def _hide_chrome_window(self):
        """Ẩn Chrome window của tool khỏi taskbar (Windows only)"""
        try:
            import platform
            if platform.system() != 'Windows':
                return

            import ctypes
            from ctypes import wintypes

            # Windows API constants
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080  # Ẩn khỏi taskbar
            WS_EX_APPWINDOW = 0x00040000

            user32 = ctypes.windll.user32

            # Lấy hwnd từ Selenium driver (chỉ ẩn window của tool)
            if hasattr(self, 'driver') and self.driver:
                try:
                    # Lấy title của window hiện tại
                    current_title = self.driver.title

                    def find_chrome_hwnd(hwnd, target_title):
                        if user32.IsWindowVisible(hwnd):
                            length = user32.GetWindowTextLengthW(hwnd)
                            if length > 0:
                                buff = ctypes.create_unicode_buffer(length + 1)
                                user32.GetWindowTextW(hwnd, buff, length + 1)
                                title = buff.value
                                # Chỉ tìm window có title trùng hoặc chứa URL của driver
                                if current_title and current_title in title:
                                    return hwnd
                                # Hoặc window mới mở (title rỗng hoặc "New Tab")
                                if 'New Tab' in title or title == 'about:blank':
                                    return hwnd
                        return None

                    # Tìm hwnd bằng cách enumerate
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.py_object)

                    found_hwnds = []
                    def callback(hwnd, results):
                        if user32.IsWindowVisible(hwnd):
                            length = user32.GetWindowTextLengthW(hwnd)
                            if length > 0:
                                buff = ctypes.create_unicode_buffer(length + 1)
                                user32.GetWindowTextW(hwnd, buff, length + 1)
                                title = buff.value
                                # Chỉ lấy window có chứa URL grok hoặc title trùng
                                if 'grok' in title.lower() or 'imagine' in title.lower():
                                    results.append(hwnd)
                                elif current_title and current_title in title:
                                    results.append(hwnd)
                        return True

                    user32.EnumWindows(WNDENUMPROC(callback), ctypes.py_object(found_hwnds))

                    # Lưu hwnd để có thể show lại sau
                    if found_hwnds:
                        self._chrome_hwnd = found_hwnds[0]

                        # Ẩn window
                        style = user32.GetWindowLongW(self._chrome_hwnd, GWL_EXSTYLE)
                        new_style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
                        user32.SetWindowLongW(self._chrome_hwnd, GWL_EXSTYLE, new_style)
                        user32.SetWindowPos(self._chrome_hwnd, 0, -2000, -2000, 0, 0, 0x0001 | 0x0004)

                        self.log(f"   Đã ẩn Chrome window")
                        self._is_hidden = True

                except Exception as e:
                    self.log(f"   Lỗi ẩn window: {e}")

        except Exception as e:
            self.log(f"   Không thể ẩn Chrome: {e}")

    def show_chrome_window(self):
        """Hiện lại Chrome window"""
        try:
            import platform
            if platform.system() != 'Windows':
                return

            import ctypes
            from ctypes import wintypes

            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            SW_RESTORE = 9
            SW_SHOW = 5
            SW_SHOWNORMAL = 1
            HWND_TOP = 0
            SWP_SHOWWINDOW = 0x0040

            user32 = ctypes.windll.user32

            # Nếu không có hwnd lưu sẵn, tìm lại
            if not hasattr(self, '_chrome_hwnd') or not self._chrome_hwnd:
                # Tìm window của Chrome/Grok
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.py_object)
                found_hwnds = []

                def callback(hwnd, results):
                    if user32.IsWindowVisible(hwnd) or True:  # Tìm cả window ẩn
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value
                            if 'grok' in title.lower() or 'imagine' in title.lower():
                                results.append(hwnd)
                    return True

                user32.EnumWindows(WNDENUMPROC(callback), ctypes.py_object(found_hwnds))
                if found_hwnds:
                    self._chrome_hwnd = found_hwnds[0]

            if hasattr(self, '_chrome_hwnd') and self._chrome_hwnd:
                # Đưa về style bình thường (hiện trên taskbar)
                style = user32.GetWindowLongW(self._chrome_hwnd, GWL_EXSTYLE)
                new_style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
                user32.SetWindowLongW(self._chrome_hwnd, GWL_EXSTYLE, new_style)

                # Restore window nếu bị minimize
                user32.ShowWindow(self._chrome_hwnd, SW_RESTORE)

                # Đưa về vị trí giữa màn hình với kích thước hợp lý
                screen_width = user32.GetSystemMetrics(0)
                screen_height = user32.GetSystemMetrics(1)
                win_width = 1200
                win_height = 800
                x = (screen_width - win_width) // 2
                y = (screen_height - win_height) // 2

                # Di chuyển và resize window
                user32.SetWindowPos(
                    self._chrome_hwnd,
                    HWND_TOP,
                    x, y,
                    win_width, win_height,
                    SWP_SHOWWINDOW
                )

                # Đưa lên foreground
                user32.SetForegroundWindow(self._chrome_hwnd)

                self.log("   Đã hiện Chrome window")
                self._is_hidden = False

        except Exception as e:
            self.log(f"   Lỗi hiện window: {e}")

    def toggle_chrome_visibility(self):
        """Toggle ẩn/hiện Chrome window"""
        if hasattr(self, '_is_hidden') and self._is_hidden:
            self.show_chrome_window()
        else:
            self._hide_chrome_window()

    def setup_driver(self, download_dir: str = None, max_retries: int = 3) -> bool:
        """Setup Chrome driver sử dụng undetected-chromedriver - có retry"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.log(f"Thử lại lần {attempt + 1}...")
                    time.sleep(2)

                self.log("Đang khởi tạo Chrome...")

                # Options cho undetected-chromedriver
                options = uc.ChromeOptions()

                # Tối ưu tốc độ khởi động
                options.add_argument("--no-first-run")
                options.add_argument("--no-default-browser-check")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-popup-blocking")
                options.add_argument("--disable-infobars")
                options.add_argument("--disable-dev-shm-usage")  # Giảm memory issues
                options.add_argument("--disable-gpu")  # Tắt GPU

                # Nếu chạy ẩn: khởi động ngay ở vị trí ngoài màn hình
                if self.headless:
                    options.add_argument("--window-size=800,600")
                    options.add_argument("--window-position=-2000,-2000")  # Ngoài màn hình ngay từ đầu
                else:
                    options.add_argument("--window-size=1920,1080")

                # Download preferences
                if download_dir:
                    self.download_dir = download_dir
                    prefs = {
                        "download.default_directory": download_dir,
                        "download.prompt_for_download": False,
                        "download.directory_upgrade": True,
                        "safebrowsing.enabled": False  # Bỏ scan file
                    }
                    options.add_experimental_option("prefs", prefs)

                # Profile path
                user_data_dir = None
                if self.profile_path:
                    profile = Path(self.profile_path)
                    profile.mkdir(parents=True, exist_ok=True)
                    user_data_dir = str(profile)
                    self.log(f"   Profile: {user_data_dir}")

                # Khởi tạo driver - KHÔNG dùng headless, sẽ giấu bằng cách đẩy ra ngoài màn hình
                self.driver = uc.Chrome(
                    options=options,
                    headless=False,  # Không dùng headless vì hay lỗi
                    user_data_dir=user_data_dir,
                    use_subprocess=True,
                    version_main=None  # Auto detect
                )

                if self.headless:
                    self.log("   Chế độ ẩn")
                    # Ẩn Chrome khỏi taskbar (Windows)
                    self._hide_chrome_window()

                self.log_ok("Chrome đã sẵn sàng!")
                return True

            except Exception as e:
                self.log_err(f"Lỗi lần {attempt + 1}: {e}")
                # Cleanup nếu có
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None

                if attempt == max_retries - 1:
                    import traceback
                    self.log_err(traceback.format_exc())
                    return False

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
            # Dùng JavaScript để đảm bảo navigate trong cùng tab
            self.driver.execute_script(f"window.location.href = '{self.GROK_IMAGINE_URL}';")
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
        """Upload ảnh bằng JavaScript + file input"""
        try:
            image_path = Path(image_path).absolute()
            if not image_path.exists():
                self.log_err(f"Không tìm thấy ảnh: {image_path}")
                return False

            # Lưu URL hiện tại để check redirect
            current_url = self.driver.current_url
            self.log(f"   URL trước upload: {current_url}")

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

            self.log_ok(f"Đã upload: {image_path.name}")

            # Chờ redirect sang /imagine/post/
            self.log("   Chờ redirect sang trang video...")
            for i in range(30):  # Chờ tối đa 30s
                time.sleep(1)
                new_url = self.driver.current_url
                if '/imagine/post/' in new_url:
                    self.log_ok(f"   Đã redirect: {new_url}")
                    # Cài lại hook sau khi redirect
                    self.install_video_hook()
                    time.sleep(2)  # Chờ page load
                    return True
                if i % 5 == 0 and i > 0:
                    self.log(f"   Chờ redirect... {i}s (URL: {new_url[:50]})")

            self.log_warn("Không thấy redirect, tiếp tục...")
            return True

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

    def close_extra_tabs(self):
        """Đóng tất cả tab thừa, chỉ giữ lại 1 tab"""
        try:
            if not self.driver:
                return

            handles = self.driver.window_handles
            if len(handles) > 1:
                self.log(f"   Đóng {len(handles) - 1} tab thừa...")
                # Giữ tab đầu tiên, đóng các tab còn lại
                main_tab = handles[0]
                for handle in handles[1:]:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                # Quay lại tab chính
                self.driver.switch_to.window(main_tab)
        except Exception as e:
            self.log_warn(f"Lỗi đóng tab: {e}")

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
        product_code: str = "",
        skip_navigate: bool = False
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

            # Navigate to Grok (sẽ cài hook tự động) - skip nếu đã ở trang rồi
            if not skip_navigate:
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
                    # Đóng tab thừa (nếu Grok mở tab khi download)
                    self.close_extra_tabs()
                    # Verify
                    if self.verify_video_file(output_path):
                        self.log_ok(f"Video hợp lệ: {output_path}")
                        return GrokVideoResult(True, video_path=output_path)
                    else:
                        self.log_warn("File video không hợp lệ hoặc chưa download xong")
                        return GrokVideoResult(False, error="File video không hợp lệ")
                else:
                    return GrokVideoResult(False, error="Không thể download video")

            # Đóng tab thừa trước khi return
            self.close_extra_tabs()
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

                # Video đầu tiên: navigate bình thường
                # Video tiếp theo: skip navigate vì đã navigate ở cuối vòng trước
                result = self.create_video(
                    image_path=task.get("image", ""),
                    prompt=task.get("prompt", ""),
                    output_path=task.get("output", ""),
                    product_code=task.get("code", ""),
                    skip_navigate=(i > 0)  # Skip nếu không phải video đầu
                )
                results.append(result)

                # Quay lại trang Grok Imagine cho video tiếp theo (cùng tab, dùng JS)
                if i < total - 1:
                    self.log("   Quay lại trang Grok Imagine...")
                    self.driver.execute_script(f"window.location.href = '{self.GROK_IMAGINE_URL}';")
                    time.sleep(3)
                    # Cài lại video hook
                    self.install_video_hook()

            if on_progress:
                on_progress(total, total, "Hoàn thành")

        finally:
            self.close_driver()

        return results
