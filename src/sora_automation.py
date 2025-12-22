"""
SORA Automation - Tự động tạo video bằng OpenAI SORA
Website: https://sora.chatgpt.com/drafts

Sử dụng PyAutoGUI + DevTools JS (giống hệt Grok)
"""

import subprocess
import time
import os
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from rich.console import Console

console = Console()

try:
    import pyautogui as pag
    pag.FAILSAFE = True
    pag.PAUSE = 0.1
    HAS_PAG = True
except ImportError:
    HAS_PAG = False
    pag = None

try:
    import pyperclip
    HAS_CLIP = True
except ImportError:
    HAS_CLIP = False
    pyperclip = None


@dataclass
class SoraResult:
    """Kết quả tạo video từ SORA"""
    success: bool
    video_path: str = ""
    video_url: str = ""
    error: str = ""


def find_sora_image(input_folder: str, product_code: str) -> Optional[str]:
    """Tìm ảnh SORA theo mã sản phẩm trong thư mục input/sora/

    Args:
        input_folder: Thư mục input gốc (ví dụ: E:/affiliate/short/input)
        product_code: Mã sản phẩm (ví dụ: SP001)

    Returns:
        Đường dẫn ảnh hoặc None

    Ví dụ:
        find_sora_image("input", "SP001") -> "input/sora/SP001.jpg"
    """
    sora_folder = Path(input_folder) / "sora"

    if not sora_folder.exists():
        return None

    # Tìm ảnh theo mã sản phẩm
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        image_path = sora_folder / f"{product_code}{ext}"
        if image_path.exists():
            return str(image_path)

    return None


def get_all_sora_images(input_folder: str) -> List[str]:
    """Lấy tất cả ảnh trong thư mục input/sora/

    Args:
        input_folder: Thư mục input gốc

    Returns:
        Danh sách đường dẫn ảnh
    """
    sora_folder = Path(input_folder) / "sora"

    if not sora_folder.exists():
        return []

    images = []
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        images.extend(sora_folder.glob(f"*{ext}"))

    return [str(img) for img in sorted(images)]


