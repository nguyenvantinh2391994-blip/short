"""
Main Tab - Giao diện chính để tạo video
Gọn gàng, dễ dùng, tất cả trong 1 màn hình
"""

import customtkinter as ctk
from pathlib import Path
import threading
from typing import Optional
import queue


class MainTab:
    """Main workspace - tất cả tính năng chính trong 1 tab"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.is_running = False
        self.current_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self.task_queue = queue.Queue()

        self.setup_ui()

    def setup_ui(self):
        """Setup UI - layout 2 cột"""
        # Main frame
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True)

        # ===== CỘT TRÁI: ACTIONS =====
        left_frame = ctk.CTkFrame(self.main_frame, width=320)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)

        self.setup_actions(left_frame)

        # ===== CỘT PHẢI: LOG & PROGRESS =====
        right_frame = ctk.CTkFrame(self.main_frame)
        right_frame.pack(side="left", fill="both", expand=True)

        self.setup_progress(right_frame)

    def setup_actions(self, parent):
        """Panel actions bên trái"""
        # Stats nhỏ gọn ở trên
        self.setup_mini_stats(parent)

        # Separator
        sep = ctk.CTkFrame(parent, height=2, fg_color=("gray80", "gray30"))
        sep.pack(fill="x", padx=15, pady=15)

        # Main buttons
        self.setup_buttons(parent)

        # Quick info ở dưới
        self.setup_quick_info(parent)

    def setup_mini_stats(self, parent):
        """Stats nhỏ gọn"""
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.pack(fill="x", padx=15, pady=(15, 0))

        # Count files
        input_folder = Path(self.app.config.input_folder)
        output_folder = Path(self.app.config.output_folder)

        input_count = 0
        if input_folder.exists():
            input_count = len([d for d in input_folder.iterdir() if d.is_dir()])

        output_count = 0
        if output_folder.exists():
            output_count = len(list(output_folder.glob("*.mp4")))

        profile_count = len(self.app.config.browser_profiles)

        # Stats row
        stats = [
            ("📁", str(input_count), "thư mục"),
            ("🎬", str(output_count), "video"),
            ("🌐", str(profile_count), "profile"),
        ]

        for icon, value, label in stats:
            stat_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
            stat_frame.pack(side="left", expand=True)

            ctk.CTkLabel(
                stat_frame,
                text=f"{icon} {value}",
                font=ctk.CTkFont(size=16, weight="bold")
            ).pack()

            ctk.CTkLabel(
                stat_frame,
                text=label,
                font=ctk.CTkFont(size=10),
                text_color="gray"
            ).pack()

    def setup_buttons(self, parent):
        """Main action buttons"""
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)

        # Nút 1: Tải ảnh Shopee
        self.shopee_btn = ctk.CTkButton(
            btn_frame,
            text="🛒  Tải ảnh Shopee",
            command=self.download_shopee_images,
            height=50,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#E65100",
            hover_color="#BF360C"
        )
        self.shopee_btn.pack(fill="x", pady=5)

        # Nút 2: Tạo Video
        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="▶️  Tạo Video",
            command=self.start_process,
            height=50,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.start_btn.pack(fill="x", pady=5)

        # Row: Stop + Show Browser
        row_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=5)

        self.stop_btn = ctk.CTkButton(
            row_frame,
            text="⏹️ Dừng",
            command=self.stop_process,
            height=40,
            width=140,
            font=ctk.CTkFont(size=13),
            fg_color="#C62828",
            hover_color="#B71C1C",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(0, 5))

        self.show_btn = ctk.CTkButton(
            row_frame,
            text="👁️ Browser",
            command=self.show_browser,
            height=40,
            width=140,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            border_width=1,
            text_color=("gray20", "gray80"),
            hover_color=("gray85", "gray25")
        )
        self.show_btn.pack(side="left")

    def setup_quick_info(self, parent):
        """Quick info panel"""
        info_frame = ctk.CTkFrame(parent, fg_color="transparent")
        info_frame.pack(fill="x", padx=15, pady=10, side="bottom")

        # Profile đang dùng
        profile_name = "Chưa cấu hình"
        if self.app.config.browser_profiles:
            profile_name = self.app.config.browser_profiles[0].get("name", "Profile 1")

        info_text = f"Profile: {profile_name}"
        if self.app.config.spreadsheet_id:
            info_text += f"\nSheet: ...{self.app.config.spreadsheet_id[-8:]}"
        else:
            info_text += "\nSheet: Chưa cấu hình"

        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        ).pack(anchor="w")

        # Refresh button
        refresh_btn = ctk.CTkButton(
            info_frame,
            text="🔄 Refresh",
            command=self.refresh_stats,
            height=28,
            width=80,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            text_color=("gray20", "gray80"),
            hover_color=("gray85", "gray25")
        )
        refresh_btn.pack(anchor="w", pady=(5, 0))

    def setup_progress(self, parent):
        """Progress & log panel"""
        # Header
        header = ctk.CTkFrame(parent, fg_color="transparent", height=40)
        header.pack(fill="x", padx=15, pady=(15, 10))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="📋 Tiến trình",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        # Clear button
        clear_btn = ctk.CTkButton(
            header,
            text="Xóa",
            command=self.clear_log,
            height=25,
            width=50,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            text_color=("gray20", "gray80"),
            hover_color=("gray85", "gray25")
        )
        clear_btn.pack(side="right")

        # Progress bar
        self.progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.progress_label.pack(anchor="w", pady=(5, 0))

        # Log area
        self.log_text = ctk.CTkTextbox(
            parent,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.log_text.configure(state="disabled")

        # Welcome message
        self.add_log("Sẵn sàng! Nhấn nút để bắt đầu.", "info")

    def add_log(self, message: str, level: str = "info"):
        """Add log message"""
        self.log_text.configure(state="normal")

        # Color based on level
        if level == "error":
            tag = "error"
        elif level == "success":
            tag = "success"
        elif level == "warning":
            tag = "warning"
        elif level == "progress":
            tag = "progress"
        else:
            tag = "info"

        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        """Clear log"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_label.configure(text="")

    def update_progress(self, current: int, total: int, message: str = ""):
        """Update progress"""
        if total > 0:
            self.progress_bar.set(current / total)
        self.progress_label.configure(text=f"{current}/{total} - {message}")

    def refresh_stats(self):
        """Refresh stats"""
        # Rebuild actions panel
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.setup_ui()
        self.add_log("Đã refresh!", "info")

    def after_safe(self, func):
        """Thread-safe UI update"""
        self.parent.after(0, func)

    # ===== ACTIONS =====

    def download_shopee_images(self):
        """Tải ảnh từ Shopee"""
        if self.is_running:
            self.add_log("Đang chạy task khác...", "warning")
            return

        self.shopee_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.clear_log()
        self.add_log("🛒 Bắt đầu tải ảnh từ Shopee...", "progress")

        thread = threading.Thread(
            target=self._run_shopee_download,
            daemon=True
        )
        thread.start()

    def _run_shopee_download(self):
        """Background thread tải ảnh"""
        try:
            from ...shopee_downloader import ShopeeDownloader
            from ...sheets_reader import SheetsReader

            self.after_safe(lambda: self.add_log("Kết nối Google Sheets...", "progress"))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect():
                self.after_safe(lambda: self.add_log("❌ Không thể kết nối!", "error"))
                return

            if not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("❌ Không thể mở spreadsheet!", "error"))
                return

            self.after_safe(lambda: self.add_log("✓ Đã kết nối", "success"))

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_log("Không có sản phẩm nào cần xử lý", "warning"))
                return

            total = len(pending)
            self.after_safe(lambda: self.add_log(f"Tìm thấy {total} mã cần xử lý", "info"))

            # Get Shopee links
            all_values = reader.sheet.get_all_values()
            shopee_link_column = getattr(self.app.config, 'shopee_link_column', 'B')
            link_col_idx = ord(shopee_link_column.upper()) - ord('A')

            # Browser profile
            chrome_path = None
            profile_path = None
            if self.app.config.browser_profiles:
                first_profile = self.app.config.browser_profiles[0]
                chrome_path = first_profile.get("chrome_path")
                profile_path = first_profile.get("profile_path")

            # Tạo downloader và lưu reference để có thể show/hide browser
            self.shopee_downloader = ShopeeDownloader(
                output_dir=self.app.config.input_folder,
                chrome_path=chrome_path,
                profile_path=profile_path,
                headless=True  # Chạy ẩn mặc định
            )
            downloader = self.shopee_downloader

            downloaded = 0
            skipped = 0

            for idx, item in enumerate(pending):
                code = item["code"]
                row_idx = item["row"] - 1
                code_folder = Path(self.app.config.input_folder) / code

                self.after_safe(lambda i=idx, t=total: self.update_progress(i, t, f"Xử lý: {code}"))

                # Check existing
                if code_folder.exists():
                    existing = list(code_folder.glob("*.jpg")) + list(code_folder.glob("*.png"))
                    if existing:
                        self.after_safe(lambda c=code: self.add_log(f"⏭️ {c}: đã có ảnh", "info"))
                        skipped += 1
                        continue

                # Get link
                if row_idx < len(all_values):
                    row_data = all_values[row_idx]
                    link = row_data[link_col_idx] if len(row_data) > link_col_idx else ""

                    if link and "shopee" in link.lower():
                        self.after_safe(lambda c=code: self.add_log(f"🛒 Tải: {c}...", "progress"))

                        images = downloader.download_from_url(
                            url=link.strip(),
                            folder_name=code,
                            skip_existing=True
                        )

                        if images:
                            self.after_safe(lambda c=code, n=len(images): self.add_log(f"✓ {c}: {n} ảnh", "success"))
                            downloaded += 1
                        else:
                            self.after_safe(lambda c=code: self.add_log(f"⚠️ {c}: không tải được", "warning"))

            self.after_safe(lambda: self.update_progress(total, total, "Hoàn thành"))
            self.after_safe(lambda: self.add_log(f"\n✅ Hoàn thành! Tải: {downloaded}, Bỏ qua: {skipped}", "success"))

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}", "error"))
        finally:
            self.after_safe(lambda: self.shopee_btn.configure(state="normal"))
            self.after_safe(lambda: self.start_btn.configure(state="normal"))

    def start_process(self):
        """Bắt đầu tạo video"""
        if self.is_running:
            return

        # Validate
        if not self.app.config.browser_profiles:
            self.add_log("❌ Chưa cấu hình Browser Profile!", "error")
            self.add_log("Vào tab Cài đặt để thêm profile", "info")
            return

        if not self.app.config.spreadsheet_id:
            self.add_log("❌ Chưa cấu hình Google Sheets!", "error")
            return

        self.is_running = True
        self.stop_flag.clear()
        self.shopee_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.clear_log()
        self.add_log("▶️ Bắt đầu tạo video...", "progress")

        self.current_thread = threading.Thread(
            target=self._run_video_creation,
            daemon=True
        )
        self.current_thread.start()

    def _run_video_creation(self):
        """Background thread tạo video"""
        try:
            from ..workers.grok_worker import GrokWorker

            worker = GrokWorker(
                input_folder=self.app.config.input_folder,
                output_folder=self.app.config.output_folder,
                music_folder=self.app.config.music_folder,
                voice_folder=self.app.config.voice_folder,
                browser_profiles=self.app.config.browser_profiles,
                config=self.app.config,
                stop_flag=self.stop_flag,
                on_progress=lambda c, t, m: self.after_safe(lambda: self.update_progress(c, t, m)),
                on_log=lambda m, l: self.after_safe(lambda: self.add_log(m, l)),
                on_automation_created=self._on_automation_created
            )

            self.current_worker = worker
            worker.run()

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}", "error"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_process_complete)

    def _on_automation_created(self, automation):
        """Callback khi automation được tạo"""
        pass

    def _on_process_complete(self):
        """Process complete"""
        self.is_running = False
        self.shopee_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def stop_process(self):
        """Stop current process"""
        if self.is_running:
            self.stop_flag.set()
            self.add_log("⏹️ Đang dừng...", "warning")

    def show_browser(self):
        """Toggle show/hide browser windows (cả Grok và Shopee)"""
        shown = False

        # Toggle Grok browser
        if hasattr(self, 'current_worker'):
            try:
                self.current_worker.show_all_browsers()
                shown = True
            except Exception:
                pass

        # Toggle Shopee browser
        if hasattr(self, 'shopee_downloader') and self.shopee_downloader:
            try:
                self.shopee_downloader.toggle_browser_visibility()
                shown = True
            except Exception:
                pass

        if shown:
            self.add_log("👁️ Đã toggle browser", "info")
        else:
            self.add_log("Không có browser nào đang chạy", "warning")
