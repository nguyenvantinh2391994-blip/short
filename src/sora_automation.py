"""
SORA Automation - Tự động tạo video bằng OpenAI SORA
Website: sora.com
"""

import os
import time
import re
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    Tự động hóa SORA để tạo video từ prompt

    Workflow:
    1. Mở sora.com
    2. Đăng nhập (nếu cần)
    3. Nhập prompt
    4. Chờ video được tạo
    5. Download video
    """

    SORA_URL = "https://sora.com"

    # Selectors cho SORA (cần cập nhật khi SORA thay đổi UI)
    SELECTORS = {
        "prompt_input": "textarea[placeholder*='prompt'], textarea[data-testid='prompt-input'], #prompt-input",
        "generate_button": "button[type='submit'], button:contains('Generate'), button:contains('Create')",
        "video_element": "video, [data-testid='video-player']",
        "download_button": "button:contains('Download'), a[download], [data-testid='download-button']",
        "loading_indicator": "[data-testid='loading'], .loading, .spinner",
        "error_message": "[data-testid='error'], .error-message, [role='alert']",
    }

    def __init__(
        self,
        output_folder: str = "OUTPUT",
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = False,
        timeout: int = 300  # 5 phút timeout cho video generation
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
            console.print("[cyan]Khởi động Chrome...[/]")
            self.driver = self._create_driver()
            self.wait = WebDriverWait(self.driver, 30)

            console.print(f"[cyan]Mở {self.SORA_URL}...[/]")
            self.driver.get(self.SORA_URL)

            # Chờ trang load
            time.sleep(3)

            # Kiểm tra đăng nhập
            if not self._check_logged_in():
                console.print("[yellow]⚠️ Chưa đăng nhập SORA. Vui lòng đăng nhập thủ công...[/]")
                console.print("[dim]Chờ 60 giây để đăng nhập...[/]")

                # Chờ user đăng nhập
                for i in range(60):
                    if self._check_logged_in():
                        console.print("[green]✓ Đã đăng nhập![/]")
                        break
                    time.sleep(1)
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
            # Tìm các dấu hiệu đã đăng nhập
            # - Có prompt input
            # - Không có nút Login/Sign in

            # Thử tìm prompt input
            prompt_selectors = [
                "textarea",
                "input[type='text']",
                "[contenteditable='true']"
            ]

            for selector in prompt_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        return True
                except:
                    pass

            # Kiểm tra URL có chứa dashboard/create không
            current_url = self.driver.current_url.lower()
            if any(x in current_url for x in ['dashboard', 'create', 'generate', 'app']):
                return True

            return False

        except Exception:
            return False

    def _find_prompt_input(self):
        """Tìm ô nhập prompt"""
        selectors = [
            "textarea",
            "textarea[placeholder]",
            "input[type='text'][placeholder*='prompt' i]",
            "[contenteditable='true']",
            "[data-testid='prompt-input']",
            ".prompt-input",
            "#prompt"
        ]

        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except:
                pass

        return None

    def _find_generate_button(self):
        """Tìm nút Generate/Create"""
        selectors = [
            "button[type='submit']",
            "button:not([disabled])",
        ]

        keywords = ['generate', 'create', 'submit', 'go', 'make']

        # Tìm button có text chứa keywords
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if not btn.is_displayed() or not btn.is_enabled():
                    continue
                btn_text = btn.text.lower()
                if any(kw in btn_text for kw in keywords):
                    return btn
        except:
            pass

        # Fallback: tìm submit button
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except:
                pass

        return None

    def _wait_for_video(self) -> Optional[str]:
        """Chờ video được tạo và trả về URL"""
        console.print(f"[dim]Chờ video (timeout: {self.timeout}s)...[/]")

        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Tìm video element
                video_selectors = [
                    "video",
                    "video source",
                    "[data-testid='video']",
                    ".video-player video"
                ]

                for selector in video_selectors:
                    try:
                        videos = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for video in videos:
                            src = video.get_attribute("src")
                            if src and src.startswith("http"):
                                console.print(f"[green]✓ Tìm thấy video![/]")
                                return src
                    except:
                        pass

                # Kiểm tra lỗi
                error_selectors = [
                    "[role='alert']",
                    ".error",
                    "[data-testid='error']"
                ]

                for selector in error_selectors:
                    try:
                        errors = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for err in errors:
                            if err.is_displayed():
                                error_text = err.text
                                if error_text:
                                    console.print(f"[red]❌ Lỗi: {error_text}[/]")
                                    return None
                    except:
                        pass

                time.sleep(5)
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0:
                    console.print(f"[dim]  Đang chờ... ({elapsed}s)[/]")

            except Exception as e:
                console.print(f"[yellow]⚠️ Lỗi khi chờ: {e}[/]")
                time.sleep(5)

        console.print("[red]❌ Timeout chờ video[/]")
        return None

    def _download_video(self, video_url: str, output_name: str) -> Optional[str]:
        """Download video từ URL"""
        try:
            output_path = self.output_folder / f"{output_name}.mp4"

            console.print(f"[dim]Downloading video...[/]")

            # Thử download bằng requests
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            console.print(f"[green]✓ Đã lưu: {output_path.name}[/]")
            return str(output_path)

        except Exception as e:
            console.print(f"[red]❌ Lỗi download: {e}[/]")
            return None

    def generate_video(
        self,
        prompt: str,
        output_name: str = "sora_video"
    ) -> Dict[str, Any]:
        """
        Tạo video từ prompt

        Args:
            prompt: Mô tả video cần tạo
            output_name: Tên file output (không có extension)

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
            console.print(f"[cyan]Tạo video: {prompt[:50]}...[/]")

            # Tìm và nhập prompt
            prompt_input = self._find_prompt_input()
            if not prompt_input:
                result["error"] = "Không tìm thấy ô nhập prompt"
                return result

            # Clear và nhập prompt
            prompt_input.clear()
            prompt_input.send_keys(prompt)
            time.sleep(1)

            # Tìm và click nút Generate
            generate_btn = self._find_generate_button()
            if not generate_btn:
                # Thử Enter
                prompt_input.send_keys(Keys.RETURN)
            else:
                generate_btn.click()

            console.print("[dim]Đã gửi prompt, chờ video...[/]")

            # Chờ video được tạo
            video_url = self._wait_for_video()

            if not video_url:
                result["error"] = "Không thể tạo video hoặc timeout"
                return result

            result["video_url"] = video_url

            # Download video
            video_path = self._download_video(video_url, output_name)

            if video_path:
                result["success"] = True
                result["video_path"] = video_path
            else:
                result["error"] = "Không thể download video"

            return result

        except Exception as e:
            result["error"] = str(e)
            console.print(f"[red]❌ Lỗi: {e}[/]")
            return result

    def close(self):
        """Đóng browser"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        console.print("[dim]Đã đóng browser[/]")


# CLI test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SORA Video Generator")
    parser.add_argument("--prompt", "-p", required=True, help="Video prompt")
    parser.add_argument("--output", "-o", default="sora_output", help="Output name")
    parser.add_argument("--headless", action="store_true", help="Run headless")

    args = parser.parse_args()

    sora = SoraAutomation(headless=args.headless)

    try:
        if sora.start():
            result = sora.generate_video(args.prompt, args.output)
            print(f"\nResult: {result}")
    finally:
        sora.close()
