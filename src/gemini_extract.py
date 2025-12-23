"""
Gemini Product Extraction - Tách sản phẩm từ ảnh sử dụng Gemini

Sử dụng PyAutoGUI để điều khiển browser, tương tự SORA/Grok automation.
"""

import os
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

try:
    import pyautogui as pag
    import pyperclip
    HAS_PAG = True
except ImportError:
    HAS_PAG = False
    pag = None
    pyperclip = None

try:
    from rich.console import Console
    console = Console()
except ImportError:
    class Console:
        def print(self, *args, **kwargs):
            print(*args)
    console = Console()


@dataclass
class ExtractResult:
    """Kết quả tách sản phẩm"""
    success: bool
    images: List[str] = None
    error: str = ""


EXTRACT_PROMPT = """IMAGE EDITING TASK — OBJECT EXTRACTION

This is an IMAGE EDITING task. You must PROCESS the input image and RETURN a NEW IMAGE as output.

Task description: Extract (cut out) the MAIN PRODUCT from the image.

Definition of the product:
- The product is the CLOTHING ONLY.
- Any human, child, model, body part, face, skin, hair, or watermark is NOT part of the product and must be completely removed.

Editing instructions:
- Remove the entire background
- Remove all people and body parts
- Remove all text, logos, and watermarks
- Keep ONLY the clothing item itself
- Preserve realistic fabric shape and folds
- Do NOT flatten the clothing
- Do NOT stylize or redesign

Output requirements:
- Output must be an IMAGE
- ONE clothing item only
- Pure white background (#FFFFFF)
- No shadows, no reflections
- No text in the output

Final rule: You must return ONLY the edited image. Do NOT return any text."""


