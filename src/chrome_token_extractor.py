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
    from rich.console import Console
    console = Console()
except ImportError:
    class Console:
        def print(self, *args, **kwargs):
            print(*args)
    console = Console()

from .chrome_manager import chrome_manager

# Token capture script - inject vào page để hook fetch
TOKEN_CAPTURE_SCRIPT = """
window._tk=null;window._pj=null;
(function(){
  var f=window.fetch;
  window.fetch=function(u,o){
    var s=u?u.toString():'';
    if(s.includes('flowMedia')||s.includes('aisandbox')){
      var h=o&&o.headers?o.headers:{};
      var a=h.Authorization||h.authorization||'';
      if(a.startsWith('Bearer ')){
        window._tk=a.substring(7);
        var m=s.match(/\\/projects\\/([^\\/]+)\\//);
        if(m) window._pj=m[1];
        console.log('[TOKEN] Captured:', window._tk ? window._tk.substring(0,20)+'...' : 'none');
      }
    }
    return f.apply(this,arguments);
  };
  console.log('[TOKEN] Capture script injected');
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
        self.bearer_token = None
        self.project_id = None

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
        """Bước 4: Chọn mode 'Tạo hình ảnh'."""
        if callback:
            callback("Đang chọn mode 'Tạo hình ảnh'...")

        # Script để click vào dropdown và chọn option
        select_script = """
        (function() {
            // Tìm dropdown/combobox
            var combo = document.querySelector('[role="combobox"], [role="listbox"], select');
            if (combo) {
                combo.click();
                copy('opened combo');
                return;
            }
            copy('no combo found');
        })();
        """

        result = chrome_manager.run_js(select_script)
        if callback:
            callback(f"Combo result: {result}")
        time.sleep(1)

        # Sau khi mở combo, chọn option
        option_script = """
        (function() {
            var options = document.querySelectorAll('[role="option"], [role="menuitem"], option, li');
            for (var i = 0; i < options.length; i++) {
                var text = options[i].innerText || options[i].textContent || '';
                if (text.includes('Tạo hình ảnh') || text.includes('Generate image') ||
                    text.includes('Text to image') || text.includes('Image')) {
                    options[i].click();
                    copy('selected: ' + text);
                    return;
                }
            }
            copy('no option found');
        })();
        """

        result = chrome_manager.run_js(option_script)
        if callback:
            callback(f"Option result: {result}")
        time.sleep(2)
        return True

    def _send_prompt(self, callback=None):
        """Bước 5: Gửi prompt để trigger API call."""
        if callback:
            callback("Đang gửi prompt...")

        prompt = "beautiful sunset over ocean, high quality photo"

        send_script = f"""
        (function() {{
            // Tìm textarea
            var textarea = document.querySelector('textarea');
            if (!textarea) {{
                textarea = document.querySelector('[contenteditable="true"]');
            }}

            if (textarea) {{
                textarea.focus();
                textarea.value = "{prompt}";
                textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
                copy('prompt entered');
            }} else {{
                copy('no textarea found');
            }}
        }})();
        """

        result = chrome_manager.run_js(send_script)
        if callback:
            callback(f"Prompt result: {result}")
        time.sleep(1)

        # Nhấn nút submit
        submit_script = """
        (function() {
            var submitBtn = document.querySelector('button[type="submit"], button[aria-label*="Generate"], button[aria-label*="Send"], button[aria-label*="Gửi"]');
            if (submitBtn) {
                submitBtn.click();
                copy('submitted');
                return;
            }

            // Thử Enter trong textarea
            var textarea = document.querySelector('textarea');
            if (textarea) {
                textarea.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    which: 13,
                    bubbles: true
                }));
                copy('enter pressed');
                return;
            }
            copy('no submit');
        })();
        """

        result = chrome_manager.run_js(submit_script)
        if callback:
            callback(f"Submit result: {result}")

        # Đợi API call được thực hiện (20-30 giây)
        if callback:
            callback("Đang đợi API call (25s)...")
        time.sleep(25)
        return True

    def _get_captured_token(self, callback=None):
        """Bước 6: Lấy token đã capture."""
        if callback:
            callback("Đang lấy token...")

        get_token_script = """
        (function() {
            if (window._tk) {
                copy('TOKEN:' + window._tk + '|PROJECT:' + (window._pj || 'none'));
            } else {
                copy('NO_TOKEN');
            }
        })();
        """

        result = chrome_manager.run_js(get_token_script)

        if result and result.startswith('TOKEN:'):
            # Parse result: TOKEN:xxx|PROJECT:yyy
            parts = result.split('|')
            token_part = parts[0].replace('TOKEN:', '')
            project_part = parts[1].replace('PROJECT:', '') if len(parts) > 1 else None

            self.bearer_token = token_part
            self.project_id = project_part if project_part != 'none' else None

            if callback:
                callback(f"✅ Token: {self.bearer_token[:30]}...")
            return True
        else:
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
