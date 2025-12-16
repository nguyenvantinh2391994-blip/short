"""
Grok Browser Automation - Selenium + Copy Profile
Không cần đóng Chrome đang mở!
"""

import json
import os
import shutil
import tempfile
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
    """
    Tạo video với Grok Imagine.
    Copy Chrome profile để không conflict với Chrome đang mở.
    """

    GROK_IMAGINE_URL = "https://grok.com/imagine"

    def __init__(
        self,
        chrome_path: str = None,
        profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
        headless: bool = False,
        timeout: int = 300,
    ):
        self.chrome_path = chrome_path or self._find_chrome()
        self.profile_path = profile_path
        self.headless = headless
        self.timeout = timeout

        self.driver = None
        self.temp_profile_dir = None

    def _find_chrome(self) -> str:
        """Tìm Chrome."""
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in paths:
            if Path(p).exists():
                return p
        return "chrome"

    def _copy_profile(self) -> str:
        """Copy Chrome profile sang thư mục tạm."""
        if not self.profile_path or not Path(self.profile_path).exists():
            console.print(f"[yellow]Profile không tồn tại: {self.profile_path}[/]")
            return None

        console.print("[cyan]Đang copy Chrome profile...[/]")

        # Tạo thư mục tạm
        self.temp_profile_dir = tempfile.mkdtemp(prefix="grok_chrome_")
        dst = Path(self.temp_profile_dir) / "Profile"
        dst.mkdir(parents=True, exist_ok=True)

        src = Path(self.profile_path)

        # Copy các file quan trọng (cookies, login)
        important_items = [
            "Cookies",
            "Login Data",
            "Web Data",
            "Preferences",
            "Secure Preferences",
            "Local State",
            "Network",
        ]

        for item in important_items:
            src_path = src / item
            if src_path.exists():
                try:
                    if src_path.is_file():
                        shutil.copy2(src_path, dst / item)
                    else:
                        shutil.copytree(src_path, dst / item, dirs_exist_ok=True)
                except Exception as e:
                    pass  # Bỏ qua lỗi copy

        # Copy Local State từ User Data folder
        local_state = src.parent / "Local State"
        if local_state.exists():
            try:
                shutil.copy2(local_state, Path(self.temp_profile_dir) / "Local State")
            except:
                pass

        console.print(f"[green]✓ Đã copy profile sang: {self.temp_profile_dir}[/]")
        return self.temp_profile_dir

    def _create_driver(self):
        """Tạo Selenium WebDriver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            console.print("[red]❌ Chưa cài Selenium![/]")
            console.print("[yellow]Chạy: pip install selenium webdriver-manager[/]")
            return False

        options = Options()

        # Profile đã copy
        temp_dir = self._copy_profile()
        if temp_dir:
            options.add_argument(f"--user-data-dir={temp_dir}")
            options.add_argument("--profile-directory=Profile")

        # Chrome path
        if self.chrome_path and Path(self.chrome_path).exists():
            options.binary_location = self.chrome_path

        # Headless
        if self.headless:
            options.add_argument("--headless=new")

        # Common options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1400,900")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Download preferences
        prefs = {
            "download.default_directory": str(Path("outputs").absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        }
        options.add_experimental_option("prefs", prefs)

        # Get ChromeDriver
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            console.print("[green]✓ ChromeDriver OK[/]")
        except Exception as e:
            console.print(f"[yellow]webdriver-manager lỗi, thử mặc định...[/]")
            service = Service()

        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.maximize_window()
            console.print("[green]✓ Chrome đã mở![/]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Không mở được Chrome: {e}[/]")
            return False

    def _wait_for_element(self, by, value, timeout=10, clickable=False):
        """Đợi element xuất hiện."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        condition = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
        return WebDriverWait(self.driver, timeout).until(condition((by, value)))

    def _check_login(self) -> bool:
        """Kiểm tra đã đăng nhập chưa."""
        # Nếu ở trang login thì chưa đăng nhập
        url = self.driver.current_url
        if "accounts.google.com" in url or "x.com/login" in url:
            return False
        return True

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
            console.print("[bold cyan]Bước 1: Mở Chrome...[/]")
            if not self._create_driver():
                return GrokVideoResult(success=False, error="Không mở được Chrome")

            # 2. Vào Grok Imagine
            console.print("[bold cyan]Bước 2: Vào Grok Imagine...[/]")
            self.driver.get(self.GROK_IMAGINE_URL)
            time.sleep(5)

            # Kiểm tra login
            if not self._check_login():
                console.print("[yellow]⚠️ Chưa đăng nhập! Đang đợi bạn đăng nhập...[/]")
                for i in range(120):
                    time.sleep(2)
                    if self._check_login():
                        console.print("[green]✓ Đã đăng nhập![/]")
                        self.driver.get(self.GROK_IMAGINE_URL)
                        time.sleep(3)
                        break
                else:
                    return GrokVideoResult(success=False, error="Timeout đợi đăng nhập")

            # 3. Click nút đính kèm
            console.print("[bold cyan]Bước 3: Click nút đính kèm...[/]")
            attach_selectors = [
                '//button[@aria-label="Đính kèm"]',
                '//button[@aria-label="Attach"]',
                '//button[contains(@class, "attach")]',
                '//button[.//svg[contains(@class, "paperclip")]]',
            ]

            attached = False
            for sel in attach_selectors:
                try:
                    btn = self._wait_for_element(By.XPATH, sel, timeout=5, clickable=True)
                    btn.click()
                    attached = True
                    console.print("[green]✓ Đã click nút đính kèm[/]")
                    break
                except:
                    continue

            if not attached:
                return GrokVideoResult(success=False, error="Không tìm thấy nút đính kèm")

            time.sleep(1)

            # 4. Click "Tải lên một tệp"
            console.print("[bold cyan]Bước 4: Click Tải lên tệp...[/]")
            upload_selectors = [
                '//div[@role="menuitem"][contains(., "Tải lên một tệp")]',
                '//div[@role="menuitem"][contains(., "Upload a file")]',
                '//div[contains(text(), "Tải lên")]',
            ]

            for sel in upload_selectors:
                try:
                    item = self._wait_for_element(By.XPATH, sel, timeout=3, clickable=True)
                    item.click()
                    console.print("[green]✓ Đã click Tải lên[/]")
                    break
                except:
                    continue

            time.sleep(1)

            # 5. Upload file
            console.print(f"[bold cyan]Bước 5: Upload ảnh: {image_path.name}[/]")
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
                file_input.send_keys(str(image_path))
                console.print("[green]✓ Đã upload ảnh[/]")
            except:
                return GrokVideoResult(success=False, error="Không tìm thấy input file")

            time.sleep(3)

            # 6. Nhập prompt nếu có
            if prompt:
                console.print(f"[bold cyan]Bước 6: Nhập prompt: {prompt[:50]}...[/]")
                try:
                    textarea = self._wait_for_element(By.TAG_NAME, "textarea", timeout=5)
                    textarea.clear()
                    textarea.send_keys(prompt)
                    console.print("[green]✓ Đã nhập prompt[/]")
                except:
                    pass

            time.sleep(1)

            # 7. Nhấn Enter để tạo video
            console.print("[bold cyan]Bước 7: Bắt đầu tạo video...[/]")
            try:
                textarea = self.driver.find_element(By.TAG_NAME, "textarea")
                textarea.send_keys(Keys.RETURN)
            except:
                pass

            console.print("[yellow]⏳ Đang tạo video... (chờ 1-5 phút)[/]")

            # 8. Đợi video xong (nút Làm lại xuất hiện)
            done_selectors = [
                '//button[contains(., "Làm lại")]',
                '//button[contains(., "Redo")]',
                '//button[contains(., "Regenerate")]',
            ]

            video_done = False
            for i in range(self.timeout):
                time.sleep(1)
                if i % 30 == 0:
                    console.print(f"[dim]...đã chờ {i}s[/]")

                for sel in done_selectors:
                    try:
                        self.driver.find_element(By.XPATH, sel)
                        video_done = True
                        break
                    except:
                        continue

                if video_done:
                    break

            if not video_done:
                return GrokVideoResult(success=False, error="Timeout chờ video")

            console.print("[green]✓ Video đã tạo xong![/]")
            time.sleep(2)

            # 9. Download video
            console.print("[bold cyan]Bước 8: Tải video...[/]")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            download_selectors = [
                '//svg[contains(@class, "lucide-download")]/..',
                '//button[.//svg[contains(@class, "download")]]',
                '//*[@data-testid="download-button"]',
            ]

            for sel in download_selectors:
                try:
                    btn = self._wait_for_element(By.XPATH, sel, timeout=5, clickable=True)
                    btn.click()
                    console.print("[green]✓ Đã click download[/]")
                    break
                except:
                    continue

            # Đợi download
            time.sleep(10)

            # Tìm file mới nhất trong outputs
            outputs_dir = Path("outputs")
            mp4_files = list(outputs_dir.glob("*.mp4"))
            if mp4_files:
                newest = max(mp4_files, key=lambda f: f.stat().st_mtime)
                if newest.name != Path(output_path).name:
                    shutil.move(str(newest), output_path)

            if Path(output_path).exists():
                console.print(f"[green]✅ Đã lưu: {output_path}[/]")
                return GrokVideoResult(success=True, video_path=output_path)
            else:
                console.print("[yellow]⚠️ Video có thể đã tải vào thư mục Downloads[/]")
                return GrokVideoResult(success=True, video_path="Downloads folder")

        except Exception as e:
            return GrokVideoResult(success=False, error=str(e))
        finally:
            self._cleanup()

    def _cleanup(self):
        """Dọn dẹp."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

        if self.temp_profile_dir and Path(self.temp_profile_dir).exists():
            try:
                shutil.rmtree(self.temp_profile_dir, ignore_errors=True)
            except:
                pass
            self.temp_profile_dir = None


def create_video_sync(
    image_path: str,
    prompt: str = "",
    output_path: str = "outputs/video.mp4",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    profile_name: str = "Default",
    headless: bool = False,
) -> GrokVideoResult:
    """Tạo video - gọi từ CLI."""
    auto = GrokBrowserAutomation(
        profile_path=chrome_profile_path,
        headless=headless,
    )
    return auto.create_video(image_path, prompt, output_path)


def create_videos_batch_sync(
    tasks: List[dict],
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    profile_name: str = "Default",
    headless: bool = False,
) -> List[GrokVideoResult]:
    """Tạo nhiều video."""
    results = []
    for i, task in enumerate(tasks, 1):
        console.print(f"\n[bold]===== Video {i}/{len(tasks)} =====[/]")
        result = create_video_sync(
            task["image"],
            task.get("prompt", ""),
            task["output"],
            chrome_profile_path,
            profile_name,
            headless,
        )
        results.append(result)

        if i < len(tasks):
            console.print("[dim]Nghỉ 5s trước video tiếp...[/]")
            time.sleep(5)

    return results


# Giữ lại để tương thích với main.py
def is_chrome_debug_running(port: int = 9222) -> bool:
    return False


def start_chrome_debug(**kwargs) -> bool:
    return True
