"""
Flow DrissionPage - Tạo ảnh bằng Google Flow
Sử dụng DrissionPage thay cho PyAutoGUI + subprocess Chrome

Thay thế chrome_token_extractor.py với cách tiếp cận mới:
- Dùng DrissionPage để tương tác với browser
- Không cần PyAutoGUI (focus window, keyboard shortcuts...)
- Tương tác trực tiếp qua API của DrissionPage
"""

import time
import json
import threading
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass

import requests
from rich.console import Console

try:
    from .drission_manager import DrissionManager
except ImportError:
    from drission_manager import DrissionManager

console = Console()


# Token capture script - inject vào page để hook fetch
TOKEN_CAPTURE_SCRIPT = """
window._tk=null;window._pj=null;window._xbv=null;window._rct=null;window._payload=null;window._url=null;
(function(){
  var f=window.fetch;
  window.fetch=function(u,o){
    var s=u?u.toString():'';
    if(s.includes('flowMedia')||s.includes('aisandbox')||s.includes('batchGenerateImages')){
      var h=o&&o.headers?o.headers:{};

      // Capture Bearer token
      var a=h.Authorization||h.authorization||'';
      if(a.startsWith('Bearer ')){
        window._tk=a.substring(7);
        console.log('[TOKEN] Bearer captured');
      }

      // Capture x-browser-validation
      var xbv=h['x-browser-validation']||'';
      if(xbv){
        window._xbv=xbv;
        console.log('[TOKEN] x-browser-validation captured');
      }

      // Capture URL
      window._url=s;

      // Capture project ID from URL
      var m=s.match(/\\/projects\\/([^\\/]+)\\//);
      if(m) window._pj=m[1];

      // Capture FULL payload from body
      if(o&&o.body){
        try{
          window._payload=typeof o.body==='string'?o.body:JSON.stringify(o.body);
          var body=JSON.parse(window._payload);
          if(body.requests&&body.requests[0]){
            var ctx=body.requests[0].clientContext||{};
            if(ctx.recaptchaToken){
              window._rct=ctx.recaptchaToken;
              console.log('[TOKEN] recaptchaToken captured:', window._rct.substring(0,20)+'...');
            }
          }
        }catch(e){console.log('[TOKEN] Parse error:',e);}
      }

      console.log('[TOKEN] Full capture done - CANCELLING original request');

      // CANCEL original request - return fake success response
      return Promise.resolve(new Response(JSON.stringify({
        media: [],
        cancelled: true,
        message: "Request captured for external use"
      }), {status: 200, headers: {'Content-Type': 'application/json'}}));
    }
    return f.apply(this,arguments);
  };
  console.log('[TOKEN] Capture script injected');
})();
"""


@dataclass
class FlowCapturedData:
    """Dữ liệu đã capture từ Flow"""
    bearer_token: str = None
    project_id: str = None
    x_browser_validation: str = None
    recaptcha_token: str = None
    payload: str = None
    url: str = None


