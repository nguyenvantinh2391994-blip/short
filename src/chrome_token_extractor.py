"""
VE3 Tool - Chrome Token Extractor
=================================
Tự động lấy Bearer Token từ Google Flow theo flow:
1. Mở Chrome với profile đã login (dùng chrome_manager chung)
2. Inject script capture token
3. Click "Dự án mới"
4. Chọn mode "Tạo hình ảnh"
5. Gửi prompt để trigger API
6. Lấy token đã capture
"""

import time
from pathlib import Path
from typing import Optional, Tuple
import threading

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

# Token capture script - inject vào page để hook fetch
# Capture: Bearer token, x-browser-validation, recaptchaToken, payload
# CANCEL original request để recaptchaToken chưa bị dùng
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
      // Điều này giữ recaptchaToken chưa bị dùng
      return Promise.resolve(new Response(JSON.stringify({
        media: [],
        cancelled: true,
        message: "Request captured for external use"
      }), {status: 200, headers: {'Content-Type': 'application/json'}}));
    }
    return f.apply(this,arguments);
  };
  console.log('[TOKEN] Capture script injected (with request cancellation)');
})();
copy('INJECTED');
"""


class ChromeTokenExtractor:
    """
    Tự động lấy Bearer Token từ Google Flow.
    Sử dụng chrome_manager chung như Gemini/Grok.
    """

    FLOW_URL = "https://labs.google/fx/vi/tools/flow"

    def __init__(
        self,
        chrome_path: str,
        profile_path: str,
        timeout: int = 120
    ):
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.timeout = timeout

        # Captured values
        self.bearer_token = None
        self.project_id = None
        self.x_browser_validation = None
        self.recaptcha_token = None
        self.captured_payload = None
        self.captured_url = None

        # Cấu hình chrome_manager
        chrome_manager.set_profile(
            chrome_path=self.chrome_path,
            profile_path=self.profile_path,
        )

    def _inject_capture_script(self, callback=None):
        """Bước 2: Inject script capture token."""
        if callback:
            callback("Injecting token capture script...")

        result = chrome_manager.run_js(TOKEN_CAPTURE_SCRIPT)
        if result and 'INJECTED' in result:
            if callback:
                callback("✅ Script injected")
            return True
        else:
            if callback:
                callback("⚠️ Script inject - checking...")
            return True  # Vẫn tiếp tục

    def _click_new_project(self, callback=None):
        """Bước 3: Click 'Dự án mới' button bằng JavaScript."""
        if callback:
            callback("Đang tìm nút 'Dự án mới'...")

        click_script = """
        (function() {
            // Tìm tất cả buttons
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                var text = buttons[i].innerText || buttons[i].textContent || '';
                if (text.includes('Dự án mới') || text.includes('New project') || text.includes('New')) {
                    buttons[i].click();
                    copy('clicked: ' + text);
                    return;
                }
            }

            // Thử tìm bằng aria-label
            var newBtn = document.querySelector('[aria-label*="New"], [aria-label*="Mới"], [aria-label*="Create"]');
            if (newBtn) {
                newBtn.click();
                copy('clicked by aria-label');
                return;
            }

            copy('not found');
        })();
        """

        result = chrome_manager.run_js(click_script)
        if callback:
            callback(f"Click result: {result}")
        time.sleep(5)  # Đợi project được tạo
        return 'clicked' in str(result).lower() if result else False

    def _select_image_mode(self, callback=None):
        """Bước 4: Chọn mode 'Tạo hình ảnh' - Click dropdown rồi chọn option."""
        if callback:
            callback("Đang click dropdown...")

        # Bước 4a: Click dropdown button
        click_dropdown_script = """
        (function() {
            var dd = document.querySelector('button[role="combobox"]');
            if (!dd) {
                copy('ERROR: no dropdown');
                return;
            }
            dd.click();
            copy('dropdown clicked');
        })();
        """

        result = chrome_manager.run_js(click_dropdown_script)
        if callback:
            callback(f"Dropdown: {result}")

        # Đợi menu mở
        time.sleep(1)

        # Bước 4b: Chọn "Tạo hình ảnh"
        if callback:
            callback("Đang chọn 'Tạo hình ảnh'...")

        select_option_script = """
        (function() {
            var all = document.querySelectorAll('*');
            for (var el of all) {
                var t = el.textContent || '';
                if (t === 'Tạo hình ảnh' || t.includes('Tạo hình ảnh từ văn bản')) {
                    var rect = el.getBoundingClientRect();
                    // Chỉ click element có kích thước hợp lý
                    if (rect.height > 10 && rect.height < 80 && rect.width > 50) {
                        el.click();
                        copy('selected: ' + t.substring(0, 40));
                        return;
                    }
                }
            }
            copy('no option found');
        })();
        """

        result = chrome_manager.run_js(select_option_script)
        if callback:
            callback(f"Option: {result}")

        # Đợi sau khi chọn mode
        time.sleep(3)
        return True

    def _send_prompt(self, callback=None):
        """Bước 5: Gửi prompt để trigger API call - dùng PyAutoGUI paste."""
        prompt = "beautiful sunset over ocean with birds"

        if not HAS_PAG:
            if callback:
                callback("ERROR: PyAutoGUI not installed")
            return False

        # Bước 5a: Focus textarea bằng JS
        if callback:
            callback("Đang focus textarea...")

        focus_script = """
        (function() {
            var ta = document.querySelector('textarea');
            if (ta) {
                ta.focus();
                ta.click();
                copy('textarea focused');
                return;
            }
            copy('no textarea');
        })();
        """

        result = chrome_manager.run_js(focus_script)
        if callback:
            callback(f"Focus: {result}")
        time.sleep(1)

        # Bước 5b: Paste prompt bằng PyAutoGUI (giống SORA)
        if callback:
            callback("Đang paste prompt...")

        try:
            # Focus Chrome window trước
            chrome_manager._focus_chrome()
            time.sleep(0.3)

            # Copy prompt vào clipboard và paste
            pyperclip.copy(prompt)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)

            if callback:
                callback("Đã paste prompt")
        except Exception as e:
            if callback:
                callback(f"Lỗi paste: {e}")
            return False

        time.sleep(1)

        # Bước 5c: Nhấn Enter để gửi (giống SORA)
        if callback:
            callback("Đang gửi (Enter)...")

        try:
            pag.press("enter")
            if callback:
                callback("Đã nhấn Enter")
        except Exception as e:
            if callback:
                callback(f"Lỗi Enter: {e}")

        # Đợi API call được thực hiện (25-30 giây)
        if callback:
            callback("Đang đợi API call (25s)...")
        time.sleep(25)
        return True

    def _get_captured_token(self, callback=None):
        """Bước 6: Lấy token và các giá trị đã capture."""
        if callback:
            callback("Đang lấy token...")

        # Script lấy tất cả captured values
        get_all_script = """
        (function() {
            var result = {
                token: window._tk || null,
                project: window._pj || null,
                xbv: window._xbv || null,
                rct: window._rct || null,
                payload: window._payload || null,
                url: window._url || null
            };
            copy(JSON.stringify(result));
        })();
        """

        result = chrome_manager.run_js(get_all_script)

        if result:
            try:
                import json
                data = json.loads(result)

                if data.get('token'):
                    self.bearer_token = data['token']
                    self.project_id = data.get('project')
                    self.x_browser_validation = data.get('xbv')
                    self.recaptcha_token = data.get('rct')
                    self.captured_payload = data.get('payload')  # Full JSON string
                    self.captured_url = data.get('url')

                    if callback:
                        callback(f"✅ Token: {self.bearer_token[:30]}...")
                        if self.x_browser_validation:
                            callback(f"✅ x-browser-validation: captured")
                        if self.recaptcha_token:
                            callback(f"✅ recaptchaToken: {self.recaptcha_token[:20]}...")
                        if self.captured_payload:
                            callback(f"✅ Full payload: captured")
                    return True
            except:
                pass

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
            # Bước 1: Mở Chrome với URL Flow
            if callback:
                callback("Bước 1: Đang mở Chrome...")

            if not chrome_manager.open_chrome(self.FLOW_URL):
                return None, None, "Không thể mở Chrome"

            # Đợi trang load (12-15 giây)
            if callback:
                callback("Đợi trang load (15s)...")
            time.sleep(15)

            # Bước 2: Inject capture script
            if callback:
                callback("Bước 2: Inject capture script...")
            self._inject_capture_script(callback)

            # Bước 3: Click "Dự án mới"
            if callback:
                callback("Bước 3: Click 'Dự án mới'...")
            self._click_new_project(callback)

            # Bước 4: Chọn mode "Tạo hình ảnh"
            if callback:
                callback("Bước 4: Chọn mode 'Tạo hình ảnh'...")
            self._select_image_mode(callback)

            # Re-inject script (có thể bị mất sau navigation)
            self._inject_capture_script(callback)

            # Bước 5: Gửi prompt
            if callback:
                callback("Bước 5: Gửi prompt...")
            self._send_prompt(callback)

            # Bước 6: Lấy token
            if callback:
                callback("Bước 6: Lấy token...")

            # Thử lấy token nhiều lần
            for attempt in range(10):
                if self._get_captured_token(callback):
                    return self.bearer_token, self.project_id, ""
                time.sleep(3)

            error = "Không capture được token. Hãy thử tạo ảnh thủ công trên trang Flow."

        except Exception as e:
            error = f"Lỗi: {str(e)}"

        return None, None, error

    # =========================================================================
    # CHROME-BASED IMAGE GENERATION (bypass captcha)
    # =========================================================================

    def generate_image_chrome(self, prompt: str, callback=None) -> bool:
        """
        Tạo ảnh bằng cách nhập prompt vào Chrome Flow UI.
        Chrome sẽ tự xử lý captcha.

        Args:
            prompt: Prompt để tạo ảnh
            callback: Callback để log progress

        Returns:
            True nếu đã gửi prompt thành công
        """
        if not HAS_PAG:
            if callback:
                callback("ERROR: PyAutoGUI not installed")
            return False

        try:
            # Focus Chrome window
            chrome_manager._focus_chrome()
            time.sleep(0.5)

            # Clear textarea và nhập prompt mới
            if callback:
                callback(f"Đang nhập prompt: {prompt[:50]}...")

            # Focus textarea
            focus_script = """
            (function() {
                var ta = document.querySelector('textarea');
                if (ta) {
                    ta.focus();
                    ta.click();
                    ta.select();
                    copy('focused');
                    return;
                }
                copy('no textarea');
            })();
            """
            chrome_manager.run_js(focus_script)
            time.sleep(0.5)

            # Xóa nội dung cũ và paste prompt mới
            pag.hotkey("ctrl", "a")
            time.sleep(0.2)

            pyperclip.copy(prompt)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)

            if callback:
                callback("Đã nhập prompt, đang gửi...")

            # Nhấn Enter để generate
            pag.press("enter")

            if callback:
                callback("Đã gửi, đang đợi tạo ảnh (60s)...")

            # Đợi ảnh được tạo (60-90 giây)
            time.sleep(60)

            return True

        except Exception as e:
            if callback:
                callback(f"Lỗi: {e}")
            return False

    def get_generated_image_urls(self, callback=None) -> list:
        """
        Lấy URLs của ảnh đã generate từ trang Flow.

        Returns:
            List of image URLs
        """
        get_images_script = """
        (function() {
            var urls = [];
            // Tìm tất cả img tags có src chứa googleusercontent
            var imgs = document.querySelectorAll('img[src*="googleusercontent"]');
            for (var img of imgs) {
                var src = img.src;
                if (src && src.includes('lh3.googleusercontent.com')) {
                    urls.push(src);
                }
            }
            // Fallback: tìm trong các elements khác
            if (urls.length === 0) {
                var allImgs = document.querySelectorAll('img');
                for (var img of allImgs) {
                    if (img.src && img.width > 200 && img.height > 200) {
                        urls.push(img.src);
                    }
                }
            }
            copy(JSON.stringify(urls));
        })();
        """

        result = chrome_manager.run_js(get_images_script)

        if result:
            try:
                import json
                urls = json.loads(result)
                if callback:
                    callback(f"Tìm thấy {len(urls)} ảnh")
                return urls
            except:
                pass

        if callback:
            callback("Không tìm thấy ảnh nào")
        return []

    def download_generated_images(self, output_dir: Path, prefix: str = "flow", callback=None) -> list:
        """
        Download ảnh đã generate về thư mục.

        Args:
            output_dir: Thư mục lưu ảnh
            prefix: Prefix cho tên file
            callback: Callback để log

        Returns:
            List of downloaded file paths
        """
        import requests
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
                        callback(f"✅ Saved: {filename}")

            except Exception as e:
                if callback:
                    callback(f"❌ Download error: {e}")

        return downloaded

    # =========================================================================
    # UPLOAD IMAGE API
    # =========================================================================

    def upload_image(self, image_path: str, callback=None) -> str:
        """
        Upload ảnh lên Google Flow và nhận mediaGenerationId.

        Args:
            image_path: Đường dẫn tới file ảnh
            callback: Callback để log

        Returns:
            mediaGenerationId string hoặc None nếu lỗi
        """
        import requests
        import json
        import base64
        from pathlib import Path

        if not self.bearer_token:
            if callback:
                callback("❌ Chưa có Bearer token")
            return None

        image_path = Path(image_path)
        if not image_path.exists():
            if callback:
                callback(f"❌ File không tồn tại: {image_path}")
            return None

        # Đọc và encode ảnh sang base64
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            raw_image_bytes = base64.b64encode(image_bytes).decode('utf-8')
        except Exception as e:
            if callback:
                callback(f"❌ Không đọc được file: {e}")
            return None

        # Xác định mime type
        suffix = image_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.gif': 'image/gif'
        }
        mime_type = mime_types.get(suffix, 'image/jpeg')

        # Tạo session ID nếu chưa có
        import time
        session_id = f";{int(time.time() * 1000)}"

        # Build payload
        payload = {
            "imageInput": {
                "aspectRatio": "IMAGE_ASPECT_RATIO_PORTRAIT",  # 9:16
                "isUserUploaded": True,
                "mimeType": mime_type,
                "rawImageBytes": raw_image_bytes
            },
            "clientContext": {
                "sessionId": session_id,
                "tool": "ASSET_MANAGER"
            }
        }

        # Build headers
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "*/*",
            "Origin": "https://labs.google",
            "Referer": "https://labs.google/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        }

        # Add x-browser-validation nếu có
        if self.x_browser_validation:
            headers["x-browser-validation"] = self.x_browser_validation
            headers["x-browser-channel"] = "stable"
            headers["x-browser-year"] = "2025"

        url = "https://aisandbox-pa.googleapis.com/v1:uploadUserImage"

        if callback:
            callback(f"Uploading image: {image_path.name}...")

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=120
            )

            if response.status_code != 200:
                if callback:
                    callback(f"❌ Upload failed: {response.status_code} - {response.text[:200]}")
                return None

            result = response.json()
            media_id = result.get("mediaGenerationId", {}).get("mediaGenerationId")

            if media_id:
                if callback:
                    callback(f"✅ Upload thành công: {media_id[:30]}...")
                return media_id
            else:
                if callback:
                    callback(f"❌ Không nhận được mediaGenerationId")
                return None

        except Exception as e:
            if callback:
                callback(f"❌ Upload error: {e}")
            return None

    # =========================================================================
    # CALL API WITH CAPTURED PAYLOAD
    # =========================================================================

    def call_api_with_captured_payload(
        self,
        custom_prompt: str = None,
        output_dir: Path = None,
        prefix: str = "flow",
        image_ref: str = None,
        callback=None
    ) -> list:
        """
        Gọi API trực tiếp với payload đã capture từ Chrome.
        recaptchaToken chưa bị dùng vì request Chrome đã bị cancel.

        Args:
            custom_prompt: Prompt mới (nếu muốn thay đổi)
            output_dir: Thư mục lưu ảnh
            prefix: Prefix cho tên file
            image_ref: mediaGenerationId từ upload_image (optional)
            callback: Callback để log

        Returns:
            List of downloaded file paths
        """
        import requests
        import json
        from datetime import datetime

        if not self.captured_payload:
            if callback:
                callback("❌ Chưa có captured payload")
            return []

        if not self.bearer_token:
            if callback:
                callback("❌ Chưa có Bearer token")
            return []

        # Parse payload
        try:
            payload = json.loads(self.captured_payload) if isinstance(self.captured_payload, str) else self.captured_payload
        except:
            if callback:
                callback("❌ Không parse được payload")
            return []

        # Mở rộng requests từ 2 lên 4
        if payload.get("requests") and len(payload["requests"]) < 4:
            import copy
            import random
            original_requests = payload["requests"]
            while len(payload["requests"]) < 4:
                new_req = copy.deepcopy(original_requests[len(payload["requests"]) % len(original_requests)])
                new_req["seed"] = random.randint(100000, 999999)
                payload["requests"].append(new_req)

        # Thay đổi prompt và aspect ratio cho tất cả requests
        if payload.get("requests"):
            for req in payload["requests"]:
                if custom_prompt:
                    req["prompt"] = custom_prompt
                # Đổi aspect ratio sang 9:16 (PORTRAIT)
                req["imageAspectRatio"] = "IMAGE_ASPECT_RATIO_PORTRAIT"

            if custom_prompt and callback:
                callback(f"Đã thay prompt: {custom_prompt[:50]}...")

        # Thêm image reference nếu có
        if image_ref and payload.get("requests"):
            for req in payload["requests"]:
                req["imageInputs"] = [{
                    "imageInputType": "IMAGE_INPUT_TYPE_REFERENCE",
                    "name": image_ref
                }]
                # Đổi tool sang PINHOLE khi có ảnh tham chiếu
                if req.get("clientContext"):
                    req["clientContext"]["tool"] = "PINHOLE"
            if callback:
                callback(f"Đã thêm image reference: {image_ref[:30]}...")

        # Build URL
        url = self.captured_url or f"https://aisandbox-pa.googleapis.com/v1/projects/{self.project_id}/flowMedia:batchGenerateImages"

        # Build headers (giống debug script)
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "*/*",
            "Origin": "https://labs.google",
            "Referer": "https://labs.google/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        # Add x-browser-validation nếu có
        if self.x_browser_validation:
            headers["x-browser-validation"] = self.x_browser_validation
            headers["x-browser-channel"] = "stable"
            headers["x-browser-year"] = "2025"

        if callback:
            callback(f"Calling API: {url[:60]}...")

        try:
            # Gọi API với data=json.dumps (giống debug script)
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),  # QUAN TRỌNG: data=, không phải json=
                timeout=120
            )

            if callback:
                callback(f"Response status: {response.status_code}")

            if response.status_code == 401:
                if callback:
                    callback("❌ Token hết hạn!")
                return []

            if response.status_code == 403:
                resp_text = response.text.lower()
                if "recaptcha" in resp_text:
                    if callback:
                        callback("❌ recaptchaToken đã hết hạn - cần tạo ảnh mới trong Chrome")
                else:
                    if callback:
                        callback(f"❌ Forbidden: {response.text[:200]}")
                return []

            if response.status_code != 200:
                if callback:
                    callback(f"❌ Error {response.status_code}: {response.text[:200]}")
                    # Log thêm thông tin debug
                    if response.status_code == 400:
                        callback(f"   Debug: requests count = {len(payload.get('requests', []))}")
                        if payload.get('requests'):
                            req0 = payload['requests'][0]
                            callback(f"   Debug: prompt length = {len(req0.get('prompt', ''))}")
                            callback(f"   Debug: imageInputs = {req0.get('imageInputs', 'none')[:100] if req0.get('imageInputs') else 'none'}")
                return []

            # Parse response
            result = response.json()
            media_list = result.get("media", [])

            if not media_list:
                if callback:
                    callback("⚠️ Không có ảnh trong response")
                return []

            if callback:
                callback(f"✅ Nhận được {len(media_list)} ảnh!")

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
                                    callback(f"✅ Saved: {filename}")
                    except Exception as e:
                        if callback:
                            callback(f"❌ Download error: {e}")

            return downloaded

        except requests.exceptions.Timeout:
            if callback:
                callback("❌ Request timeout")
            return []
        except Exception as e:
            if callback:
                callback(f"❌ Error: {e}")
            return []

    def trigger_and_capture(self, prompt: str, callback=None) -> bool:
        """
        Trigger Chrome để tạo request mới với prompt, capture payload.
        Request sẽ bị cancel để giữ recaptchaToken.

        Args:
            prompt: Prompt để gửi
            callback: Callback để log

        Returns:
            True nếu capture thành công
        """
        if not HAS_PAG:
            if callback:
                callback("ERROR: PyAutoGUI not installed")
            return False

        # Reset captured values
        self.captured_payload = None
        self.recaptcha_token = None

        try:
            # Re-inject capture script
            self._inject_capture_script(callback)
            time.sleep(0.5)

            # Focus Chrome
            chrome_manager._focus_chrome()
            time.sleep(0.3)

            # Focus textarea
            focus_script = """
            (function() {
                var ta = document.querySelector('textarea');
                if (ta) { ta.focus(); ta.click(); ta.select(); }
            })();
            """
            chrome_manager.run_js(focus_script)
            time.sleep(0.5)

            # Clear và paste prompt
            pag.hotkey("ctrl", "a")
            time.sleep(0.2)
            pyperclip.copy(prompt)
            pag.hotkey("ctrl", "v")
            time.sleep(0.5)

            if callback:
                callback(f"Đã nhập prompt, đang trigger request...")

            # Nhấn Enter để trigger request (sẽ bị cancel bởi script)
            pag.press("enter")
            time.sleep(3)  # Đợi request được trigger và capture

            # Lấy captured values
            if self._get_captured_token(callback):
                if self.captured_payload and self.recaptcha_token:
                    if callback:
                        callback("✅ Đã capture payload với recaptchaToken mới!")
                    return True

            if callback:
                callback("⚠️ Không capture được payload mới")
            return False

        except Exception as e:
            if callback:
                callback(f"Lỗi: {e}")
            return False

    def close(self):
        """Đóng tab Flow (không đóng Chrome)."""
        chrome_manager.close_current_tab()

    def extract_token_async(self, callback=None, on_complete=None):
        """Lấy token trong background thread."""
        def worker():
            token, project_id, error = self.extract_token(callback)
            if on_complete:
                on_complete(token, project_id, error)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Chrome Token Extractor - Google Flow")
    print("=" * 60)

    # Default paths
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    profile_path = r"C:\Users\admin\AppData\Local\Google\Chrome\User Data\Profile 2"

    if len(sys.argv) >= 3:
        chrome_path = sys.argv[1]
        profile_path = sys.argv[2]

    print(f"Chrome: {chrome_path}")
    print(f"Profile: {profile_path}")
    print()

    def progress(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    extractor = ChromeTokenExtractor(
        chrome_path=chrome_path,
        profile_path=profile_path,
        timeout=120
    )

    token, project_id, error = extractor.extract_token(callback=progress)

    print()
    if token:
        print("=" * 60)
        print("✅ SUCCESS!")
        print(f"Token: {token[:50]}...")
        print(f"Project ID: {project_id}")
        print("=" * 60)
    else:
        print("=" * 60)
        print(f"❌ FAILED: {error}")
        print("=" * 60)

    input("\nNhấn Enter để đóng tab...")
    extractor.close()
