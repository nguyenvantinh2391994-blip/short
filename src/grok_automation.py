"""
Grok Browser Automation - PyAutoGUI
Mở Chrome bình thường + điều khiển bằng chuột/bàn phím
"""

import subprocess
import time
import os
from pathlib import Path
from typing import Optional, List
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
class GrokVideoResult:
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


class GrokBrowserAutomation:
    GROK_IMAGINE_URL = "https://grok.com/imagine"

    def __init__(
        self,
        chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
        headless: bool = False,
    ):
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.chrome_process = None

    def log(self, msg: str):
        console.print(f"[cyan]{msg}[/]")

    def open_chrome(self, url: str) -> bool:
        """Mở Chrome bình thường."""
        try:
            cmd = [self.chrome_path]

            if self.profile_path and Path(self.profile_path).exists():
                profile = Path(self.profile_path)
                cmd.extend([
                    f"--user-data-dir={profile.parent}",
                    f"--profile-directory={profile.name}"
                ])

            cmd.extend([
                "--window-size=1200,800",
                "--window-position=50,50",
                url
            ])

            self.chrome_process = subprocess.Popen(cmd, shell=False)
            self.log(f"Chrome PID: {self.chrome_process.pid}")
            return True
        except Exception as e:
            console.print(f"[red]Lỗi mở Chrome: {e}[/]")
            return False

    def close_chrome(self):
        """Đóng Chrome."""
        try:
            if pag:
                pag.hotkey('alt', 'F4')
                time.sleep(1)
        except:
            pass

    def click_attach_button(self) -> bool:
        """Click nút đính kèm bằng JS qua DevTools."""
        if not pag or not pyperclip:
            return False

        js = '''(function(){
            var btns = document.querySelectorAll('button');
            for(var b of btns){
                var label = b.getAttribute('aria-label') || '';
                if(label.includes('Đính kèm') || label.includes('Attach')){
                    b.click();
                    console.log('Clicked attach');
                    return true;
                }
            }
            return false;
        })();'''

        try:
            # Mở DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1.5)

            # Chạy JS
            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(1)

            # Đóng DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)
            return True
        except:
            return False

    def click_upload_menu(self) -> bool:
        """Click menu Tải lên."""
        if not pag or not pyperclip:
            return False

        js = '''(function(){
            var items = document.querySelectorAll('div[role="menuitem"]');
            for(var item of items){
                var text = item.textContent || '';
                if(text.includes('Tải lên') || text.includes('Upload')){
                    item.click();
                    console.log('Clicked upload');
                    return true;
                }
            }
            return false;
        })();'''

        try:
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)
            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(1)
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)
            return True
        except:
            return False

    def upload_file(self, file_path: str) -> bool:
        """Upload file qua input."""
        if not pag or not pyperclip:
            return False

        # Dùng JS để set file vào input
        js = f'''(function(){{
            var input = document.querySelector('input[type="file"]');
            if(input){{
                // Trigger click để mở dialog
                input.click();
                return true;
            }}
            return false;
        }})();'''

        try:
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)
            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(0.5)
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)

            # Đợi dialog mở, paste path
            time.sleep(1)
            pyperclip.copy(str(file_path))
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)
            pag.press("enter")
            time.sleep(2)
            return True
        except:
            return False

    def type_prompt(self, prompt: str) -> bool:
        """Nhập prompt vào textarea."""
        if not pag or not pyperclip:
            return False

        js = '''(function(){
            var ta = document.querySelector('textarea');
            if(ta){ ta.focus(); ta.click(); return true; }
            return false;
        })();'''

        try:
            # Focus textarea
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)
            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(0.5)
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            # Paste prompt
            if prompt:
                pyperclip.copy(prompt)
                pag.hotkey("ctrl", "v")
                time.sleep(0.5)

            return True
        except:
            return False

    def press_enter(self):
        """Nhấn Enter để gửi."""
        if pag:
            pag.press("enter")
            time.sleep(0.5)

    def wait_for_video_done(self, timeout: int = 300) -> bool:
        """Đợi video tạo xong."""
        if not pag or not pyperclip:
            return False

        js = '''(function(){
            var btns = document.querySelectorAll('button');
            for(var b of btns){
                var text = b.textContent || '';
                if(text.includes('Làm lại') || text.includes('Redo')){
                    return true;
                }
            }
            return false;
        })();'''

        for i in range(timeout // 5):
            time.sleep(5)
            if i % 6 == 0:
                self.log(f"...đã chờ {i*5}s")

            try:
                pag.hotkey("ctrl", "shift", "j")
                time.sleep(1)
                pyperclip.copy(js)
                pag.hotkey("ctrl", "v")
                time.sleep(0.3)
                pag.press("enter")
                time.sleep(0.5)

                # Check console output
                check_js = 'copy(document.querySelector("button")?.textContent?.includes("Làm lại") || false)'
                pyperclip.copy(check_js)
                pag.hotkey("ctrl", "v")
                time.sleep(0.3)
                pag.press("enter")
                time.sleep(0.5)

                pag.hotkey("ctrl", "shift", "j")
                time.sleep(0.3)

                result = pyperclip.paste()
                if result == "true":
                    return True
            except:
                pass

        return False

    def click_download(self) -> bool:
        """Click nút download."""
        if not pag or not pyperclip:
            return False

        js = '''(function(){
            var svgs = document.querySelectorAll('svg');
            for(var svg of svgs){
                if(svg.classList.contains('lucide-download') ||
                   svg.className.baseVal?.includes('download')){
                    var btn = svg.closest('button') || svg.parentElement;
                    if(btn){ btn.click(); return true; }
                }
            }
            return false;
        })();'''

        try:
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)
            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(1)
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)
            return True
        except:
            return False

    def create_video(self, image_path: str, prompt: str = "", output_path: str = "") -> GrokVideoResult:
        """Tạo video."""
        if not HAS_PAG:
            console.print("[red]❌ Chưa cài pyautogui![/]")
            console.print("[yellow]Chạy: pip install pyautogui pyperclip[/]")
            return GrokVideoResult(False, error="Thiếu pyautogui")

        if not HAS_CLIP:
            console.print("[red]❌ Chưa cài pyperclip![/]")
            return GrokVideoResult(False, error="Thiếu pyperclip")

        image_path = Path(image_path).absolute()
        if not image_path.exists():
            return GrokVideoResult(False, error=f"Không tìm thấy: {image_path}")

        try:
            # 1. Mở Chrome
            self.log("1. Mở Chrome...")
            if not self.open_chrome(self.GROK_IMAGINE_URL):
                return GrokVideoResult(False, error="Không mở được Chrome")

            self.log("Đợi trang load (8s)...")
            time.sleep(8)

            # 2. Click đính kèm
            self.log("2. Click nút đính kèm...")
            self.click_attach_button()
            time.sleep(1)

            # 3. Click tải lên
            self.log("3. Click tải lên...")
            self.click_upload_menu()
            time.sleep(1)

            # 4. Upload file
            self.log(f"4. Upload: {image_path.name}")
            self.upload_file(str(image_path))
            time.sleep(3)

            # 5. Nhập prompt
            if prompt:
                self.log(f"5. Nhập prompt: {prompt[:30]}...")
            self.type_prompt(prompt)
            time.sleep(1)

            # 6. Nhấn Enter
            self.log("6. Gửi yêu cầu tạo video...")
            self.press_enter()

            # 7. Đợi video
            self.log("7. Đang tạo video (1-5 phút)...")
            if not self.wait_for_video_done():
                return GrokVideoResult(False, error="Timeout chờ video")

            self.log("✓ Video xong!")
            time.sleep(2)

            # 8. Download
            self.log("8. Tải video...")
            self.click_download()
            time.sleep(10)

            console.print("[green]✅ Xong! Video trong Downloads[/]")
            return GrokVideoResult(True, video_path="Downloads")

        except Exception as e:
            return GrokVideoResult(False, error=str(e))
        finally:
            # Không tự đóng Chrome để user xem kết quả
            pass


def create_video_sync(
    image_path: str,
    prompt: str = "",
    output_path: str = "",
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    headless: bool = False,
) -> GrokVideoResult:
    return GrokBrowserAutomation(chrome_path, chrome_profile_path, headless).create_video(image_path, prompt, output_path)


def create_videos_batch_sync(
    tasks: List[dict],
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    headless: bool = False,
) -> List[GrokVideoResult]:
    results = []
    for i, task in enumerate(tasks, 1):
        console.print(f"\n[bold]===== Video {i}/{len(tasks)} =====[/]")
        results.append(create_video_sync(task["image"], task.get("prompt", ""), task["output"], chrome_path, chrome_profile_path, headless))
        if i < len(tasks):
            time.sleep(5)
    return results


def is_chrome_debug_running(port=9222):
    return False

def start_chrome_debug(**kwargs):
    return True
