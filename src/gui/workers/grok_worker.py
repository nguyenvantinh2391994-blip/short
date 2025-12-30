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
from dataclasses import dataclass, field


@dataclass
class ProcessResult:
    """Kết quả xử lý một item"""
    success: bool
    output_path: str = ""
    error: str = ""
    remaining_images: List = field(default_factory=list)  # Ảnh còn lại nếu bị rate limit


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

    def process_single_item(self, item: Dict, reader: Any = None, profile: Dict = None) -> Any:
        """
        Simplified method cho main_tab.py
        Tự động chọn profile và tạo merger

        Args:
            item: Dict chứa code, row, images
            reader: SheetsReader (optional)
            profile: Browser profile để dùng (optional, nếu không có sẽ dùng profile đầu tiên)

        Returns:
            Object với success và output_path
        """
        from dataclasses import dataclass

        @dataclass
        class Result:
            success: bool = False
            output_path: str = ""
            error: str = ""
            remaining_images: list = None

        # Lấy profile
        if profile is None:
            if not self.browser_profiles:
                return Result(success=False, error="Không có browser profile")
            profile = self.browser_profiles[0]

        # Tạo merger
        from ...video_merger import VideoMerger
        merger = VideoMerger(
            transition_type=self.transition_type,
            transition_duration=0.5,
            on_log=self.log
        )

        # Gọi process_single_product
        try:
            result = self.process_single_product(item, profile, reader, merger)
            code = item.get("code", "")

            # Handle ProcessResult
            if isinstance(result, ProcessResult):
                return Result(
                    success=result.success,
                    output_path=result.output_path or str(self.output_folder / f"{code}.mp4") if result.success else "",
                    error=result.error,
                    remaining_images=result.remaining_images if hasattr(result, 'remaining_images') else None
                )
            else:
                # Fallback cho boolean return (không nên xảy ra)
                output_path = str(self.output_folder / f"{code}.mp4") if result else ""
                return Result(success=bool(result), output_path=output_path)
        except Exception as e:
            return Result(success=False, error=str(e))

    def process_single_product(
        self,
        item: Dict,
        profile: Dict,
        reader: Any,
        merger: Any
    ) -> bool:
        """Xử lý 1 mã sản phẩm với 1 profile"""
        # Chọn mode dựa trên config: "selenium" (cũ) hoặc "drission" (mới)
        browser_mode = getattr(self.config, 'browser_mode', 'selenium') if self.config else 'selenium'

        if browser_mode == "drission":
            try:
                from ...grok_drission import GrokDrissionAutomation as GrokAutomation
                self.log("   Dùng mode: DrissionPage", "info")
            except ImportError:
                from ...grok_selenium import GrokSeleniumAutomation as GrokAutomation
                self.log("   DrissionPage chưa cài, fallback sang Selenium", "warning")
        else:
            from ...grok_selenium import GrokSeleniumAutomation as GrokAutomation
            self.log("   Dùng mode: Selenium (cũ)", "info")

        from ...video_merger import get_random_music, get_voice_for_code

        code = item["code"]
        row = item["row"]
        images = item["images"]

        profile_name = profile.get("name", "Unknown")
        self.log(f"\n[{profile_name}] Bắt đầu xử lý: {code} ({len(images)} ảnh)", "progress")

        # Get browser settings
        chrome_path = profile.get("chrome_path", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        profile_path = profile.get("profile_path", "")

        # Create automation instance for this profile (DrissionPage hoặc Selenium)
        automation = GrokAutomation(
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
            # Thư mục video cho mã này - lưu vào input/{code}/video/
            code_video_folder = self.input_folder / code / "video"
            code_video_folder.mkdir(parents=True, exist_ok=True)

            # ===== BƯỚC 1: Tạo video từ mỗi ảnh =====
            self.log(f"[{profile_name}] Tạo {len(images)} video từ ảnh...", "progress")

            created_videos = []

            for j, image_path in enumerate(images):
                if self.stop_flag.is_set():
                    break

                video_name = f"{code}_{j+1:02d}.mp4"
                video_path = code_video_folder / video_name

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
                    self.log(f"[{profile_name}] Video thất bại - error: {result.error}", "warning")

                    # Kiểm tra rate limit
                    if result.error == "RATE_LIMIT":
                        self.log(f"[{profile_name}] 🚫 RATE LIMIT DETECTED!", "error")
                        self.log(f"[{profile_name}] → Đóng Chrome profile này...", "warning")
                        # Đánh dấu profile này bị rate limit
                        profile["rate_limited"] = True
                        # Đóng automation hiện tại
                        automation.close_driver()
                        # Return đặc biệt để chuyển profile
                        remaining = images[j:]
                        self.log(f"[{profile_name}] → Return với {len(remaining)} ảnh còn lại", "info")
                        return ProcessResult(False, error="RATE_LIMIT", remaining_images=remaining)

                    self.log(f"[{profile_name}] ✗ Thất bại: {result.error}", "error")

                # Navigate về Grok cho ảnh tiếp theo
                if j < len(images) - 1 and result.success:
                    # Hỗ trợ cả DrissionPage và Selenium
                    if hasattr(automation, 'manager') and automation.manager:
                        # DrissionPage
                        automation.manager.navigate("https://grok.com/imagine", wait=3)
                    elif hasattr(automation, 'driver') and automation.driver:
                        # Selenium
                        automation.driver.execute_script(
                            "window.location.href = 'https://grok.com/imagine';"
                        )
                        time.sleep(3)
                    automation.install_video_hook()

            if not created_videos:
                self.log(f"[{profile_name}] ✗ Không tạo được video nào cho {code}", "error")
                return ProcessResult(False, error="Không tạo được video")

            # ===== HOÀN THÀNH - Không edit tự động =====
            # Edit sẽ được chạy riêng khi user nhấn nút Edit
            self.log(f"[{profile_name}] ✓ Đã tạo {len(created_videos)} video cho {code}", "success")

            # Update progress
            with self._lock:
                self._completed_count += 1
                self.progress(self._completed_count, self._total_count, f"Hoàn thành: {code}")

            return ProcessResult(True, output_path=str(code_video_folder))

        except Exception as e:
            self.log(f"[{profile_name}] Lỗi xử lý {code}: {e}", "error")
            return ProcessResult(False, error=str(e))

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

            # Log browser mode
            browser_mode = getattr(self.config, 'browser_mode', 'selenium') if self.config else 'selenium'
            self.log(f"Browser mode: {browser_mode}", "info")
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

            # ===== AUTO DOWNLOAD ẢNH TỪ SHOPEE =====
            auto_shopee = getattr(self.config, 'auto_shopee', True)
            shopee_link_column = getattr(self.config, 'shopee_link_column', 'B')

            if auto_shopee:
                self.log("🛒 Kiểm tra và tải ảnh từ Shopee...", "progress")
                try:
                    from ...shopee_downloader import ShopeeDownloader

                    # Lấy dữ liệu cột link Shopee
                    all_values = reader.sheet.get_all_values()
                    link_col_idx = ord(shopee_link_column.upper()) - ord('A')

                    # Lấy browser profile để dùng (profile đầu tiên nếu có)
                    chrome_path = None
                    profile_path = None
                    if self.browser_profiles:
                        first_profile = self.browser_profiles[0]
                        chrome_path = first_profile.get("chrome_path")
                        profile_path = first_profile.get("profile_path")
                        self.log(f"  📱 Dùng profile: {first_profile.get('name', 'Default')}", "info")

                    downloader = ShopeeDownloader(
                        output_dir=str(self.input_folder),
                        chrome_path=chrome_path,
                        profile_path=profile_path
                    )

                    for item in pending:
                        code = item["code"]
                        row_idx = item["row"] - 1  # Row trong sheet bắt đầu từ 1
                        code_folder = self.input_folder / code

                        # Kiểm tra đã có ảnh chưa
                        if code_folder.exists():
                            existing = self.get_images_in_folder(code_folder)
                            if existing:
                                continue  # Đã có ảnh, bỏ qua

                        # Lấy link Shopee từ sheet
                        if row_idx < len(all_values):
                            row_data = all_values[row_idx]
                            shopee_link = row_data[link_col_idx] if len(row_data) > link_col_idx else ""

                            if shopee_link and "shopee" in shopee_link.lower():
                                self.log(f"  🛒 Tải ảnh cho {code}...", "progress")
                                images = downloader.download_from_url(
                                    url=shopee_link.strip(),
                                    folder_name=code,
                                    skip_existing=True
                                )
                                if images:
                                    self.log(f"  ✅ Đã tải {len(images)} ảnh cho {code}", "success")
                                else:
                                    self.log(f"  ⚠️ Không tải được ảnh cho {code}", "warning")

                except Exception as e:
                    self.log(f"⚠️ Lỗi tải ảnh Shopee: {e}", "warning")

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

            # ===== XỬ LÝ VỚI RATE LIMIT HANDLING =====
            self.log(f"\n{'='*40}", "info")
            self.log(f"Bắt đầu xử lý với {num_profiles} profile (có rate limit handling)...", "progress")

            # Hiển thị danh sách profiles
            for i, p in enumerate(self.browser_profiles):
                self.log(f"   Profile {i+1}: {p.get('name', 'Unknown')} - {p.get('profile_path', 'N/A')}", "info")

            # Đánh dấu profile nào bị rate limit
            for profile in self.browser_profiles:
                profile["rate_limited"] = False

            # Hàm lấy profile khả dụng tiếp theo
            def get_available_profile():
                available = [p for p in self.browser_profiles if not p.get("rate_limited", False)]
                self.log(f"   📊 Profiles khả dụng: {len(available)}/{len(self.browser_profiles)}", "info")
                if available:
                    return available[0]
                return None

            # Queue các item cần xử lý
            pending_queue = list(still_pending)

            while pending_queue and not self.stop_flag.is_set():
                # Lấy profile khả dụng
                profile = get_available_profile()

                if not profile:
                    self.log("⚠️ Tất cả profile đều bị rate limit!", "error")
                    self.log("   Vui lòng thêm thêm profile Chrome trong Settings.", "warning")
                    self.log(f"   Còn {len(pending_queue)} mã chưa xử lý.", "warning")
                    break

                item = pending_queue.pop(0)
                code = item["code"]

                self.log(f"\n[{profile.get('name', 'Unknown')}] Xử lý: {code}", "progress")

                try:
                    result = self.process_single_product(item, profile, reader, merger)

                    if isinstance(result, ProcessResult):
                        if result.error == "RATE_LIMIT":
                            # Đánh dấu profile bị rate limit
                            profile["rate_limited"] = True
                            self.log(f"🚫 Profile '{profile.get('name')}' bị RATE LIMIT!", "warning")

                            # Kiểm tra còn profile nào không
                            remaining_profiles = [p for p in self.browser_profiles if not p.get("rate_limited", False)]
                            if remaining_profiles:
                                self.log(f"   ↪ Chuyển sang profile: {remaining_profiles[0].get('name')}", "info")
                            else:
                                self.log(f"   ❌ Không còn profile nào khả dụng!", "error")

                            # Nếu còn ảnh chưa xử lý, tạo item mới với ảnh còn lại
                            if result.remaining_images:
                                new_item = item.copy()
                                new_item["images"] = result.remaining_images
                                pending_queue.insert(0, new_item)  # Thêm vào đầu queue
                                self.log(f"   📷 Còn {len(result.remaining_images)} ảnh chưa xử lý", "info")
                            else:
                                # Thêm lại item vào đầu queue để thử với profile khác
                                pending_queue.insert(0, item)
                                self.log(f"   📷 Thêm lại {code} vào queue", "info")

                        elif not result.success:
                            self.log(f"✗ Lỗi xử lý {code}: {result.error}", "error")
                        # Nếu thành công, không cần làm gì thêm

                except Exception as e:
                    self.log(f"Lỗi xử lý {code}: {e}", "error")
                    import traceback
                    self.log(traceback.format_exc(), "error")

            # Hoàn thành
            self.progress(self._total_count, self._total_count, "Hoàn thành")
            self.log(f"\n{'='*40}", "info")
            self.log(f"Hoàn thành xử lý {self._completed_count}/{self._total_count} mã!", "success")

            # Báo cáo profile bị rate limit
            rate_limited_profiles = [p.get("name") for p in self.browser_profiles if p.get("rate_limited")]
            if rate_limited_profiles:
                self.log(f"⚠️ Profiles bị rate limit: {', '.join(rate_limited_profiles)}", "warning")

        except Exception as e:
            self.log(f"Lỗi: {str(e)}", "error")
            import traceback
            self.log(traceback.format_exc(), "error")
            raise
