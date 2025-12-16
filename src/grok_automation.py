"""
Grok Browser Automation - Tự động tạo video trên grok.com/imagine
Sử dụng Playwright để điều khiển Chrome với profile đã đăng nhập
"""

import asyncio
import time
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
        chrome_profile_path: str = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data",
        profile_name: str = "Default",
        headless: bool = False,  # False để xem browser hoạt động
        slow_mo: int = 100,  # Delay giữa các actions (ms)
    ):
        self.chrome_profile_path = Path(chrome_profile_path)
        self.profile_name = profile_name
        self.headless = headless
        self.slow_mo = slow_mo

        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def init_browser(self) -> bool:
        """Khởi tạo browser với Chrome profile"""
        if not PLAYWRIGHT_AVAILABLE:
            console.print("[red]❌ Chưa cài Playwright. Chạy: pip install playwright && playwright install chromium[/]")
            return False

        try:
            self.playwright = await async_playwright().start()

            # Sử dụng Chrome profile đã đăng nhập
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.chrome_profile_path),
                channel="chrome",  # Sử dụng Chrome đã cài
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    f"--profile-directory={self.profile_name}",
                    "--disable-blink-features=AutomationControlled",
                ],
                viewport={"width": 1280, "height": 800},
            )

            # Lấy page đầu tiên hoặc tạo mới
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()

            console.print("[green]✅ Đã khởi tạo browser[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi khởi tạo browser: {e}[/]")
            return False

    async def close_browser(self):
        """Đóng browser"""
        if self.context:
            await self.context.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def navigate_to_grok(self) -> bool:
        """Truy cập trang grok.com/imagine"""
        try:
            await self.page.goto(self.GROK_IMAGINE_URL, wait_until="networkidle")
            await asyncio.sleep(2)  # Chờ page load hoàn toàn

            # Kiểm tra đã đăng nhập chưa
            current_url = self.page.url
            if "login" in current_url or "signin" in current_url:
                console.print("[yellow]⚠️ Cần đăng nhập vào Grok. Vui lòng đăng nhập thủ công...[/]")
                # Chờ user đăng nhập
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

            await asyncio.sleep(2)  # Chờ upload xong
            console.print(f"[green]✅ Đã upload ảnh: {image_path.name}[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi upload ảnh: {e}[/]")
            return False

    async def enter_prompt(self, prompt: str) -> bool:
        """Nhập prompt vào textarea"""
        if not prompt:
            return True  # Không có prompt thì bỏ qua

        try:
            # Tìm textarea
            textarea = await self.page.wait_for_selector(
                self.SELECTORS["prompt_input"],
                timeout=5000
            )

            # Clear và nhập prompt
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
            # Nhấn Enter để gửi
            await self.page.keyboard.press("Enter")
            console.print("[cyan]⏳ Đang tạo video... (có thể mất 1-3 phút)[/]")

            # Đợi nút "Làm lại" xuất hiện (dấu hiệu video xong)
            await self.page.wait_for_selector(
                self.SELECTORS["retry_button"],
                timeout=timeout * 1000  # Convert to ms
            )

            await asyncio.sleep(2)  # Chờ thêm để video load hoàn toàn
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

            # Tìm nút download
            download_btn = await self.page.wait_for_selector(
                self.SELECTORS["download_button"],
                timeout=10000
            )

            # Lắng nghe download event
            async with self.page.expect_download() as download_info:
                await download_btn.click()

            download = await download_info.value

            # Lưu file
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
        """
        Tạo video từ ảnh với Grok

        Args:
            image_path: Đường dẫn đến ảnh
            prompt: Prompt tùy chỉnh video (optional)
            output_path: Đường dẫn lưu video
            timeout: Thời gian chờ tối đa (giây)
        """
        try:
            # 1. Truy cập Grok
            if not await self.navigate_to_grok():
                return GrokVideoResult(success=False, error="Không thể truy cập Grok")

            # 2. Upload ảnh
            if not await self.upload_image(image_path):
                return GrokVideoResult(success=False, error="Không thể upload ảnh")

            # 3. Nhập prompt (nếu có)
            if prompt:
                if not await self.enter_prompt(prompt):
                    return GrokVideoResult(success=False, error="Không thể nhập prompt")

            # 4. Gửi và đợi
            if not await self.submit_and_wait(timeout):
                return GrokVideoResult(success=False, error="Timeout tạo video")

            # 5. Tải video
            if not await self.download_video(output_path):
                return GrokVideoResult(success=False, error="Không thể tải video")

            return GrokVideoResult(success=True, video_path=output_path)

        except Exception as e:
            return GrokVideoResult(success=False, error=str(e))

    async def create_video_batch(
        self,
        tasks: List[dict],  # [{"image": "path", "prompt": "...", "output": "path"}, ...]
        delay_between: int = 5,  # Delay giữa các video (giây)
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


# Synchronous wrapper cho CLI
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
    # Test
    result = create_video_sync(
        image_path="products/SP001/1.jpg",
        prompt="Tạo video quảng cáo sản phẩm thời trang",
        output_path="outputs/test_video.mp4"
    )
    print(f"Result: {result}")
