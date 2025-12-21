"""
SORA Automation - Tự động tạo video bằng OpenAI SORA
Website: https://sora.chatgpt.com/drafts

Workflow:
1. Mở Chrome với profile đã đăng nhập
2. Vào https://sora.chatgpt.com/drafts
3. Nhập prompt + upload ảnh
4. Chờ video tạo xong
5. Download + xóa watermark
6. Lưu vào thư mục OUTPUT
"""

import os
import time
import re
import shutil
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from rich.console import Console

console = Console()


@dataclass
class SoraResult:
    """Kết quả tạo video từ SORA"""
    success: bool
    video_path: str = ""
    video_url: str = ""
    error: str = ""
    duration: float = 0


class SoraAutomation:
    """
    Tự động hóa SORA để tạo video từ prompt + ảnh

    Workflow:
    1. Mở sora.chatgpt.com/drafts
    2. Nhập prompt vào textarea
    3. Click nút + để upload ảnh
    4. Chọn file ảnh
    5. Enter để gửi
    6. Chờ video tạo xong (check loading spinner)
    7. Download video
    8. Xóa watermark
    9. Lưu với tên ưu tiên (00_sora_xxx.mp4)
    """

    SORA_URL = "https://sora.chatgpt.com/drafts"

    def __init__(
        self,
        output_folder: str = "OUTPUT",
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = False,
        timeout: int = 300  # 5 phút timeout
    ):
        """
        Args:
            output_folder: Thư mục lưu video
            chrome_path: Đường dẫn Chrome executable
            profile_path: Đường dẫn Chrome profile (để giữ đăng nhập)
            headless: Chạy ẩn browser
            timeout: Timeout cho việc tạo video (giây)
        """
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.headless = headless
        self.timeout = timeout

        self.driver = None
        self.wait = None

    def _create_driver(self) -> webdriver.Chrome:
        """Tạo Chrome WebDriver với cấu hình"""
        options = Options()

        # Profile để giữ đăng nhập
        if self.profile_path:
            options.add_argument(f"--user-data-dir={self.profile_path}")

        # Chrome path
        if self.chrome_path:
            options.binary_location = self.chrome_path

        # Headless mode
        if self.headless:
            options.add_argument("--headless=new")

        # Các options khác
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Tắt thông báo
        options.add_argument("--disable-notifications")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Cho phép file dialog
        prefs = {
            "profile.default_content_setting_values.automatic_downloads": 1,
            "download.prompt_for_download": False,
        }
        options.add_experimental_option("prefs", prefs)

        driver = webdriver.Chrome(options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        return driver

    def start(self) -> bool:
        """Khởi động browser và mở SORA"""
        try:
            console.print("[cyan]🚀 Khởi động Chrome cho SORA...[/]")
            self.driver = self._create_driver()
            self.wait = WebDriverWait(self.driver, 30)

            console.print(f"[cyan]🌐 Mở {self.SORA_URL}...[/]")
            self.driver.get(self.SORA_URL)

            # Chờ trang load
            time.sleep(3)

            # Kiểm tra đăng nhập - tìm textarea prompt
            if not self._check_logged_in():
                console.print("[yellow]⚠️ Chưa đăng nhập SORA/ChatGPT. Vui lòng đăng nhập thủ công...[/]")
                console.print("[dim]Chờ 120 giây để đăng nhập...[/]")

                for i in range(120):
                    if self._check_logged_in():
                        console.print("[green]✓ Đã đăng nhập![/]")
                        break
                    time.sleep(1)
                    if i % 30 == 0 and i > 0:
                        console.print(f"[dim]Còn {120-i}s...[/]")
                else:
                    console.print("[red]❌ Timeout đăng nhập[/]")
                    return False

            console.print("[green]✓ SORA sẵn sàng[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi khởi động: {e}[/]")
            return False

    def _check_logged_in(self) -> bool:
        """Kiểm tra đã đăng nhập SORA chưa"""
        try:
            # Tìm textarea với placeholder "Describe your video..."
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            for ta in textareas:
                placeholder = ta.get_attribute("placeholder") or ""
                if "describe" in placeholder.lower() or "video" in placeholder.lower():
                    return True

            # Kiểm tra URL
            current_url = self.driver.current_url.lower()
            if "drafts" in current_url or "sora" in current_url:
                # Có thể đã đăng nhập, kiểm tra thêm
                textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                if textareas:
                    return True

            return False

        except Exception:
            return False

    def _find_prompt_input(self):
        """Tìm ô nhập prompt (textarea với placeholder 'Describe your video...')"""
        try:
            # Tìm textarea với placeholder chứa "Describe your video"
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            for ta in textareas:
                if ta.is_displayed():
                    placeholder = ta.get_attribute("placeholder") or ""
                    if "describe" in placeholder.lower():
                        return ta
                    # Fallback: textarea đầu tiên visible

            # Fallback
            for ta in textareas:
                if ta.is_displayed():
                    return ta

            return None
        except Exception as e:
            console.print(f"[dim]Lỗi tìm prompt input: {e}[/]")
            return None

    def _find_upload_button(self):
        """Tìm nút upload (icon +)"""
        try:
            # Tìm button chứa SVG với path có icon +
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if not btn.is_displayed():
                    continue
                try:
                    # Kiểm tra có SVG với path icon + không
                    svg = btn.find_element(By.TAG_NAME, "svg")
                    paths = svg.find_elements(By.TAG_NAME, "path")
                    for path in paths:
                        d = path.get_attribute("d") or ""
                        # Icon + thường có path với M12 6a1 1 0 0 1...
                        if "M12 6" in d or "M12 " in d:
                            return btn
                except:
                    pass

            # Fallback: tìm button gần textarea
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            if textareas:
                ta = textareas[0]
                parent = ta.find_element(By.XPATH, "./../..")
                buttons = parent.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if btn.is_displayed():
                        return btn

            return None
        except Exception as e:
            console.print(f"[dim]Lỗi tìm upload button: {e}[/]")
            return None

    def _upload_image(self, image_path: str) -> bool:
        """Upload ảnh bằng cách gửi path đến file input"""
        try:
            # Tìm input type="file" (có thể ẩn)
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")

            if file_inputs:
                # Sử dụng file input trực tiếp
                file_input = file_inputs[0]
                file_input.send_keys(os.path.abspath(image_path))
                console.print(f"[dim]Đã upload qua file input: {Path(image_path).name}[/]")
                return True

            # Nếu không có file input, click button upload
            upload_btn = self._find_upload_button()
            if upload_btn:
                upload_btn.click()
                time.sleep(1)

                # Chờ file input xuất hiện
                for _ in range(10):
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_inputs:
                        file_inputs[0].send_keys(os.path.abspath(image_path))
                        console.print(f"[dim]Đã upload: {Path(image_path).name}[/]")
                        return True
                    time.sleep(0.5)

            console.print("[yellow]⚠️ Không tìm thấy cách upload ảnh[/]")
            return False

        except Exception as e:
            console.print(f"[red]❌ Lỗi upload ảnh: {e}[/]")
            return False

    def _wait_for_video(self) -> Optional[str]:
        """
        Chờ video được tạo xong và trả về URL

        Video đang tạo sẽ có loading spinner (animate-spin)
        Video xong sẽ có thẻ <video src="...">
        """
        console.print(f"[dim]⏳ Chờ video tạo xong (timeout: {self.timeout}s)...[/]")

        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Kiểm tra loading spinner (video đang tạo)
                spinners = self.driver.find_elements(By.CSS_SELECTOR, "[class*='animate-spin'], .animate-spin")
                is_loading = any(s.is_displayed() for s in spinners)

                # Tìm video element
                videos = self.driver.find_elements(By.TAG_NAME, "video")
                for video in videos:
                    if not video.is_displayed():
                        continue
                    src = video.get_attribute("src")
                    if src and src.startswith("http") and "videos.openai.com" in src:
                        # Kiểm tra video đã sẵn sàng chưa
                        ready_state = self.driver.execute_script(
                            "return arguments[0].readyState", video
                        )
                        if ready_state >= 2:  # HAVE_CURRENT_DATA
                            console.print(f"[green]✓ Video đã sẵn sàng![/]")
                            return src

                # Nếu không còn loading và chưa có video -> có thể lỗi
                if not is_loading:
                    # Kiểm tra lỗi
                    error_elements = self.driver.find_elements(By.CSS_SELECTOR,
                        "[role='alert'], .error, [class*='error']")
                    for err in error_elements:
                        if err.is_displayed() and err.text:
                            console.print(f"[red]❌ Lỗi: {err.text}[/]")
                            return None

                # Log progress
                elapsed = int(time.time() - start_time)
                if elapsed % 15 == 0 and elapsed > 0:
                    status = "đang tạo..." if is_loading else "đang chờ..."
                    console.print(f"[dim]  {elapsed}s - {status}[/]")

                time.sleep(3)

            except Exception as e:
                console.print(f"[yellow]⚠️ Lỗi khi chờ: {e}[/]")
                time.sleep(3)

        console.print("[red]❌ Timeout chờ video[/]")
        return None

    def _download_video(self, video_url: str, output_path: str) -> bool:
        """Download video từ URL"""
        try:
            console.print(f"[dim]📥 Downloading video...[/]")

            # Lấy cookies từ browser để download
            cookies = {c['name']: c['value'] for c in self.driver.get_cookies()}

            headers = {
                'User-Agent': self.driver.execute_script("return navigator.userAgent"),
                'Referer': self.SORA_URL,
            }

            response = requests.get(
                video_url,
                cookies=cookies,
                headers=headers,
                stream=True,
                timeout=120
            )
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            console.print(f"[green]✓ Đã tải: {Path(output_path).name}[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi download: {e}[/]")
            return False

    def _remove_watermark(self, input_path: str, output_path: str) -> bool:
        """
        Xử lý watermark của SORA

        LƯU Ý: Watermark SORA nhảy vị trí trong video (icon + "Sora" + @username)
        nên không thể crop đơn giản. Tạm thời giữ nguyên video.

        Các cách xử lý trong tương lai:
        1. AI inpainting để xóa watermark động
        2. Dùng tool chuyên dụng như Remove.bg cho video
        3. Blur vùng watermark (cần detect vị trí)
        """
        try:
            # Tạm thời: Giữ nguyên video, chỉ rename
            console.print(f"[yellow]⚠️ Watermark SORA nhảy vị trí - giữ nguyên video[/]")
            shutil.move(input_path, output_path)
            return True

        except Exception as e:
            console.print(f"[yellow]⚠️ Lỗi: {e}[/]")
            if os.path.exists(input_path):
                shutil.move(input_path, output_path)
            return False

    def generate_video(
        self,
        prompt: str,
        image_path: str = None,
        output_name: str = "sora_video",
        code: str = ""
    ) -> Dict[str, Any]:
        """
        Tạo video từ prompt và ảnh

        Args:
            prompt: Mô tả video cần tạo
            image_path: Đường dẫn ảnh (optional)
            output_name: Tên file output
            code: Mã sản phẩm (để lưu vào đúng thư mục)

        Returns:
            Dict với keys: success, video_path, video_url, error
        """
        result = {
            "success": False,
            "video_path": "",
            "video_url": "",
            "error": ""
        }

        if not self.driver:
            result["error"] = "Browser chưa khởi động"
            return result

        try:
            # Refresh trang để bắt đầu mới
            self.driver.get(self.SORA_URL)
            time.sleep(2)

            console.print(f"[cyan]🎬 Tạo video SORA: {prompt[:50]}...[/]")

            # Tìm và nhập prompt
            prompt_input = self._find_prompt_input()
            if not prompt_input:
                result["error"] = "Không tìm thấy ô nhập prompt"
                return result

            # Nhập prompt
            prompt_input.clear()
            prompt_input.click()
            time.sleep(0.5)

            # Nhập từng đoạn để tránh bị block
            for char in prompt:
                prompt_input.send_keys(char)
                time.sleep(0.01)

            time.sleep(1)

            # Upload ảnh nếu có
            if image_path and os.path.exists(image_path):
                console.print(f"[dim]📷 Upload ảnh: {Path(image_path).name}[/]")
                if not self._upload_image(image_path):
                    console.print("[yellow]⚠️ Không upload được ảnh, tiếp tục không có ảnh[/]")
                time.sleep(2)

            # Gửi prompt (Enter)
            prompt_input.send_keys(Keys.RETURN)
            console.print("[dim]📤 Đã gửi prompt[/]")

            time.sleep(3)

            # Chờ video được tạo
            video_url = self._wait_for_video()

            if not video_url:
                result["error"] = "Không thể tạo video hoặc timeout"
                return result

            result["video_url"] = video_url

            # Xác định thư mục output
            if code:
                # Lưu vào thư mục _temp_videos/{code}/
                video_folder = self.output_folder / "_temp_videos" / code
            else:
                video_folder = self.output_folder

            video_folder.mkdir(parents=True, exist_ok=True)

            # Tên file: 00_sora_xxx.mp4 để xếp đầu khi edit
            final_name = f"00_sora_{output_name}.mp4"
            temp_path = str(video_folder / f"_temp_{output_name}.mp4")
            final_path = str(video_folder / final_name)

            # Download video
            if not self._download_video(video_url, temp_path):
                result["error"] = "Không thể download video"
                return result

            # Xóa watermark
            self._remove_watermark(temp_path, final_path)

            result["success"] = True
            result["video_path"] = final_path

            console.print(f"[green]✓ Video SORA đã lưu: {final_name}[/]")
            return result

        except Exception as e:
            result["error"] = str(e)
            console.print(f"[red]❌ Lỗi: {e}[/]")
            import traceback
            traceback.print_exc()
            return result

    def close(self):
        """Đóng browser"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        console.print("[dim]Đã đóng browser SORA[/]")


# CLI test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SORA Video Generator")
    parser.add_argument("--prompt", "-p", required=True, help="Video prompt")
    parser.add_argument("--image", "-i", help="Image path to upload")
    parser.add_argument("--output", "-o", default="sora_output", help="Output name")
    parser.add_argument("--headless", action="store_true", help="Run headless")

    args = parser.parse_args()

    sora = SoraAutomation(headless=args.headless)

    try:
        if sora.start():
            result = sora.generate_video(
                args.prompt,
                image_path=args.image,
                output_name=args.output
            )
            print(f"\nResult: {result}")
    finally:
        sora.close()
