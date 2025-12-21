"""
Grok Worker - Background worker for Grok video creation
Workflow: Thư mục con theo mã → Tạo video từ ảnh → Ghép + nhạc + voice → Done
Hỗ trợ chạy song song với nhiều profile
"""

import threading
import os
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List
from queue import Queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class GrokWorker:
    """Worker để tạo video Grok trong background - hỗ trợ song song"""

    def __init__(
        self,
        input_folder: str,
        output_folder: str,
        music_folder: str = "",
        voice_folder: str = "",
        transition_type: str = "fade_black",
        browser_profile: Optional[Dict] = None,  # Single profile (backwards compat)
        browser_profiles: Optional[List[Dict]] = None,  # Multiple profiles for parallel
        config: Any = None,
        stop_flag: threading.Event = None,
        on_progress: Callable[[int, int, str], None] = None,
        on_log: Callable[[str, str], None] = None,
        headless: bool = True,
        on_automation_created: Optional[Callable] = None
    ):
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.music_folder = Path(music_folder) if music_folder else None
        self.voice_folder = Path(voice_folder) if voice_folder else None
        self.transition_type = transition_type

        # Hỗ trợ cả single profile và multiple profiles
        if browser_profiles:
            self.browser_profiles = browser_profiles
        elif browser_profile:
            self.browser_profiles = [browser_profile]
        else:
            self.browser_profiles = []

        self.config = config
        self.stop_flag = stop_flag or threading.Event()
        self.on_progress = on_progress
        self.on_log = on_log
        self.headless = headless
        self.on_automation_created = on_automation_created

        # Thư mục tạm
        self.temp_folder = self.output_folder / "_temp_videos"

        # Thread-safe counters
        self._completed_count = 0
        self._total_count = 0
        self._lock = threading.Lock()
        self._music_index = 0

        # Lưu tất cả automation instances để có thể ẩn/hiện
        self._automations = []
        self._automations_lock = threading.Lock()

    def log(self, message: str, status: str = "info"):
        """Log message (thread-safe)"""
        if self.on_log:
            self.on_log(message, status)

    def show_all_browsers(self):
        """Hiện tất cả browser windows"""
        with self._automations_lock:
            for automation in self._automations:
                try:
                    automation.show_chrome_window()
                except:
                    pass

    def hide_all_browsers(self):
        """Ẩn tất cả browser windows"""
        with self._automations_lock:
            for automation in self._automations:
                try:
                    automation._hide_chrome_window()
                except:
                    pass

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

    def process_single_product(
        self,
        item: Dict,
        profile: Dict,
        reader: Any,
        merger: Any
    ) -> bool:
        """Xử lý 1 mã sản phẩm với 1 profile"""
        from ...grok_selenium import GrokSeleniumAutomation
        from ...video_merger import get_random_music, get_voice_for_code

        code = item["code"]
        row = item["row"]
        images = item["images"]

        profile_name = profile.get("name", "Unknown")
        self.log(f"\n[{profile_name}] Bắt đầu xử lý: {code} ({len(images)} ảnh)", "progress")

        # Get browser settings
        chrome_path = profile.get("chrome_path", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        profile_path = profile.get("profile_path", "")

        # Create automation instance for this profile
        automation = GrokSeleniumAutomation(
            chrome_path=chrome_path,
            profile_path=profile_path,
            headless=self.headless,
            on_log=lambda msg, s="info": self.log(f"[{profile_name}] {msg}", s)
        )

        # Lưu automation để có thể ẩn/hiện
        with self._automations_lock:
            self._automations.append(automation)
            # Gọi callback để GUI biết có automation mới
            if self.on_automation_created:
                self.on_automation_created(self)  # Truyền worker thay vì single automation

        try:
            # Thư mục tạm cho mã này
            code_temp_folder = self.temp_folder / code
            code_temp_folder.mkdir(parents=True, exist_ok=True)

            # ===== BƯỚC 1: Tạo video từ mỗi ảnh =====
            self.log(f"[{profile_name}] Tạo {len(images)} video từ ảnh...", "progress")

            created_videos = []

            for j, image_path in enumerate(images):
                if self.stop_flag.is_set():
                    break

                video_name = f"{code}_{j+1:02d}.mp4"
                video_path = code_temp_folder / video_name

                # Bỏ qua nếu đã có
                if video_path.exists() and video_path.stat().st_size > 50000:
                    self.log(f"[{profile_name}] [{j+1}/{len(images)}] Đã có: {video_name}", "success")
                    created_videos.append(str(video_path))
                    continue

                self.log(f"[{profile_name}] [{j+1}/{len(images)}] Tạo video từ: {image_path.name}", "progress")

                result = automation.create_video(
                    image_path=str(image_path),
                    prompt=item.get("prompt", ""),
                    output_path=str(video_path),
                    product_code=code,
                    skip_navigate=(j > 0)
                )

                if result.success:
                    created_videos.append(str(video_path))
                    self.log(f"[{profile_name}] ✓ Tạo xong: {video_name}", "success")
                else:
                    self.log(f"[{profile_name}] ✗ Thất bại: {result.error}", "error")

                # Navigate về Grok cho ảnh tiếp theo
                if j < len(images) - 1 and result.success:
                    automation.driver.execute_script(
                        "window.location.href = 'https://grok.com/imagine';"
                    )
                    time.sleep(3)
                    automation.install_video_hook()

            if not created_videos:
                self.log(f"[{profile_name}] ✗ Không tạo được video nào cho {code}", "error")
                return False

            # ===== BƯỚC 2: Ghép video + nhạc + voice =====
            self.log(f"[{profile_name}] Ghép {len(created_videos)} video...", "progress")

            # Lấy nhạc ngẫu nhiên từ thư mục music
            music_path = None
            if self.music_folder and self.music_folder.exists():
                music_path = get_random_music(str(self.music_folder))
                if music_path:
                    self.log(f"[{profile_name}] 🎵 Nhạc (random): {Path(music_path).name}", "info")

            # Lấy voice
            voice_path = None
            if self.voice_folder and self.voice_folder.exists():
                voice_path = get_voice_for_code(str(self.voice_folder), code)
                if voice_path:
                    self.log(f"[{profile_name}] 🎤 Voice: {Path(voice_path).name}", "info")

            # Đường dẫn output
            final_video = self.output_folder / f"{code}.mp4"

            # Ghép video với nhạc nền 60% volume
            success = merger.merge_videos(
                video_paths=created_videos,
                output_path=str(final_video),
                music_path=music_path,
                voice_path=voice_path,
                music_volume=0.6,  # 60% volume
                voice_volume=1.0
            )

            if success:
                reader.update_status(row, "EDIT XONG", self.config.status_column)
                self.log(f"[{profile_name}] ✓ Hoàn thành: {code}", "success")

                # Update progress
                with self._lock:
                    self._completed_count += 1
                    self.progress(self._completed_count, self._total_count, f"Hoàn thành: {code}")

                return True
            else:
                self.log(f"[{profile_name}] ✗ Lỗi ghép video cho {code}", "error")
                return False

        except Exception as e:
            self.log(f"[{profile_name}] Lỗi xử lý {code}: {e}", "error")
            return False

        finally:
            # Remove từ list trước khi đóng
            with self._automations_lock:
                if automation in self._automations:
                    self._automations.remove(automation)
            automation.close_driver()

    def run(self):
        """Run the video creation process"""
        try:
            self.log("Bắt đầu quá trình tạo video Grok...", "progress")

            num_profiles = len(self.browser_profiles)
            if num_profiles == 0:
                self.log("Không có browser profile nào!", "error")
                return

            self.log(f"Chế độ ẩn: {'BẬT' if self.headless else 'TẮT'}", "info")
            self.log(f"Số profile (chạy song song): {num_profiles}", "info")

            # Import modules
            from ...grok_selenium import GrokSeleniumAutomation
            from ...sheets_reader import SheetsReader
            from ...video_merger import VideoMerger

            # Setup folders
            self.output_folder.mkdir(parents=True, exist_ok=True)
            self.temp_folder.mkdir(parents=True, exist_ok=True)

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

            self.log(f"Tìm thấy {len(pending)} mã cần xử lý", "info")

            # Kiểm tra thư mục con
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
                        self.log(f"  ⚠️ {code}: Thư mục rỗng", "warning")
                else:
                    self.log(f"  ⚠️ {code}: Không tìm thấy thư mục", "warning")

            if not valid_items:
                self.log("Không có mã nào có thư mục ảnh hợp lệ!", "error")
                return

            # Lọc các mã đã hoàn thành
            still_pending = []
            for item in valid_items:
                code = item["code"]
                final_video = self.output_folder / f"{code}.mp4"

                if final_video.exists() and final_video.stat().st_size > 100 * 1024:
                    try:
                        with open(final_video, "rb") as f:
                            if b"ftyp" in f.read(12):
                                self.log(f"✓ {code} - video đã có", "success")
                                reader.update_status(item["row"], "EDIT XONG", self.config.status_column)
                                continue
                    except:
                        pass
                still_pending.append(item)

            if not still_pending:
                self.log("Tất cả video đã hoàn thành!", "success")
                return

            self._total_count = len(still_pending)
            self._completed_count = 0
            self.log(f"Còn {self._total_count} mã cần xử lý", "info")

            # Create video merger
            merger = VideoMerger(
                transition_type=self.transition_type,
                transition_duration=0.5,
                on_log=self.log
            )

            # ===== CHẠY SONG SONG =====
            self.log(f"\n{'='*40}", "info")
            self.log(f"Bắt đầu xử lý song song với {num_profiles} profile...", "progress")

            # Phân chia công việc cho các profile
            # Mỗi profile xử lý các mã theo round-robin
            with ThreadPoolExecutor(max_workers=num_profiles) as executor:
                futures = []

                for i, item in enumerate(still_pending):
                    if self.stop_flag.is_set():
                        break

                    # Chọn profile theo round-robin
                    profile = self.browser_profiles[i % num_profiles]

                    # Submit task
                    future = executor.submit(
                        self.process_single_product,
                        item, profile, reader, merger
                    )
                    futures.append((item["code"], future))

                # Chờ tất cả hoàn thành
                for code, future in futures:
                    if self.stop_flag.is_set():
                        break
                    try:
                        future.result()
                    except Exception as e:
                        self.log(f"Lỗi xử lý {code}: {e}", "error")

            # Hoàn thành
            self.progress(self._total_count, self._total_count, "Hoàn thành")
            self.log(f"\n{'='*40}", "info")
            self.log(f"Hoàn thành xử lý {self._completed_count}/{self._total_count} mã!", "success")

        except Exception as e:
            self.log(f"Lỗi: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            raise
