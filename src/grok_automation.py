"""
Grok Browser Automation
Copy profile để giữ đăng nhập + không conflict Chrome đang mở
"""

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
        self.temp_profile_dir = None

    def _copy_profile(self) -> str:
        """Copy profile sang thư mục tạm - GIỮ ĐĂNG NHẬP."""
        src = Path(self.profile_path)
        if not src.exists():
            console.print(f"[red]❌ Profile không tồn tại: {src}[/]")
            return None

        self.temp_profile_dir = tempfile.mkdtemp(prefix="grok_chrome_")
        dst = Path(self.temp_profile_dir) / "Default"
        dst.mkdir(parents=True, exist_ok=True)

        # Copy các file quan trọng (cookies, login)
        important = ["Cookies", "Login Data", "Web Data", "Preferences",
                     "Secure Preferences", "Network"]

        for item in important:
            src_path = src / item
            if src_path.exists():
                try:
                    if src_path.is_file():
                        shutil.copy2(src_path, dst / item)
                    else:
                        shutil.copytree(src_path, dst / item, dirs_exist_ok=True)
                except:
                    pass

        # Copy Local State
        local_state = src.parent / "Local State"
        if local_state.exists():
            try:
                shutil.copy2(local_state, Path(self.temp_profile_dir) / "Local State")
            except:
                pass

        console.print(f"[green]✓ Đã copy profile (giữ đăng nhập)[/]")
        return self.temp_profile_dir

    def _create_driver(self):
        """Tạo Chrome driver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            console.print("[red]❌ Chưa cài Selenium![/]")
            console.print("[yellow]Chạy: pip install selenium webdriver-manager[/]")
            return False

        # Copy profile
        temp_dir = self._copy_profile()
        if not temp_dir:
            return False

        options = Options()
        options.binary_location = self.chrome_path
        options.add_argument(f"--user-data-dir={temp_dir}")
        options.add_argument("--profile-directory=Default")

        if self.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

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
            console.print(f"[red]❌ Lỗi mở Chrome: {e}[/]")
            return False

    def _wait(self, by, value, timeout=10, clickable=False):
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        cond = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
        return WebDriverWait(self.driver, timeout).until(cond((by, value)))

    def create_video(self, image_path: str, prompt: str = "", output_path: str = "") -> GrokVideoResult:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        image_path = Path(image_path).absolute()
        if not image_path.exists():
            return GrokVideoResult(False, error=f"Không tìm thấy: {image_path}")

        try:
            console.print("[cyan]1. Mở Chrome...[/]")
            if not self._create_driver():
                return GrokVideoResult(False, error="Không mở được Chrome")

            console.print("[cyan]2. Vào grok.com/imagine...[/]")
            self.driver.get(self.GROK_IMAGINE_URL)
            time.sleep(5)

            # Check login
            if "x.com/login" in self.driver.current_url:
                console.print("[yellow]⚠️ Chưa đăng nhập! Đợi...[/]")
                for _ in range(60):
                    time.sleep(2)
                    if "x.com/login" not in self.driver.current_url:
                        self.driver.get(self.GROK_IMAGINE_URL)
                        time.sleep(3)
                        break

            console.print("[cyan]3. Click đính kèm...[/]")
            for sel in ['//button[@aria-label="Đính kèm"]', '//button[@aria-label="Attach"]']:
                try:
                    self._wait(By.XPATH, sel, 5, True).click()
                    console.print("[green]✓[/]")
                    break
                except:
                    continue
            time.sleep(1)

            console.print("[cyan]4. Click tải lên...[/]")
            for sel in ['//div[@role="menuitem"][contains(., "Tải lên")]', '//div[@role="menuitem"][contains(., "Upload")]']:
                try:
                    self._wait(By.XPATH, sel, 3, True).click()
                    break
                except:
                    continue
            time.sleep(1)

            console.print(f"[cyan]5. Upload: {image_path.name}[/]")
            self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys(str(image_path))
            console.print("[green]✓[/]")
            time.sleep(3)

            if prompt:
                console.print("[cyan]6. Nhập prompt...[/]")
                self.driver.find_element(By.TAG_NAME, "textarea").send_keys(prompt)
            time.sleep(1)

            console.print("[cyan]7. Tạo video...[/]")
            self.driver.find_element(By.TAG_NAME, "textarea").send_keys(Keys.RETURN)
            console.print("[yellow]⏳ Đang tạo (1-5 phút)...[/]")

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

            console.print("[cyan]8. Tải video...[/]")
            for sel in ['//svg[contains(@class, "download")]/..', '//button[contains(@class, "download")]']:
                try:
                    self._wait(By.XPATH, sel, 5, True).click()
                    break
                except:
                    continue

            time.sleep(10)
            console.print("[green]✅ Xong! Video trong Downloads[/]")
            return GrokVideoResult(True, video_path="Downloads")

        except Exception as e:
            return GrokVideoResult(False, error=str(e))
        finally:
            self._cleanup()

    def _cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        if self.temp_profile_dir:
            try:
                shutil.rmtree(self.temp_profile_dir, ignore_errors=True)
            except:
                pass


def create_video_sync(
    image_path: str,
    prompt: str = "",
    output_path: str = "",
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    headless: bool = False,
) -> GrokVideoResult:
    return GrokBrowserAutomation(chrome_path, chrome_profile_path, headless).create_video(image_path, prompt, output_path)


def create_videos_batch_sync(
    tasks: List[dict],
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default",
    headless: bool = False,
) -> List[GrokVideoResult]:
    results = []
    for i, task in enumerate(tasks, 1):
        console.print(f"\n[bold]===== Video {i}/{len(tasks)} =====[/]")
        results.append(create_video_sync(task["image"], task.get("prompt", ""), task["output"], chrome_path, chrome_profile_path, headless))
        if i < len(tasks):
            time.sleep(5)
    return results


def is_chrome_debug_running(port=9222):
    return False

def start_chrome_debug(**kwargs):
    return True
