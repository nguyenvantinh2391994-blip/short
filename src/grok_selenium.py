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

    def setup_driver(self, download_dir: str = None) -> bool:
        """Setup Chrome driver sử dụng undetected-chromedriver"""
        try:
            self.log("Đang khởi tạo Chrome (undetected-chromedriver)...")

            # Options cho undetected-chromedriver
            options = uc.ChromeOptions()

            # Window size
            options.add_argument("--window-size=1920,1080")

            # Download preferences
            if download_dir:
                self.download_dir = download_dir
                prefs = {
                    "download.default_directory": download_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True
                }
                options.add_experimental_option("prefs", prefs)
                self.log(f"   Download dir: {download_dir}")

            # Profile path - dùng thư mục riêng cho automation
            user_data_dir = None
            if self.profile_path:
                profile = Path(self.profile_path)
                self.log(f"   Profile path: {profile}")

                # Tạo thư mục nếu chưa có
                profile.mkdir(parents=True, exist_ok=True)
                user_data_dir = str(profile)
                self.log(f"   User data dir: {user_data_dir}")

            # Headless mode
            if self.headless:
                self.log("   Chế độ ẩn (headless) đã bật")
            else:
                self.log("   Chế độ hiện browser")

            # Khởi tạo driver
            self.log("   Đang khởi động Chrome...")
            self.driver = uc.Chrome(
                options=options,
                headless=self.headless,
                user_data_dir=user_data_dir,
                use_subprocess=True  # Tránh conflict
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

    def submit_and_wait(self, timeout: int = 180) -> bool:
        """Submit và chờ video tạo xong - sử dụng fetch hook + DOM check"""
        try:
            self.log("Đang chờ video được tạo...")
            start_time = time.time()

            while time.time() - start_time < timeout:
                elapsed = int(time.time() - start_time)

                # Check bằng JavaScript - ưu tiên DOM video có mp4, sau đó hook
                js_check = '''
                (function() {
                    // 1. Check video #sd-video có src mp4 (ưu tiên cao nhất)
                    var sdVideo = document.querySelector('#sd-video');
                    if (sdVideo && sdVideo.src && sdVideo.src.includes('.mp4')) {
                        return {status: 'video_found', url: sdVideo.src};
                    }

                    // 2. Check tất cả video elements
                    var videos = document.querySelectorAll('video');
                    for (var v of videos) {
                        var src = v.src || '';
                        if (src.includes('generated_video.mp4') || src.includes('assets.grok.com')) {
                            return {status: 'video_found', url: src};
                        }
                    }

                    // 3. Check từ fetch hook
                    if (window._videoReady && window._capturedVideoUrl) {
                        return {status: 'hook_ready', url: window._capturedVideoUrl};
                    }

                    // 4. Check nút download
                    var dlBtn = document.querySelector('button[aria-label="Tải xuống"]') ||
                                document.querySelector('button[aria-label="Download"]');
                    if (dlBtn) return {status: 'download_ready', url: null};

                    // 5. Check nút Làm lại (done)
                    var btns = document.querySelectorAll('button');
                    for (var b of btns) {
                        var text = b.textContent || '';
                        if (text.includes('Làm lại') || text.includes('Redo')) {
                            return {status: 'done', url: null};
                        }
                    }

                    return {status: 'waiting', url: null};
                })();
                '''

                result = self.driver.execute_script(js_check)
                status = result.get('status', 'waiting') if isinstance(result, dict) else result
                url = result.get('url') if isinstance(result, dict) else None

                if status in ['hook_ready', 'video_found', 'download_ready', 'done']:
                    self.log_ok(f"Video sẵn sàng! ({elapsed}s) - {status}")
                    if url:
                        self._captured_video_url = url
                        self.log(f"   URL: {url[:80]}...")
                    return True

                if elapsed % 10 == 0 and elapsed > 0:
                    self.log(f"   Đã chờ {elapsed}s...")

                time.sleep(2)

            self.log_warn(f"Timeout sau {timeout}s")
            return False

        except Exception as e:
            self.log_err(f"Lỗi chờ video: {e}")
            return False

    def download_video(self, output_path: str) -> bool:
        """Download video - ưu tiên URL từ DOM #sd-video, sau đó blob download"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 1. Lấy URL từ DOM trước (ưu tiên #sd-video)
            js_get_url = '''
            (function() {
                // Ưu tiên #sd-video
                var sdVideo = document.querySelector('#sd-video');
                if (sdVideo && sdVideo.src && sdVideo.src.includes('.mp4')) {
                    return sdVideo.src;
                }

                // Tìm video có generated_video.mp4
                var videos = document.querySelectorAll('video');
                for (var v of videos) {
                    if (v.src && v.src.includes('generated_video.mp4')) {
                        return v.src;
                    }
                }

                // Fallback: video có assets.grok.com
                for (var v of videos) {
                    if (v.src && v.src.includes('assets.grok.com')) {
                        return v.src;
                    }
                }

                // Từ hook
                if (window._capturedVideoUrl) return window._capturedVideoUrl;

                return null;
            })();
            '''
            video_url = self.driver.execute_script(js_get_url)

            # 2. Nếu chưa có, dùng URL đã capture từ submit_and_wait
            if not video_url:
                video_url = getattr(self, '_captured_video_url', None)

            # 3. Download nếu có URL
            if video_url and video_url.startswith('http'):
                self.log(f"   Đang download từ URL...")

                import requests
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://grok.com/'
                }
                cookies = {c['name']: c['value'] for c in self.driver.get_cookies()}

                response = requests.get(video_url, headers=headers, cookies=cookies, stream=True, timeout=60)

                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    self.log_ok(f"Đã lưu: {output_path}")
                    return True
                else:
                    self.log_warn(f"HTTP {response.status_code}, thử cách khác...")

            # 4. Fallback: Click nút download trực tiếp
            self.log("   Thử click nút download...")
            js_click_download = '''
            (function() {
                // Tìm nút download bằng nhiều cách
                var btn = null;

                // 1. Tìm bằng aria-label
                btn = document.querySelector('button[aria-label="Download"]') ||
                      document.querySelector('button[aria-label="Tải xuống"]');

                // 2. Tìm bằng SVG class lucide-download
                if (!btn) {
                    var svg = document.querySelector('svg.lucide-download');
                    if (svg) btn = svg.closest('button');
                }

                // 3. Tìm button chứa text Download
                if (!btn) {
                    var buttons = document.querySelectorAll('button');
                    for (var b of buttons) {
                        if (b.textContent.includes('Download') || b.textContent.includes('Tải')) {
                            btn = b;
                            break;
                        }
                    }
                }

                if (btn) {
                    console.log('Found download button:', btn);
                    btn.click();
                    return {success: true, method: 'button_click'};
                }

                return {success: false, error: 'Button not found'};
            })();
            '''
            click_result = self.driver.execute_script(js_click_download)
            self.log(f"   Click result: {click_result}")

            if click_result and click_result.get('success'):
                self.log_ok("Đã click download button - chờ file...")
                time.sleep(5)  # Chờ download dialog hoặc file

                # Kiểm tra xem file đã được tải chưa
                if output_path.exists() and output_path.stat().st_size > 10000:
                    return True

                # Nếu chưa có file, thử download bằng blob
                self.log("   File chưa có, thử blob download...")

            # 5. Download bằng blob trong JS (backup)
            self.log("   Thử download bằng blob...")
            js_blob_download = '''
            (async function() {
                try {
                    // Ưu tiên #sd-video
                    var video = document.querySelector('#sd-video') || document.querySelector('video');
                    if (!video || !video.src) return {success: false, error: 'No video element'};

                    var src = video.src;
                    if (!src.includes('.mp4')) return {success: false, error: 'No mp4 src'};

                    console.log('Blob downloading:', src);

                    // Fetch video as blob
                    var res = await fetch(src);
                    if (!res.ok) return {success: false, error: 'Fetch failed: ' + res.status};

                    var blob = await res.blob();

                    // Tạo download link
                    var url = URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'grok_video_' + Date.now() + '.mp4';
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();

                    // Cleanup
                    setTimeout(() => {
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                    }, 1000);

                    return {success: true, size: blob.size, src: src};
                } catch(e) {
                    return {success: false, error: e.message};
                }
            })();
            '''
            result = self.driver.execute_script(js_blob_download)
            self.log(f"   Blob result: {result}")

            if result and result.get('success'):
                self.log_ok(f"Đã trigger blob download ({result.get('size', 0)} bytes)")
                time.sleep(5)  # Chờ download
                return True

            self.log_warn("Không thể download video")
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

            # Submit and wait (180s timeout)
            self.log("4. Chờ video (tối đa 3 phút)...")
            if not self.submit_and_wait(timeout=180):
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
