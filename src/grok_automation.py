"""
Grok Browser Automation - Kết nối Chrome qua CDP
Không cần đóng Chrome đang mở!
"""

import asyncio
import subprocess
import time
import socket
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from rich.console import Console

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

console = Console()

# Port mặc định cho Chrome debug
DEBUG_PORT = 9222


@dataclass
class GrokVideoResult:
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


def is_chrome_debug_running(port: int = DEBUG_PORT) -> bool:
    """Kiểm tra Chrome debug đang chạy không"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
    except:
        return False


def kill_chrome():
    """Đóng tất cả Chrome đang chạy"""
    import platform
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/IM", "chrome.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10
            )
        else:
            subprocess.run(
                ["pkill", "-f", "chrome"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10
            )
        time.sleep(2)
    except:
        pass


def find_chrome_path() -> str:
    """Tìm đường dẫn Chrome"""
    import platform
    import os

    if platform.system() == "Windows":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in paths:
            if Path(p).exists():
                return p
    return "chrome"


def start_chrome_debug(
    chrome_path: str = None,
    profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
    profile_name: str = "Default",
    port: int = DEBUG_PORT,
    auto_kill: bool = True
) -> bool:
    """Mở Chrome với debug port"""
    if is_chrome_debug_running(port):
        console.print(f"[green]✅ Chrome debug đã chạy trên port {port}[/]")
        return True

    # Tìm Chrome
    if not chrome_path:
        chrome_path = find_chrome_path()

    console.print(f"[cyan]Chrome: {chrome_path}[/]")
    console.print(f"[cyan]Profile: {profile_path}[/]")

    # Đóng Chrome cũ nếu cần
    if auto_kill:
        console.print("[dim]Đóng Chrome cũ...[/]")
        kill_chrome()

    try:
        # Mở Chrome với debug port
        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_path}",
            f"--profile-directory={profile_name}",
            "https://grok.com/imagine"
        ]

        console.print(f"[dim]Đang chạy: {' '.join(cmd[:2])}...[/]")

        # Không ẩn window để debug
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Đợi Chrome khởi động
        console.print("[cyan]Đợi Chrome mở (tối đa 30s)...[/]")
        for i in range(30):
            time.sleep(1)
            console.print(f"[dim]...{i+1}s[/]", end=" ")
            if is_chrome_debug_running(port):
                console.print(f"\n[green]✅ Chrome đã mở trên port {port}![/]")
                time.sleep(3)  # Đợi trang load
                return True

        # Kiểm tra lỗi
        if process.poll() is not None:
            _, stderr = process.communicate()
            if stderr:
                console.print(f"\n[red]Lỗi Chrome: {stderr.decode()[:200]}[/]")

        console.print("\n[red]❌ Chrome không mở được![/]")
        return False

    except FileNotFoundError:
        console.print(f"[red]❌ Không tìm thấy Chrome tại: {chrome_path}[/]")
        console.print("[yellow]Hãy kiểm tra Chrome đã cài đặt chưa[/]")
        return False
    except Exception as e:
        console.print(f"[red]❌ Lỗi: {e}[/]")
        return False


class GrokBrowserAutomation:
    GROK_IMAGINE_URL = "https://grok.com/imagine"

    def __init__(self, debug_port: int = DEBUG_PORT):
        self.debug_port = debug_port
        self.browser = None
        self.page = None

    async def connect(self) -> bool:
        """Kết nối vào Chrome đang chạy"""
        if not PLAYWRIGHT_AVAILABLE:
            console.print("[red]❌ Chưa cài Playwright. Chạy: pip install playwright && playwright install chromium[/]")
            return False

        if not is_chrome_debug_running(self.debug_port):
            console.print(f"[red]❌ Chrome debug chưa chạy![/]")
            console.print(f"[yellow]Chạy lệnh: run.bat start-chrome[/]")
            return False

        try:
            console.print(f"[cyan]Đang kết nối Chrome (port {self.debug_port})...[/]")

            self.playwright = await async_playwright().start()

            # Kết nối vào Chrome qua CDP
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{self.debug_port}"
            )

            # Lấy context và page
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                pages = self.context.pages

                # Tìm tab Grok hoặc dùng tab đầu tiên
                self.page = None
                for p in pages:
                    if "grok.com" in p.url:
                        self.page = p
                        break

                if not self.page and pages:
                    self.page = pages[0]

            if not self.page:
                self.page = await self.context.new_page()

            console.print("[green]✅ Đã kết nối Chrome![/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi kết nối: {e}[/]")
            return False

    async def disconnect(self):
        """Ngắt kết nối (không đóng Chrome)"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def create_video(
        self,
        image_path: str,
        prompt: str = "",
        output_path: str = "outputs/video.mp4",
    ) -> GrokVideoResult:
        """Tạo video từ ảnh"""

        image_path = Path(image_path).absolute()
        if not image_path.exists():
            return GrokVideoResult(success=False, error=f"Không tìm thấy: {image_path}")

        try:
            # 1. Vào trang Grok Imagine nếu chưa
            current_url = self.page.url
            if "grok.com/imagine" not in current_url:
                console.print("[cyan]Đang vào Grok Imagine...[/]")
                await self.page.goto(self.GROK_IMAGINE_URL, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(2)

            # 2. Click nút đính kèm (thử nhiều selector)
            console.print("[cyan]Click nút đính kèm...[/]")
            attach_selectors = [
                'button[aria-label="Đính kèm"]',
                'button[aria-label="Attach"]',
                'button:has(svg.lucide-paperclip)',
                '[data-testid="attach-button"]',
            ]

            clicked = False
            for selector in attach_selectors:
                try:
                    btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if btn:
                        await btn.click()
                        clicked = True
                        break
                except:
                    continue

            if not clicked:
                return GrokVideoResult(success=False, error="Không tìm thấy nút đính kèm")

            await asyncio.sleep(0.5)

            # 3. Click "Tải lên một tệp" và upload
            console.print(f"[cyan]Upload ảnh: {image_path.name}[/]")
            upload_selectors = [
                'div[role="menuitem"]:has-text("Tải lên một tệp")',
                'div[role="menuitem"]:has-text("Upload a file")',
                '[data-testid="upload-file"]',
            ]

            async with self.page.expect_file_chooser() as fc_info:
                for selector in upload_selectors:
                    try:
                        item = await self.page.wait_for_selector(selector, timeout=2000)
                        if item:
                            await item.click()
                            break
                    except:
                        continue

            file_chooser = await fc_info.value
            await file_chooser.set_files(str(image_path))
            await asyncio.sleep(2)

            # 4. Nhập prompt nếu có
            if prompt:
                console.print(f"[cyan]Nhập prompt: {prompt[:50]}...[/]")
                textarea_selectors = [
                    'textarea[placeholder*="Nhập để tùy chỉnh"]',
                    'textarea[placeholder*="Enter to customize"]',
                    'textarea',
                ]
                for selector in textarea_selectors:
                    try:
                        textarea = await self.page.wait_for_selector(selector, timeout=2000)
                        if textarea:
                            await textarea.fill(prompt)
                            break
                    except:
                        continue
                await asyncio.sleep(0.5)

            # 5. Nhấn Enter để tạo video
            console.print("[cyan]Đang tạo video... (chờ 1-3 phút)[/]")
            await self.page.keyboard.press("Enter")

            # 6. Đợi video xong (nút "Làm lại" xuất hiện)
            done_selectors = [
                'button:has-text("Làm lại")',
                'button:has-text("Redo")',
                'button:has-text("Regenerate")',
            ]

            for selector in done_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=300000)
                    break
                except:
                    continue

            console.print("[green]✅ Video đã tạo xong![/]")
            await asyncio.sleep(2)

            # 7. Download video
            console.print("[cyan]Đang tải video...[/]")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            download_selectors = [
                'svg.lucide-download',
                'button:has(svg.lucide-download)',
                '[data-testid="download-button"]',
            ]

            async with self.page.expect_download() as download_info:
                for selector in download_selectors:
                    try:
                        btn = await self.page.wait_for_selector(selector, timeout=3000)
                        if btn:
                            await btn.click()
                            break
                    except:
                        continue

            download = await download_info.value
            await download.save_as(output_path)

            console.print(f"[green]✅ Đã lưu: {output_path}[/]")
            return GrokVideoResult(success=True, video_path=output_path)

        except Exception as e:
            return GrokVideoResult(success=False, error=str(e))