class SoraAutomation:
    """
    Tự động hóa SORA bằng PyAutoGUI + DevTools JS
    Cấu trúc giống hệt GrokBrowserAutomation
    """

    SORA_URL = "https://sora.chatgpt.com/drafts"

    def __init__(
        self,
        chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        profile_path: str = None,
        output_folder: str = "OUTPUT",
        timeout: int = 300,
        headless: bool = False,
        maximize: bool = True,  # Mặc định maximize để PyAutoGUI hoạt động tốt
    ):
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.maximize = maximize
        self.chrome_process = None

    def log(self, msg: str):
        console.print(f"[cyan]{msg}[/]")

    def log_ok(self, msg: str):
        console.print(f"[green]   ✓ {msg}[/]")

    def log_err(self, msg: str):
        console.print(f"[red]   ✗ {msg}[/]")

    def log_warn(self, msg: str):
        console.print(f"[yellow]   ⚠ {msg}[/]")

    def run_js(self, js: str, close_devtools: bool = True) -> bool:
        """Chạy JS qua DevTools Console."""
        if not pag or not pyperclip:
            return False

        try:
            # Focus vào Chrome trước
            self._focus_chrome_window()

            # Mở DevTools Console
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1.5)

            # Paste và chạy JS
            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(0.8)

            # Đóng DevTools
            if close_devtools:
                pag.hotkey("ctrl", "shift", "j")
                time.sleep(0.5)

            return True
        except Exception as e:
            self.log_err(f"run_js error: {e}")
            return False

    def run_js_get_result(self, js: str) -> Optional[str]:
        """Chạy JS và lấy kết quả qua clipboard."""
        if not pag or not pyperclip:
            return None

        try:
            # Focus vào Chrome trước
            self._focus_chrome_window()

            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1.5)

            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(1)

            result = pyperclip.paste()

            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            return result
        except Exception as e:
            self.log_err(f"run_js_get_result error: {e}")
            return None

    def open_chrome(self, url: str) -> bool:
        """Mở Chrome bình thường."""
        try:
            cmd = [self.chrome_path]

            self.log(f"   Profile path: {self.profile_path}")

            # Xử lý profile path - đảm bảo có Default/Profile X ở cuối (giống Grok)
            profile_path = self.profile_path
            if profile_path:
                profile = Path(profile_path)
                # Nếu path không kết thúc bằng Default hoặc Profile X, tự động thêm Default
                if not profile.name.startswith("Profile") and profile.name != "Default":
                    profile_path = str(profile / "Default")
                    self.log(f"   Auto-append Default: {profile_path}")

            if profile_path and Path(profile_path).exists():
                profile = Path(profile_path)
                self.log(f"   user-data-dir: {profile.parent}")
                self.log(f"   profile-directory: {profile.name}")
                cmd.extend([
                    f"--user-data-dir={profile.parent}",
                    f"--profile-directory={profile.name}"
                ])
            else:
                self.log_warn(f"Profile không tồn tại: {profile_path}")

            # Window size - maximize hoặc fixed size
            if self.maximize:
                cmd.append("--start-maximized")
                self.log("   Window: Maximized")
            else:
                cmd.extend([
                    "--window-size=1200,800",
                    "--window-position=50,50",
                ])

            cmd.append(url)

            self.log(f"   CMD: {' '.join(cmd[:5])}...")
            self.chrome_process = subprocess.Popen(cmd, shell=False)
            self.log_ok(f"Chrome PID: {self.chrome_process.pid}")

            # Chờ Chrome mở và focus vào nó
            time.sleep(3)
            self._focus_chrome_window()

            return True
        except Exception as e:
            self.log_err(f"Lỗi mở Chrome: {e}")
            return False

    def _focus_chrome_window(self) -> bool:
        """Focus vào cửa sổ Chrome vừa mở."""
        try:
            import pygetwindow as gw
            # Tìm cửa sổ có "Sora" hoặc "ChatGPT" trong title
            windows = gw.getWindowsWithTitle('Sora')
            if not windows:
                windows = gw.getWindowsWithTitle('ChatGPT')
            if not windows:
                # Fallback: tìm Chrome window mới nhất
                windows = gw.getWindowsWithTitle('Chrome')

            if windows:
                win = windows[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.5)
                self.log_ok(f"Đã focus: {win.title[:30]}...")
                return True
            return False
        except Exception as e:
            self.log_warn(f"Không focus được: {e}")
            return False

    def click_and_type_prompt(self, prompt: str) -> bool:
        """Click vào textarea và paste prompt - sử dụng SORA_HELPER từ extension."""
        # Sử dụng SORA_HELPER nếu có, fallback về cách cũ
        js = '''(function(){
            if(window.SORA_HELPER){
                SORA_HELPER.clickTextarea();
                SORA_HELPER.inputPrompt(`''' + prompt.replace('`', '\\`').replace('\\', '\\\\') + '''`);
                copy('ok');
                return;
            }
            // Fallback
            var ta = document.querySelector('textarea[placeholder*="Describe"]');
            if(!ta) ta = document.querySelector('textarea');
            if(ta){
                ta.focus();
                ta.click();
                copy('clicked');
                return;
            }
            copy('notfound');
        })();'''

        self.log(f"   Nhập prompt: {prompt[:50]}...")
        result = self.run_js_get_result(js)

        if result == 'ok':
            self.log_ok("Đã nhập prompt (SORA_HELPER)")
            return True

        if result == 'clicked':
            # Fallback: paste prompt manually
            time.sleep(0.5)
            pyperclip.copy(prompt)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)
            self.log_ok("Đã paste prompt (fallback)")
            return True

        self.log_err("Không tìm thấy textarea")
        return False

    def click_upload_button(self) -> bool:
        """Click nút upload (+) - tìm theo text Attach."""
        js = '''(function(){
            var btns = document.querySelectorAll('button');
            // Ưu tiên: tim theo text Attach
            for(var b of btns){
                var text = b.textContent || '';
                if(text.includes('Attach')){
                    b.click();
                    copy('clicked');
                    return;
                }
            }
            // Fallback: SVG path
            for(var b of btns){
                var svg = b.querySelector('svg');
                if(svg){
                    var paths = svg.querySelectorAll('path');
                    for(var p of paths){
                        var d = p.getAttribute('d') || '';
                        if(d.startsWith('M12 6') || d.startsWith('M12 5')){
                            b.click();
                            copy('clicked');
                            return;
                        }
                    }
                }
            }
            copy('notfound');
        })();'''

        self.log("   Click nút upload (+)...")
        result = self.run_js_get_result(js)

        if result and 'clicked' in str(result).lower():
            self.log_ok("Đã click nút upload")
            return True

        self.log_err("Không tìm thấy nút upload")
        return False

    def upload_file(self, file_path: str) -> bool:
        """Upload file qua dialog."""
        if not os.path.exists(file_path):
            self.log_err(f"Không tìm thấy file: {file_path}")
            return False

        time.sleep(1.5)

        abs_path = os.path.abspath(file_path)
        self.log(f"   Paste path: {Path(file_path).name}")
        pyperclip.copy(abs_path)
        pag.hotkey("ctrl", "v")
        time.sleep(0.5)
        pag.press("enter")
        time.sleep(2)

        self.log_ok(f"Đã upload: {Path(file_path).name}")
        return True

    def wait_for_send_button_ready(self, wait_seconds: int = 10) -> bool:
        """Đợi ảnh load xong trước khi gửi.

        Đợi khoảng 10s để ảnh upload hoàn tất.
        """
        self.log(f"   Đợi ảnh load ({wait_seconds}s)...")
        time.sleep(wait_seconds)
        self.log_ok("Sẵn sàng gửi")
        return True

    def check_video_status(self) -> str:
        """Check trạng thái video: 'done', 'loading', 'waiting' - sử dụng SORA_HELPER."""
        js = '''(function(){
            if(window.SORA_HELPER){
                var status = SORA_HELPER.checkStatus();
                copy(status.status || 'waiting');
                return;
            }
            // Fallback
            var videos = document.querySelectorAll('video');
            for(var v of videos){
                var src = v.src || v.currentSrc || '';
                if(src.includes('videos.openai.com')){
                    copy('done');
                    return;
                }
            }
            var spinners = document.querySelectorAll('[class*="animate-spin"]');
            for(var s of spinners){
                if(s.offsetParent !== null){
                    copy('loading');
                    return;
                }
            }
            copy('waiting');
        })();'''

        result = self.run_js_get_result(js)
        if result in ['done', 'loading', 'waiting']:
            return result
        return 'waiting'

    def get_video_url(self) -> Optional[str]:
        """Lấy URL video - sử dụng SORA_HELPER."""
        js = '''(function(){
            if(window.SORA_HELPER){
                var url = SORA_HELPER.getVideoUrl();
                copy(url || 'notfound');
                return;
            }
            // Fallback
            var videos = document.querySelectorAll('video');
            for(var v of videos){
                var src = v.src || v.currentSrc || '';
                if(src.includes('videos.openai.com')){
                    copy(src);
                    return;
                }
            }
            copy('notfound');
        })();'''

        result = self.run_js_get_result(js)
        if result and result.startswith('http'):
            return result
        return None

    def wait_for_video_done(self, timeout: int = 60) -> bool:
        """Đợi video tạo xong (check mỗi 5s)."""
        self.log(f"   Đang chờ video... (tối đa {timeout}s)")

        for i in range(timeout // 5):
            time.sleep(5)
            elapsed = i * 5

            status = self.check_video_status()

            if status == 'done':
                self.log_ok(f"Video xong! ({elapsed}s)")
                return True

            if elapsed % 15 == 0 and elapsed > 0:
                self.log(f"   {elapsed}s - {status}...")

        self.log_err(f"Timeout sau {timeout}s")
        return False

    def download_video(self, video_url: str, output_path: str) -> bool:
        """Download video từ URL."""
        try:
            self.log("📥 Downloading video...")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': self.SORA_URL,
            }

            response = requests.get(
                video_url,
                headers=headers,
                stream=True,
                timeout=120
            )
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.log_ok(f"Đã tải: {Path(output_path).name}")
            return True

        except Exception as e:
            self.log_err(f"Lỗi download: {e}")
            return False

    def create_video(
        self,
        image_path: str,
        prompt: str = "",
        output_path: str = "",
        product_code: str = ""
    ) -> SoraResult:
        """Tạo video (giống Grok.create_video).

        Flow: Nhập prompt → Upload ảnh → Enter → Đợi video → Download
        """
        if not HAS_PAG:
            console.print("[red]❌ Chưa cài pyautogui![/]")
            return SoraResult(False, error="Missing pyautogui")

        if not HAS_CLIP:
            console.print("[red]❌ Chưa cài pyperclip![/]")
            return SoraResult(False, error="Missing pyperclip")

        try:
            self.log(f"\n🎬 SORA: Tạo video...")
            self.log(f"   Ảnh: {Path(image_path).name if image_path else 'Không có'}")
            self.log(f"   Prompt: {prompt[:50]}..." if prompt else "   Prompt: (không có)")

            # Mở Chrome
            self.log("🌐 Mở Chrome...")
            if not self.open_chrome(self.SORA_URL):
                return SoraResult(False, error="Không mở được Chrome")
            time.sleep(5)

            # Nhập prompt (nếu có)
            if prompt:
                if not self.click_and_type_prompt(prompt):
                    return SoraResult(False, error="Không nhập được prompt")
                time.sleep(1)

            # Upload ảnh (nếu có)
            if image_path and os.path.exists(image_path):
                self.log(f"📷 Upload ảnh: {Path(image_path).name}")
                if self.click_upload_button():
                    self.upload_file(image_path)
                    # Đợi ảnh load xong (nút Create video sáng lên)
                    self.wait_for_send_button_ready()

            # Gửi (Enter)
            self.log("   Nhấn Enter gửi...")
            pag.press("enter")
            time.sleep(3)

            # Chờ video
            if not self.wait_for_video_done(self.timeout):
                return SoraResult(False, error="Timeout chờ video")

            # Lấy URL video
            video_url = self.get_video_url()
            if not video_url:
                return SoraResult(False, error="Không lấy được URL video")

            self.log_ok(f"Video URL: {video_url[:60]}...")

            # Download video
            if output_path:
                video_folder = Path(output_path).parent
            elif product_code:
                video_folder = self.output_folder / "_temp_videos" / product_code
            else:
                video_folder = self.output_folder

            video_folder.mkdir(parents=True, exist_ok=True)
            final_name = f"00_sora_{product_code or 'video'}.mp4"
            final_path = str(video_folder / final_name)

            if not self.download_video(video_url, final_path):
                return SoraResult(False, error="Không download được video")

            console.print(f"[green]✅ Video SORA: {final_name}[/]")
            return SoraResult(True, video_path=final_path, video_url=video_url)

        except Exception as e:
            self.log_err(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return SoraResult(False, error=str(e))

    def create_video_continue(
        self,
        image_path: str,
        prompt: str = "",
        output_path: str = "",
        product_code: str = ""
    ) -> SoraResult:
        """Tạo video tiếp tục (không mở Chrome mới).

        Flow: Refresh → Nhập prompt → Upload ảnh → Enter → Đợi video → Download
        """
        if not HAS_PAG or not HAS_CLIP:
            return SoraResult(False, error="Missing dependencies")

        try:
            self.log(f"\n🎬 SORA: Tạo video tiếp...")

            # Refresh trang
            pag.press("f5")
            time.sleep(3)

            # Nhập prompt (nếu có)
            if prompt:
                if not self.click_and_type_prompt(prompt):
                    return SoraResult(False, error="Không nhập được prompt")
                time.sleep(1)

            # Upload ảnh (nếu có)
            if image_path and os.path.exists(image_path):
                self.log(f"📷 Upload ảnh: {Path(image_path).name}")
                if self.click_upload_button():
                    self.upload_file(image_path)
                    # Đợi ảnh load xong (nút Create video sáng lên)
                    self.wait_for_send_button_ready()

            # Gửi (Enter)
            pag.press("enter")
            time.sleep(3)

            # Chờ video
            if not self.wait_for_video_done(self.timeout):
                return SoraResult(False, error="Timeout chờ video")

            # Lấy URL và download
            video_url = self.get_video_url()
            if not video_url:
                return SoraResult(False, error="Không lấy được URL video")

            if output_path:
                video_folder = Path(output_path).parent
            elif product_code:
                video_folder = self.output_folder / "_temp_videos" / product_code
            else:
                video_folder = self.output_folder

            video_folder.mkdir(parents=True, exist_ok=True)
            final_name = f"00_sora_{product_code or 'video'}.mp4"
            final_path = str(video_folder / final_name)

            if not self.download_video(video_url, final_path):
                return SoraResult(False, error="Không download được video")

            return SoraResult(True, video_path=final_path, video_url=video_url)

        except Exception as e:
            self.log_err(f"Exception: {e}")
            return SoraResult(False, error=str(e))


# Hàm tiện ích giống Grok
def create_video_sync(
    image_path: str,
    prompt: str = "",
    output_path: str = "",
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = None,
) -> SoraResult:
    return SoraAutomation(chrome_path, chrome_profile_path).create_video(image_path, prompt, output_path)


# CLI test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SORA Video Generator")
    parser.add_argument("--prompt", "-p", required=True, help="Video prompt")
    parser.add_argument("--image", "-i", help="Image path to upload")
    parser.add_argument("--output", "-o", default="", help="Output path")
    parser.add_argument("--chrome", help="Chrome path")
    parser.add_argument("--profile", help="Chrome profile path")

    args = parser.parse_args()

    result = create_video_sync(
        args.image or "",
        args.prompt,
        args.output,
        args.chrome or r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        args.profile
    )
    print(f"\nResult: {result}")
