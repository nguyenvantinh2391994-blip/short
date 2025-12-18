"""
Grok Tab - Tạo video từ Grok AI
Giao diện đơn giản, dễ dùng
"""

import customtkinter as ctk
from pathlib import Path
import threading
from typing import Optional
import queue


class GrokTab:
    """Grok Video Creation Tab - Giao diện đơn giản"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.is_running = False
        self.current_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self.task_queue = queue.Queue()

        self.setup_ui()

    def setup_ui(self):
        """Setup UI - Đơn giản, dễ dùng"""
        # Main container
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== PHẦN TRÊN: ACTION BUTTONS (QUAN TRỌNG NHẤT) ==========
        self.setup_action_section()

        # ========== PHẦN GIỮA: PROGRESS ==========
        self.setup_progress_section()

    def setup_action_section(self):
        """Phần action chính - NỔI BẬT, DỄ DÙNG"""
        action_frame = ctk.CTkFrame(self.main_frame)
        action_frame.pack(fill="x", padx=5, pady=(0, 10))

        # Title
        title = ctk.CTkLabel(
            action_frame,
            text="🎬 Tạo Video Tự Động",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title.pack(pady=(20, 5))

        subtitle = ctk.CTkLabel(
            action_frame,
            text="Tải ảnh từ Shopee → Tạo video với Grok AI",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        subtitle.pack(pady=(0, 15))

        # ===== HÀNG NÚT CHÍNH =====
        main_btn_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        main_btn_frame.pack(pady=10)

        # Nút 1: Tải ảnh Shopee
        self.shopee_btn = ctk.CTkButton(
            main_btn_frame,
            text="🛒 Tải ảnh Shopee",
            command=self.download_shopee_images,
            width=180,
            height=55,
            fg_color="#FF5722",
            hover_color="#E64A19",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.shopee_btn.pack(side="left", padx=8)

        # Nút 2: Bắt đầu tạo video
        self.start_btn = ctk.CTkButton(
            main_btn_frame,
            text="▶️ Tạo Video",
            command=self.start_process,
            width=180,
            height=55,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.start_btn.pack(side="left", padx=8)

        # Nút 3: Dừng
        self.stop_btn = ctk.CTkButton(
            main_btn_frame,
            text="⏹️ Dừng",
            command=self.stop_process,
            width=120,
            height=55,
            fg_color="#f44336",
            hover_color="#D32F2F",
            state="disabled",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.stop_btn.pack(side="left", padx=8)

        # Nút 4: Hiện Browser
        self.show_btn = ctk.CTkButton(
            main_btn_frame,
            text="👁️ Hiện",
            command=self.toggle_browser_visibility,
            width=80,
            height=55,
            fg_color="#9E9E9E",
            hover_color="#757575",
            state="disabled",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.show_btn.pack(side="left", padx=8)

        # ===== HƯỚNG DẪN NHANH =====
        help_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        help_frame.pack(fill="x", padx=30, pady=(15, 20))

        steps = [
            "1️⃣ Điền link Shopee vào cột B trong Google Sheet",
            "2️⃣ Bấm '🛒 Tải ảnh Shopee' để tải ảnh",
            "3️⃣ Bấm '▶️ Tạo Video' để tạo video tự động"
        ]

        for step in steps:
            label = ctk.CTkLabel(
                help_frame,
                text=step,
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            label.pack(anchor="w", pady=1)

    def setup_progress_section(self):
        """Phần hiển thị tiến trình"""
        progress_frame = ctk.CTkFrame(self.main_frame)
        progress_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Header
        header_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            header_frame,
            text="📊 Tiến trình",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        # Progress info
        self.progress_label = ctk.CTkLabel(
            header_frame,
            text="0/0",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#4CAF50"
        )
        self.progress_label.pack(side="right")

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=500, height=15)
        self.progress_bar.pack(padx=20, pady=(0, 10))
        self.progress_bar.set(0)

        # Current task
        self.current_task_label = ctk.CTkLabel(
            progress_frame,
            text="Sẵn sàng",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.current_task_label.pack(pady=(0, 10))

        # Task list (log)
        self.task_list = ctk.CTkTextbox(
            progress_frame,
            font=ctk.CTkFont(size=12),
            wrap="word"
        )
        self.task_list.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Biến lưu automation
        self.current_worker = None
        self._browser_visible = False

    def get_profile_names(self) -> list:
        """Get list of browser profile names"""
        profiles = self.app.config.browser_profiles
        if not profiles:
            return ["Default"]
        return [p.get("name", "Profile") for p in profiles]

    def add_task_log(self, message: str, status: str = "info"):
        """Add message to task list"""
        colors = {
            "info": "",
            "success": "✅ ",
            "error": "❌ ",
            "warning": "⚠️ ",
            "progress": "🔄 "
        }
        prefix = colors.get(status, "")
        self.task_list.insert("end", f"{prefix}{message}\n")
        self.task_list.see("end")

    def update_progress(self, current: int, total: int, task_name: str = ""):
        """Update progress bar and label"""
        if total > 0:
            self.progress_bar.set(current / total)
            self.progress_label.configure(text=f"{current}/{total}")
        if task_name:
            self.current_task_label.configure(text=task_name)

    def start_process(self):
        """Start video creation process"""
        if self.is_running:
            return

        self.is_running = True
        self.stop_flag.clear()

        # Update UI
        self.start_btn.configure(state="disabled")
        self.shopee_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.task_list.delete("1.0", "end")
        self.progress_bar.set(0)

        # Get settings from app config
        input_folder = self.app.config.input_folder
        output_folder = self.app.config.output_folder
        music_folder = getattr(self.app.config, 'music_folder', '')
        voice_folder = getattr(self.app.config, 'voice_folder', '')
        transition_type = "fade_black"

        # Start thread
        self.current_thread = threading.Thread(
            target=self.run_grok_process,
            args=(input_folder, output_folder, music_folder, voice_folder, transition_type),
            daemon=True
        )
        self.current_thread.start()

        num_profiles = len(self.app.config.browser_profiles)
        self.app.log(f"Bắt đầu tạo video Grok với {num_profiles} profile")
        self.add_task_log(f"Bắt đầu tạo video ({num_profiles} profile)...", "progress")

    def stop_process(self):
        """Stop video creation process"""
        self.stop_flag.set()
        self.add_task_log("Đang dừng...", "warning")
        self.app.log("Yêu cầu dừng tạo video")

    def run_grok_process(
        self,
        input_folder: str,
        output_folder: str,
        music_folder: str,
        voice_folder: str,
        transition_type: str
    ):
        """Run Grok video creation (in background thread)"""
        try:
            # Auto-update nếu được bật
            auto_update = getattr(self.app.config, 'auto_update', True)
            if auto_update:
                self.after_safe(lambda: self.add_task_log("Kiểm tra cập nhật...", "progress"))
                try:
                    from ..utils.updater import AutoUpdater
                    updater = AutoUpdater(on_log=self.on_worker_log)
                    updated, msg = updater.update_if_available()
                    if updated:
                        self.after_safe(lambda: self.add_task_log("Đã cập nhật code mới!", "success"))
                except Exception as e:
                    self.after_safe(lambda: self.add_task_log(f"Bỏ qua cập nhật: {e}", "warning"))

            # Import here to avoid circular imports
            from ..workers.grok_worker import GrokWorker

            # Get ALL browser profiles
            browser_profiles = self.app.config.browser_profiles or []

            if not browser_profiles:
                self.after_safe(lambda: self.add_task_log("Chưa có profile! Vào ⚙️ Cài đặt để thêm.", "error"))
                return

            # Get headless setting
            headless = getattr(self.app.config, 'headless', True)

            # Create worker
            worker = GrokWorker(
                input_folder=input_folder,
                output_folder=output_folder,
                music_folder=music_folder,
                voice_folder=voice_folder,
                transition_type=transition_type,
                browser_profiles=browser_profiles,
                config=self.app.config,
                stop_flag=self.stop_flag,
                on_progress=self.on_worker_progress,
                on_log=self.on_worker_log,
                headless=headless,
                on_automation_created=self.set_automation
            )

            # Run
            worker.run()

        except Exception as e:
            self.after_safe(lambda: self.add_task_log(f"Lỗi: {e}", "error"))
            self.app.log(f"Lỗi Grok: {e}", "ERROR")

        finally:
            self.after_safe(self.on_process_complete)

    def on_worker_progress(self, current: int, total: int, task_name: str):
        """Callback from worker for progress update"""
        self.after_safe(lambda: self.update_progress(current, total, task_name))

    def on_worker_log(self, message: str, status: str = "info"):
        """Callback from worker for log message"""
        self.after_safe(lambda: self.add_task_log(message, status))

    def on_process_complete(self):
        """Called when process completes"""
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.shopee_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.show_btn.configure(state="disabled")
        self.current_task_label.configure(text="Hoàn thành")
        self.app.set_status("Hoàn thành tạo video")
        self.add_task_log("Hoàn thành!", "success")
        self.current_worker = None

    def toggle_browser_visibility(self):
        """Toggle ẩn/hiện tất cả browser"""
        if self.current_worker:
            try:
                if self._browser_visible:
                    self.current_worker.hide_all_browsers()
                    self.show_btn.configure(text="👁️ Hiện")
                    self._browser_visible = False
                    self.add_task_log("Đã ẩn browser", "info")
                else:
                    self.current_worker.show_all_browsers()
                    self.show_btn.configure(text="🙈 Ẩn")
                    self._browser_visible = True
                    self.add_task_log("Đã hiện browser", "info")
            except Exception as e:
                self.add_task_log(f"Lỗi: {e}", "error")

    def set_automation(self, worker):
        """Lưu reference đến worker"""
        self.current_worker = worker
        self.after_safe(lambda: self.show_btn.configure(state="normal"))
        self._browser_visible = False
        self.after_safe(lambda: self.show_btn.configure(text="👁️ Hiện"))

    def download_shopee_images(self):
        """Tải ảnh từ Shopee"""
        if self.is_running:
            self.add_task_log("Đang chạy task khác...", "warning")
            return

        # Disable button
        self.shopee_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.task_list.delete("1.0", "end")
        self.add_task_log("🛒 Bắt đầu tải ảnh từ Shopee...", "progress")

        # Get settings
        input_folder = self.app.config.input_folder
        shopee_link_column = getattr(self.app.config, 'shopee_link_column', 'B')

        # Start thread
        thread = threading.Thread(
            target=self._run_shopee_download,
            args=(input_folder, shopee_link_column),
            daemon=True
        )
        thread.start()

    def _run_shopee_download(self, input_folder: str, shopee_link_column: str):
        """Background thread để tải ảnh Shopee"""
        try:
            from ...shopee_downloader import ShopeeDownloader
            from ...sheets_reader import SheetsReader

            # Connect to Google Sheets
            self.after_safe(lambda: self.add_task_log("Kết nối Google Sheets...", "progress"))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect():
                self.after_safe(lambda: self.add_task_log("Không thể kết nối Google Sheets!", "error"))
                return

            if not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_task_log("Không thể mở spreadsheet!", "error"))
                return

            self.after_safe(lambda: self.add_task_log("Đã kết nối Google Sheets", "success"))

            # Get pending products
            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_task_log("Không có sản phẩm nào cần xử lý", "warning"))
                return

            total = len(pending)
            self.after_safe(lambda: self.add_task_log(f"Tìm thấy {total} mã cần xử lý", "info"))
            self.after_safe(lambda: self.update_progress(0, total, "Đang tải ảnh..."))

            # Get all values for Shopee links
            all_values = reader.sheet.get_all_values()
            link_col_idx = ord(shopee_link_column.upper()) - ord('A')

            # Init downloader với browser profile (nếu có)
            from pathlib import Path
            chrome_path = None
            profile_path = None

            # Lấy browser profile đầu tiên để dùng
            if self.app.config.browser_profiles:
                first_profile = self.app.config.browser_profiles[0]
                chrome_path = first_profile.get("chrome_path")
                profile_path = first_profile.get("profile_path")
                profile_name = first_profile.get("name", "Default")
                self.after_safe(lambda n=profile_name: self.add_task_log(f"📱 Dùng profile: {n}", "info"))

            downloader = ShopeeDownloader(
                output_dir=input_folder,
                chrome_path=chrome_path,
                profile_path=profile_path
            )

            downloaded_count = 0
            skipped_count = 0

            for idx, item in enumerate(pending):
                code = item["code"]
                row_idx = item["row"] - 1
                code_folder = Path(input_folder) / code

                # Update progress
                self.after_safe(lambda i=idx, t=total: self.update_progress(i, t, f"Đang xử lý: {code}"))

                # Check if already has images
                if code_folder.exists():
                    existing = list(code_folder.glob("*.jpg")) + list(code_folder.glob("*.png"))
                    if existing:
                        self.after_safe(lambda c=code, n=len(existing): self.add_task_log(f"⏭️ {c}: đã có {n} ảnh", "info"))
                        skipped_count += 1
                        continue

                # Get Shopee link
                if row_idx < len(all_values):
                    row_data = all_values[row_idx]
                    shopee_link = row_data[link_col_idx] if len(row_data) > link_col_idx else ""

                    if shopee_link and "shopee" in shopee_link.lower():
                        self.after_safe(lambda c=code: self.add_task_log(f"🛒 Đang tải: {c}...", "progress"))

                        images = downloader.download_from_url(
                            url=shopee_link.strip(),
                            folder_name=code,
                            skip_existing=True
                        )

                        if images:
                            self.after_safe(lambda c=code, n=len(images): self.add_task_log(f"✅ {c}: {n} ảnh", "success"))
                            downloaded_count += 1
                        else:
                            self.after_safe(lambda c=code: self.add_task_log(f"⚠️ {c}: không tải được", "warning"))
                    else:
                        self.after_safe(lambda c=code: self.add_task_log(f"⚠️ {c}: không có link", "warning"))

            # Summary
            self.after_safe(lambda: self.update_progress(total, total, "Hoàn thành"))
            self.after_safe(lambda: self.add_task_log(f"\n{'='*40}", "info"))
            self.after_safe(lambda: self.add_task_log(f"✅ Hoàn thành!", "success"))
            self.after_safe(lambda: self.add_task_log(f"   Đã tải: {downloaded_count} sản phẩm", "info"))
            self.after_safe(lambda: self.add_task_log(f"   Bỏ qua: {skipped_count} (đã có ảnh)", "info"))

        except Exception as e:
            self.after_safe(lambda: self.add_task_log(f"Lỗi: {e}", "error"))
            import traceback
            self.after_safe(lambda: self.add_task_log(traceback.format_exc(), "error"))

        finally:
            self.after_safe(lambda: self.shopee_btn.configure(state="normal"))
            self.after_safe(lambda: self.start_btn.configure(state="normal"))

    def after_safe(self, func):
        """Safely call function on main thread"""
        try:
            self.parent.after(0, func)
        except:
            pass
