"""
Grok Browser Automation - Tự động tạo video trên grok.com/imagine
Sử dụng Playwright để điều khiển Chrome với profile đã đăng nhập
"""

import asyncio
import subprocess
import time
import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

console = Console()


@dataclass
class GrokVideoResult:
    """Kết quả tạo video"""
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


class GrokBrowserAutomation:
    """Tự động tạo video trên grok.com/imagine bằng browser"""

    GROK_IMAGINE_URL = "https://grok.com/imagine/"
    DEBUG_PORT = 9222

    # Selectors
    SELECTORS = {
        # Nút đính kèm (attach button)
        "attach_button": 'button[aria-label="Đính kèm"]',

        # Menu item "Tải lên một tệp"
        "upload_file_option": 'div[role="menuitem"]:has-text("Tải lên một tệp")',

        # Textarea nhập prompt
        "prompt_input": 'textarea[placeholder*="Nhập để tùy chỉnh"]',

        # Nút "Làm lại" - dấu hiệu video đã xong
        "retry_button": 'button:has-text("Làm lại")',

        # Nút download
        "download_button": 'svg.lucide-download',

        # Alternative selectors
        "attach_button_alt": 'button:has(svg path[d*="M10 9V15"])',
        "prompt_input_alt": 'textarea[aria-label="Tạo video"]',
    }

    def __init__(
        self,
        chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
        profile_name: str = "Default",
        headless: bool = False,
        slow_mo: int = 100,
    ):
        self.chrome_path = chrome_path
        self.chrome_profile_path = Path(chrome_profile_path)
        self.profile_name = profile_name
        self.headless = headless
        self.slow_mo = slow_mo

        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.chrome_process = None

    def _is_chrome_running_debug(self) -> bool:
        """Kiểm tra Chrome có đang chạy với debug port không"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', self.DEBUG_PORT))
        sock.close()
        return result == 0

    def _kill_chrome(self) -> None:
        """Đóng tất cả Chrome processes"""
        console.print("[yellow]Đang đóng Chrome cũ...[/]")
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'],
                             capture_output=True, timeout=10)
            else:  # Linux/Mac
                subprocess.run(['pkill', '-f', 'chrome'],
                             capture_output=True, timeout=10)
            time.sleep(2)  # Chờ Chrome đóng hoàn toàn
            console.print("[green]✅ Đã đóng Chrome cũ[/]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Không thể đóng Chrome: {e}[/]")

    def _start_chrome_debug(self, auto_kill: bool = True) -> bool:
        """Khởi động Chrome với remote debugging"""
        if self._is_chrome_running_debug():
            console.print("[green]✅ Chrome debug mode đã sẵn sàng[/]")
            return True

        # Nếu Chrome đang chạy nhưng không có debug port, đóng nó
        if auto_kill:
            self._kill_chrome()

        console.print("[cyan]Đang khởi động Chrome với debug mode...[/]")

        cmd = [
            self.chrome_path,
            f"--remote-debugging-port={self.DEBUG_PORT}",
            f"--user-data-dir={self.chrome_profile_path}",
            f"--profile-directory={self.profile_name}",
            "about:blank",
        ]

        console.print(f"[dim]Profile: {self.profile_name}[/]")

        try:
            # Khởi động Chrome như process riêng
            self.chrome_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            console.print(f"[dim]Chrome PID: {self.chrome_process.pid}[/]")

            # Chờ Chrome khởi động
            for i in range(15):  # Chờ tối đa 15 giây
                if self._is_chrome_running_debug():
                    console.print("[green]✅ Chrome đã khởi động với debug port[/]")
                    time.sleep(1)  # Chờ thêm chút để Chrome ổn định
                    return True
                console.print(f"[dim]Đang chờ Chrome... ({i+1}/15)[/]")
                time.sleep(1)

            console.print("[red]❌ Timeout khởi động Chrome[/]")
            console.print("[yellow]Thử đóng Chrome thủ công và chạy lại[/]")
            return False

        except Exception as e:
            console.print(f"[red]❌ Lỗi khởi động Chrome: {e}[/]")
            return False

    async def init_browser(self) -> bool:
        """Khởi tạo browser bằng cách connect đến Chrome đang chạy"""
        if not PLAYWRIGHT_AVAILABLE:
            console.print("[red]❌ Chưa cài Playwright. Chạy: pip install playwright && playwright install chromium[/]")
            return False

        # Khởi động Chrome với debug mode nếu chưa chạy
        if not self._start_chrome_debug():
            return False

        try:
            self.playwright = await async_playwright().start()

            # Connect đến Chrome đang chạy
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{self.DEBUG_PORT}"
            )

            # Lấy context và page
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                if self.context.pages:
                    self.page = self.context.pages[0]
                else:
                    self.page = await self.context.new_page()
            else:
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()

            console.print("[green]✅ Đã kết nối đến Chrome[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi kết nối browser: {e}[/]")
            return False

    async def close_browser(self):
        """Đóng kết nối (không đóng Chrome)"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def navigate_to_grok(self) -> bool:
        """Truy cập trang grok.com/imagine"""
        try:
            await self.page.goto(self.GROK_IMAGINE_URL, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)

            # Kiểm tra đã đăng nhập chưa
            current_url = self.page.url
            if "login" in current_url or "signin" in current_url:
                console.print("[yellow]⚠️ Cần đăng nhập vào Grok. Vui lòng đăng nhập thủ công trong Chrome...[/]")
                await self.page.wait_for_url("**/imagine/**", timeout=120000)

            console.print("[green]✅ Đã vào trang Grok Imagine[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi truy cập Grok: {e}[/]")
            return False

    async def upload_image(self, image_path: str) -> bool:
        """Upload ảnh lên Grok"""
        image_path = Path(image_path)
        if not image_path.exists():
            console.print(f"[red]❌ Không tìm thấy ảnh: {image_path}[/]")
            return False

        try:
            # Click nút đính kèm
            attach_btn = await self.page.wait_for_selector(
                self.SELECTORS["attach_button"],
                timeout=10000
            )
            await attach_btn.click()
            await asyncio.sleep(0.5)

            # Click "Tải lên một tệp"
            upload_option = await self.page.wait_for_selector(
                self.SELECTORS["upload_file_option"],
                timeout=5000
            )

            # Lắng nghe file chooser trước khi click
            async with self.page.expect_file_chooser() as fc_info:
                await upload_option.click()

            file_chooser = await fc_info.value
            await file_chooser.set_files(str(image_path.absolute()))

            await asyncio.sleep(2)
            console.print(f"[green]✅ Đã upload ảnh: {image_path.name}[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi upload ảnh: {e}[/]")
            return False

    async def enter_prompt(self, prompt: str) -> bool:
        """Nhập prompt vào textarea"""
        if not prompt:
            return True

        try:
            textarea = await self.page.wait_for_selector(
                self.SELECTORS["prompt_input"],
                timeout=5000
            )
            await textarea.fill(prompt)
            await asyncio.sleep(0.5)
            console.print(f"[green]✅ Đã nhập prompt[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi nhập prompt: {e}[/]")
            return False

    async def submit_and_wait(self, timeout: int = 300) -> bool:
        """Gửi request và đợi video hoàn thành"""
        try:
            await self.page.keyboard.press("Enter")
            console.print("[cyan]⏳ Đang tạo video... (có thể mất 1-3 phút)[/]")

            await self.page.wait_for_selector(
                self.SELECTORS["retry_button"],
                timeout=timeout * 1000
            )

            await asyncio.sleep(2)
            console.print("[green]✅ Video đã được tạo xong![/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Timeout hoặc lỗi tạo video: {e}[/]")
            return False

    async def download_video(self, output_path: str) -> bool:
        """Tải video về"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            download_btn = await self.page.wait_for_selector(
                self.SELECTORS["download_button"],
                timeout=10000
            )

            async with self.page.expect_download() as download_info:
                await download_btn.click()

            download = await download_info.value
            await download.save_as(str(output_path))

            console.print(f"[green]✅ Đã tải video: {output_path}[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi tải video: {e}[/]")
            return False

    async def create_video(
        self,
        image_path: str,
        prompt: str = "",
        output_path: str = "outputs/video.mp4",
        timeout: int = 300
    ) -> GrokVideoResult:
        """Tạo video từ ảnh với Grok"""
        try:
            if not await self.navigate_to_grok():
                return GrokVideoResult(success=False, error="Không thể truy cập Grok")

            if not await self.upload_image(image_path):
                return GrokVideoResult(success=False, error="Không thể upload ảnh")

            if prompt:
                if not await self.enter_prompt(prompt):
                    return GrokVideoResult(success=False, error="Không thể nhập prompt")

            if not await self.submit_and_wait(timeout):
                return GrokVideoResult(success=False, error="Timeout tạo video")

            if not await self.download_video(output_path):
                return GrokVideoResult(success=False, error="Không thể tải video")

            return GrokVideoResult(success=True, video_path=output_path)

        except Exception as e:
            return GrokVideoResult(success=False, error=str(e))

    async def create_video_batch(
        self,
        tasks: List[dict],
        delay_between: int = 5,
    ) -> List[GrokVideoResult]:
        """Tạo nhiều video hàng loạt"""
        results = []

        for i, task in enumerate(tasks, 1):
            console.print(f"\n[bold]({i}/{len(tasks)}) Đang xử lý...[/]")

            result = await self.create_video(
                image_path=task["image"],
                prompt=task.get("prompt", ""),
                output_path=task["output"]
            )
            results.append(result)

            if i < len(tasks):
                console.print(f"[dim]Chờ {delay_between}s trước video tiếp theo...[/]")
                await asyncio.sleep(delay_between)

        return results


def create_video_sync(
    image_path: str,
    prompt: str = "",
    output_path: str = "outputs/video.mp4",
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
    profile_name: str = "Default",
    headless: bool = False,
) -> GrokVideoResult:
    """Wrapper đồng bộ để gọi từ CLI"""

    async def _run():
        automation = GrokBrowserAutomation(
            chrome_profile_path=chrome_profile_path,
            profile_name=profile_name,
            headless=headless,
        )

        try:
            if not await automation.init_browser():
                return GrokVideoResult(success=False, error="Không thể khởi tạo browser")

            result = await automation.create_video(
                image_path=image_path,
                prompt=prompt,
                output_path=output_path
            )
            return result
        finally:
            await automation.close_browser()

    return asyncio.run(_run())


def create_videos_batch_sync(
    tasks: List[dict],
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
    profile_name: str = "Default",
    headless: bool = False,
) -> List[GrokVideoResult]:
    """Tạo nhiều video - wrapper đồng bộ"""

    async def _run():
        automation = GrokBrowserAutomation(
            chrome_profile_path=chrome_profile_path,
            profile_name=profile_name,
            headless=headless,
        )

        try:
            if not await automation.init_browser():
                return [GrokVideoResult(success=False, error="Không thể khởi tạo browser")]

            results = await automation.create_video_batch(tasks)
            return results
        finally:
            await automation.close_browser()

    return asyncio.run(_run())


if __name__ == "__main__":
    result = create_video_sync(
        image_path="products/SP001/1.jpg",
        prompt="Tạo video quảng cáo sản phẩm thời trang",
        output_path="outputs/test_video.mp4"
    )
    print(f"Result: {result}")
