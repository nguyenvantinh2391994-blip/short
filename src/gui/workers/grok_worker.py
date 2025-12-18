"""
Grok Worker - Background worker for Grok video creation
Workflow mới: Thư mục con theo mã → Tạo video từ ảnh → Ghép + nhạc + voice → Done
"""

import threading
import os
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List
import time


class GrokWorker:
    """Worker để tạo video Grok trong background"""

    def __init__(
        self,
        input_folder: str,
        output_folder: str,
        music_folder: str = "",
        voice_folder: str = "",
        transition_type: str = "fade_black",
        browser_profile: Optional[Dict] = None,
        config: Any = None,
        stop_flag: threading.Event = None,
        on_progress: Callable[[int, int, str], None] = None,
        on_log: Callable[[str, str], None] = None,
        headless: bool = True,
        on_automation_created: Optional[Callable] = None
    ):
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)  # Thư mục done
        self.music_folder = Path(music_folder) if music_folder else None
        self.voice_folder = Path(voice_folder) if voice_folder else None
        self.transition_type = transition_type
        self.browser_profile = browser_profile
        self.config = config
        self.stop_flag = stop_flag or threading.Event()
        self.on_progress = on_progress
        self.on_log = on_log
        self.headless = headless
        self.on_automation_created = on_automation_created

        # Thư mục tạm để lưu video từ Grok (trước khi ghép)
        self.temp_folder = self.output_folder / "_temp_videos"

    def log(self, message: str, status: str = "info"):
        """Log message"""
        if self.on_log:
            self.on_log(message, status)

    def progress(self, current: int, total: int, task: str = ""):
        """Update progress"""
        if self.on_progress:
            self.on_progress(current, total, task)

    def get_images_in_folder(self, folder: Path) -> List[Path]:
        """Lấy danh sách ảnh trong thư mục"""
        images = []
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            images.extend(folder.glob(f"*{ext}"))
            images.extend(folder.glob(f"*{ext.upper()}"))
        return sorted(images)

    def run(self):
        """Run the video creation process"""
        try:
            self.log("Bắt đầu quá trình tạo video Grok...", "progress")
            self.log(f"Chế độ ẩn: {'BẬT' if self.headless else 'TẮT'}", "info")

            # Import modules
            from ...grok_selenium import GrokSeleniumAutomation, GrokVideoResult
            from ...sheets_reader import SheetsReader
            from ...video_merger import VideoMerger, get_music_for_index, get_voice_for_code

            # Setup folders
            self.output_folder.mkdir(parents=True, exist_ok=True)
            self.temp_folder.mkdir(parents=True, exist_ok=True)

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

            # Get pending products (status != EDIT XONG)
            pending = reader.get_pending_products(
                status_column=self.config.status_column,
                prompt_column=self.config.prompt_column
            )

            if not pending:
                self.log("Không có sản phẩm nào cần làm video", "warning")
                return

            self.log(f"Tìm thấy {len(pending)} mã cần xử lý", "info")

            # Kiểm tra thư mục con tương ứng với mã
            valid_items = []
            for item in pending:
                code = item["code"]
                code_folder = self.input_folder / code

                if code_folder.exists() and code_folder.is_dir():
                    images = self.get_images_in_folder(code_folder)
                    if images:
                        item["folder"] = code_folder
                        item["images"] = images
                        valid_items.append(item)
                        self.log(f"  📁 {code}: {len(images)} ảnh", "info")
                    else:
                        self.log(f"  ⚠️ {code}: Thư mục rỗng, bỏ qua", "warning")
                else:
                    self.log(f"  ⚠️ {code}: Không tìm thấy thư mục, bỏ qua", "warning")

            if not valid_items:
                self.log("Không có mã nào có thư mục ảnh hợp lệ!", "error")
                return

            self.log(f"Sẽ xử lý {len(valid_items)} mã", "info")

            # Pre-check: Bỏ qua các mã đã có video hoàn chỉnh
            still_pending = []
            for item in valid_items:
                code = item["code"]
                final_video = self.output_folder / f"{code}.mp4"

                if final_video.exists():
                    file_size = final_video.stat().st_size
                    if file_size > 100 * 1024:  # > 100KB
                        try:
                            with open(final_video, "rb") as f:
                                header = f.read(12)
                                if b"ftyp" in header:
                                    self.log(f"✓ {code} - video đã có ({file_size // 1024}KB)", "success")
                                    reader.update_status(item["row"], "EDIT XONG", self.config.status_column)
                                    continue
                        except:
                            pass

                still_pending.append(item)

            if not still_pending:
                self.log("Tất cả video đã hoàn thành!", "success")
                return

            total = len(still_pending)
            self.log(f"Còn {total} mã cần xử lý", "info")

            # Create Selenium automation
            automation = GrokSeleniumAutomation(
                chrome_path=chrome_path,
                profile_path=profile_path,
                headless=self.headless,
                on_log=self.log
            )

            # Callback để GUI có thể ẩn/hiện browser
            if self.on_automation_created:
                self.on_automation_created(automation)

            # Create video merger
            merger = VideoMerger(
                transition_type=self.transition_type,
                transition_duration=0.5,
                on_log=self.log
            )

            music_index = 0  # Đếm để lấy nhạc lần lượt

            # Xử lý từng mã
            for i, item in enumerate(still_pending):
                if self.stop_flag.is_set():
                    self.log("Đã dừng theo yêu cầu", "warning")
                    break

                code = item["code"]
                row = item["row"]
                images = item["images"]

                self.progress(i, total, f"Đang xử lý: {code}")
                self.log(f"\n{'='*40}", "info")
                self.log(f"[{i+1}/{total}] Mã: {code} ({len(images)} ảnh)", "progress")

                # Thư mục tạm cho mã này
                code_temp_folder = self.temp_folder / code
                code_temp_folder.mkdir(parents=True, exist_ok=True)

                # ===== BƯỚC 1: Tạo video từ mỗi ảnh =====
                self.log(f"Bước 1: Tạo {len(images)} video từ ảnh...", "progress")

                created_videos = []

                for j, image_path in enumerate(images):
                    if self.stop_flag.is_set():
                        break

                    video_name = f"{code}_{j+1:02d}.mp4"
                    video_path = code_temp_folder / video_name

                    # Bỏ qua nếu đã có
                    if video_path.exists() and video_path.stat().st_size > 50000:
                        self.log(f"  [{j+1}/{len(images)}] Đã có: {video_name}", "success")
                        created_videos.append(str(video_path))
                        continue

                    self.log(f"  [{j+1}/{len(images)}] Tạo video từ: {image_path.name}", "progress")

                    result = automation.create_video(
                        image_path=str(image_path),
                        prompt=item.get("prompt", ""),
                        output_path=str(video_path),
                        product_code=code,
                        skip_navigate=(j > 0)  # Skip navigate cho ảnh 2 trở đi
                    )

                    if result.success:
                        created_videos.append(str(video_path))
                        self.log(f"  ✓ Tạo xong: {video_name}", "success")
                    else:
                        self.log(f"  ✗ Thất bại: {result.error}", "error")

                    # Navigate về Grok cho ảnh tiếp theo
                    if j < len(images) - 1 and result.success:
                        automation.driver.execute_script(
                            f"window.location.href = 'https://grok.com/imagine';"
                        )
                        time.sleep(3)
                        automation.install_video_hook()

                if not created_videos:
                    self.log(f"✗ Không tạo được video nào cho {code}", "error")
                    continue

                # ===== BƯỚC 2: Ghép video + nhạc + voice =====
                self.log(f"Bước 2: Ghép {len(created_videos)} video...", "progress")

                # Lấy nhạc (lần lượt)
                music_path = None
                if self.music_folder and self.music_folder.exists():
                    music_path = get_music_for_index(str(self.music_folder), music_index)
                    if music_path:
                        self.log(f"  🎵 Nhạc: {Path(music_path).name}", "info")
                    music_index += 1

                # Lấy voice (theo mã)
                voice_path = None
                if self.voice_folder and self.voice_folder.exists():
                    voice_path = get_voice_for_code(str(self.voice_folder), code)
                    if voice_path:
                        self.log(f"  🎤 Voice: {Path(voice_path).name}", "info")

                # Đường dẫn output
                final_video = self.output_folder / f"{code}.mp4"

                # Ghép video
                success = merger.merge_videos(
                    video_paths=created_videos,
                    output_path=str(final_video),
                    music_path=music_path,
                    voice_path=voice_path,
                    music_volume=0.3,
                    voice_volume=1.0
                )

                if success:
                    # Cập nhật status = EDIT XONG
                    reader.update_status(row, "EDIT XONG", self.config.status_column)
                    self.log(f"✓ Hoàn thành: {code} → {final_video.name}", "success")
                else:
                    self.log(f"✗ Lỗi ghép video cho {code}", "error")

            # Hoàn thành
            self.progress(total, total, "Hoàn thành")
            self.log(f"\n{'='*40}", "info")
            self.log(f"Hoàn thành xử lý {total} mã!", "success")

            # Đóng browser
            automation.close_driver()

        except Exception as e:
            self.log(f"Lỗi: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            raise