class GeminiExtract:
    """Tách sản phẩm từ ảnh sử dụng Gemini - PyAutoGUI approach"""

    # Dung URL moi de tao conversation moi moi lan
    GEMINI_URL = "https://gemini.google.com/app?hl=vi"

    def __init__(
        self,
        chrome_path: str = None,
        profile_path: str = None,
        output_folder: str = "OUTPUT",
        headless: bool = False,
    ):
        self.chrome_path = chrome_path or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.profile_path = profile_path
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.chrome_process = None
        self._is_hidden = False

    def log(self, msg: str):
        console.print(f"[cyan]{msg}[/]")

    def log_ok(self, msg: str):
        console.print(f"[green]   OK: {msg}[/]")

    def log_err(self, msg: str):
        console.print(f"[red]   Loi: {msg}[/]")

    def _focus_chrome_window(self) -> bool:
        """Focus vao cua so Chrome"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle('Gemini')
            if not windows:
                windows = gw.getWindowsWithTitle('Google')
            if windows:
                win = windows[0]
                win.activate()
                time.sleep(0.3)
                return True
        except:
            pass
        return False

    def open_chrome(self, url: str) -> bool:
        """Mo Chrome voi profile"""
        try:
            cmd = [self.chrome_path]

            profile_path = self.profile_path
            if profile_path:
                profile = Path(profile_path)
                if not profile.name.startswith("Profile") and profile.name != "Default":
                    profile_path = str(profile / "Default")

            if profile_path and Path(profile_path).exists():
                profile = Path(profile_path)
                cmd.extend([
                    f"--user-data-dir={profile.parent}",
                    f"--profile-directory={profile.name}"
                ])

            cmd.append("--start-maximized")
            cmd.append(url)

            self.chrome_process = subprocess.Popen(cmd, shell=False)
            self.log_ok(f"Chrome PID: {self.chrome_process.pid}")

            time.sleep(4)
            self._focus_chrome_window()
            return True

        except Exception as e:
            self.log_err(f"Loi mo Chrome: {e}")
            return False

    def run_js(self, js: str) -> Optional[str]:
        """Chay JS qua DevTools Console"""
        if not pag or not pyperclip:
            return None

        try:
            self._focus_chrome_window()

            # Mo DevTools Console
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            # Copy JS
            pyperclip.copy(js)
            time.sleep(0.1)

            # Paste va chay
            pag.hotkey("ctrl", "v")
            time.sleep(0.2)
            pag.press("enter")
            time.sleep(0.5)

            # Lay ket qua tu clipboard
            result = pyperclip.paste()

            # Dong DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.3)

            return result

        except Exception as e:
            self.log_err(f"Loi run JS: {e}")
            return None

    def type_prompt(self) -> bool:
        """Nhap prompt vao textarea"""
        self.log("Nhap prompt...")

        escaped_prompt = EXTRACT_PROMPT.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

        js = f'''
        (function() {{
            var editor = document.querySelector('.ql-editor');
            if (!editor) {{ copy('ERROR'); return; }}
            editor.focus();
            editor.textContent = `{escaped_prompt}`;
            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
            copy('OK');
        }})();
        '''

        result = self.run_js(js)
        if result and 'OK' in result:
            self.log_ok("Da nhap prompt")
            return True
        else:
            self.log_err("Khong nhap duoc prompt")
            return False

    def upload_files(self, image_paths: List[str]) -> bool:
        """Upload files - dung Tab + Enter de navigate menu (hoat dong khi an)"""
        self.log(f"Upload {len(image_paths)} files...")

        # Click nut upload menu bang JS
        js1 = '''
        (function() {
            var btn = document.querySelector('.upload-card-button');
            if (btn) { btn.click(); copy('OK'); }
            else { copy('ERROR'); }
        })();
        '''
        result = self.run_js(js1)
        if not result or 'OK' not in result:
            self.log_err("Khong tim thay nut upload")
            return False

        time.sleep(0.8)

        # Dong DevTools truoc khi dung keyboard
        self._focus_chrome_window()
        time.sleep(0.3)

        # Dung Tab de navigate den "Tai tep len" roi Enter
        # Menu da mo, Tab 1 lan de focus vao item dau tien, Enter de click
        pag.press("tab")
        time.sleep(0.2)
        pag.press("enter")

        # Cho file dialog mo
        time.sleep(1.5)

        # Nhap duong dan file vao dialog
        if len(image_paths) == 1:
            file_str = str(Path(image_paths[0]).resolve())
        else:
            # Nhieu file: "file1" "file2"
            file_str = ' '.join([f'"{str(Path(p).resolve())}"' for p in image_paths])

        self.log(f"   Chon {len(image_paths)} file...")
        pyperclip.copy(file_str)
        time.sleep(0.3)

        # Paste vao dialog
        pag.hotkey("ctrl", "v")
        time.sleep(0.5)

        # Nhan Enter de xac nhan
        pag.press("enter")
        time.sleep(2)

        self.log_ok("Da upload files")
        return True

    def send_prompt(self) -> bool:
        """Gui prompt"""
        self.log("Gui prompt...")

        js = '''
        (function() {
            var btn = document.querySelector('button[aria-label="Gửi tin nhắn"]');
            if (!btn) btn = document.querySelector('.send-button');
            if (btn) { btn.click(); copy('OK'); }
            else { copy('ERROR'); }
        })();
        '''
        result = self.run_js(js)
        if result and 'OK' in result:
            self.log_ok("Da gui prompt")
            return True
        else:
            self.log_err("Khong gui duoc prompt")
            return False

    def wait_for_completion(self, timeout: int = 180) -> bool:
        """Doi tao anh xong"""
        self.log(f"Doi tao anh... (toi da {timeout}s)")

        start = time.time()
        check_interval = 10

        while time.time() - start < timeout:
            time.sleep(check_interval)
            elapsed = int(time.time() - start)

            js = '''
            (function() {
                var stop = document.querySelector('mat-icon[fonticon="stop"]');
                var imgs = document.querySelectorAll('generated-image img.image');
                if (imgs.length > 0 && !stop) { copy('DONE'); }
                else { copy('WAIT'); }
            })();
            '''
            result = self.run_js(js)

            self.log(f"   {elapsed}s - Check...")

            if result and 'DONE' in result:
                self.log_ok(f"Hoan thanh! ({elapsed}s)")
                return True

        self.log_err(f"Timeout sau {timeout}s")
        return False

    def get_generated_images(self) -> List[str]:
        """Lay URL cac anh da tao"""
        js = '''
        (function() {
            // Tim tat ca img co class "image" hoac "image loaded" va src googleusercontent
            var imgs = document.querySelectorAll('img.image');
            var urls = [];
            imgs.forEach(function(img) {
                if (img.src && img.src.includes('googleusercontent') && img.src.includes('gg-dl')) {
                    urls.push(img.src);
                }
            });
            copy(JSON.stringify(urls));
        })();
        '''
        result = self.run_js(js)
        if result:
            try:
                import json
                urls = json.loads(result)
                self.log(f"   Tim thay {len(urls)} anh")
                return urls
            except:
                pass
        return []

    def create_new_conversation(self) -> bool:
        """Tao conversation moi trong Gemini"""
        self.log("Tao conversation moi...")

        js = '''
        (function() {
            // Tim nut New chat
            var newBtn = document.querySelector('a[aria-label*="chat"]') ||
                         document.querySelector('button[aria-label*="New"]') ||
                         document.querySelector('.new-chat-button');
            if (newBtn) {
                newBtn.click();
                copy('OK');
            } else {
                // Fallback: navigate to new URL
                window.location.href = 'https://gemini.google.com/app?hl=vi&t=' + Date.now();
                copy('NAVIGATE');
            }
        })();
        '''
        result = self.run_js(js)
        time.sleep(3)

        if result and ('OK' in result or 'NAVIGATE' in result):
            self.log_ok("Da tao conversation moi")
            return True
        return False

    def click_download_buttons(self, count: int = 0) -> int:
        """Click tat ca nut download trong Gemini UI"""
        self.log("Click nut download...")

        # Dem so nut download
        js_count = '''
        (function() {
            var icons = document.querySelectorAll('mat-icon[fonticon="download"]');
            copy(String(icons.length));
        })();
        '''
        result = self.run_js(js_count)

        try:
            num_buttons = int(result) if result else 0
        except:
            num_buttons = 0

        if num_buttons == 0:
            self.log_err("Khong tim thay nut download")
            return 0

        self.log(f"   Tim thay {num_buttons} nut download")

        # Click tung nut download
        js_click = '''
        (function() {
            var icons = document.querySelectorAll('mat-icon[fonticon="download"]');
            var clicked = 0;
            icons.forEach(function(icon, i) {
                setTimeout(function() {
                    var btn = icon.closest('button');
                    if (btn) btn.click();
                    else icon.click();
                }, i * 500);
                clicked++;
            });
            copy(String(clicked));
        })();
        '''
        result = self.run_js(js_click)

        # Cho download hoan thanh (500ms * so anh + 2s buffer)
        wait_time = num_buttons * 0.5 + 2
        self.log(f"   Doi {wait_time}s cho download...")
        time.sleep(wait_time)

        try:
            clicked = int(result) if result else 0
            self.log_ok(f"Da click {clicked} nut download")
            return clicked
        except:
            return num_buttons

    def move_downloads_to_folder(self, output_folder: Path, prefix: str, count: int) -> List[str]:
        """Di chuyen anh tu Downloads sang output folder"""
        import shutil
        from pathlib import Path

        # Tim thu muc Downloads
        home = Path.home()
        downloads = home / "Downloads"
        if not downloads.exists():
            downloads = home / "Tải xuống"  # Vietnamese
        if not downloads.exists():
            self.log_err("Khong tim thay thu muc Downloads")
            return []

        output_folder.mkdir(parents=True, exist_ok=True)
        saved = []

        # Tim cac file anh moi nhat trong Downloads (trong 60s gan day)
        import time as time_module
        now = time_module.time()
        recent_files = []

        for f in downloads.iterdir():
            if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
                # Chi lay file duoc tao trong 60s gan day
                if now - f.stat().st_mtime < 60:
                    recent_files.append(f)

        # Sap xep theo thoi gian tao
        recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Lay so file can thiet
        files_to_move = recent_files[:count] if count > 0 else recent_files

        self.log(f"   Tim thay {len(files_to_move)} file moi trong Downloads")

        for i, src_file in enumerate(files_to_move):
            try:
                filename = f"{prefix}_{i+1}{src_file.suffix}"
                dst_file = output_folder / filename
                shutil.move(str(src_file), str(dst_file))
                saved.append(str(dst_file))
                self.log_ok(f"Moved: {src_file.name} -> {filename}")
            except Exception as e:
                self.log_err(f"Loi move file: {e}")

        return saved

    def extract_product(
        self,
        image_paths: List[str],
        output_folder: str,
        product_code: str = ""
    ) -> ExtractResult:
        """Tach san pham tu anh"""
        if not HAS_PAG:
            return ExtractResult(False, error="Thieu pyautogui/pyperclip")

        if not image_paths:
            return ExtractResult(False, error="Khong co anh")

        try:
            self.log(f"\n=== GEMINI EXTRACT: {product_code or 'images'} ===")
            self.log(f"   {len(image_paths)} anh can xu ly")

            # Mo Gemini
            if not self.open_chrome(self.GEMINI_URL):
                return ExtractResult(False, error="Khong mo duoc Chrome")

            time.sleep(3)

            # Nhap prompt
            if not self.type_prompt():
                return ExtractResult(False, error="Khong nhap duoc prompt")

            time.sleep(1)

            # Upload files
            if not self.upload_files(image_paths):
                return ExtractResult(False, error="Khong upload duoc files")

            time.sleep(2)

            # Gui prompt
            if not self.send_prompt():
                return ExtractResult(False, error="Khong gui duoc prompt")

            # Doi hoan thanh
            if not self.wait_for_completion(timeout=180):
                return ExtractResult(False, error="Timeout")

            # Doi them 5s de anh on dinh
            self.log("   Doi 5s cho anh on dinh...")
            time.sleep(5)

            # Click nut download trong Gemini UI
            num_downloaded = self.click_download_buttons()

            if num_downloaded == 0:
                return ExtractResult(False, error="Khong tim thay nut download")

            # Di chuyen file tu Downloads sang output folder
            out_folder = Path(output_folder)
            prefix = product_code or "extracted"
            saved = self.move_downloads_to_folder(out_folder, prefix, num_downloaded)

            if saved:
                self.log_ok(f"Da luu {len(saved)} anh vao {out_folder}")
                return ExtractResult(True, images=saved)
            else:
                return ExtractResult(False, error="Khong move duoc file tu Downloads")

        except Exception as e:
            self.log_err(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return ExtractResult(False, error=str(e))

    def extract_product_continue(
        self,
        image_paths: List[str],
        output_folder: str,
        product_code: str = ""
    ) -> ExtractResult:
        """Tach san pham (tiep tuc, khong mo Chrome moi)"""
        if not HAS_PAG:
            return ExtractResult(False, error="Thieu pyautogui/pyperclip")

        if not image_paths:
            return ExtractResult(False, error="Khong co anh")

        try:
            self.log(f"\n=== GEMINI EXTRACT (continue): {product_code or 'images'} ===")
            self.log(f"   {len(image_paths)} anh can xu ly")

            # Focus Chrome va refresh
            self._focus_chrome_window()
            pag.press("f5")
            time.sleep(4)

            # Nhap prompt
            if not self.type_prompt():
                return ExtractResult(False, error="Khong nhap duoc prompt")

            time.sleep(1)

            # Upload files
            if not self.upload_files(image_paths):
                return ExtractResult(False, error="Khong upload duoc files")

            time.sleep(2)

            # Gui prompt
            if not self.send_prompt():
                return ExtractResult(False, error="Khong gui duoc prompt")

            # Doi hoan thanh
            if not self.wait_for_completion(timeout=180):
                return ExtractResult(False, error="Timeout")

            # Doi them 5s de anh on dinh
            self.log("   Doi 5s cho anh on dinh...")
            time.sleep(5)

            # Click nut download trong Gemini UI
            num_downloaded = self.click_download_buttons()

            if num_downloaded == 0:
                return ExtractResult(False, error="Khong tim thay nut download")

            # Di chuyen file tu Downloads sang output folder
            out_folder = Path(output_folder)
            prefix = product_code or "extracted"
            saved = self.move_downloads_to_folder(out_folder, prefix, num_downloaded)

            if saved:
                self.log_ok(f"Da luu {len(saved)} anh vao {out_folder}")
                return ExtractResult(True, images=saved)
            else:
                return ExtractResult(False, error="Khong move duoc file tu Downloads")

        except Exception as e:
            self.log_err(f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return ExtractResult(False, error=str(e))


def get_images_in_folder(folder: str) -> List[str]:
    """Lay danh sach anh trong folder"""
    folder = Path(folder)
    if not folder.exists():
        return []

    extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    images = []
    for f in folder.iterdir():
        if f.suffix.lower() in extensions:
            images.append(str(f))

    return sorted(images)
