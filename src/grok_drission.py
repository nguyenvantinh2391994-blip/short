"""
Grok DrissionPage Automation - Tạo video từ ảnh với Grok
Sử dụng DrissionPage thay cho undetected-chromedriver/Selenium
"""

import time
import os
import glob
import shutil
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass

from rich.console import Console

try:
    from .drission_manager import DrissionManager
except ImportError:
    from drission_manager import DrissionManager

console = Console()


@dataclass
class GrokVideoResult:
    """Kết quả tạo video"""
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


class GrokDrissionAutomation:
    """Grok Automation sử dụng DrissionPage"""

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

        # DrissionManager instance
        self.manager: Optional[DrissionManager] = None
        self.download_dir: Optional[str] = None
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

    def _hide_chrome_window(self):
        """Ẩn Chrome window"""
        if self.manager:
            self.manager._hide_window()
            self._is_hidden = True
            self.log("   Đã ẩn Chrome window")

    def show_chrome_window(self):
        """Hiện Chrome window"""
        if self.manager:
            self.manager.show_window()
            self._is_hidden = False
            self.log("   Đã hiện Chrome window")

    def toggle_chrome_visibility(self):
        """Toggle ẩn/hiện Chrome window"""
        if hasattr(self, '_is_hidden') and self._is_hidden:
            self.show_chrome_window()
        else:
            self._hide_chrome_window()

    def setup_driver(self, download_dir: str = None, max_retries: int = 3) -> bool:
        """Setup DrissionPage browser"""
        try:
            self.log("Đang khởi tạo Chrome với DrissionPage...")

            # Tạo DrissionManager
            self.manager = DrissionManager(
                chrome_path=self.chrome_path,
                profile_path=self.profile_path,
                headless=self.headless,
                on_log=self.on_log,
            )

            if not self.manager.is_available():
                self.log_err("DrissionPage chưa được cài đặt!")
                self.log_err("Chạy: pip install DrissionPage")
                return False

            # Lưu download dir
            if download_dir:
                self.download_dir = download_dir

            # Setup browser
            if not self.manager.setup(download_dir=download_dir, max_retries=max_retries):
                return False

            self.log_ok("Chrome đã sẵn sàng!")
            return True

        except Exception as e:
            self.log_err(f"Lỗi setup: {e}")
            return False

    def close_driver(self):
        """Đóng browser"""
        if self.manager:
            self.manager.close()
            self.manager = None

    def check_rate_limit(self) -> bool:
        """
        Kiểm tra xem có bị rate limit không

        Returns:
            True nếu bị rate limit
        """
        if not self.manager or not self.manager.page:
            return False

        try:
            # Dùng JavaScript để tìm toast rate limit
            js_check = '''
            (function() {
                // Tìm toast error của sonner
                var toasts = document.querySelectorAll('[data-sonner-toast][data-type="error"]');
                for (var toast of toasts) {
                    var text = toast.textContent || toast.innerText || '';
                    if (text.toLowerCase().includes('rate limit')) {
                        return 'RATE_LIMIT:' + text.substring(0, 100);
                    }
                }

                // Backup: tìm bất kỳ element nào có text "rate limit reached"
                var body = document.body.innerText || '';
                if (body.toLowerCase().includes('rate limit reached')) {
                    return 'RATE_LIMIT_TEXT';
                }

                return '';
            })();
            '''

            result = self.manager.run_js_return(js_check)

            if result and str(result).startswith('RATE_LIMIT'):
                self.log_warn(f"Phát hiện Rate Limit! ({result})")
                return True

            return False
        except Exception as e:
            self.log(f"   Lỗi check rate limit: {e}")
            return False

    def navigate_to_grok(self) -> bool:
        """Navigate to Grok Imagine"""
        try:
            self.manager.navigate(self.GROK_IMAGINE_URL, wait=3)

            # Cài đặt fetch hook để bắt video URL
            self.install_video_hook()

            # Check if logged in - tìm ô nhập prompt
            if self.manager.wait_for("div[contenteditable='true'], .ProseMirror", timeout=10):
                self.log_ok("Đã vào trang Grok Imagine")
                return True
            else:
                self.log_warn("Có thể chưa đăng nhập Grok")
                return True  # Continue anyway

        except Exception as e:
            self.log_err(f"Lỗi truy cập Grok: {e}")
            return False

    def install_video_hook(self):
        """Cài đặt fetch hook để tự động bắt video URL"""
        js_hook = '''
        (function() {
            if (window._grokVideoHook) return;
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

                        const patterns = [
                            /https:\\/\\/assets\\.grok\\.com\\/[^"'\\s]+generated_video\\.mp4[^"'\\s]*/gi,
                            /https:\\/\\/assets\\.grok\\.com\\/[^"'\\s]+\\.mp4[^"'\\s]*/gi,
                            /"url":\\s*"([^"]+\\.mp4[^"]*)"/gi,
                            /"videoUrl":\\s*"([^"]+)"/gi
                        ];

                        for (const pattern of patterns) {
                            const matches = text.matchAll(pattern);
                            for (const match of matches) {
                                let videoUrl = match[1] || match[0];
                                videoUrl = videoUrl.replace(/["\\s]/g, '');
                                if (videoUrl && videoUrl.includes('.mp4')) {
                                    console.log('Grok Hook: Video URL!', videoUrl);
                                    window._capturedVideoUrl = videoUrl;
                                    window._videoReady = true;
                                }
                            }
                        }
                    } catch(e) {}
                }).catch(e => {});

                return result;
            };

            console.log('Grok Video Hook installed');
        })();
        '''
        try:
            self.manager.run_js(js_hook)
            self.log("   Đã cài đặt video hook")
        except:
            pass

    def input_prompt(self, prompt: str) -> bool:
        """Nhập prompt vào ô input"""
        if not prompt:
            return True

        try:
            # Escape prompt cho JS
            escaped = prompt.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')

            js_code = f'''
            (function() {{
                var el = document.querySelector('.ProseMirror') ||
                         document.querySelector('div[contenteditable="true"]') ||
                         document.querySelector('p[data-placeholder]');
                if (el) {{
                    el.focus();
                    el.innerHTML = '<p>{escaped}</p>';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }})();
            '''

            result = self.manager.run_js_return(js_code)

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
        """Upload ảnh"""
        try:
            image_path = Path(image_path).absolute()
            if not image_path.exists():
                self.log_err(f"Không tìm thấy ảnh: {image_path}")
                return False

            current_url = self.manager.get_current_url()
            self.log(f"   URL trước upload: {current_url}")

            # Click nút đính kèm
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
            self.manager.run_js(js_attach)
            time.sleep(1)

            # Click menu Tải lên
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
            self.manager.run_js(js_upload)
            time.sleep(1)

            # Tìm file input và upload
            file_input = self.manager.get_element("input[type='file']", timeout=5)
            if file_input:
                file_input.input(str(image_path))
                self.log_ok(f"Đã upload: {image_path.name}")
            else:
                self.log_err("Không tìm thấy file input")
                return False

            # Chờ redirect sang /imagine/post/
            self.log("   Chờ redirect sang trang video...")
            for i in range(30):
                time.sleep(1)
                new_url = self.manager.get_current_url()
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
            self.log_err(f"Lỗi upload ảnh: {e}")
            return False

    def submit_and_wait(self, timeout: int = 90) -> str:
        """
        Submit và chờ video tạo xong

        Returns:
            "OK" nếu video tạo xong
            "RATE_LIMIT" nếu bị rate limit
            "TIMEOUT" nếu hết thời gian
            "ERROR" nếu có lỗi
        """
        try:
            self.log("Đang chờ video được tạo (tối đa 90s)...")
            start_time = time.time()

            while time.time() - start_time < timeout:
                elapsed = int(time.time() - start_time)

                js_check = '''
                (function() {
                    // Check rate limit
                    var toasts = document.querySelectorAll('[data-sonner-toast][data-type="error"]');
                    for (var toast of toasts) {
                        var text = toast.textContent || toast.innerText || '';
                        if (text.toLowerCase().includes('rate limit')) {
                            return 'rate_limit|' + text.substring(0, 50);
                        }
                    }

                    // Check progress %
                    var progressDiv = document.querySelector('div.tabular-nums');
                    if (progressDiv) {
                        var text = progressDiv.textContent || '';
                        if (text.includes('%')) {
                            return 'progress|' + text.trim();
                        }
                    }

                    // Check film icon (video ready)
                    var filmIcon = document.querySelector('svg.lucide-film');
                    if (filmIcon) {
                        return 'film_ready|';
                    }

                    // Check video src
                    var video = document.querySelector('#sd-video');
                    if (video && video.src && video.src.includes('.mp4')) {
                        return 'video_src|' + video.src;
                    }

                    return 'waiting|';
                })();
                '''

                try:
                    result = self.manager.run_js_return(js_check)

                    if result and isinstance(result, str):
                        parts = result.split('|')
                        status = parts[0]
                        data = parts[1] if len(parts) > 1 else ''

                        if elapsed % 5 == 0:
                            if status == 'progress':
                                self.log(f"   [{elapsed}s] Đang tạo: {data}")
                            elif status != 'waiting':
                                self.log(f"   [{elapsed}s] {status}")

                        if status == 'rate_limit':
                            self.log_warn(f"Rate Limit detected! ({data})")
                            return "RATE_LIMIT"

                        if status == 'film_ready':
                            self.log_ok(f"Thấy icon film - Video đã xong! ({elapsed}s)")
                            self.log("   Chờ thêm 10s để video load hoàn toàn...")
                            time.sleep(10)
                            return "OK"
                        elif status == 'video_src':
                            self.log_ok(f"Thấy video src! ({elapsed}s)")
                            self._captured_video_url = data
                            time.sleep(5)
                            return "OK"

                except Exception as e:
                    if elapsed % 10 == 0:
                        self.log(f"   [{elapsed}s] JS error: {e}")

                time.sleep(2)

            self.log_warn(f"Timeout sau {timeout}s")
            if self.check_rate_limit():
                return "RATE_LIMIT"
            return "TIMEOUT"

        except Exception as e:
            self.log_err(f"Lỗi chờ video: {e}")
            return "ERROR"

    def download_video(self, output_path: str) -> bool:
        """Download video bằng cách click nút Download"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Các thư mục có thể chứa file download
            possible_dirs = []
            if self.download_dir:
                possible_dirs.append(self.download_dir)
            home = Path.home()
            possible_dirs.append(str(home / "Downloads"))
            possible_dirs.append(str(output_path.parent))

            self.log(f"   Sẽ tìm file mp4 trong: {possible_dirs}")
            before_click = time.time()

            js_click = '''
            (function() {
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
            })();
            '''

            for attempt in range(3):
                self.log(f"   Click nút download (lần {attempt + 1})...")

                result = self.manager.run_js_return(js_click)
                self.log(f"   Click result: {result}")

                if not result or not str(result).startswith('clicked'):
                    self.log_warn("Không tìm thấy nút download")
                    if attempt < 2:
                        time.sleep(3)
                        continue
                    return False

                self.log_ok("Đã click download!")

                # Chờ file download
                for i in range(20):
                    time.sleep(1)

                    for dir_path in possible_dirs:
                        if not os.path.exists(dir_path):
                            continue

                        files = glob.glob(f"{dir_path}/*.mp4")
                        for f in files:
                            try:
                                if os.path.getctime(f) > before_click - 5:
                                    file_size = os.path.getsize(f)
                                    if file_size > 10000:
                                        self.log(f"   Tìm thấy: {f} ({file_size} bytes)")
                                        shutil.move(f, output_path)
                                        self.log_ok(f"Đã lưu: {output_path}")
                                        return True
                            except:
                                pass

                    if i % 5 == 0 and i > 0:
                        self.log(f"   Chờ file... {i}s")

                if attempt < 2:
                    self.log_warn("Không thấy file mp4 sau 20s, thử click lại...")
                    before_click = time.time()
                    time.sleep(2)

            self.log_warn("Không tải được file sau 3 lần thử")
            return False

        except Exception as e:
            self.log_err(f"Lỗi download: {e}")
            return False

    def close_extra_tabs(self):
        """Đóng tất cả tab thừa"""
        if self.manager:
            self.manager.close_extra_tabs()

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
            self._captured_video_url = None

            # Setup driver nếu chưa có
            if not self.manager or not self.manager.is_running():
                download_dir = str(Path(output_path).parent) if output_path else None
                if not self.setup_driver(download_dir=download_dir):
                    return GrokVideoResult(False, error="Không thể khởi tạo browser")

            # Navigate to Grok
            if not skip_navigate:
                self.log("1. Mở trang Grok Imagine...")
                if not self.navigate_to_grok():
                    return GrokVideoResult(False, error="Không thể truy cập Grok")
            else:
                current_url = self.manager.get_current_url()
                if 'grok.com' not in current_url:
                    self.log(f"1. URL sai ({current_url[:40]}...), navigate về Grok...")
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
            self.log("4. Chờ video (tối đa 90s)...")
            wait_result = self.submit_and_wait(timeout=90)

            if wait_result == "RATE_LIMIT":
                return GrokVideoResult(False, error="RATE_LIMIT")
            elif wait_result != "OK":
                if self.check_rate_limit():
                    return GrokVideoResult(False, error="RATE_LIMIT")
                return GrokVideoResult(False, error=f"Lỗi chờ video: {wait_result}")

            time.sleep(5)

            # Download
            self.log("5. Download video...")
            if output_path:
                if self.download_video(output_path):
                    self.close_extra_tabs()
                    if self.verify_video_file(output_path):
                        self.log_ok(f"Video hợp lệ: {output_path}")
                        return GrokVideoResult(True, video_path=output_path)
                    else:
                        self.log_warn("File video không hợp lệ")
                        return GrokVideoResult(False, error="File video không hợp lệ")
                else:
                    return GrokVideoResult(False, error="Không thể download video")

            self.close_extra_tabs()
            return GrokVideoResult(True, video_path="Downloads")

        except Exception as e:
            self.log_err(f"Exception: {e}")
            return GrokVideoResult(False, error=str(e))

    def reset_video_hook(self):
        """Reset trạng thái hook"""
        self._captured_video_url = None
        if self.manager and self.manager.page:
            try:
                self.manager.run_js('''
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
            if not self.manager or not self.manager.is_running():
                if not self.setup_driver():
                    return [GrokVideoResult(False, error="Không thể khởi tạo browser")] * total

            for i, task in enumerate(tasks):
                if on_progress:
                    on_progress(i, total, f"Đang xử lý: {task.get('code', '')}")

                self.log(f"\n===== [{i+1}/{total}] Mã: {task.get('code', '')} =====")

                self.reset_video_hook()

                result = self.create_video(
                    image_path=task.get("image", ""),
                    prompt=task.get("prompt", ""),
                    output_path=task.get("output", ""),
                    product_code=task.get("code", ""),
                    skip_navigate=(i > 0)
                )
                results.append(result)

                # Quay lại trang Grok Imagine cho video tiếp theo
                if i < total - 1:
                    self.log("   Quay lại trang Grok Imagine...")
                    self.manager.navigate(self.GROK_IMAGINE_URL, wait=3)
                    self.install_video_hook()

            if on_progress:
                on_progress(total, total, "Hoàn thành")

        finally:
            self.close_driver()

        return results


# Alias để dễ import
GrokAutomation = GrokDrissionAutomation
