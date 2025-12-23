"""
Gemini Product Extraction - Tách sản phẩm từ ảnh sử dụng Gemini

Sử dụng Selenium với undetected_chromedriver để hỗ trợ headless và chạy song song.
"""

import os
import time
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    uc = None

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
    """Tách sản phẩm từ ảnh sử dụng Gemini với Selenium"""

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
        self.driver = None
        self._is_hidden = False

    def log(self, msg: str):
        console.print(f"[cyan]{msg}[/]")

    def log_ok(self, msg: str):
        console.print(f"[green]   OK: {msg}[/]")

    def log_err(self, msg: str):
        console.print(f"[red]   Loi: {msg}[/]")

    def _setup_driver(self) -> bool:
        """Khoi tao Selenium driver"""
        if not HAS_SELENIUM:
            self.log_err("Thieu undetected_chromedriver. Cai bang: pip install undetected-chromedriver")
            return False

        try:
            options = uc.ChromeOptions()

            # Profile path
            if self.profile_path:
                profile = Path(self.profile_path)
                if profile.exists():
                    options.add_argument(f"--user-data-dir={profile.parent}")
                    options.add_argument(f"--profile-directory={profile.name}")

            # Headless mode
            if self.headless:
                options.add_argument("--headless=new")

            # Cac option chong detect
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--start-maximized")

            self.driver = uc.Chrome(
                options=options,
                browser_executable_path=self.chrome_path if os.path.exists(self.chrome_path) else None,
            )

            self.log_ok("Da khoi tao Chrome driver")
            return True

        except Exception as e:
            self.log_err(f"Loi khoi tao driver: {e}")
            return False

    def open_gemini(self) -> bool:
        """Mo trang Gemini"""
        try:
            self.driver.get(self.GEMINI_URL)
            time.sleep(3)

            # Doi trang load xong
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ql-editor"))
            )
            self.log_ok("Da mo Gemini")
            return True

        except Exception as e:
            self.log_err(f"Loi mo Gemini: {e}")
            return False

    def type_prompt(self) -> bool:
        """Nhap prompt vao textarea"""
        self.log("Nhap prompt...")

        try:
            editor = self.driver.find_element(By.CSS_SELECTOR, ".ql-editor")
            editor.click()
            time.sleep(0.3)

            # Dung JavaScript de set text (vi textContent/innerHTML bi block)
            self.driver.execute_script(
                "arguments[0].textContent = arguments[1];",
                editor,
                EXTRACT_PROMPT
            )

            # Trigger input event
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                editor
            )

            self.log_ok("Da nhap prompt")
            return True

        except Exception as e:
            self.log_err(f"Loi nhap prompt: {e}")
            return False

    def upload_files(self, image_paths: List[str]) -> bool:
        """Upload files bang cach tao input[type=file] an va trigger"""
        self.log(f"Upload {len(image_paths)} files...")

        try:
            # Click nut upload menu
            upload_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".upload-card-button"))
            )
            upload_btn.click()
            time.sleep(0.5)

            # Doi menu xuat hien va click "Tai tep len"
            file_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-test-id="local-images-files-uploader-button"]'))
            )

            # Tao input[type=file] an de upload
            # Inject hidden file input
            self.driver.execute_script("""
                var input = document.createElement('input');
                input.type = 'file';
                input.id = 'selenium-file-input';
                input.multiple = true;
                input.accept = 'image/*';
                input.style.display = 'none';
                document.body.appendChild(input);
            """)

            # Tim input vua tao
            file_input = self.driver.find_element(By.ID, "selenium-file-input")

            # Gui file paths vao input (phan cach bang \n)
            file_paths_str = "\n".join(image_paths)
            file_input.send_keys(file_paths_str)

            time.sleep(1)

            # Lay files tu input va dispatch vao Gemini
            # Su dung DataTransfer API
            self.driver.execute_script("""
                var input = document.getElementById('selenium-file-input');
                var files = input.files;

                // Tim nut upload thuc su va trigger
                var uploadBtn = document.querySelector('button[data-test-id="local-images-files-uploader-button"]');
                if (uploadBtn) {
                    // Tao DataTransfer object
                    var dt = new DataTransfer();
                    for (var i = 0; i < files.length; i++) {
                        dt.items.add(files[i]);
                    }

                    // Tim hidden input trong component
                    var hiddenInputs = document.querySelectorAll('input[type="file"]');
                    if (hiddenInputs.length > 0) {
                        hiddenInputs[0].files = dt.files;
                        hiddenInputs[0].dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }

                // Xoa input tam
                input.remove();
            """)

            time.sleep(2)

            # Kiem tra xem co anh duoc upload khong
            # Neu khong co input[type=file], thu cach khac: drag & drop
            uploaded = self.driver.execute_script("""
                var previews = document.querySelectorAll('.preview-image, .uploaded-image, img[src*="blob:"]');
                return previews.length;
            """)

            if uploaded > 0:
                self.log_ok(f"Da upload {uploaded} files")
                return True

            # Neu cach tren khong duoc, thu drag & drop
            self.log("Thu upload bang drag & drop...")
            return self._upload_via_drag_drop(image_paths)

        except Exception as e:
            self.log_err(f"Loi upload: {e}")
            return False

    def _upload_via_drag_drop(self, image_paths: List[str]) -> bool:
        """Upload bang cach mo phong drag & drop"""
        try:
            # Tao input file moi
            self.driver.execute_script("""
                var input = document.createElement('input');
                input.type = 'file';
                input.id = 'selenium-drop-input';
                input.multiple = true;
                input.style.position = 'fixed';
                input.style.top = '0';
                input.style.left = '0';
                input.style.opacity = '0';
                document.body.appendChild(input);
            """)

            file_input = self.driver.find_element(By.ID, "selenium-drop-input")
            file_paths_str = "\n".join(image_paths)
            file_input.send_keys(file_paths_str)

            # Simulate drop event vao editor
            self.driver.execute_script("""
                var input = document.getElementById('selenium-drop-input');
                var files = input.files;
                var editor = document.querySelector('.ql-editor');

                if (editor && files.length > 0) {
                    var dt = new DataTransfer();
                    for (var i = 0; i < files.length; i++) {
                        dt.items.add(files[i]);
                    }

                    var dropEvent = new DragEvent('drop', {
                        bubbles: true,
                        cancelable: true,
                        dataTransfer: dt
                    });

                    editor.dispatchEvent(dropEvent);
                }

                input.remove();
            """)

            time.sleep(2)
            self.log_ok("Da thu drag & drop")
            return True

        except Exception as e:
            self.log_err(f"Loi drag & drop: {e}")
            return False

    def send_prompt(self) -> bool:
        """Gui prompt"""
        self.log("Gui prompt...")

        try:
            # Tim va click nut gui
            send_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Gửi tin nhắn"], .send-button'))
            )
            send_btn.click()

            self.log_ok("Da gui prompt")
            return True

        except Exception as e:
            self.log_err(f"Loi gui: {e}")
            return False

    def wait_for_completion(self, timeout: int = 180) -> bool:
        """Doi Gemini tao anh xong"""
        self.log(f"Doi tao anh... (toi da {timeout}s)")

        start = time.time()
        check_interval = 5

        while time.time() - start < timeout:
            time.sleep(check_interval)
            elapsed = int(time.time() - start)

            # Check xem con dang loading khong
            is_loading = self.driver.execute_script("""
                var stop = document.querySelector('mat-icon[fonticon="stop"]');
                var loading = document.querySelector('[data-test-id="loading-indicator"]');
                return !!(stop || loading);
            """)

            if not is_loading:
                # Check co anh ket qua khong
                has_images = self.driver.execute_script("""
                    var imgs = document.querySelectorAll('generated-image img.image');
                    return imgs.length > 0;
                """)

                if has_images:
                    self.log_ok(f"Hoan thanh! ({elapsed}s)")
                    return True

            self.log(f"   {elapsed}s - Dang xu ly...")

        self.log_err(f"Timeout sau {timeout}s")
        return False

    def get_generated_images(self) -> List[str]:
        """Lay URL cac anh da tao"""
        try:
            urls = self.driver.execute_script("""
                var imgs = document.querySelectorAll('generated-image img.image');
                var urls = [];
                imgs.forEach(function(img) {
                    if (img.src && img.src.includes('googleusercontent')) {
                        urls.push(img.src);
                    }
                });
                return urls;
            """)

            self.log(f"   Tim thay {len(urls)} anh")
            return urls or []

        except Exception as e:
            self.log_err(f"Loi lay URL anh: {e}")
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

    def close(self):
        """Dong driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

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
        if not HAS_SELENIUM:
            return ExtractResult(False, error="Thieu selenium. Cai: pip install undetected-chromedriver selenium")

        if not image_paths:
            return ExtractResult(False, error="Khong co anh")

        try:
            self.log(f"\n=== GEMINI EXTRACT: {product_code or 'images'} ===")
            self.log(f"   {len(image_paths)} anh can xu ly")

            # Khoi tao driver
            if not self._setup_driver():
                return ExtractResult(False, error="Khong khoi tao duoc driver")

            # Mo Gemini
            if not self.open_gemini():
                return ExtractResult(False, error="Khong mo duoc Gemini")

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

        finally:
            self.close()


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
