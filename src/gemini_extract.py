"""
Gemini Product Extraction - Tách sản phẩm từ ảnh sử dụng Gemini

Sử dụng PyAutoGUI để điều khiển browser, tương tự SORA automation.
"""

import os
import time
import subprocess
import requests
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
    images: List[str] = None  # Danh sách đường dẫn ảnh đã lưu
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
    """Tách sản phẩm từ ảnh sử dụng Gemini"""

    GEMINI_URL = "https://gemini.google.com/app"

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

    def _hide_chrome_window(self):
        """An Chrome window"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle('Gemini')
            if not windows:
                windows = gw.getWindowsWithTitle('Google')
            if windows:
                windows[0].minimize()
                self._is_hidden = True
                self.log("   Da an Chrome")
        except:
            pass

    def show_chrome_window(self):
        """Hien Chrome window"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle('Gemini')
            if not windows:
                windows = gw.getWindowsWithTitle('Google')
            if windows:
                win = windows[0]
                win.restore()
                win.maximize()
                win.activate()
                self._is_hidden = False
                self.log("   Da hien Chrome")
        except:
            pass

    def toggle_chrome_visibility(self):
        """Toggle an/hien"""
        if self._is_hidden:
            self.show_chrome_window()
        else:
            self._hide_chrome_window()

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

        # Dung textContent thay vi innerHTML (do TrustedHTML policy)
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

    def click_upload_and_select_files(self, image_paths: List[str]) -> bool:
        """Click upload va chon files"""
        self.log("Click upload...")

        # Click nut upload (+)
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

        time.sleep(1)

        # Click "Tai tep len" - dung hidden button
        js2 = '''
        (function() {
            var btn = document.querySelector('.hidden-local-file-image-selector-button');
            if (btn) { btn.click(); copy('OK'); }
            else { copy('ERROR'); }
        })();
        '''
        result = self.run_js(js2)
        if not result or 'OK' not in result:
            self.log_err("Khong tim thay nut Tai tep len")
            return False

        time.sleep(1)

        # Nhap duong dan file vao dialog Open
        # Cac file cach nhau boi dau " (Windows)
        if len(image_paths) == 1:
            file_str = image_paths[0]
        else:
            # Nhieu file: "file1" "file2" "file3"
            file_str = ' '.join([f'"{p}"' for p in image_paths])

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

        # Click nut gui tin nhan
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

    def is_generating(self) -> bool:
        """Check dang tao anh (co icon stop)"""
        js = '''
        (function() {
            var stop = document.querySelector('mat-icon[fonticon="stop"]');
            copy(stop ? 'YES' : 'NO');
        })();
        '''
        result = self.run_js(js)
        return result and 'YES' in result

    def is_complete(self) -> bool:
        """Check da xong (co icon mic, khong co stop)"""
        js = '''
        (function() {
            var mic = document.querySelector('.text-input-field mat-icon[fonticon="mic"]');
            var stop = document.querySelector('mat-icon[fonticon="stop"]');
            copy((mic && !stop) ? 'DONE' : 'WAIT');
        })();
        '''
        result = self.run_js(js)
        return result and 'DONE' in result

    def wait_for_completion(self, timeout: int = 180) -> bool:
        """Doi tao anh xong (toi da 3 phut)"""
        self.log(f"Doi tao anh... (toi da {timeout}s)")

        if self.headless:
            self._hide_chrome_window()

        start = time.time()
        check_interval = 10

        while time.time() - start < timeout:
            time.sleep(check_interval)
            elapsed = int(time.time() - start)

            if self.headless:
                self.show_chrome_window()
                time.sleep(0.5)

            self.log(f"   {elapsed}s - Check...")

            if self.is_complete():
                self.log_ok(f"Hoan thanh! ({elapsed}s)")
                return True

            if self.headless:
                self._hide_chrome_window()

        self.log_err(f"Timeout sau {timeout}s")
        return False

    def get_generated_images(self) -> List[str]:
        """Lay URL cac anh da tao"""
        js = '''
        (function() {
            var imgs = document.querySelectorAll('generated-image img.image');
            var urls = [];
            imgs.forEach(function(img) {
                if (img.src && img.src.includes('googleusercontent')) {
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

    def download_images(self, urls: List[str], output_folder: Path, prefix: str = "extracted") -> List[str]:
        """Download cac anh tu URL"""
        saved = []
        output_folder.mkdir(parents=True, exist_ok=True)

        for i, url in enumerate(urls):
            try:
                self.log(f"   Download anh {i+1}/{len(urls)}...")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    filename = f"{prefix}_{i+1}.png"
                    filepath = output_folder / filename
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    saved.append(str(filepath))
                    self.log_ok(f"Saved: {filename}")
            except Exception as e:
                self.log_err(f"Loi download: {e}")

        return saved

    def extract_product(
        self,
        image_paths: List[str],
        output_folder: str,
        product_code: str = ""
    ) -> ExtractResult:
        """
        Tach san pham tu anh

        Args:
            image_paths: Danh sach duong dan anh can tach
            output_folder: Thu muc luu anh da tach
            product_code: Ma san pham (de dat ten file)

        Returns:
            ExtractResult
        """
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
            if not self.click_upload_and_select_files(image_paths):
                return ExtractResult(False, error="Khong upload duoc files")

            time.sleep(2)

            # Gui prompt
            if not self.send_prompt():
                return ExtractResult(False, error="Khong gui duoc prompt")

            # Doi hoan thanh
            if not self.wait_for_completion(timeout=180):
                return ExtractResult(False, error="Timeout")

            # Lay URL anh
            urls = self.get_generated_images()
            if not urls:
                return ExtractResult(False, error="Khong tim thay anh da tao")

            # Download anh
            out_folder = Path(output_folder)
            prefix = product_code or "extracted"
            saved = self.download_images(urls, out_folder, prefix)

            if saved:
                self.log_ok(f"Da luu {len(saved)} anh vao {out_folder}")
                return ExtractResult(True, images=saved)
            else:
                return ExtractResult(False, error="Khong download duoc anh")

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
        """
        Tach san pham (tiep tuc, khong mo Chrome moi)
        """
        if not HAS_PAG:
            return ExtractResult(False, error="Thieu pyautogui/pyperclip")

        if not image_paths:
            return ExtractResult(False, error="Khong co anh")

        try:
            self.log(f"\n=== GEMINI EXTRACT (continue): {product_code or 'images'} ===")

            # Focus Chrome
            self._focus_chrome_window()
            time.sleep(1)

            # Refresh trang
            pag.press("f5")
            time.sleep(4)

            # Nhap prompt
            if not self.type_prompt():
                return ExtractResult(False, error="Khong nhap duoc prompt")

            time.sleep(1)

            # Upload files
            if not self.click_upload_and_select_files(image_paths):
                return ExtractResult(False, error="Khong upload duoc files")

            time.sleep(2)

            # Gui prompt
            if not self.send_prompt():
                return ExtractResult(False, error="Khong gui duoc prompt")

            # Doi hoan thanh
            if not self.wait_for_completion(timeout=180):
                return ExtractResult(False, error="Timeout")

            # Lay URL anh
            urls = self.get_generated_images()
            if not urls:
                return ExtractResult(False, error="Khong tim thay anh da tao")

            # Download anh
            out_folder = Path(output_folder)
            prefix = product_code or "extracted"
            saved = self.download_images(urls, out_folder, prefix)

            if saved:
                return ExtractResult(True, images=saved)
            else:
                return ExtractResult(False, error="Khong download duoc anh")

        except Exception as e:
            self.log_err(f"Exception: {e}")
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
