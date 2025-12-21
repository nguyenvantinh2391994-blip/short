"""
SORA Automation - Tự động tạo video bằng OpenAI SORA
Website: https://sora.chatgpt.com/drafts

Sử dụng PyAutoGUI + DevTools JS (giống Grok) để hỗ trợ Chrome extension
"""

import subprocess
import time
import os
import shutil
import requests
from pathlib import Path
from typing import Optional, Dict, Any
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
    duration: float = 0


class SoraAutomation:
    """
    Tự động hóa SORA bằng PyAutoGUI + DevTools JS
    Hỗ trợ Chrome extension (debug mode)
    """

    SORA_URL = "https://sora.chatgpt.com/drafts"

    def __init__(
        self,
        output_folder: str = "OUTPUT",
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = False,
        timeout: int = 300
    ):
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

        self.chrome_path = chrome_path or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.profile_path = profile_path
        self.timeout = timeout
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
        """Chạy JS qua DevTools Console"""
        if not pag or not pyperclip:
            self.log_err("Thiếu pyautogui hoặc pyperclip")
            return False

        try:
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
        """Chạy JS và lấy kết quả qua clipboard"""
        if not pag or not pyperclip:
            return None

        try:
            # Clear clipboard
            pyperclip.copy("")

            # Mở DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1.5)

            # Paste code
            full_js = f"copy({js})"
            pyperclip.copy(full_js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(1)

            # Lấy kết quả từ clipboard
            result = pyperclip.paste()

            # Đóng DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            return result
        except Exception as e:
            self.log_err(f"run_js_get_result error: {e}")
            return None

    def start(self) -> bool:
        """Khởi động Chrome và mở SORA"""
        if not HAS_PAG:
            self.log_err("Cần cài pyautogui: pip install pyautogui")
            return False

        if not HAS_CLIP:
            self.log_err("Cần cài pyperclip: pip install pyperclip")
            return False

        try:
            self.log("🚀 Mở Chrome cho SORA...")

            # Tạo lệnh mở Chrome
            cmd = [self.chrome_path]

            # Thêm profile nếu có
            if self.profile_path:
                # Lấy thư mục parent (User Data) và tên profile
                profile_dir = Path(self.profile_path)
                if profile_dir.name == "Default" or profile_dir.name.startswith("Profile"):
                    user_data_dir = str(profile_dir.parent)
                    profile_name = profile_dir.name
                    cmd.append(f"--user-data-dir={user_data_dir}")
                    cmd.append(f"--profile-directory={profile_name}")
                else:
                    cmd.append(f"--user-data-dir={self.profile_path}")

            # Thêm URL SORA
            cmd.append(self.SORA_URL)

            self.log(f"   Lệnh: {' '.join(cmd)}")

            # Mở Chrome
            self.chrome_process = subprocess.Popen(cmd)
            time.sleep(5)

            # Kiểm tra đăng nhập bằng JS
            self.log("🔍 Kiểm tra đăng nhập SORA...")

            for attempt in range(30):
                is_logged_in = self._check_logged_in_js()
                if is_logged_in:
                    self.log_ok("Đã đăng nhập SORA!")
                    return True

                if attempt % 10 == 0 and attempt > 0:
                    self.log(f"   Chờ đăng nhập... ({attempt}s)")

                time.sleep(2)

            self.log_warn("Chưa xác nhận được đăng nhập, tiếp tục thử...")
            return True

        except Exception as e:
            self.log_err(f"Lỗi khởi động: {e}")
            return False

    def _check_logged_in_js(self) -> bool:
        """Kiểm tra đã đăng nhập bằng JS"""
        try:
            result = self.run_js_get_result(
                "document.querySelector('textarea') ? 'yes' : 'no'"
            )
            return result and "yes" in result.lower()
        except:
            return False

    def _input_prompt_js(self, prompt: str) -> bool:
        """Nhập prompt qua JS"""
        # Escape prompt cho JS
        escaped = prompt.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")

        js = f"""
        (function() {{
            const textarea = document.querySelector('textarea');
            if (textarea) {{
                textarea.focus();
                textarea.value = '{escaped}';
                textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'done';
            }}
            return 'not_found';
        }})()
        """

        result = self.run_js_get_result(js)
        return result and "done" in str(result).lower()

    def _upload_image_js(self, image_path: str) -> bool:
        """Upload ảnh - dùng PyAutoGUI vì cần file dialog"""
        if not os.path.exists(image_path):
            self.log_warn(f"Không tìm thấy ảnh: {image_path}")
            return False

        try:
            # Tìm và click nút upload (+)
            js_click_upload = """
            (function() {
                // Tìm button có SVG với icon +
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const svg = btn.querySelector('svg');
                    if (svg) {
                        const paths = svg.querySelectorAll('path');
                        for (const path of paths) {
                            const d = path.getAttribute('d') || '';
                            if (d.includes('M12 6') || d.includes('M12 ')) {
                                btn.click();
                                return 'clicked';
                            }
                        }
                    }
                }
                // Fallback: click input file trực tiếp
                const fileInput = document.querySelector('input[type="file"]');
                if (fileInput) {
                    fileInput.click();
                    return 'file_input';
                }
                return 'not_found';
            })()
            """

            result = self.run_js_get_result(js_click_upload)
            self.log(f"   Upload click: {result}")

            time.sleep(1)

            # Type đường dẫn file vào dialog
            abs_path = os.path.abspath(image_path)
            pyperclip.copy(abs_path)

            time.sleep(0.5)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)
            pag.press("enter")

            self.log_ok(f"Đã upload: {Path(image_path).name}")
            time.sleep(2)
            return True

        except Exception as e:
            self.log_err(f"Lỗi upload ảnh: {e}")
            return False

    def _submit_prompt(self) -> bool:
        """Gửi prompt bằng Enter"""
        try:
            pag.press("enter")
            self.log_ok("Đã gửi prompt")
            return True
        except:
            return False

    def _wait_for_video_js(self) -> Optional[str]:
        """Chờ video tạo xong và lấy URL"""
        self.log(f"⏳ Chờ video tạo xong (timeout: {self.timeout}s)...")

        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Kiểm tra video element
                js = """
                (function() {
                    const videos = document.querySelectorAll('video');
                    for (const v of videos) {
                        const src = v.src || v.currentSrc;
                        if (src && src.includes('videos.openai.com')) {
                            return src;
                        }
                    }
                    // Kiểm tra loading
                    const spinners = document.querySelectorAll('[class*="animate-spin"], .animate-spin');
                    for (const s of spinners) {
                        if (s.offsetParent !== null) {
                            return 'loading';
                        }
                    }
                    return 'waiting';
                })()
                """

                result = self.run_js_get_result(js)

                if result and result.startswith("http"):
                    self.log_ok("Video đã sẵn sàng!")
                    return result

                # Log progress
                elapsed = int(time.time() - start_time)
                if elapsed % 15 == 0 and elapsed > 0:
                    status = "đang tạo..." if result == "loading" else "đang chờ..."
                    self.log(f"   {elapsed}s - {status}")

                time.sleep(3)

            except Exception as e:
                self.log_warn(f"Lỗi khi chờ: {e}")
                time.sleep(3)

        self.log_err("Timeout chờ video")
        return None

    def _download_video(self, video_url: str, output_path: str) -> bool:
        """Download video từ URL"""
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

    def generate_video(
        self,
        prompt: str,
        image_path: str = None,
        output_name: str = "sora_video",
        code: str = ""
    ) -> Dict[str, Any]:
        """Tạo video từ prompt và ảnh"""
        result = {
            "success": False,
            "video_path": "",
            "video_url": "",
            "error": ""
        }

        try:
            self.log(f"🎬 Tạo video SORA: {prompt[:50]}...")

            # Refresh trang
            pag.press("f5")
            time.sleep(3)

            # Nhập prompt
            if not self._input_prompt_js(prompt):
                # Fallback: type trực tiếp
                self.log("   Fallback: type prompt trực tiếp...")
                pag.click()
                time.sleep(0.5)
                pyperclip.copy(prompt)
                pag.hotkey("ctrl", "v")

            time.sleep(1)

            # Upload ảnh nếu có
            if image_path and os.path.exists(image_path):
                self.log(f"📷 Upload ảnh: {Path(image_path).name}")
                self._upload_image_js(image_path)
                time.sleep(2)

            # Gửi prompt
            self._submit_prompt()
            time.sleep(3)

            # Chờ video
            video_url = self._wait_for_video_js()

            if not video_url:
                result["error"] = "Không thể tạo video hoặc timeout"
                return result

            result["video_url"] = video_url

            # Xác định thư mục output
            if code:
                video_folder = self.output_folder / "_temp_videos" / code
            else:
                video_folder = self.output_folder

            video_folder.mkdir(parents=True, exist_ok=True)

            # Tên file: 00_sora_xxx.mp4 để xếp đầu khi edit
            final_name = f"00_sora_{output_name}.mp4"
            final_path = str(video_folder / final_name)

            # Download video
            if not self._download_video(video_url, final_path):
                result["error"] = "Không thể download video"
                return result

            result["success"] = True
            result["video_path"] = final_path

            self.log_ok(f"Video SORA đã lưu: {final_name}")
            return result

        except Exception as e:
            result["error"] = str(e)
            self.log_err(f"Lỗi: {e}")
            import traceback
            traceback.print_exc()
            return result

    def close(self):
        """Đóng browser"""
        # Không đóng Chrome vì user có thể đang dùng
        self.log("   SORA automation kết thúc")


# CLI test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SORA Video Generator")
    parser.add_argument("--prompt", "-p", required=True, help="Video prompt")
    parser.add_argument("--image", "-i", help="Image path to upload")
    parser.add_argument("--output", "-o", default="sora_output", help="Output name")

    args = parser.parse_args()

    sora = SoraAutomation()

    try:
        if sora.start():
            result = sora.generate_video(
                args.prompt,
                image_path=args.image,
                output_name=args.output
            )
            print(f"\nResult: {result}")
    finally:
        sora.close()
