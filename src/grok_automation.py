"""
Grok Browser Automation - Đơn giản hóa
Mở Chrome với profile và thao tác
"""

import asyncio
import time
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


@dataclass
class GrokVideoResult:
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


class GrokBrowserAutomation:
    GROK_IMAGINE_URL = "https://grok.com/imagine/"

    def __init__(
        self,
        chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
        profile_name: str = "Default",
    ):
        self.chrome_profile_path = chrome_profile_path
        self.profile_name = profile_name
        self.browser = None
        self.page = None

    async def start(self) -> bool:
        """Mở Chrome với profile"""
        if not PLAYWRIGHT_AVAILABLE:
            console.print("[red]❌ Chưa cài Playwright. Chạy: pip install playwright && playwright install chromium[/]")
            return False

        try:
            console.print("[cyan]Đang mở Chrome...[/]")

            self.playwright = await async_playwright().start()

            # Mở Chrome với profile
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.chrome_profile_path,
                channel="chrome",
                headless=False,
                args=[f"--profile-directory={self.profile_name}"],
            )

            # Lấy hoặc tạo page
            if self.browser.pages:
                self.page = self.browser.pages[0]
            else:
                self.page = await self.browser.new_page()

            console.print("[green]✅ Chrome đã mở[/]")
            return True

        except Exception as e:
            error_msg = str(e)
            if "Target page, context or browser has been closed" in error_msg:
                console.print("[red]❌ Chrome đang mở. Đóng Chrome rồi chạy lại![/]")
            else:
                console.print(f"[red]❌ Lỗi: {e}[/]")
            return False

    async def stop(self):
        """Đóng browser"""
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
            # 1. Vào trang Grok Imagine
            console.print("[cyan]Đang vào Grok Imagine...[/]")
            await self.page.goto(self.GROK_IMAGINE_URL, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(2)

            # 2. Click nút đính kèm
            console.print("[cyan]Click nút đính kèm...[/]")
            await self.page.click('button[aria-label="Đính kèm"]')
            await asyncio.sleep(0.5)

            # 3. Click "Tải lên một tệp" và upload
            console.print(f"[cyan]Upload ảnh: {image_path.name}[/]")
            async with self.page.expect_file_chooser() as fc_info:
                await self.page.click('div[role="menuitem"]:has-text("Tải lên một tệp")')

            file_chooser = await fc_info.value
            await file_chooser.set_files(str(image_path))
            await asyncio.sleep(2)

            # 4. Nhập prompt nếu có
            if prompt:
                console.print(f"[cyan]Nhập prompt: {prompt[:50]}...[/]")
                await self.page.fill('textarea[placeholder*="Nhập để tùy chỉnh"]', prompt)
                await asyncio.sleep(0.5)

            # 5. Nhấn Enter để tạo video
            console.print("[cyan]Đang tạo video... (chờ 1-3 phút)[/]")
            await self.page.keyboard.press("Enter")

            # 6. Đợi nút "Làm lại" xuất hiện
            await self.page.wait_for_selector('button:has-text("Làm lại")', timeout=300000)
            console.print("[green]✅ Video đã tạo xong![/]")
            await asyncio.sleep(2)

            # 7. Download video
            console.print("[cyan]Đang tải video...[/]")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            async with self.page.expect_download() as download_info:
                await self.page.click('svg.lucide-download')

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
    headless: bool = False,
) -> GrokVideoResult:
    """Tạo video - gọi từ CLI"""

    async def _run():
        auto = GrokBrowserAutomation(chrome_profile_path, profile_name)

        if not await auto.start():
            return GrokVideoResult(success=False, error="Không thể mở Chrome")

        try:
            return await auto.create_video(image_path, prompt, output_path)
        finally:
            await auto.stop()

    return asyncio.run(_run())


def create_videos_batch_sync(
    tasks: List[dict],
    chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
    profile_name: str = "Default",
    headless: bool = False,
) -> List[GrokVideoResult]:
    """Tạo nhiều video"""

    async def _run():
        auto = GrokBrowserAutomation(chrome_profile_path, profile_name)

        if not await auto.start():
            return [GrokVideoResult(success=False, error="Không thể mở Chrome")]

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
            await auto.stop()

        return results

    return asyncio.run(_run())
