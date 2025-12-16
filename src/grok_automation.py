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

    # Đường dẫn đến icon done.PNG (cạnh run.bat)
    DONE_ICON_PATH = Path(__file__).parent.parent / "icon" / "done.PNG"

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

    def wait_for_done_image(self, timeout: int = 60) -> bool:
        """Chờ cho đến khi thấy icon done.PNG trên màn hình."""
        if not pag:
            return False

        icon_path = str(self.DONE_ICON_PATH)
        self.log(f"   Tìm icon: {icon_path}")

        if not Path(icon_path).exists():
            self.log_warn(f"Không tìm thấy file icon: {icon_path}")
            self.log_warn("Sẽ chờ 20s thay thế...")
            time.sleep(20)
            return True

        start_time = time.time()
        check_interval = 2  # Check mỗi 2 giây

        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            try:
                # Tìm icon trên màn hình (confidence >= 0.95)
                location = pag.locateOnScreen(icon_path, confidence=0.95)
                if location:
                    self.log_ok(f"Tìm thấy icon done! ({elapsed}s)")
                    return True
            except Exception as e:
                # Có thể lỗi nếu thiếu opencv-python
                pass

            if elapsed % 10 == 0 and elapsed > 0:
                self.log(f"   ...đã chờ {elapsed}s")

            time.sleep(check_interval)

        self.log_warn(f"Timeout {timeout}s, tiếp tục download anyway...")
        return False

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

    def click_download(self, output_path: str = "", product_code: str = "") -> bool:
        """Click nút download bằng JS và xử lý dialog Save As.

        Args:
            output_path: Đường dẫn đầy đủ đến file output (nếu có)
            product_code: Mã sản phẩm để làm tên file (ưu tiên dùng cái này)

        Flow Save As:
        1. Paste mã sản phẩm vào ô Name (đã focus sẵn)
        2. Ctrl+L → paste đường dẫn thư mục
        3. Enter → đi đến thư mục
        4. Alt+S → lưu
        """
        js = '''document.querySelector('button[aria-label="Tải xuống"]').dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}))'''

        self.log("   === CLICK DOWNLOAD ===")

        # DevTools đang mở sẵn - chỉ cần paste và chạy
        pyperclip.copy(js)
        pag.hotkey("ctrl", "v")
        time.sleep(0.3)

        pag.press("enter")
        time.sleep(1)

        self.log_ok("Đã chạy lệnh download")

        # Đợi dialog Save As xuất hiện
        self.log("   Đợi dialog Save As (5s)...")
        time.sleep(5)

        # Lấy tên file và folder
        filename = product_code if product_code else (Path(output_path).stem if output_path else "")
        folder = str(Path(output_path).parent.absolute()) if output_path else ""

        if filename:
            # Bước 1: Paste mã sản phẩm vào ô Name (đã focus sẵn)
            self.log(f"   Paste tên file: {filename}")
            pyperclip.copy(filename)
            pag.hotkey("ctrl", "a")  # Select all text hiện tại
            time.sleep(0.2)
            pag.hotkey("ctrl", "v")  # Paste tên mới
            time.sleep(0.5)

        if folder:
            # Bước 2: Ctrl+L để đưa về thanh địa chỉ (folder)
            self.log(f"   Ctrl+L → folder: {folder}")
            pag.hotkey("ctrl", "l")
            time.sleep(0.5)
            pyperclip.copy(folder)
            pag.hotkey("ctrl", "a")  # Select all
            time.sleep(0.2)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)

            # Bước 3: Enter để đi đến folder
            pag.press("enter")
            time.sleep(1.5)

        # Bước 4: Alt+S để lưu
        self.log("   Alt+S để lưu...")
        pag.hotkey("alt", "s")
        time.sleep(1)

        self.log_ok(f"Đã lưu: {filename} vào {folder}")
        return True

    def open_new_tab_and_close_old(self) -> bool:
        """Mở tab mới với URL grok, đóng tab cũ.

        Thứ tự:
        1. Ctrl+T mở tab mới (tab 2) - đang ở tab 2
        2. Nhập URL và Enter - load trang ở tab 2
        3. Ctrl+Shift+Tab quay lại tab 1 (tab cũ)
        4. Ctrl+W đóng tab 1 (tab cũ)
        5. Tự động chuyển sang tab 2 để tiếp tục làm việc
        """
        self.log("   Mở tab mới...")

        # Bước 1: Ctrl+T mở tab mới (đang ở tab 2)
        pag.hotkey("ctrl", "t")
        time.sleep(1)

        # Bước 2: Nhập URL vào tab mới
        pyperclip.copy(self.GROK_IMAGINE_URL)
        pag.hotkey("ctrl", "v")
        time.sleep(0.3)
        pag.press("enter")
        time.sleep(3)  # Đợi trang load

        # Bước 3: Ctrl+Shift+Tab quay lại tab cũ (tab 1)
        self.log("   Quay lại tab cũ...")
        pag.hotkey("ctrl", "shift", "tab")
        time.sleep(0.5)

        # Bước 4: Ctrl+W đóng tab cũ (tab 1)
        self.log("   Đóng tab cũ...")
        pag.hotkey("ctrl", "w")
        time.sleep(1)

        # Giờ đang ở tab 2 (tab mới) để tiếp tục làm việc
        self.log_ok("Đã mở tab mới, đóng tab cũ")
        return True

    def create_video(self, image_path: str, prompt: str = "", output_path: str = "", product_code: str = "") -> GrokVideoResult:
        """Tạo video.

        Args:
            image_path: Đường dẫn ảnh input
            prompt: Prompt mô tả (tùy chọn)
            output_path: Đường dẫn output (tùy chọn)
            product_code: Mã sản phẩm để đặt tên file khi Save As
        """
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

            # === BƯỚC 6: Chờ icon done (tối đa 60s) ===
            self.log("6. Chờ video tạo xong (tìm icon done, max 60s)...")
            self.wait_for_done_image(timeout=60)

            # === BƯỚC 7: Download ===
            self.log("7. Tải video...")
            self.click_download(output_path, product_code)
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

    def create_video_continue(self, image_path: str, prompt: str = "", output_path: str = "", product_code: str = "") -> GrokVideoResult:
        """Tạo video tiếp tục (không mở Chrome mới, dùng tab hiện tại).

        Args:
            image_path: Đường dẫn ảnh input
            prompt: Prompt mô tả (tùy chọn)
            output_path: Đường dẫn output (tùy chọn)
            product_code: Mã sản phẩm để đặt tên file khi Save As
        """
        image_path = Path(image_path).absolute()
        if not image_path.exists():
            return GrokVideoResult(False, error=f"Không tìm thấy: {image_path}")

        try:
            # Đợi trang load
            self.log("   Đợi trang load (5s)...")
            time.sleep(5)

            # === Nhập prompt ===
            if prompt:
                self.log(f"   Nhập prompt: {prompt[:50]}...")
                self.click_and_type_prompt(prompt)
                time.sleep(1)

            # === Click đính kèm ===
            self.log("   Click nút đính kèm...")
            self.click_attach_button()
            time.sleep(1)

            # === Click tải lên ===
            self.log("   Click menu tải lên...")
            self.click_upload_menu()
            time.sleep(1)

            # === Upload file ===
            self.log(f"   Upload: {image_path.name}")
            self.upload_file(str(image_path))

            # === Chờ icon done ===
            self.log("   Chờ video tạo xong...")
            self.wait_for_done_image(timeout=60)

            # === Download ===
            self.log("   Tải video...")
            self.click_download(output_path, product_code)
            time.sleep(3)

            return GrokVideoResult(True, video_path=output_path)

        except Exception as e:
            self.log_err(f"Exception: {e}")
            return GrokVideoResult(False, error=str(e))


