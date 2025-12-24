# Google Flow Image Generation - Complete Implementation

## PROMPT CHO SESSION KHÁC

Copy toàn bộ nội dung dưới đây vào session mới:

---

## Yêu cầu: Implement tính năng tạo ảnh với Google Flow

Tạo một Python module hoàn chỉnh để:
1. Mở Chrome với profile có sẵn (đã login Google)
2. Navigate đến Google Flow
3. Tự động click tạo project mới, chọn "Tạo hình ảnh"
4. Gửi prompt test để trigger API call
5. Capture Bearer Token từ network request
6. Dùng token gọi Proxy API để tạo ảnh
7. Download ảnh về thư mục local

---

## PHẦN 1: Dependencies cần cài

```bash
pip install selenium pyautogui pyperclip requests
```

---

## PHẦN 2: Code hoàn chỉnh

### File: `flow_image_generator.py`

```python
"""
Google Flow Image Generator
===========================
Tự động mở Chrome, lấy token, tạo ảnh và download.

Usage:
    generator = FlowImageGenerator(
        chrome_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        profile_dir="./chrome_profiles/main",
        proxy_api_token="YOUR_NANOAI_TOKEN"
    )

    # Bước 1: Mở Chrome và lấy token
    token, project_id = generator.get_token()

    # Bước 2: Tạo ảnh
    images = generator.generate_images("a beautiful sunset over ocean", count=2)

    # Bước 3: Download
    generator.download_images(images, output_dir="./output")
"""

import os
import sys
import time
import json
import uuid
import random
import base64
import subprocess
import requests
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

# Optional: PyAutoGUI cho automation
try:
    import pyautogui as pag
    pag.FAILSAFE = True
    pag.PAUSE = 0.1
    HAS_PYAUTOGUI = True
except ImportError:
    pag = None
    HAS_PYAUTOGUI = False

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    pyperclip = None
    HAS_PYPERCLIP = False

# Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


class FlowImageGenerator:
    """
    Tạo ảnh với Google Flow API.

    Hỗ trợ 2 mode:
    - Selenium mode: Tự động hoàn toàn bằng Selenium WebDriver
    - PyAutoGUI mode: Dùng PyAutoGUI để click UI (fallback)
    """

    # URLs
    FLOW_URL = "https://labs.google/fx/vi/tools/flow"

    # Proxy API (bypass captcha)
    PROXY_IMAGE_API = "https://flow-api.nanoai.pics/api/fix/create-image-veo3"
    PROXY_TASK_STATUS = "https://flow-api.nanoai.pics/api/fix/task-status"

    # Direct API (có thể bị captcha)
    DIRECT_API_BASE = "https://aisandbox-pa.googleapis.com"

    # Image settings
    DEFAULT_MODEL = "GEM_PIX_2"
    DEFAULT_ASPECT_RATIO = "IMAGE_ASPECT_RATIO_LANDSCAPE"  # 16:9

    def __init__(
        self,
        chrome_path: str = None,
        profile_dir: str = None,
        proxy_api_token: str = None,
        headless: bool = False,
        verbose: bool = True
    ):
        """
        Khởi tạo generator.

        Args:
            chrome_path: Đường dẫn Chrome executable
            profile_dir: Thư mục Chrome profile (đã login Google)
            proxy_api_token: Token từ nanoai.pics để bypass captcha
            headless: Chạy ẩn browser (không khuyến khích lần đầu)
            verbose: In log chi tiết
        """
        # Chrome path
        if chrome_path:
            self.chrome_path = chrome_path
        elif sys.platform == "win32":
            self.chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        else:
            self.chrome_path = "/usr/bin/google-chrome"

        # Profile
        self.profile_dir = Path(profile_dir) if profile_dir else Path("./chrome_profiles/main")

        # API
        self.proxy_api_token = proxy_api_token

        # Settings
        self.headless = headless
        self.verbose = verbose

        # State
        self.bearer_token = None
        self.project_id = None
        self.driver = None  # Selenium driver

        # Token cache
        self.token_cache_file = self.profile_dir.parent / "token_cache.json"
        self._load_cached_token()

    def log(self, msg: str, level: str = "INFO"):
        """Print log message."""
        if self.verbose:
            print(f"[{level}] {msg}")

    # =========================================================================
    # TOKEN CACHING
    # =========================================================================

    def _load_cached_token(self):
        """Load token từ cache nếu còn hạn."""
        if not self.token_cache_file.exists():
            return

        try:
            with open(self.token_cache_file, 'r') as f:
                data = json.load(f)

            # Check hết hạn (50 phút)
            token_time = data.get("time", 0)
            if time.time() - token_time < 50 * 60:
                self.bearer_token = data.get("token")
                self.project_id = data.get("project_id")
                self.log(f"Loaded cached token: {self.bearer_token[:30]}...")
        except Exception as e:
            self.log(f"Load cache error: {e}", "WARN")

    def _save_token_cache(self):
        """Lưu token vào cache."""
        try:
            self.token_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_cache_file, 'w') as f:
                json.dump({
                    "token": self.bearer_token,
                    "project_id": self.project_id,
                    "time": time.time()
                }, f)
            self.log("Token cached")
        except Exception as e:
            self.log(f"Save cache error: {e}", "WARN")

    def is_token_valid(self) -> bool:
        """Check token còn valid không."""
        return bool(self.bearer_token and self.bearer_token.startswith("ya29."))

    # =========================================================================
    # METHOD 1: SELENIUM (Khuyến khích)
    # =========================================================================

    def get_token_selenium(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Lấy token bằng Selenium WebDriver.

        Flow:
        1. Mở Chrome với profile
        2. Navigate đến Flow
        3. Inject capture script
        4. Click "Dự án mới" -> "Tạo hình ảnh"
        5. Gửi prompt test
        6. Capture token từ window._tk

        Returns:
            Tuple[bearer_token, project_id]
        """
        if not HAS_SELENIUM:
            self.log("Selenium không được cài. Chạy: pip install selenium", "ERROR")
            return None, None

        self.log("=== LẤY TOKEN BẰNG SELENIUM ===")

        try:
            # Tạo Chrome options
            options = Options()

            # Profile - QUAN TRỌNG: phải dùng profile đã login Google
            profile_path = self.profile_dir.resolve()
            profile_path.mkdir(parents=True, exist_ok=True)

            # Working profile (copy từ profile gốc)
            working_profile = Path.home() / ".flow_chrome_profiles" / self.profile_dir.name
            working_profile.mkdir(parents=True, exist_ok=True)

            # Copy profile data lần đầu
            if not any(working_profile.iterdir()) and profile_path.exists():
                import shutil
                for item in profile_path.iterdir():
                    try:
                        dest = working_profile / item.name
                        if item.is_dir():
                            shutil.copytree(item, dest, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, dest)
                    except:
                        pass
                self.log(f"Copied profile to {working_profile}")

            options.add_argument(f"--user-data-dir={working_profile}")

            # Random port để tránh conflict
            debug_port = random.randint(9222, 9999)
            options.add_argument(f"--remote-debugging-port={debug_port}")

            # Headless (không khuyến khích lần đầu vì cần đăng nhập)
            if self.headless:
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")

            # Các options khác
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--window-size=1920,1080")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])

            # Khởi động Chrome
            self.log(f"Khởi động Chrome (port {debug_port})...")
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_script_timeout(120)

            # Hide webdriver flag
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            # Navigate đến Flow
            self.log(f"Navigate đến {self.FLOW_URL}...")
            self.driver.get(self.FLOW_URL)

            # Đợi trang load
            self.log("Đợi trang load (10s)...")
            time.sleep(10)

            # Check đã login chưa
            if "accounts.google.com" in self.driver.current_url:
                self.log("CHƯA ĐĂNG NHẬP GOOGLE! Hãy đăng nhập thủ công.", "ERROR")
                self.log("Sau khi đăng nhập, chạy lại script.")
                input("Nhấn Enter sau khi đăng nhập xong...")
                self.driver.get(self.FLOW_URL)
                time.sleep(5)

            # Inject capture script
            self.log("Inject capture script...")
            capture_script = """
            window._tk = null;
            window._pj = null;

            (function() {
                var originalFetch = window.fetch;
                window.fetch = function(url, options) {
                    var urlStr = url ? url.toString() : '';

                    if (urlStr.includes('flowMedia') || urlStr.includes('aisandbox') || urlStr.includes('batchGenerate')) {
                        var headers = options && options.headers ? options.headers : {};
                        var auth = headers.Authorization || headers.authorization || '';

                        if (auth.startsWith('Bearer ')) {
                            window._tk = auth.substring(7);

                            // Extract project_id từ URL
                            var match = urlStr.match(/\\/projects\\/([^\\/]+)\\//);
                            if (match) window._pj = match[1];

                            console.log('=== TOKEN CAPTURED ===');
                            console.log('Token:', window._tk.substring(0, 30) + '...');
                            console.log('Project:', window._pj);
                        }
                    }
                    return originalFetch.apply(this, arguments);
                };
                console.log('Capture script ready');
            })();
            """
            self.driver.execute_script(capture_script)
            time.sleep(1)

            # Click "Dự án mới"
            self.log("Tìm và click 'Dự án mới'...")
            clicked_new = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for (var btn of buttons) {
                    var text = btn.textContent || '';
                    if (text.includes('Dự án mới') || text.includes('New project')) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            """)

            if clicked_new:
                self.log("Đã click 'Dự án mới'")
            else:
                self.log("Không tìm thấy nút 'Dự án mới'", "WARN")

            time.sleep(5)

            # Click dropdown và chọn "Tạo hình ảnh"
            self.log("Chọn 'Tạo hình ảnh' từ dropdown...")
            self.driver.execute_script("""
                (async function() {
                    // Click dropdown
                    var dropdown = document.querySelector('button[role="combobox"]');
                    if (dropdown) {
                        dropdown.click();
                        await new Promise(r => setTimeout(r, 500));

                        // Tìm và click "Tạo hình ảnh"
                        var allElements = document.querySelectorAll('*');
                        for (var el of allElements) {
                            var text = el.textContent || '';
                            if (text === 'Tạo hình ảnh' || text.includes('Tạo hình ảnh từ văn bản') ||
                                text === 'Generate image') {
                                var rect = el.getBoundingClientRect();
                                if (rect.height > 10 && rect.height < 80 && rect.width > 50) {
                                    el.click();
                                    console.log('Clicked: ' + text.substring(0, 40));
                                    return;
                                }
                            }
                        }
                    }
                })();
            """)
            time.sleep(3)

            # Lưu project URL
            current_url = self.driver.current_url
            if '/project/' in current_url:
                project_id = current_url.split('/project/')[1].split('/')[0].split('?')[0]
                self.project_id = project_id
                self.log(f"Project ID từ URL: {project_id}")

            # Focus textarea và gửi prompt
            self.log("Gửi prompt test...")
            test_prompt = "beautiful sunset over ocean, golden hour, cinematic"

            self.driver.execute_script("""
                var textarea = document.querySelector('textarea');
                if (textarea) {
                    textarea.focus();
                    textarea.click();

                    // Set value (React compatible)
                    var setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
                    if (setter) {
                        setter.call(textarea, arguments[0]);
                    } else {
                        textarea.value = arguments[0];
                    }
                    textarea.dispatchEvent(new Event('input', {bubbles: true}));
                    textarea.dispatchEvent(new Event('change', {bubbles: true}));

                    // Enter để gửi
                    setTimeout(function() {
                        textarea.dispatchEvent(new KeyboardEvent('keydown', {
                            key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                        }));
                    }, 500);
                }
            """, test_prompt)

            # Đợi ảnh được tạo (20-30s)
            self.log("Đợi ảnh được tạo (25s)...")
            time.sleep(25)

            # Lấy token
            self.log("Kiểm tra token...")
            for attempt in range(10):
                result = self.driver.execute_script(
                    "return {token: window._tk, project: window._pj};"
                )

                token = result.get("token")
                project = result.get("project")

                if token and len(token) > 50:
                    self.bearer_token = token
                    self.project_id = project or self.project_id
                    self.log(f"=== ĐÃ LẤY ĐƯỢC TOKEN ===")
                    self.log(f"Token: {token[:40]}...{token[-20:]}")
                    self.log(f"Project: {self.project_id}")
                    self._save_token_cache()
                    return token, self.project_id

                self.log(f"Thử lần {attempt + 1}/10...")
                time.sleep(3)

            self.log("Không lấy được token", "ERROR")
            return None, None

        except Exception as e:
            self.log(f"Lỗi: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return None, None

        finally:
            # Không đóng browser để có thể debug
            pass

    def close_browser(self):
        """Đóng browser."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    # =========================================================================
    # METHOD 2: PYAUTOGUI (Fallback)
    # =========================================================================

    def get_token_pyautogui(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Lấy token bằng PyAutoGUI (click thật trên màn hình).

        Yêu cầu: Chrome phải visible, không có cửa sổ che.
        """
        if not HAS_PYAUTOGUI or not HAS_PYPERCLIP:
            self.log("Cần cài pyautogui và pyperclip", "ERROR")
            return None, None

        self.log("=== LẤY TOKEN BẰNG PYAUTOGUI ===")

        try:
            # Mở Chrome
            profile_path = self.profile_dir.resolve()
            cmd = [
                self.chrome_path,
                f"--user-data-dir={profile_path.parent}",
                f"--profile-directory={profile_path.name}",
                self.FLOW_URL
            ]
            subprocess.Popen(cmd)

            self.log("Chrome đang mở, đợi 12s...")
            time.sleep(12)

            # Inject capture script qua DevTools
            self.log("Mở DevTools và inject script...")
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1.5)

            capture_script = '''window._tk=null;window._pj=null;(function(){var f=window.fetch;window.fetch=function(u,o){var s=u?u.toString():'';if(s.includes('flowMedia')||s.includes('aisandbox')){var h=o&&o.headers?o.headers:{};var a=h.Authorization||h.authorization||'';if(a.startsWith('Bearer ')){window._tk=a.substring(7);var m=s.match(/\\/projects\\/([^\\/]+)\\//);if(m)window._pj=m[1];console.log('TOKEN CAPTURED!');}}return f.apply(this,arguments);};console.log('Capture ready');})();'''

            pyperclip.copy(capture_script)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(0.5)

            # Đóng DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            # Click "Dự án mới" bằng JS
            self.log("Click 'Dự án mới'...")
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)

            js_click_new = '''(function(){var btns=document.querySelectorAll('button');for(var b of btns){if(b.textContent.includes('Dự án mới')){b.click();console.log('Clicked');return true;}}return false;})();'''
            pyperclip.copy(js_click_new)
            pag.hotkey("ctrl", "v")
            pag.press("enter")
            time.sleep(0.5)
            pag.hotkey("ctrl", "shift", "j")

            time.sleep(5)

            # Chọn "Tạo hình ảnh"
            self.log("Chọn 'Tạo hình ảnh'...")
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)

            js_select_image = '''(async function(){var dd=document.querySelector('button[role="combobox"]');if(dd){dd.click();await new Promise(r=>setTimeout(r,500));var all=document.querySelectorAll('*');for(var el of all){var t=el.textContent||'';if(t==='Tạo hình ảnh'||t.includes('Tạo hình ảnh từ văn bản')){var r=el.getBoundingClientRect();if(r.height>10&&r.height<80){el.click();return true;}}}}return false;})();'''
            pyperclip.copy(js_select_image)
            pag.hotkey("ctrl", "v")
            pag.press("enter")
            time.sleep(1)
            pag.hotkey("ctrl", "shift", "j")

            time.sleep(3)

            # Focus textarea và gửi prompt
            self.log("Gửi prompt...")
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)

            js_focus = '''(function(){var ta=document.querySelector('textarea');if(ta){ta.focus();ta.click();return true;}return false;})();'''
            pyperclip.copy(js_focus)
            pag.hotkey("ctrl", "v")
            pag.press("enter")
            time.sleep(0.5)
            pag.hotkey("ctrl", "shift", "j")

            time.sleep(1)

            # Paste prompt và Enter
            test_prompt = "beautiful sunset over ocean"
            pyperclip.copy(test_prompt)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)
            pag.press("enter")

            # Đợi ảnh tạo xong
            self.log("Đợi ảnh tạo xong (25s)...")
            time.sleep(25)

            # Lấy token từ DevTools
            self.log("Lấy token...")
            for attempt in range(10):
                pag.hotkey("ctrl", "shift", "j")
                time.sleep(1.2)

                js_get_token = 'copy(JSON.stringify({t:window._tk,p:window._pj}))'
                pyperclip.copy(js_get_token)
                pag.hotkey("ctrl", "v")
                pag.press("enter")
                time.sleep(0.8)

                pag.hotkey("ctrl", "shift", "j")
                time.sleep(0.3)

                try:
                    text = pyperclip.paste()
                    if text and text.startswith('{'):
                        data = json.loads(text)
                        token = data.get("t")
                        project = data.get("p")

                        if token and len(token) > 50:
                            self.bearer_token = token
                            self.project_id = project
                            self.log(f"=== ĐÃ LẤY ĐƯỢC TOKEN ===")
                            self._save_token_cache()
                            return token, project
                except:
                    pass

                self.log(f"Thử lần {attempt + 1}/10...")
                time.sleep(3)

            return None, None

        except Exception as e:
            self.log(f"Lỗi: {e}", "ERROR")
            return None, None

    # =========================================================================
    # IMAGE GENERATION
    # =========================================================================

    def generate_images(
        self,
        prompt: str,
        count: int = 2,
        aspect_ratio: str = None,
        reference_media_names: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Tạo ảnh bằng Proxy API.

        Args:
            prompt: Mô tả ảnh cần tạo
            count: Số lượng ảnh (1-4)
            aspect_ratio: Tỷ lệ khung hình
            reference_media_names: List media_name để reference

        Returns:
            List[{url, media_name, seed}]
        """
        if not self.bearer_token:
            self.log("Chưa có token! Gọi get_token_selenium() trước.", "ERROR")
            return []

        if not self.proxy_api_token:
            self.log("Chưa có proxy_api_token!", "ERROR")
            return []

        self.log(f"=== TẠO {count} ẢNH ===")
        self.log(f"Prompt: {prompt[:50]}...")

        # Build request
        aspect = aspect_ratio or self.DEFAULT_ASPECT_RATIO

        # Build imageInputs cho reference
        image_inputs = []
        if reference_media_names:
            for name in reference_media_names:
                if name:
                    image_inputs.append({
                        "name": name,
                        "imageInputType": "IMAGE_INPUT_TYPE_REFERENCE"
                    })
            self.log(f"References: {len(image_inputs)}")

        # Build requests array
        requests_list = []
        for i in range(count):
            requests_list.append({
                "clientContext": {
                    "sessionId": str(uuid.uuid4()),
                    "projectId": self.project_id,
                    "tool": "PINHOLE"
                },
                "seed": random.randint(1, 999999),
                "imageModelName": self.DEFAULT_MODEL,
                "imageAspectRatio": aspect,
                "prompt": prompt,
                "imageInputs": image_inputs
            })

        body_json = {"requests": requests_list}

        # Proxy payload
        proxy_payload = {
            "body_json": body_json,
            "flow_auth_token": self.bearer_token,
            "flow_url": f"{self.DIRECT_API_BASE}/v1/projects/{self.project_id}/flowMedia:batchGenerateImages"
        }

        headers = {
            "Authorization": f"Bearer {self.proxy_api_token}",
            "Content-Type": "application/json"
        }

        try:
            # Step 1: Create task
            self.log("Gửi request tạo ảnh...")
            response = requests.post(
                self.PROXY_IMAGE_API,
                headers=headers,
                json=proxy_payload,
                timeout=30
            )

            if response.status_code == 401:
                self.log("Proxy API authentication failed!", "ERROR")
                return []

            if response.status_code != 200:
                self.log(f"API error: {response.status_code} - {response.text[:200]}", "ERROR")
                return []

            result = response.json()

            if not result.get("success"):
                self.log(f"Create task failed: {result.get('error')}", "ERROR")
                return []

            task_id = result.get("taskId")
            self.log(f"Task created: {task_id}")

            # Step 2: Poll for result
            return self._poll_and_parse(task_id, headers)

        except Exception as e:
            self.log(f"Generate error: {e}", "ERROR")
            return []

    def _poll_and_parse(
        self,
        task_id: str,
        headers: Dict[str, str],
        max_attempts: int = 60,
        interval: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Poll task status và parse kết quả."""
        self.log(f"Polling task {task_id}...")

        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    f"{self.PROXY_TASK_STATUS}?taskId={task_id}",
                    headers=headers,
                    timeout=30
                )

                if response.status_code != 200:
                    time.sleep(interval)
                    continue

                result = response.json()

                if not result.get("success"):
                    time.sleep(interval)
                    continue

                task_result = result.get("result", {})

                # Check error
                if "error" in task_result:
                    error = task_result["error"]
                    if isinstance(error, dict):
                        error = error.get("message", str(error))
                    self.log(f"API Error: {error}", "ERROR")
                    return []

                # Check media
                if "media" in task_result and task_result["media"]:
                    self.log(f"Task completed! Parsing {len(task_result['media'])} images...")
                    return self._parse_media(task_result["media"])

                # Check explicit success
                if task_result.get("success") == True:
                    return self._parse_media(task_result.get("media", []))

                if task_result.get("success") == False:
                    self.log(f"Task failed: {task_result.get('error')}", "ERROR")
                    return []

                # Still processing
                if (attempt + 1) % 10 == 0:
                    self.log(f"Still processing... ({attempt + 1}/{max_attempts})")

            except Exception as e:
                self.log(f"Poll error: {e}", "WARN")

            time.sleep(interval)

        self.log("Timeout waiting for result", "ERROR")
        return []

    def _parse_media(self, media_list: List[Dict]) -> List[Dict[str, Any]]:
        """Parse media response."""
        results = []

        for i, media in enumerate(media_list):
            image_wrapper = media.get("image", {})
            generated_image = image_wrapper.get("generatedImage", {})

            url = generated_image.get("fifeUrl")
            media_name = media.get("name")  # QUAN TRỌNG: lưu để reference sau
            seed = generated_image.get("seed")

            if url:
                results.append({
                    "url": url,
                    "media_name": media_name,
                    "seed": seed,
                    "index": i
                })
                self.log(f"  Image {i+1}: seed={seed}, media_name={media_name[:40] if media_name else 'N/A'}...")

        return results

    # =========================================================================
    # DOWNLOAD
    # =========================================================================

    def download_images(
        self,
        images: List[Dict[str, Any]],
        output_dir: str,
        prefix: str = "image"
    ) -> List[Path]:
        """
        Download ảnh về local.

        Args:
            images: List từ generate_images()
            output_dir: Thư mục lưu
            prefix: Tiền tố tên file

        Returns:
            List đường dẫn file đã tải
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        downloaded = []

        for img in images:
            url = img.get("url")
            if not url:
                continue

            try:
                response = requests.get(url, timeout=60)
                if response.status_code == 200:
                    idx = img.get("index", 0)
                    seed = img.get("seed", "")
                    filename = f"{prefix}_{idx+1}_{seed}.png"
                    filepath = output_path / filename

                    with open(filepath, 'wb') as f:
                        f.write(response.content)

                    downloaded.append(filepath)
                    self.log(f"Downloaded: {filename}")
            except Exception as e:
                self.log(f"Download error: {e}", "ERROR")

        return downloaded

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def get_token(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Lấy token - tự động chọn method phù hợp.
        Ưu tiên dùng token cached nếu còn hạn.
        """
        # Check cached token
        if self.is_token_valid():
            self.log("Sử dụng token từ cache")
            return self.bearer_token, self.project_id

        # Selenium (khuyến khích)
        if HAS_SELENIUM:
            return self.get_token_selenium()

        # Fallback PyAutoGUI
        if HAS_PYAUTOGUI and HAS_PYPERCLIP:
            return self.get_token_pyautogui()

        self.log("Không có method để lấy token!", "ERROR")
        return None, None

    def generate_and_download(
        self,
        prompt: str,
        output_dir: str,
        count: int = 2,
        prefix: str = "image"
    ) -> List[Path]:
        """
        Tạo và download ảnh trong 1 bước.
        """
        # Đảm bảo có token
        if not self.is_token_valid():
            self.get_token()

        if not self.is_token_valid():
            self.log("Không lấy được token!", "ERROR")
            return []

        # Generate
        images = self.generate_images(prompt, count)

        if not images:
            return []

        # Download
        return self.download_images(images, output_dir, prefix)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║         GOOGLE FLOW IMAGE GENERATOR                          ║
╠══════════════════════════════════════════════════════════════╣
║  Bước 1: Tạo thư mục chrome_profiles/main                    ║
║  Bước 2: Mở Chrome thủ công, đăng nhập Google                ║
║  Bước 3: Chạy script này                                     ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Config
    CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    PROFILE_DIR = "./chrome_profiles/main"
    PROXY_TOKEN = input("Nhập proxy_api_token từ nanoai.pics: ").strip()

    if not PROXY_TOKEN:
        print("Cần proxy_api_token để tiếp tục!")
        sys.exit(1)

    # Khởi tạo
    generator = FlowImageGenerator(
        chrome_path=CHROME_PATH,
        profile_dir=PROFILE_DIR,
        proxy_api_token=PROXY_TOKEN,
        headless=False,
        verbose=True
    )

    # Lấy token
    print("\n=== BƯỚC 1: LẤY TOKEN ===")
    token, project_id = generator.get_token()

    if not token:
        print("Không lấy được token!")
        sys.exit(1)

    print(f"Token: {token[:40]}...")
    print(f"Project: {project_id}")

    # Tạo ảnh
    print("\n=== BƯỚC 2: TẠO ẢNH ===")
    prompt = input("Nhập prompt (Enter để dùng mặc định): ").strip()
    if not prompt:
        prompt = "a majestic lion in the African savanna at golden hour, cinematic lighting, ultra detailed"

    images = generator.generate_images(prompt, count=2)

    if not images:
        print("Không tạo được ảnh!")
        sys.exit(1)

    print(f"Tạo được {len(images)} ảnh")

    # Download
    print("\n=== BƯỚC 3: DOWNLOAD ===")
    output_dir = input("Thư mục lưu (Enter = ./output): ").strip() or "./output"

    files = generator.download_images(images, output_dir)

    print(f"\n=== HOÀN THÀNH ===")
    print(f"Đã tải {len(files)} ảnh về {output_dir}")
    for f in files:
        print(f"  - {f}")

    # Cleanup
    generator.close_browser()
```

