"""
VE3 Tool - Chrome Token Extractor
=================================
Tự động lấy Bearer Token từ Google Flow theo flow:
1. Mở Chrome với profile đã login
2. Inject script capture token
3. Click "Dự án mới"
4. Chọn mode "Tạo hình ảnh"
5. Gửi prompt để trigger API
6. Lấy token đã capture
"""

import time
import subprocess
import platform
from pathlib import Path
from typing import Optional, Tuple
import threading

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
"""


class ChromeTokenExtractor:
    """
    Tự động lấy Bearer Token từ Google Flow.
    Sử dụng PyAutoGUI để tự động hóa các thao tác UI.
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
        self.driver = None
        self.bearer_token = None
        self.project_id = None

        # Xử lý profile path
        profile_path_obj = Path(profile_path)
        if (profile_path_obj.parent / "Local State").exists():
            # System Chrome profile (e.g., "Profile 2" trong User Data)
            self.user_data_dir = str(profile_path_obj.parent)
            self.profile_name = profile_path_obj.name
        else:
            # Tool's user-data-dir
            self.user_data_dir = str(profile_path_obj)
            self.profile_name = "Default"

    def _create_driver(self):
        """Tạo Selenium driver với Chrome profile."""
        try:
            import undetected_chromedriver as uc

            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={self.user_data_dir}")
            options.add_argument(f"--profile-directory={self.profile_name}")
            options.binary_location = self.chrome_path
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1400,900")
            options.add_argument("--disable-blink-features=AutomationControlled")

            self.driver = uc.Chrome(options=options, use_subprocess=True)
            return True

        except ImportError:
            # Fallback to regular selenium
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            options.add_argument(f"--user-data-dir={self.user_data_dir}")
            options.add_argument(f"--profile-directory={self.profile_name}")
            options.binary_location = self.chrome_path
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1400,900")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])

            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            except:
                self.driver = webdriver.Chrome(options=options)

            return True

    def _inject_capture_script(self, callback=None):
        """Bước 2: Inject script capture token."""
        if callback:
            callback("Injecting token capture script...")

        try:
            self.driver.execute_script(TOKEN_CAPTURE_SCRIPT)
            time.sleep(1)
            return True
        except Exception as e:
            if callback:
                callback(f"Inject error: {e}")
            return False

    def _click_new_project(self, callback=None):
        """Bước 3: Click 'Dự án mới' button."""
        if callback:
            callback("Đang tìm nút 'Dự án mới'...")

        # Thử click bằng JavaScript - tìm button có text "Dự án mới"
        click_script = """
        (function() {
            // Tìm tất cả buttons
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                var text = buttons[i].innerText || buttons[i].textContent || '';
                if (text.includes('Dự án mới') || text.includes('New project') || text.includes('New')) {
                    buttons[i].click();
                    return 'clicked: ' + text;
                }
            }

            // Thử tìm bằng aria-label
            var newBtn = document.querySelector('[aria-label*="New"], [aria-label*="Mới"], [aria-label*="Create"]');
            if (newBtn) {
                newBtn.click();
                return 'clicked by aria-label';
            }

            return 'not found';
        })();
        """

        try:
            result = self.driver.execute_script(click_script)
            if callback:
                callback(f"Click result: {result}")
            time.sleep(5)  # Đợi project được tạo
            return 'clicked' in str(result).lower()
        except Exception as e:
            if callback:
                callback(f"Click error: {e}")
            return False

    def _select_image_mode(self, callback=None):
        """Bước 4: Chọn mode 'Tạo hình ảnh'."""
        if callback:
            callback("Đang chọn mode 'Tạo hình ảnh'...")

        select_script = """
        (function() {
            // Tìm dropdown/combobox
            var combo = document.querySelector('[role="combobox"], [role="listbox"], select');
            if (combo) {
                combo.click();

                // Đợi menu mở
                setTimeout(function() {
                    // Tìm option "Tạo hình ảnh"
                    var options = document.querySelectorAll('[role="option"], [role="menuitem"], option, li');
                    for (var i = 0; i < options.length; i++) {
                        var text = options[i].innerText || options[i].textContent || '';
                        if (text.includes('Tạo hình ảnh') || text.includes('Generate image') ||
                            text.includes('Text to image') || text.includes('Image')) {
                            options[i].click();
                            return 'selected: ' + text;
                        }
                    }
                }, 500);

                return 'opened combo';
            }
            return 'no combo found';
        })();
        """

        try:
            result = self.driver.execute_script(select_script)
            if callback:
                callback(f"Select result: {result}")
            time.sleep(3)
            return True
        except Exception as e:
            if callback:
                callback(f"Select error: {e}")
            return False

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
                // Thử tìm contenteditable
                textarea = document.querySelector('[contenteditable="true"]');
            }}

            if (textarea) {{
                // Focus và nhập text
                textarea.focus();
                textarea.value = "{prompt}";

                // Trigger input event
                textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));

                // Nhấn Enter để gửi
                setTimeout(function() {{
                    textarea.dispatchEvent(new KeyboardEvent('keydown', {{
                        key: 'Enter',
                        code: 'Enter',
                        keyCode: 13,
                        which: 13,
                        bubbles: true
                    }}));

                    // Thử click nút submit nếu Enter không work
                    var submitBtn = document.querySelector('button[type="submit"], button[aria-label*="Generate"], button[aria-label*="Send"], button[aria-label*="Gửi"]');
                    if (submitBtn) {{
                        submitBtn.click();
                    }}
                }}, 500);

                return 'prompt sent';
            }}
            return 'no textarea found';
        }})();
        """

        try:
            result = self.driver.execute_script(send_script)
            if callback:
                callback(f"Send result: {result}")

            # Đợi API call được thực hiện (20-30 giây)
            if callback:
                callback("Đang đợi API call (20-30s)...")
            time.sleep(25)
            return True
        except Exception as e:
            if callback:
                callback(f"Send error: {e}")
            return False

    def _get_captured_token(self, callback=None):
        """Bước 6: Lấy token đã capture."""
        if callback:
            callback("Đang lấy token...")

        try:
            result = self.driver.execute_script("""
                return {
                    token: window._tk || null,
                    projectId: window._pj || null
                };
            """)

            if result and result.get('token'):
                self.bearer_token = result['token']
                self.project_id = result.get('projectId')
                if callback:
                    callback(f"✅ Token: {self.bearer_token[:30]}...")
                return True
            else:
                if callback:
                    callback("Token chưa được capture")
                return False
        except Exception as e:
            if callback:
                callback(f"Get token error: {e}")
            return False

    def extract_token(self, callback=None) -> Tuple[Optional[str], Optional[str], str]:
        """
        Thực hiện toàn bộ flow lấy token.

        Returns:
            Tuple[bearer_token, project_id, error_message]
        """
        error = ""

        try:
            # Bước 1: Mở Chrome
            if callback:
                callback("Bước 1: Đang mở Chrome...")

            if not self._create_driver():
                return None, None, "Không thể tạo Chrome driver"

            # Navigate đến Flow
            if callback:
                callback(f"Đang mở {self.FLOW_URL}...")
            self.driver.get(self.FLOW_URL)

            # Đợi trang load (10-12 giây)
            if callback:
                callback("Đợi trang load (12s)...")
            time.sleep(12)

            # Check login
            if "accounts.google.com" in self.driver.current_url:
                if callback:
                    callback("⚠️ Cần đăng nhập Google trong cửa sổ Chrome...")
                # Đợi user login (max 2 phút)
                for i in range(120):
                    if "labs.google" in self.driver.current_url:
                        break
                    time.sleep(1)
                else:
                    return None, None, "Timeout đợi đăng nhập"
                time.sleep(5)

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
        finally:
            if self.driver:
                try:
                    # Không đóng Chrome ngay để user có thể thao tác thủ công nếu cần
                    pass
                except:
                    pass

        return None, None, error

    def close(self):
        """Đóng Chrome driver."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

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

    input("\nNhấn Enter để đóng Chrome...")
    extractor.close()