def create_video_sync(
    image_path: str,
    prompt: str = "",
    output_path: str = "outputs/video.mp4",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
    profile_name: str = "Default",
    headless: bool = False,  # Không dùng nhưng giữ để tương thích
) -> GrokVideoResult:
    """Tạo video - gọi từ CLI"""

    async def _run():
        # Mở Chrome nếu chưa chạy
        if not is_chrome_debug_running():
            if not start_chrome_debug(profile_path=chrome_profile_path, profile_name=profile_name):
                return GrokVideoResult(success=False, error="Không thể mở Chrome")

        auto = GrokBrowserAutomation()

        if not await auto.connect():
            return GrokVideoResult(success=False, error="Không thể kết nối Chrome")

        try:
            return await auto.create_video(image_path, prompt, output_path)
        finally:
            await auto.disconnect()

    return asyncio.run(_run())


def create_videos_batch_sync(
    tasks: List[dict],
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
    profile_name: str = "Default",
    headless: bool = False,
) -> List[GrokVideoResult]:
    """Tạo nhiều video"""

    async def _run():
        # Mở Chrome nếu chưa chạy
        if not is_chrome_debug_running():
            if not start_chrome_debug(profile_path=chrome_profile_path, profile_name=profile_name):
                return [GrokVideoResult(success=False, error="Không thể mở Chrome")]

        auto = GrokBrowserAutomation()

        if not await auto.connect():
            return [GrokVideoResult(success=False, error="Không thể kết nối Chrome")]

        results = []
        try:
            for i, task in enumerate(tasks, 1):
                console.print(f"\n[bold]({i}/{len(tasks)})[/]")
                result = await auto.create_video(
                    task["image"],
                    task.get("prompt", ""),
                    task["output"]
                )
                results.append(result)

                if i < len(tasks):
                    await asyncio.sleep(3)
        finally:
            await auto.disconnect()

        return results

    return asyncio.run(_run())
