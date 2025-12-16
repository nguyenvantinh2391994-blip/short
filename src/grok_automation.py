"""
Grok Browser Automation - PyAutoGUI
Mở Chrome bình thường + điều khiển bằng chuột/bàn phím + JS qua DevTools
"""

import subprocess
import time
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
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1.5)

            pyperclip.copy(js)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(0.8)

            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            return pyperclip.paste()
        except:
            return None

    def get_element_position(self, selector: str) -> Optional[tuple]:
        """Lấy vị trí element qua JS, trả về (x, y) để click."""
        js = f'''(function(){{
            var el = document.querySelector('{selector}');
            if(el){{
                var rect = el.getBoundingClientRect();
                var x = Math.round(rect.left + rect.width/2);
                var y = Math.round(rect.top + rect.height/2);
                copy(x + ',' + y);
                return;
            }}
            copy('notfound');
        }})();'''

        result = self.run_js_get_result(js)
        if result and result != 'notfound' and ',' in result:
            try:
                parts = result.split(',')
                x, y = int(parts[0]), int(parts[1])
                # Cộng thêm offset cho window position (50,50) và Chrome UI (~100px)
                return (x + 50, y + 50 + 80)
            except:
                pass
        return None

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
            self.log_ok(f"Chrome PID: {self.chrome_process.pid}")
            return True
        except Exception as e:
            self.log_err(f"Lỗi mở Chrome: {e}")
            return False

    def click_attach_button(self) -> bool:
        """Click nút đính kèm."""
        js = '''(function(){
            var btns = document.querySelectorAll('button');
            for(var b of btns){
                var label = b.getAttribute('aria-label') || '';
                if(label.includes('Đính kèm') || label.includes('Attach')){
                    b.click();
                    console.log('OK: Clicked attach button');
                    return true;
                }
            }
            console.log('FAIL: Attach button not found');
            return false;
        })();'''

        if self.run_js(js):
            self.log_ok("Đã click nút đính kèm")
            return True
        return False

    def click_upload_menu(self) -> bool:
        """Click menu Tải lên."""
        js = '''(function(){
            var items = document.querySelectorAll('div[role="menuitem"]');
            for(var item of items){
                var text = item.textContent || '';
                if(text.includes('Tải lên') || text.includes('Upload')){
                    item.click();
                    console.log('OK: Clicked upload menu');
                    return true;
                }
            }
            console.log('FAIL: Upload menu not found');
            return false;
        })();'''

        if self.run_js(js):
            self.log_ok("Đã click menu tải lên")
            return True
        return False

    def upload_file(self, file_path: str) -> bool:
        """Upload file qua dialog."""
        # Click input[type=file] để mở dialog
        js = '''(function(){
            var input = document.querySelector('input[type="file"]');
            if(input){
                input.click();
                console.log('OK: Opened file dialog');
                return true;
            }
            console.log('FAIL: File input not found');
            return false;
        })();'''

        if not self.run_js(js):
            return False

        time.sleep(1.5)

        # Paste đường dẫn file và Enter
        pyperclip.copy(str(file_path))
        pag.hotkey("ctrl", "v")
        time.sleep(0.5)
        pag.press("enter")
        time.sleep(2)

        self.log_ok(f"Đã upload: {Path(file_path).name}")
        return True

    def click_and_type_prompt(self, prompt: str) -> bool:
        """Click vào ô prompt bằng JS rồi paste (giống upload)."""
        # JS click vào ô nhập prompt
        js = '''(function(){
            // Tìm ô nhập "Gõ để tưởng tượng"
            var el = document.querySelector('p[data-placeholder="Gõ để tưởng tượng"]');
            if(!el) el = document.querySelector('.ProseMirror');
            if(!el) el = document.querySelector('div[contenteditable="true"]');
            if(el){
                el.focus();
                el.click();
                console.log('OK: Clicked prompt input');
                return true;
            }
            console.log('FAIL: Prompt input not found');
            return false;
        })();'''

        self.log("   JS: Click vào ô nhập prompt...")
        if not self.run_js(js):
            self.log_err("Không tìm thấy ô nhập prompt")
            return False

        self.log_ok("Đã click ô nhập prompt")
        time.sleep(0.5)

        # Paste prompt bằng PyAutoGUI (giống upload_file paste path)
        self.log(f"   Paste: {prompt[:30]}...")
        pyperclip.copy(prompt)
        pag.hotkey("ctrl", "v")
        time.sleep(0.5)

        self.log_ok("Đã paste prompt")
        return True

    def press_enter_to_send(self) -> bool:
        """Nhấn Enter để gửi."""
        self.log("   PyAutoGUI: Nhấn Enter...")
        pag.press("enter")
        time.sleep(0.5)
        self.log_ok("Đã nhấn Enter gửi yêu cầu")
        return True

    def check_video_status(self) -> str:
        """Check trạng thái video: 'done', 'download_ready', 'waiting'."""
        js = '''(function(){
            // Check nút Làm lại
            var btns = document.querySelectorAll('button');
            for(var b of btns){
                var text = b.textContent || '';
                if(text.includes('Làm lại') || text.includes('Redo') || text.includes('Regenerate')){
                    copy('done'); return;
                }
            }
            // Check nút download với aria-label="Tải xuống" (chính xác)
            var dlBtn = document.querySelector('button[aria-label="Tải xuống"]');
            if(dlBtn){ copy('download_ready'); return; }
            // Check SVG download
            var dlSvg = document.querySelector('svg.lucide-download, svg[class*="lucide-download"]');
            if(dlSvg){ copy('download_ready'); return; }
            // Check video element
            var videos = document.querySelectorAll('video');
            if(videos.length > 0){ copy('video_exists'); return; }
            copy('waiting');
        })();'''

        result = self.run_js_get_result(js)
        return result if result in ['done', 'download_ready', 'video_exists', 'waiting'] else 'waiting'

    def wait_for_video_done(self, timeout: int = 300) -> bool:
        """Đợi video tạo xong."""
        self.log("   Đang chờ video...")

        for i in range(timeout // 5):
            time.sleep(5)
            elapsed = i * 5

            if elapsed > 0 and elapsed % 30 == 0:
                self.log(f"   ...đã chờ {elapsed}s")

            status = self.check_video_status()
            self.log(f"   [dim]Status: {status}[/]")

            if status in ['done', 'download_ready', 'video_exists']:
                self.log_ok(f"Video sẵn sàng! (status={status})")
                return True

            # Fallback: sau 30s thử click download
            if elapsed >= 30 and elapsed % 30 == 0:
                self.log_warn("Thử click download...")
                self.click_download()

        return False

    def click_download(self, output_path: str = "") -> bool:
        """Click nút download bằng JS và xử lý dialog Save As."""
        # JS click nút download - thử nhiều cách
        js = '''(function(){
            // Cách 1: Tìm button với aria-label chính xác
            var btn = document.querySelector('button[aria-label="Tải xuống"]');
            if(btn){
                console.log('Found button[aria-label="Tải xuống"]');
                btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                console.log('OK: Dispatched click event');
                return true;
            }

            // Cách 2: Tìm qua SVG lucide-download
            var svg = document.querySelector('svg.lucide-download');
            if(svg){
                console.log('Found svg.lucide-download');
                btn = svg.closest('button');
                if(btn){
                    btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    console.log('OK: Clicked via SVG parent');
                    return true;
                }
            }

            // Cách 3: Tìm tất cả button và filter
            var allBtns = document.querySelectorAll('button');
            for(var b of allBtns){
                var label = b.getAttribute('aria-label') || '';
                if(label.includes('Tải') || label.includes('Download')){
                    console.log('Found button with label:', label);
                    b.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                    console.log('OK: Clicked');
                    return true;
                }
            }

            console.log('FAIL: Download button not found');
            console.log('Available buttons with aria-label:');
            document.querySelectorAll('button[aria-label]').forEach(b => {
                console.log(' -', b.getAttribute('aria-label'));
            });
            return false;
        })();'''

        self.log("   JS: Click nút Tải xuống...")
        if not self.run_js(js):
            self.log_err("Không tìm thấy nút download")
            return False

        self.log_ok("Đã click nút download")

        # Đợi dialog Save As xuất hiện (3s để chắc chắn)
        self.log("   Đợi dialog Save As (3s)...")
        time.sleep(3)

        # Đảm bảo DevTools đã đóng (nhấn Escape)
        pag.press("escape")
        time.sleep(0.3)

        if output_path:
            output_path = Path(output_path).absolute()
            folder = str(output_path.parent)
            filename = output_path.name

            # Bước 1: Gõ tên file (Tab để focus vào ô filename nếu chưa)
            self.log(f"   Gõ tên file: {filename}")
            pag.press("tab")  # Focus vào filename field
            time.sleep(0.3)
            pyperclip.copy(filename)
            pag.hotkey("ctrl", "a")  # Select all text hiện tại
            time.sleep(0.2)
            pag.hotkey("ctrl", "v")  # Paste tên mới
            time.sleep(0.5)

            # Bước 2: Ctrl+L để đưa về thanh địa chỉ (folder)
            self.log(f"   Ctrl+L → folder: {folder}")
            pag.hotkey("ctrl", "l")
            time.sleep(0.5)
            pyperclip.copy(folder)
            pag.hotkey("ctrl", "a")  # Select all
            time.sleep(0.2)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)
            pag.press("enter")  # Đi đến folder
            time.sleep(1.5)

            # Bước 3: Alt+S để lưu
            self.log("   Alt+S để lưu...")
            pag.hotkey("alt", "s")
            time.sleep(1)

            self.log_ok(f"Đã lưu: {output_path}")
        else:
            # Không có output_path, chỉ nhấn Enter để lưu mặc định
            self.log("   Enter để lưu mặc định...")
            pag.press("enter")
            time.sleep(1)

        return True

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
            # === BƯỚC 1: Mở Chrome ===
            self.log("1. Mở Chrome...")
            if not self.open_chrome(self.GROK_IMAGINE_URL):
                return GrokVideoResult(False, error="Không mở được Chrome")

            self.log("   Đợi trang load (10s)...")
            time.sleep(10)

            # === BƯỚC 2: Nhập prompt TRƯỚC (click "Gõ để tưởng tượng") ===
            if prompt:
                self.log(f"2. Nhập prompt: {prompt[:50]}...")
                self.click_and_type_prompt(prompt)
                time.sleep(1)
            else:
                self.log("2. Không có prompt, bỏ qua...")

            # === BƯỚC 3: Click đính kèm ===
            self.log("3. Click nút đính kèm...")
            if not self.click_attach_button():
                self.log_warn("Có thể không click được, tiếp tục...")
            time.sleep(1)

            # === BƯỚC 4: Click tải lên ===
            self.log("4. Click menu tải lên...")
            if not self.click_upload_menu():
                self.log_warn("Có thể không click được, tiếp tục...")
            time.sleep(1)

            # === BƯỚC 5: Upload file ===
            self.log(f"5. Upload: {image_path.name}")
            if not self.upload_file(str(image_path)):
                return GrokVideoResult(False, error="Không upload được file")

            # === BƯỚC 6: Chờ 20s để video tạo xong ===
            self.log("6. Chờ video tạo xong (20s)...")
            time.sleep(20)

            # === BƯỚC 7: Download ===
            self.log("7. Tải video...")
            self.click_download(output_path)
            time.sleep(3)

            if output_path:
                console.print(f"[green]✅ Xong! Video lưu tại: {output_path}[/]")
                return GrokVideoResult(True, video_path=output_path)
            else:
                console.print("[green]✅ Xong! Kiểm tra thư mục Downloads[/]")
                return GrokVideoResult(True, video_path="Downloads")

        except Exception as e:
            self.log_err(f"Exception: {e}")
            return GrokVideoResult(False, error=str(e))
        finally:
            pass  # Không đóng Chrome để user kiểm tra


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