def create_videos_from_sheets(
    sheets_reader,
    input_folder: str = "input",
    output_folder: str = "outputs",
    prompt: str = "",
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
) -> List[GrokVideoResult]:
    """
    Tạo video batch từ Google Sheets.
    - Đọc các sản phẩm có cột E trống
    - Ảnh từ input/{code}.jpg hoặc .png
    - Video lưu vào outputs/{code}.mp4
    - Cập nhật cột E = "VIDEO" sau khi xong
    """
    from pathlib import Path

    input_folder = Path(input_folder)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Lấy danh sách sản phẩm chưa làm
    pending = sheets_reader.get_pending_products(status_column="E")
    if not pending:
        console.print("[yellow]Không có sản phẩm nào cần làm video[/]")
        return []

    results = []
    automation = GrokBrowserAutomation(chrome_path, chrome_profile_path)

    for i, item in enumerate(pending):
        code = item["code"]
        row = item["row"]

        console.print(f"\n[bold cyan]===== [{i+1}/{len(pending)}] Mã: {code} =====[/]")

        # Tìm ảnh input
        image_path = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            candidate = input_folder / f"{code}{ext}"
            if candidate.exists():
                image_path = candidate
                break

        if not image_path:
            console.print(f"[red]❌ Không tìm thấy ảnh cho mã {code}[/]")
            results.append(GrokVideoResult(False, error=f"Không tìm thấy ảnh: {code}"))
            continue

        # Output path
        video_path = output_folder / f"{code}.mp4"

        # Tạo video (truyền code làm tên file khi Save As)
        if i == 0:
            # Lần đầu: mở Chrome mới
            result = automation.create_video(str(image_path), prompt, str(video_path), code)
        else:
            # Các lần sau: mở tab mới, đóng tab cũ, tiếp tục
            automation.open_new_tab_and_close_old()
            result = automation.create_video_continue(str(image_path), prompt, str(video_path), code)

        results.append(result)

        # Cập nhật trạng thái nếu thành công
        if result.success:
            sheets_reader.update_status(row, "VIDEO", "E")
            console.print(f"[green]✅ Hoàn thành: {code}[/]")
        else:
            console.print(f"[red]❌ Lỗi: {code} - {result.error}[/]")

    console.print(f"\n[bold green]===== HOÀN THÀNH {len([r for r in results if r.success])}/{len(pending)} video =====[/]")
    return results


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