---

## PHẦN 3: Cách sử dụng

### 3.1 Chuẩn bị Profile Chrome

```bash
# Tạo thư mục profile
mkdir -p chrome_profiles/main

# Mở Chrome và đăng nhập Google
# Windows:
"C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir=./chrome_profiles --profile-directory=main

# Linux:
google-chrome --user-data-dir=./chrome_profiles --profile-directory=main
```

Sau đó đăng nhập tài khoản Google và truy cập https://labs.google/fx/vi/tools/flow để verify.

### 3.2 Lấy Proxy API Token

1. Truy cập https://nanoai.pics
2. Đăng ký/đăng nhập
3. Vào Settings/API để lấy token

### 3.3 Chạy Script

```python
from flow_image_generator import FlowImageGenerator

# Khởi tạo
gen = FlowImageGenerator(
    chrome_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    profile_dir="./chrome_profiles/main",
    proxy_api_token="YOUR_NANOAI_TOKEN"
)

# Lấy token (chỉ cần lần đầu hoặc khi hết hạn)
token, project_id = gen.get_token()

# Tạo ảnh
images = gen.generate_images(
    prompt="a cute cat playing with yarn, studio lighting",
    count=2
)

# Download
files = gen.download_images(images, output_dir="./my_images")

# In kết quả
for img in images:
    print(f"URL: {img['url']}")
    print(f"Media Name: {img['media_name']}")  # Lưu để reference sau!
    print(f"Seed: {img['seed']}")
```

