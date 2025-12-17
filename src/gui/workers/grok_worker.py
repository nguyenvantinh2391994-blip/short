"""
Grok Worker - Background worker for Grok video creation
Sử dụng Selenium để chạy ẩn (headless mode)
"""

import threading
from pathlib import Path
from typing import Callable, Optional, Dict, Any
import time


class GrokWorker:
    """Worker để tạo video Grok trong background"""

    def __init__(
        self,
        input_folder: str,
        output_folder: str,
        browser_profile: Optional[Dict],
        config: Any,
        stop_flag: threading.Event,
        on_progress: Callable[[int, int, str], None],
        on_log: Callable[[str, str], None],
        headless: bool = True  # Mặc định chạy ẩn
    ):
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.browser_profile = browser_profile
        self.config = config
        self.stop_flag = stop_flag
        self.on_progress = on_progress
        self.on_log = on_log
        self.headless = headless

    def log(self, message: str, status: str = "info"):
        """Log message"""
        if self.on_log:
            self.on_log(message, status)

    def progress(self, current: int, total: int, task: str = ""):
        """Update progress"""
        if self.on_progress:
            self.on_progress(current, total, task)

    def run(self):
        """Run the video creation process"""
        try:
            self.log("Bắt đầu quá trình tạo video Grok...", "progress")
            self.log(f"Chế độ ẩn: {'BẬT' if self.headless else 'TẮT'}", "info")

            # Import grok automation (Selenium version)
            from ...grok_selenium import GrokSeleniumAutomation, GrokVideoResult
            from ...sheets_reader import SheetsReader

            # Setup output folder
            self.output_folder.mkdir(parents=True, exist_ok=True)

            # Get browser settings
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            profile_path = ""

            if self.browser_profile:
                chrome_path = self.browser_profile.get("chrome_path", chrome_path)
                profile_path = self.browser_profile.get("profile_path", "")
                self.log(f"Sử dụng profile: {self.browser_profile.get('name')}", "info")

            # Connect to Google Sheets
            self.log("Kết nối Google Sheets...", "progress")

            reader = SheetsReader(
                credentials_file=self.config.credentials_file,
                spreadsheet_id=self.config.spreadsheet_id,
                sheet_name=self.config.sheet_name
            )

            if not reader.connect():
                self.log("Không thể kết nối Google Sheets!", "error")
                return

            if not reader.open_spreadsheet():
                self.log("Không thể mở spreadsheet!", "error")
                return

            self.log("Đã kết nối Google Sheets", "success")

            # Get pending products
            pending = reader.get_pending_products(
                status_column=self.config.status_column,
                prompt_column=self.config.prompt_column
            )

            if not pending:
                self.log("Không có sản phẩm nào cần làm video", "warning")
                return

            # Pre-scan existing videos
            self.log("Rà soát video đã có sẵn...", "progress")
            existing_count = 0
            still_pending = []

            for item in pending:
                if self.stop_flag.is_set():
                    self.log("Đã dừng theo yêu cầu", "warning")
                    return

                code = item["code"]
                row = item["row"]
                video_path = self.output_folder / f"{code}.mp4"

                if video_path.exists():
                    file_size = video_path.stat().st_size
                    if file_size > 100 * 1024:  # > 100KB
                        try:
                            with open(video_path, "rb") as f:
                                header = f.read(12)
                                if b"ftyp" in header:
                                    self.log(f"✓ {code} - video đã có ({file_size // 1024}KB)", "success")
                                    reader.update_status(row, "VIDEO", self.config.status_column)
                                    existing_count += 1
                                    continue
                        except:
                            pass

                still_pending.append(item)

            if existing_count > 0:
                self.log(f"Đã cập nhật {existing_count} video có sẵn", "success")

            if not still_pending:
                self.log("Tất cả video đã có sẵn!", "success")
                return

            self.log(f"Còn {len(still_pending)} video cần tạo", "info")

            # Create Selenium automation instance (hỗ trợ headless)
            automation = GrokSeleniumAutomation(
                chrome_path=chrome_path,
                profile_name=profile_path,  # profile_path giờ chứa tên profile (ví dụ "Profile 5")
                headless=self.headless,
                on_log=self.log
            )

            total = len(still_pending)

            # Tạo danh sách tasks
            tasks = []
            for item in still_pending:
                code = item["code"]

                # Find input image
                image_path = None
                for ext in [".jpg", ".jpeg", ".png", ".webp"]:
                    candidate = self.input_folder / f"{code}{ext}"
                    if candidate.exists():
                        image_path = candidate
                        break

                if not image_path:
                    self.log(f"Không tìm thấy ảnh cho mã {code}", "error")
                    continue

                tasks.append({
                    "code": code,
                    "row": item["row"],
                    "image": str(image_path),
                    "prompt": item.get("prompt", ""),
                    "output": str(self.output_folder / f"{code}.mp4")
                })

            # Chạy batch với Selenium
            for i, task in enumerate(tasks):
                if self.stop_flag.is_set():
                    self.log("Đã dừng theo yêu cầu", "warning")
                    break

                code = task["code"]
                row = task["row"]

                self.progress(i, total, f"Đang xử lý: {code}")
                self.log(f"[{i+1}/{total}] Mã: {code}", "progress")

                # Tạo video với Selenium
                result = automation.create_video(
                    image_path=task["image"],
                    prompt=task["prompt"],
                    output_path=task["output"],
                    product_code=code
                )

                if result.success:
                    reader.update_status(row, "VIDEO", self.config.status_column)
                    self.log(f"✓ Hoàn thành: {code}", "success")
                else:
                    self.log(f"✗ Thất bại: {code} - {result.error}", "error")

                # Mở tab mới cho video tiếp theo
                if i < len(tasks) - 1:
                    try:
                        automation.driver.execute_script("window.open('');")
                        automation.driver.switch_to.window(automation.driver.window_handles[-1])
                    except:
                        pass

            self.progress(total, total, "Hoàn thành")
            self.log(f"Hoàn thành xử lý {total} video!", "success")

            # Đóng browser
            automation.close_driver()

        except Exception as e:
            self.log(f"Lỗi: {str(e)}", "error")
            raise
