"""
Grok Browser Automation - Đơn giản
Dùng trực tiếp Chrome + Profile có sẵn
"""

import time
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from rich.console import Console

console = Console()


@dataclass
class GrokVideoResult:
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


class GrokBrowserAutomation:
    """Tạo video với Grok Imagine - dùng Chrome có sẵn."""

    GROK_IMAGINE_URL = "https://grok.com/imagine"

    def __init__(
        self,
        chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
        headless: bool = False,
    ):
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.headless = headless
        self.driver = None

    def _create_driver(self):
        """Mở Chrome với profile có sẵn."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            console.print("[red]❌ Chưa cài Selenium![/]")
            console.print("[yellow]Chạy: pip install selenium webdriver-manager[/]")
            return False

        options = Options()

        # Dùng Chrome + Profile có sẵn
        options.binary_location = self.chrome_path

        # Profile path: lấy thư mục cha (User Data) và tên profile
        profile = Path(self.profile_path)
        user_data_dir = profile.parent  # C:\Users\trant\AppData\Local\Google\Chrome\User Data
        profile_name = profile.name     # Default

        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_name}")

        if self.headless:
            options.add_argument("--headless=new")

        # Tắt automation flags
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # ChromeDriver
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except:
            service = Service()

        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.maximize_window()
            console.print("[green]✓ Chrome đã mở![/]")
            return True
        except Exception as e:
            if "user data directory is already in use" in str(e).lower():
                console.print("[red]❌ Chrome đang mở! Đóng Chrome rồi chạy lại.[/]")
            else:
                console.print(f"[red]❌ Lỗi: {e}[/]")
            return False

    def _wait_for_element(self, by, value, timeout=10, clickable=False):
        """Đợi element."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        condition = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
        return WebDriverWait(self.driver, timeout).until(condition((by, value)))

    def create_video(
        self,
        image_path: str,
        prompt: str = "",
        output_path: str = "outputs/video.mp4",
    ) -> GrokVideoResult:
        """Tạo video từ ảnh."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        image_path = Path(image_path).absolute()
        if not image_path.exists():
            return GrokVideoResult(success=False, error=f"Không tìm thấy: {image_path}")

        try:
            # 1. Mở Chrome
            console.print("[cyan]1. Mở Chrome...[/]")
            if not self._create_driver():
                return GrokVideoResult(success=False, error="Không mở được Chrome")

            # 2. Vào Grok
            console.print("[cyan]2. Vào grok.com/imagine...[/]")
            self.driver.get(self.GROK_IMAGINE_URL)
            time.sleep(5)

            # Kiểm tra đăng nhập
            if "x.com/login" in self.driver.current_url:
                console.print("[yellow]⚠️ Chưa đăng nhập! Đợi bạn đăng nhập...[/]")
                for _ in range(60):
                    time.sleep(2)
                    if "x.com/login" not in self.driver.current_url:
                        self.driver.get(self.GROK_IMAGINE_URL)
                        time.sleep(3)
                        break

            # 3. Click đính kèm
            console.print("[cyan]3. Click nút đính kèm...[/]")
            for sel in ['//button[@aria-label="Đính kèm"]', '//button[@aria-label="Attach"]']:
                try:
                    btn = self._wait_for_element(By.XPATH, sel, timeout=5, clickable=True)
                    btn.click()
                    console.print("[green]✓ OK[/]")
                    break
                except:
                    continue
            time.sleep(1)

            # 4. Click tải lên
            console.print("[cyan]4. Click tải lên...[/]")
            for sel in ['//div[@role="menuitem"][contains(., "Tải lên")]', '//div[@role="menuitem"][contains(., "Upload")]']:
                try:
                    item = self._wait_for_element(By.XPATH, sel, timeout=3, clickable=True)
                    item.click()
                    break
                except:
                    continue
            time.sleep(1)

            # 5. Upload ảnh
            console.print(f"[cyan]5. Upload: {image_path.name}[/]")
            file_input = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            file_input.send_keys(str(image_path))
            console.print("[green]✓ OK[/]")
            time.sleep(3)

            # 6. Nhập prompt
            if prompt:
                console.print(f"[cyan]6. Nhập prompt...[/]")
                textarea = self.driver.find_element(By.TAG_NAME, "textarea")
                textarea.send_keys(prompt)
            time.sleep(1)

            # 7. Enter để tạo
            console.print("[cyan]7. Bắt đầu tạo video...[/]")
            textarea = self.driver.find_element(By.TAG_NAME, "textarea")
            textarea.send_keys(Keys.RETURN)

            console.print("[yellow]⏳ Đang tạo video (1-5 phút)...[/]")

            # 8. Đợi xong
            for i in range(300):
                time.sleep(1)
                if i % 30 == 0 and i > 0:
                    console.print(f"[dim]...{i}s[/]")
                try:
                    self.driver.find_element(By.XPATH, '//button[contains(., "Làm lại") or contains(., "Redo")]')
                    break
                except:
                    continue

            console.print("[green]✓ Video xong![/]")
            time.sleep(2)

            # 9. Download
            console.print("[cyan]8. Tải video...[/]")
            for sel in ['//svg[contains(@class, "download")]/..', '//button[contains(@class, "download")]']:
                try:
                    btn = self._wait_for_element(By.XPATH, sel, timeout=5, clickable=True)
                    btn.click()
                    break
                except:
                    continue

            time.sleep(10)
            console.print(f"[green]✅ Xong! Video đã tải về Downloads[/]")
            return GrokVideoResult(success=True, video_path="Downloads")

        except Exception as e:
            return GrokVideoResult(success=False, error=str(e))
        finally:
            if self.driver:
                self.driver.quit()


def create_video_sync(
    image_path: str,
    prompt: str = "",
    output_path: str = "outputs/video.mp4",
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    headless: bool = False,
) -> GrokVideoResult:
    """Tạo video."""
    auto = GrokBrowserAutomation(chrome_path, chrome_profile_path, headless)
    return auto.create_video(image_path, prompt, output_path)


def create_videos_batch_sync(
    tasks: List[dict],
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    headless: bool = False,
) -> List[GrokVideoResult]:
    """Tạo nhiều video."""
    results = []
    for i, task in enumerate(tasks, 1):
        console.print(f"\n[bold]===== Video {i}/{len(tasks)} =====[/]")
        result = create_video_sync(
            task["image"], task.get("prompt", ""), task["output"],
            chrome_path, chrome_profile_path, headless
        )
        results.append(result)
        if i < len(tasks):
            time.sleep(5)
    return results


# Giữ tương thích
def is_chrome_debug_running(port: int = 9222) -> bool:
    return False

def start_chrome_debug(**kwargs) -> bool:
    return True