---

## PHẦN 4: API Reference

### 4.1 Aspect Ratios

```python
"IMAGE_ASPECT_RATIO_LANDSCAPE"  # 16:9 (mặc định)
"IMAGE_ASPECT_RATIO_PORTRAIT"   # 9:16
"IMAGE_ASPECT_RATIO_SQUARE"     # 1:1
```

### 4.2 Image Models

```python
"GEM_PIX"    # Version cũ
"GEM_PIX_2"  # Version mới (mặc định, chất lượng tốt hơn)
```

### 4.3 Reference Images

Để dùng ảnh đã tạo làm reference cho ảnh mới:

```python
# Lưu media_name từ ảnh đã tạo
first_image_media_name = images[0]["media_name"]

# Dùng làm reference
new_images = gen.generate_images(
    prompt="same person but in winter clothes",
    reference_media_names=[first_image_media_name]
)
```

---

## PHẦN 5: Troubleshooting

### Token không capture được

1. Đảm bảo đã đăng nhập Google trong profile
2. Đợi đủ 25s sau khi gửi prompt test
3. Check DevTools Console có log "TOKEN CAPTURED!" không

### API trả về 401

1. Token đã hết hạn (1 giờ)
2. Xóa token cache và lấy lại:
   ```python
   gen.bearer_token = None
   gen.get_token()
   ```

### Captcha

- Proxy API giúp bypass captcha
- Nếu vẫn gặp, thử:
  1. Tạo project mới trong browser thủ công
  2. Hoàn thành captcha
  3. Chạy lại script

---

## Summary

Đây là module Python hoàn chỉnh để:
1. ✅ Mở Chrome với profile có sẵn
2. ✅ Tự động navigate đến Flow
3. ✅ Inject script capture token
4. ✅ Click tạo project mới
5. ✅ Chọn "Tạo hình ảnh"
6. ✅ Gửi prompt test
7. ✅ Capture Bearer Token
8. ✅ Gọi Proxy API tạo ảnh
9. ✅ Poll task status
10. ✅ Download ảnh về local
11. ✅ Hỗ trợ reference images
