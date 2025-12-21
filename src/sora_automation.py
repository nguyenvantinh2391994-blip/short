"""
SORA Automation - Tự động tạo video bằng OpenAI SORA
Website: https://sora.chatgpt.com/drafts

Sử dụng PyAutoGUI + DevTools JS (giống Grok)
Dùng chung Chrome profile với Grok (đã đăng nhập sẵn)
"""

import subprocess
import time
import os
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


class SoraAutomation:
    """
    Tự động hóa SORA bằng PyAutoGUI + DevTools JS
    Dùng chung Chrome với Grok (cài đặt browser profiles)
    """

    SORA_URL = "https://sora.chatgpt.com/drafts"

    def __init__(
        self,
        output_folder: str = "OUTPUT",
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = False,
        timeout: int = 300,
        use_existing_browser: bool = True  # Dùng Chrome đang mở (từ Grok)
    ):
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

        self.chrome_path = chrome_path or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.profile_path = profile_path
        self.timeout = timeout
        self.chrome_process = None
        self.use_existing_browser = use_existing_browser

    def log(self, msg: str):
        console.print(f"[cyan]{msg}[/]")

    def log_ok(self, msg: str):
        console.print(f"[green]   ✓ {msg}[/]")

    def log_err(self, msg: str):
        console.print(f"[red]   ✗ {msg}[/]")

    def log_warn(self, msg: str):
        console.print(f"[yellow]   ⚠ {msg}[/]")

    def run_js(self, js: str, close_devtools: bool = True) -> bool:
        """Chạy JS qua DevTools Console (không lấy kết quả)"""
        if not pag or not pyperclip:
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
        """Chạy JS và lấy kết quả qua clipboard (dùng copy())"""
        if not pag or not pyperclip:
            return None

        try:
            # Mở DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1.5)

            # Paste code (đã có copy() bên trong js)
            pyperclip.copy(js)
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

    def open_chrome(self, url: str) -> bool:
        """Mở Chrome với profile (giống Grok)"""
        try:
            cmd = [self.chrome_path]

            self.log(f"   Chrome path: {self.chrome_path}")
            self.log(f"   Profile path: {self.profile_path}")

            if self.profile_path and Path(self.profile_path).exists():
                profile = Path(self.profile_path)
                # Kiểm tra xem path là profile folder hay user-data-dir
                if profile.name == "Default" or profile.name.startswith("Profile "):
                    # Đường dẫn đầy đủ đến profile (VD: .../User Data/Default)
                    user_data_dir = profile.parent
                    profile_dir = profile.name
                else:
                    # Đường dẫn là user-data-dir (VD: E:/chrome-profiles/1)
                    user_data_dir = profile
                    profile_dir = "Default"

                self.log(f"   User data dir: {user_data_dir}")
                self.log(f"   Profile dir: {profile_dir}")
                cmd.extend([
                    f"--user-data-dir={user_data_dir}",
                    f"--profile-directory={profile_dir}"
                ])
            else:
                self.log_warn("Profile path không tồn tại, dùng Chrome mặc định")

            cmd.extend([
                "--window-size=1200,800",
                "--window-position=50,50",
                url
            ])

            self.log(f"   Lệnh: {' '.join(cmd[:3])}...")
            self.chrome_process = subprocess.Popen(cmd, shell=False)
            self.log_ok(f"Chrome PID: {self.chrome_process.pid}")
            return True
        except Exception as e:
            self.log_err(f"Lỗi mở Chrome: {e}")
            return False

    def navigate_to_sora(self) -> bool:
        """Mở tab SORA trong browser đang có (Ctrl+T rồi navigate)"""
        try:
            self.log("🌐 Mở tab SORA trong browser hiện tại...")

            # Mở tab mới
            pag.hotkey("ctrl", "t")
            time.sleep(1)

            # Gõ URL và Enter
            pyperclip.copy(self.SORA_URL)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(4)

            self.log_ok("Đã mở tab SORA")
            return True
        except Exception as e:
            self.log_err(f"Lỗi mở tab SORA: {e}")
            return False

    def start(self) -> bool:
        """Khởi động SORA (dùng browser đang mở hoặc mở Chrome mới)"""
        if not HAS_PAG:
            self.log_err("Cần cài pyautogui: pip install pyautogui")
            return False

        if not HAS_CLIP:
            self.log_err("Cần cài pyperclip: pip install pyperclip")
            return False

        try:
            if self.use_existing_browser:
                # Dùng browser đang mở (từ Grok) - chỉ mở tab mới
                self.log("🚀 Dùng browser đang mở...")
                if not self.navigate_to_sora():
                    return False
            else:
                # Mở Chrome mới
                self.log("🚀 Mở Chrome cho SORA...")
                if not self.open_chrome(self.SORA_URL):
                    return False
                time.sleep(5)

            # Kiểm tra đăng nhập - tìm textarea
            self.log("🔍 Kiểm tra đăng nhập SORA...")

            for attempt in range(30):
                if self._check_logged_in():
                    self.log_ok("Đã đăng nhập SORA!")
                    return True

                if attempt % 10 == 0 and attempt > 0:
                    self.log(f"   Chờ đăng nhập... ({attempt * 2}s)")

                time.sleep(2)

            self.log_warn("Chưa xác nhận được đăng nhập, tiếp tục thử...")
            return True

        except Exception as e:
            self.log_err(f"Lỗi khởi động: {e}")
            return False

    def _check_logged_in(self) -> bool:
        """Kiểm tra đã đăng nhập - tìm textarea 'Describe your video...'"""
        js = '''(function(){
            var ta = document.querySelector('textarea[placeholder*="Describe"]');
            if(ta){ copy('yes'); return; }
            var tas = document.querySelectorAll('textarea');
            if(tas.length > 0){ copy('yes'); return; }
            copy('no');
        })();'''

        result = self.run_js_get_result(js)
        return result and 'yes' in str(result).lower()

    def click_and_type_prompt(self, prompt: str) -> bool:
        """Click vào textarea và paste prompt"""
        # JS focus vào textarea
        js = '''(function(){
            var ta = document.querySelector('textarea[placeholder*="Describe"]');
            if(!ta) ta = document.querySelector('textarea');
            if(ta){
                ta.focus();
                ta.click();
                console.log('OK: Clicked textarea');
                return true;
            }
            console.log('FAIL: Textarea not found');
            return false;
        })();'''

        self.log("   JS: Click vào textarea prompt...")
        if not self.run_js(js):
            self.log_err("Không tìm thấy textarea")
            return False

        self.log_ok("Đã click textarea")
        time.sleep(0.5)

        # Paste prompt
        self.log(f"   Paste: {prompt[:40]}...")
        pyperclip.copy(prompt)
        pag.hotkey("ctrl", "v")
        time.sleep(0.5)

        self.log_ok("Đã paste prompt")
        return True

    def click_upload_button(self) -> bool:
        """Click nút upload (+) - SVG với path M12 6"""
        js = '''(function(){
            // Tìm button chứa SVG với path icon +
            var btns = document.querySelectorAll('button');
            for(var b of btns){
                var svg = b.querySelector('svg');
                if(svg){
                    var paths = svg.querySelectorAll('path');
                    for(var p of paths){
                        var d = p.getAttribute('d') || '';
                        if(d.includes('M12 6')){
                            b.click();
                            console.log('OK: Clicked upload button');
                            copy('clicked');
                            return;
                        }
                    }
                }
            }
            console.log('FAIL: Upload button not found');
            copy('notfound');
        })();'''

        self.log("   JS: Click nút upload (+)...")
        result = self.run_js_get_result(js)

        if result and 'clicked' in str(result).lower():
            self.log_ok("Đã click nút upload")
            return True

        self.log_err("Không tìm thấy nút upload")
        return False

    def upload_file(self, file_path: str) -> bool:
        """Upload file sau khi đã click nút upload"""
        if not os.path.exists(file_path):
            self.log_err(f"Không tìm thấy file: {file_path}")
            return False

        # Chờ dialog mở
        time.sleep(1.5)

        # Paste đường dẫn file và Enter
        abs_path = os.path.abspath(file_path)
        self.log(f"   Paste path: {Path(file_path).name}")
        pyperclip.copy(abs_path)
        pag.hotkey("ctrl", "v")
        time.sleep(0.5)
        pag.press("enter")
        time.sleep(2)

        self.log_ok(f"Đã upload: {Path(file_path).name}")
        return True

    def press_enter_to_send(self) -> bool:
        """Nhấn Enter để gửi prompt"""
        self.log("   PyAutoGUI: Nhấn Enter...")
        pag.press("enter")
        time.sleep(0.5)
        self.log_ok("Đã nhấn Enter gửi yêu cầu")
        return True

    def check_video_status(self) -> str:
        """Check trạng thái video: 'done', 'loading', 'waiting'"""
        js = '''(function(){
            // Check video element với src từ videos.openai.com
            var videos = document.querySelectorAll('video');
            for(var v of videos){
                var src = v.src || v.currentSrc || '';
                if(src.includes('videos.openai.com')){
                    copy('done');
                    return;
                }
            }
            // Check loading spinner (animate-spin)
            var spinners = document.querySelectorAll('svg.animate-spin, svg circle.animate-spin, [class*="animate-spin"]');
            for(var s of spinners){
                if(s.offsetParent !== null){
                    copy('loading');
                    return;
                }
            }
            // Check thêm bằng circle element trong SVG
            var circles = document.querySelectorAll('circle[stroke-dasharray]');
            for(var c of circles){
                var parent = c.closest('svg');
                if(parent && parent.offsetParent !== null){
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
        """Lấy URL video từ element <video src="...">"""
        js = '''(function(){
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

    def wait_for_video_done(self, timeout: int = 300) -> bool:
        """Đợi video tạo xong"""
        self.log(f"   Đang chờ video... (timeout: {timeout}s)")

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
        """
        Tạo video SORA

        Workflow:
        1. Vào SORA URL
        2. Nhập prompt vào textarea
        3. Click nút + để upload ảnh
        4. Chọn file ảnh, Enter
        5. Enter để gửi prompt
        6. Chờ video tạo xong (check spinner)
        7. Download video
        8. Lưu với tên 00_sora_xxx.mp4
        """
        result = {
            "success": False,
            "video_path": "",
            "video_url": "",
            "error": ""
        }

        try:
            self.log(f"🎬 Tạo video SORA...")
            self.log(f"   Prompt: {prompt[:50]}...")

            # Refresh trang
            pag.press("f5")
            time.sleep(3)

            # Bước 1: Nhập prompt
            if not self.click_and_type_prompt(prompt):
                result["error"] = "Không thể nhập prompt"
                return result

            time.sleep(1)

            # Bước 2: Upload ảnh nếu có
            if image_path and os.path.exists(image_path):
                self.log(f"📷 Upload ảnh: {Path(image_path).name}")

                if self.click_upload_button():
                    if not self.upload_file(image_path):
                        self.log_warn("Không upload được ảnh, tiếp tục không có ảnh")
                else:
                    self.log_warn("Không tìm thấy nút upload, tiếp tục không có ảnh")

                time.sleep(2)

            # Bước 3: Gửi prompt (Enter)
            self.press_enter_to_send()
            time.sleep(3)

            # Bước 4: Chờ video tạo xong
            if not self.wait_for_video_done(self.timeout):
                result["error"] = "Timeout chờ video"
                return result

            # Bước 5: Lấy URL video
            video_url = self.get_video_url()
            if not video_url:
                result["error"] = "Không lấy được URL video"
                return result

            result["video_url"] = video_url
            self.log_ok(f"Video URL: {video_url[:60]}...")

            # Bước 6: Xác định thư mục output (cùng chỗ với Grok)
            if code:
                video_folder = self.output_folder / "_temp_videos" / code
            else:
                video_folder = self.output_folder

            video_folder.mkdir(parents=True, exist_ok=True)

            # Tên file: 00_sora_xxx.mp4 để xếp đầu khi edit
            final_name = f"00_sora_{output_name}.mp4"
            final_path = str(video_folder / final_name)

            # Bước 7: Download video
            if not self.download_video(video_url, final_path):
                result["error"] = "Không thể download video"
                return result

            # TODO: Bước 8 - Xóa watermark SORA (cần AI inpainting vì WM nhảy vị trí)

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
        """Đóng - không đóng Chrome vì user có thể đang dùng"""
        self.log("   SORA automation kết thúc")


# CLI test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SORA Video Generator")
    parser.add_argument("--prompt", "-p", required=True, help="Video prompt")
    parser.add_argument("--image", "-i", help="Image path to upload")
    parser.add_argument("--output", "-o", default="sora_output", help="Output name")
    parser.add_argument("--chrome", help="Chrome path")
    parser.add_argument("--profile", help="Chrome profile path")

    args = parser.parse_args()

    sora = SoraAutomation(
        chrome_path=args.chrome,
        profile_path=args.profile
    )

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