class FlowDrission:
    """
    Google Flow automation sử dụng DrissionPage.
    Tạo ảnh bằng cách interact với UI Flow.
    """

    FLOW_URL = "https://labs.google/fx/vi/tools/flow"

    def __init__(
        self,
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = False,
        timeout: int = 120
    ):
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.headless = headless
        self.timeout = timeout

        # DrissionManager instance
        self.manager: Optional[DrissionManager] = None

        # Captured values
        self.captured = FlowCapturedData()

    def log(self, msg: str, level: str = "info"):
        """Log message"""
        if level == "success":
            console.print(f"[green]   ✓ {msg}[/]")
        elif level == "error":
            console.print(f"[red]   ✗ {msg}[/]")
        elif level == "warning":
            console.print(f"[yellow]   ⚠ {msg}[/]")
        else:
            console.print(f"[cyan]{msg}[/]")

    def setup(self) -> bool:
        """Khởi tạo browser"""
        try:
            self.manager = DrissionManager(
                chrome_path=self.chrome_path,
                profile_path=self.profile_path,
                headless=self.headless,
            )

            if not self.manager.is_available():
                self.log("DrissionPage chưa được cài đặt!", "error")
                return False

            return self.manager.setup()

        except Exception as e:
            self.log(f"Lỗi setup: {e}", "error")
            return False

    def close(self):
        """Đóng browser"""
        if self.manager:
            self.manager.close()
            self.manager = None

    def _inject_capture_script(self, callback=None) -> bool:
        """Inject script capture token"""
        if callback:
            callback("Injecting token capture script...")

        try:
            self.manager.run_js(TOKEN_CAPTURE_SCRIPT)
            if callback:
                callback("Script injected")
            return True
        except Exception as e:
            if callback:
                callback(f"Script inject error: {e}")
            return False

    def _click_new_project(self, callback=None) -> bool:
        """Click nút 'Dự án mới'"""
        if callback:
            callback("Đang tìm nút 'Dự án mới'...")

        js_click = '''
        (function() {
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                var text = buttons[i].innerText || buttons[i].textContent || '';
                if (text.includes('Dự án mới') || text.includes('New project') || text.includes('New')) {
                    buttons[i].click();
                    return 'clicked: ' + text;
                }
            }

            var newBtn = document.querySelector('[aria-label*="New"], [aria-label*="Mới"], [aria-label*="Create"]');
            if (newBtn) {
                newBtn.click();
                return 'clicked by aria-label';
            }

            return 'not found';
        })();
        '''

        result = self.manager.run_js_return(js_click)
        if callback:
            callback(f"Click result: {result}")
        time.sleep(5)
        return 'clicked' in str(result).lower() if result else False

    def _select_image_mode(self, callback=None) -> bool:
        """Chọn mode 'Tạo hình ảnh'"""
        if callback:
            callback("Đang click dropdown...")

        # Click dropdown
        js_dropdown = '''
        (function() {
            var dd = document.querySelector('button[role="combobox"]');
            if (!dd) return 'ERROR: no dropdown';
            dd.click();
            return 'dropdown clicked';
        })();
        '''
        result = self.manager.run_js_return(js_dropdown)
        if callback:
            callback(f"Dropdown: {result}")
        time.sleep(1)

        # Chọn "Tạo hình ảnh"
        if callback:
            callback("Đang chọn 'Tạo hình ảnh'...")

        js_select = '''
        (function() {
            var all = document.querySelectorAll('*');
            for (var el of all) {
                var t = el.textContent || '';
                if (t === 'Tạo hình ảnh' || t.includes('Tạo hình ảnh từ văn bản')) {
                    var rect = el.getBoundingClientRect();
                    if (rect.height > 10 && rect.height < 80 && rect.width > 50) {
                        el.click();
                        return 'selected: ' + t.substring(0, 40);
                    }
                }
            }
            return 'no option found';
        })();
        '''
        result = self.manager.run_js_return(js_select)
        if callback:
            callback(f"Option: {result}")
        time.sleep(3)
        return True

    def _send_prompt(self, prompt: str, callback=None) -> bool:
        """Gửi prompt để trigger API call"""
        if callback:
            callback("Đang focus textarea...")

        # Focus textarea
        js_focus = '''
        (function() {
            var ta = document.querySelector('textarea');
            if (ta) {
                ta.focus();
                ta.click();
                return 'focused';
            }
            return 'no textarea';
        })();
        '''
        result = self.manager.run_js_return(js_focus)
        if callback:
            callback(f"Focus: {result}")
        time.sleep(0.5)

        # Nhập prompt bằng DrissionPage
        if callback:
            callback(f"Đang nhập prompt: {prompt[:50]}...")

        try:
            textarea = self.manager.get_element("textarea", timeout=5)
            if textarea:
                textarea.clear()
                textarea.input(prompt)
                if callback:
                    callback("Đã nhập prompt")
            else:
                if callback:
                    callback("Không tìm thấy textarea")
                return False
        except Exception as e:
            if callback:
                callback(f"Lỗi nhập prompt: {e}")
            return False

        time.sleep(1)

        # Nhấn Enter để gửi - simulate key press
        if callback:
            callback("Đang gửi (Enter)...")

        try:
            # Gửi Enter key
            self.manager.run_js('''
                var ta = document.querySelector('textarea');
                if (ta) {
                    ta.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                    }));
                }
            ''')
            if callback:
                callback("Đã nhấn Enter")
        except Exception as e:
            if callback:
                callback(f"Lỗi Enter: {e}")

        # Đợi API call
        if callback:
            callback("Đang đợi API call (25s)...")
        time.sleep(25)
        return True

    def _get_captured_token(self, callback=None) -> bool:
        """Lấy token và các giá trị đã capture"""
        if callback:
            callback("Đang lấy token...")

        js_get = '''
        (function() {
            return JSON.stringify({
                token: window._tk || null,
                project: window._pj || null,
                xbv: window._xbv || null,
                rct: window._rct || null,
                payload: window._payload || null,
                url: window._url || null
            });
        })();
        '''

        result = self.manager.run_js_return(js_get)

        if result:
            try:
                data = json.loads(result)

                if data.get('token'):
                    self.captured.bearer_token = data['token']
                    self.captured.project_id = data.get('project')
                    self.captured.x_browser_validation = data.get('xbv')
                    self.captured.recaptcha_token = data.get('rct')
                    self.captured.payload = data.get('payload')
                    self.captured.url = data.get('url')

                    if callback:
                        callback(f"Token: {self.captured.bearer_token[:30]}...")
                        if self.captured.x_browser_validation:
                            callback("x-browser-validation: captured")
                        if self.captured.recaptcha_token:
                            callback(f"recaptchaToken: {self.captured.recaptcha_token[:20]}...")
                    return True
            except Exception as e:
                if callback:
                    callback(f"Parse error: {e}")

        if callback:
            callback("Token chưa được capture")
        return False

    def extract_token(self, callback=None) -> Tuple[Optional[str], Optional[str], str]:
        """
        Thực hiện toàn bộ flow lấy token.

        Returns:
            Tuple[bearer_token, project_id, error_message]
        """
        error = ""

        try:
            # Setup browser nếu chưa có
            if not self.manager or not self.manager.is_running():
                if callback:
                    callback("Bước 1: Đang khởi tạo browser...")
                if not self.setup():
                    return None, None, "Không thể khởi tạo browser"

            # Mở trang Flow
            if callback:
                callback("Bước 1: Đang mở trang Flow...")
            self.manager.navigate(self.FLOW_URL, wait=15)

            # Inject capture script
            if callback:
                callback("Bước 2: Inject capture script...")
            self._inject_capture_script(callback)

            # Click "Dự án mới"
            if callback:
                callback("Bước 3: Click 'Dự án mới'...")
            self._click_new_project(callback)

            # Chọn mode "Tạo hình ảnh"
            if callback:
                callback("Bước 4: Chọn mode 'Tạo hình ảnh'...")
            self._select_image_mode(callback)

            # Re-inject script
            self._inject_capture_script(callback)

            # Gửi prompt
            if callback:
                callback("Bước 5: Gửi prompt...")
            self._send_prompt("beautiful sunset over ocean with birds", callback)

            # Lấy token
            if callback:
                callback("Bước 6: Lấy token...")

            for attempt in range(10):
                if self._get_captured_token(callback):
                    return self.captured.bearer_token, self.captured.project_id, ""
                time.sleep(3)

            error = "Không capture được token. Hãy thử tạo ảnh thủ công trên trang Flow."

        except Exception as e:
            error = f"Lỗi: {str(e)}"

        return None, None, error

    # =========================================================================
    # CHROME-BASED IMAGE GENERATION
    # =========================================================================

    def generate_image_chrome(self, prompt: str, callback=None) -> bool:
        """Tạo ảnh bằng cách nhập prompt vào Chrome Flow UI"""
        try:
            # Focus textarea và nhập prompt
            if callback:
                callback(f"Đang nhập prompt: {prompt[:50]}...")

            js_focus = '''
            (function() {
                var ta = document.querySelector('textarea');
                if (ta) { ta.focus(); ta.click(); ta.select(); return 'focused'; }
                return 'no textarea';
            })();
            '''
            self.manager.run_js(js_focus)
            time.sleep(0.5)

            # Nhập prompt
            textarea = self.manager.get_element("textarea", timeout=5)
            if textarea:
                textarea.clear()
                textarea.input(prompt)
            else:
                if callback:
                    callback("Không tìm thấy textarea")
                return False

            if callback:
                callback("Đã nhập prompt, đang gửi...")

            # Enter để generate
            self.manager.run_js('''
                var ta = document.querySelector('textarea');
                if (ta) {
                    ta.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                    }));
                }
            ''')

            if callback:
                callback("Đã gửi, đang đợi tạo ảnh (60s)...")

            time.sleep(60)
            return True

        except Exception as e:
            if callback:
                callback(f"Lỗi: {e}")
            return False

    def get_generated_image_urls(self, callback=None) -> List[str]:
        """Lấy URLs của ảnh đã generate"""
        js_get = '''
        (function() {
            var urls = [];
            var imgs = document.querySelectorAll('img[src*="googleusercontent"]');
            for (var img of imgs) {
                var src = img.src;
                if (src && src.includes('lh3.googleusercontent.com')) {
                    urls.push(src);
                }
            }
            if (urls.length === 0) {
                var allImgs = document.querySelectorAll('img');
                for (var img of allImgs) {
                    if (img.src && img.width > 200 && img.height > 200) {
                        urls.push(img.src);
                    }
                }
            }
            return JSON.stringify(urls);
        })();
        '''

        result = self.manager.run_js_return(js_get)

        if result:
            try:
                urls = json.loads(result)
                if callback:
                    callback(f"Tìm thấy {len(urls)} ảnh")
                return urls
            except:
                pass

        if callback:
            callback("Không tìm thấy ảnh nào")
        return []

    def download_generated_images(self, output_dir: Path, prefix: str = "flow", callback=None) -> List[str]:
        """Download ảnh đã generate về thư mục"""
        from datetime import datetime

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        urls = self.get_generated_image_urls(callback)
        downloaded = []

        for i, url in enumerate(urls):
            try:
                if callback:
                    callback(f"Downloading image {i+1}/{len(urls)}...")

                resp = requests.get(url, timeout=60)
                if resp.status_code == 200:
                    timestamp = datetime.now().strftime("%H%M%S")
                    filename = f"{prefix}_{timestamp}_{i+1}.png"
                    filepath = output_dir / filename

                    with open(filepath, 'wb') as f:
                        f.write(resp.content)

                    downloaded.append(str(filepath))
                    if callback:
                        callback(f"Saved: {filename}")

            except Exception as e:
                if callback:
                    callback(f"Download error: {e}")

        return downloaded

    # =========================================================================
    # API CALLS WITH CAPTURED PAYLOAD
    # =========================================================================

    def call_api_with_captured_payload(
        self,
        custom_prompt: str = None,
        output_dir: Path = None,
        prefix: str = "flow",
        image_ref: str = None,
        callback=None
    ) -> List[str]:
        """Gọi API trực tiếp với payload đã capture"""
        from datetime import datetime

        if not self.captured.payload:
            if callback:
                callback("Chưa có captured payload")
            return []

        if not self.captured.bearer_token:
            if callback:
                callback("Chưa có Bearer token")
            return []

        # Parse payload
        try:
            payload = json.loads(self.captured.payload) if isinstance(self.captured.payload, str) else self.captured.payload
        except:
            if callback:
                callback("Không parse được payload")
            return []

        # Mở rộng requests
        if payload.get("requests") and len(payload["requests"]) < 4:
            import copy
            import random
            original_requests = payload["requests"]
            while len(payload["requests"]) < 4:
                new_req = copy.deepcopy(original_requests[len(payload["requests"]) % len(original_requests)])
                new_req["seed"] = random.randint(100000, 999999)
                payload["requests"].append(new_req)

        # Thay đổi prompt và aspect ratio
        if payload.get("requests"):
            for req in payload["requests"]:
                if custom_prompt:
                    req["prompt"] = custom_prompt
                req["imageAspectRatio"] = "IMAGE_ASPECT_RATIO_PORTRAIT"

        # Thêm image reference
        if image_ref and payload.get("requests"):
            for req in payload["requests"]:
                req["imageInputs"] = [{
                    "imageInputType": "IMAGE_INPUT_TYPE_REFERENCE",
                    "name": image_ref
                }]
                if req.get("clientContext"):
                    req["clientContext"]["tool"] = "PINHOLE"

        # Build URL
        url = self.captured.url or f"https://aisandbox-pa.googleapis.com/v1/projects/{self.captured.project_id}/flowMedia:batchGenerateImages"

        # Build headers
        headers = {
            "Authorization": f"Bearer {self.captured.bearer_token}",
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "*/*",
            "Origin": "https://labs.google",
            "Referer": "https://labs.google/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        if self.captured.x_browser_validation:
            headers["x-browser-validation"] = self.captured.x_browser_validation
            headers["x-browser-channel"] = "stable"
            headers["x-browser-year"] = "2025"

        if callback:
            callback(f"Calling API: {url[:60]}...")

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=120
            )

            if callback:
                callback(f"Response status: {response.status_code}")

            if response.status_code == 429:
                if callback:
                    callback("Quota limit (429)")
                return []

            if response.status_code != 200:
                if callback:
                    callback(f"Error {response.status_code}: {response.text[:200]}")
                return []

            result = response.json()
            media_list = result.get("media", [])

            if not media_list:
                if callback:
                    callback("Không có ảnh trong response")
                return []

            if callback:
                callback(f"Nhận được {len(media_list)} ảnh!")

            # Download images
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

            downloaded = []
            for i, media in enumerate(media_list):
                fife_url = media.get("image", {}).get("generatedImage", {}).get("fifeUrl")

                if fife_url:
                    try:
                        if callback:
                            callback(f"Downloading image {i+1}/{len(media_list)}...")

                        img_resp = requests.get(fife_url, timeout=60)
                        if img_resp.status_code == 200:
                            timestamp = datetime.now().strftime("%H%M%S")
                            filename = f"{prefix}_{timestamp}_{i+1}.png"

                            if output_dir:
                                filepath = output_dir / filename
                                with open(filepath, 'wb') as f:
                                    f.write(img_resp.content)
                                downloaded.append(str(filepath))
                                if callback:
                                    callback(f"Saved: {filename}")
                    except Exception as e:
                        if callback:
                            callback(f"Download error: {e}")

            return downloaded

        except Exception as e:
            if callback:
                callback(f"Error: {e}")
            return []

    def trigger_and_capture(self, prompt: str, callback=None) -> bool:
        """Trigger Chrome để tạo request mới với prompt, capture payload"""
        self.captured.payload = None
        self.captured.recaptcha_token = None

        try:
            self._inject_capture_script(callback)
            time.sleep(0.5)

            # Focus và nhập prompt
            js_focus = '''
            (function() {
                var ta = document.querySelector('textarea');
                if (ta) { ta.focus(); ta.click(); ta.select(); }
            })();
            '''
            self.manager.run_js(js_focus)
            time.sleep(0.5)

            textarea = self.manager.get_element("textarea", timeout=5)
            if textarea:
                textarea.clear()
                textarea.input(prompt)
            else:
                if callback:
                    callback("Không tìm thấy textarea")
                return False

            if callback:
                callback("Đã nhập prompt, đang trigger request...")

            # Enter
            self.manager.run_js('''
                var ta = document.querySelector('textarea');
                if (ta) {
                    ta.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                    }));
                }
            ''')
            time.sleep(3)

            if self._get_captured_token(callback):
                if self.captured.payload and self.captured.recaptcha_token:
                    if callback:
                        callback("Đã capture payload với recaptchaToken mới!")
                    return True

            if callback:
                callback("Không capture được payload mới")
            return False

        except Exception as e:
            if callback:
                callback(f"Lỗi: {e}")
            return False

    def extract_token_async(self, callback=None, on_complete=None):
        """Lấy token trong background thread"""
        def worker():
            token, project_id, error = self.extract_token(callback)
            if on_complete:
                on_complete(token, project_id, error)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread


# Alias
FlowTokenExtractor = FlowDrission
ChromeTokenExtractor = FlowDrission  # Backward compatible
