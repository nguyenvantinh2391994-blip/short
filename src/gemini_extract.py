"""
Gemini Product Extraction - Tách sản phẩm từ ảnh sử dụng Gemini

Sử dụng PyAutoGUI để điều khiển browser, dùng chrome_manager chung.
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

from .chrome_manager import chrome_manager


@dataclass
class ExtractResult:
    """Kết quả tách sản phẩm"""
    success: bool
    images: List[str] = None
    error: str = ""


EXTRACT_PROMPT_TEMPLATE = """IMAGE EDITING TASK — OBJECT EXTRACTION

This is an IMAGE EDITING task.
You must PROCESS the input image and RETURN a NEW IMAGE as output.

Task description:
Extract (cut out) the MAIN PRODUCT from the image.

Target product:
- The product to extract is: {product_name}
- The product must be treated as a standalone physical object.

Explicit exclusions (VERY IMPORTANT):
- Any human, child, model, mannequin
- Any body part: face, skin, hair, hands, arms, legs, feet
- Any human silhouette or body shape
- Any text, logo, watermark, branding
NONE of the above are part of the product and must be COMPLETELY REMOVED.

Editing instructions:
- Remove the entire background
- Keep ONLY the main product object
- Preserve real-world shape, proportions, and surface details
- Maintain natural structure (do NOT flatten unless the real product is flat)
- Do NOT stylize, beautify, redesign, or invent details

Output requirements:
- Output must be an IMAGE
- ONE product object only
- Pure white background (#FFFFFF)
- No shadows, no reflections, no floor
- No text in the output

Final rule:
You must return ONLY the edited product image.
Do NOT return any text."""


class GeminiExtract:
    """Tách sản phẩm từ ảnh sử dụng Gemini - dùng chrome_manager chung"""

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
        self._is_hidden = False

        # Cấu hình chrome_manager
        chrome_manager.set_profile(
            chrome_path=self.chrome_path,
            profile_path=self.profile_path,
        )

    def log(self, msg: str):
        console.print(f"[cyan]{msg}[/]")

    def log_ok(self, msg: str):
        console.print(f"[green]   OK: {msg}[/]")

    def log_err(self, msg: str):
        console.print(f"[red]   Loi: {msg}[/]")

    def _focus_chrome_window(self) -> bool:
        """Focus vao cua so Chrome - dùng chrome_manager"""
        return chrome_manager._focus_chrome()

    def open_chrome(self, url: str) -> bool:
        """Mo Chrome voi profile - dùng chrome_manager chung"""
        return chrome_manager.open_chrome(url)

    def run_js(self, js: str) -> Optional[str]:
        """Chay JS qua DevTools Console - dùng chrome_manager"""
        return chrome_manager.run_js(js)

    def type_prompt(self, product_name: str = "sản phẩm") -> bool:
        """Nhap prompt vao textarea"""
        self.log(f"Nhap prompt (san pham: {product_name})...")

        # Format prompt với tên sản phẩm
        prompt = EXTRACT_PROMPT_TEMPLATE.format(product_name=product_name)
        escaped_prompt = prompt.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

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
        product_code: str = "",
        product_name: str = ""
    ) -> ExtractResult:
        """Tach san pham tu anh

        Args:
            image_paths: Danh sách đường dẫn ảnh
            output_folder: Thư mục output
            product_code: Mã sản phẩm
            product_name: Tên sản phẩm (từ cột C) - giúp Gemini hiểu cần tách gì
        """
        if not HAS_PAG:
            return ExtractResult(False, error="Thieu pyautogui/pyperclip")

        if not image_paths:
            return ExtractResult(False, error="Khong co anh")

        try:
            self.log(f"\n=== GEMINI EXTRACT: {product_code or 'images'} ===")
            self.log(f"   San pham: {product_name or 'N/A'}")
            self.log(f"   {len(image_paths)} anh can xu ly")

            # Mo Gemini
            if not self.open_chrome(self.GEMINI_URL):
                return ExtractResult(False, error="Khong mo duoc Chrome")

            time.sleep(3)

            # Nhap prompt với tên sản phẩm
            if not self.type_prompt(product_name=product_name or "sản phẩm"):
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
        product_code: str = "",
        product_name: str = ""
    ) -> ExtractResult:
        """Tach san pham (tiep tuc, khong mo Chrome moi)

        Args:
            image_paths: Danh sách đường dẫn ảnh
            output_folder: Thư mục output
            product_code: Mã sản phẩm
            product_name: Tên sản phẩm (từ cột C)
        """
        if not HAS_PAG:
            return ExtractResult(False, error="Thieu pyautogui/pyperclip")

        if not image_paths:
            return ExtractResult(False, error="Khong co anh")

        try:
            self.log(f"\n=== GEMINI EXTRACT (continue): {product_code or 'images'} ===")
            self.log(f"   San pham: {product_name or 'N/A'}")
            self.log(f"   {len(image_paths)} anh can xu ly")

            # Navigate den URL moi de tao conversation moi
            chrome_manager._focus_chrome()
            self.log(f"   Mo conversation moi...")

            # Dung chrome_manager de navigate
            chrome_manager.navigate_to("https://gemini.google.com/app?hl=vi")
            time.sleep(5)  # Doi page load

            # Nhap prompt với tên sản phẩm
            if not self.type_prompt(product_name=product_name or "sản phẩm"):
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
