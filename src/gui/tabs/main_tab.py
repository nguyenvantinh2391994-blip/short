"""
Main Tab - Giao diện chính để tạo video
Hiển thị tiến độ chi tiết từng mã: Input → Video → Render
"""

import customtkinter as ctk
from pathlib import Path
import threading
from typing import Optional, Dict, List
import queue
import subprocess
import platform


class TaskItem:
    """Đại diện 1 task trong bảng tiến độ"""
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"
    STATUS_SKIP = "skip"

    def __init__(self, code: str, row: int = 0):
        self.code = code
        self.row = row
        self.input_status = self.STATUS_PENDING  # Tải ảnh
        self.video_status = self.STATUS_PENDING  # Tạo video Grok
        self.render_status = self.STATUS_PENDING  # Render cuối
        self.output_path: Optional[Path] = None
        self.error_msg = ""

    @property
    def overall_progress(self) -> int:
        """Tính % hoàn thành tổng"""
        progress = 0
        if self.input_status == self.STATUS_DONE:
            progress += 33
        elif self.input_status == self.STATUS_SKIP:
            progress += 33
        if self.video_status == self.STATUS_DONE:
            progress += 34
        if self.render_status == self.STATUS_DONE:
            progress += 33
        return min(progress, 100)

    @property
    def is_complete(self) -> bool:
        return self.render_status == self.STATUS_DONE

    @property
    def has_error(self) -> bool:
        return self.STATUS_ERROR in [self.input_status, self.video_status, self.render_status]


class MainTab:
    """Main workspace - Tiến độ chi tiết từng mã"""

    # Status icons
    ICONS = {
        TaskItem.STATUS_PENDING: "⬜",
        TaskItem.STATUS_RUNNING: "🔄",
        TaskItem.STATUS_DONE: "✅",
        TaskItem.STATUS_ERROR: "❌",
        TaskItem.STATUS_SKIP: "⏭️",
    }

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.is_running = False
        self.current_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()

        # Task tracking
        self.tasks: Dict[str, TaskItem] = {}
        self.task_widgets: Dict[str, dict] = {}

        self.setup_ui()

    def setup_ui(self):
        """Setup UI - Layout mới gọn gàng"""
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== TOP: Action buttons =====
        self.setup_action_bar()

        # ===== MIDDLE: Progress table =====
        self.setup_progress_table()

        # ===== BOTTOM: Log area (nhỏ gọn) =====
        self.setup_log_area()

    def setup_action_bar(self):
        """Action bar - nút bấm nằm ngang"""
        action_frame = ctk.CTkFrame(self.main_frame, fg_color=("gray90", "gray17"))
        action_frame.pack(fill="x", pady=(0, 10))

        # Left: buttons
        btn_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_frame.pack(side="left", padx=10, pady=10)

        # Nút Tải ảnh
        self.shopee_btn = ctk.CTkButton(
            btn_frame,
            text="🛒 Tải ảnh",
            command=self.download_shopee_images,
            width=100,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#E65100",
            hover_color="#BF360C"
        )
        self.shopee_btn.pack(side="left", padx=(0, 8))

        # Nút Tạo Video
        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="▶️ Tạo Video",
            command=self.start_process,
            width=110,
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2E7D32",
            hover_color="#1B5E20"
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        # Nút Dừng
        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="⏹️ Dừng",
            command=self.stop_process,
            width=80,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color="#C62828",
            hover_color="#B71C1C",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(0, 8))

        # Nút Browser
        self.show_btn = ctk.CTkButton(
            btn_frame,
            text="👁️",
            command=self.show_browser,
            width=36,
            height=36,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            border_width=1,
            text_color=("gray20", "gray80"),
            hover_color=("gray85", "gray25")
        )
        self.show_btn.pack(side="left")

        # Right: stats
        stats_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        stats_frame.pack(side="right", padx=10, pady=10)

        # Progress tổng
        self.total_progress = ctk.CTkProgressBar(stats_frame, width=150, height=12)
        self.total_progress.pack(side="left", padx=(0, 10))
        self.total_progress.set(0)

        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="0/0",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.stats_label.pack(side="left")

    def setup_progress_table(self):
        """Bảng tiến độ chi tiết"""
        table_frame = ctk.CTkFrame(self.main_frame)
        table_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Header
        header_frame = ctk.CTkFrame(table_frame, fg_color=("gray85", "gray20"), height=35)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        headers = [
            ("Mã", 100),
            ("Ảnh", 60),
            ("Video", 60),
            ("Render", 60),
            ("Tiến độ", 100),
            ("", 80),  # Actions
        ]

        for text, width in headers:
            lbl = ctk.CTkLabel(
                header_frame,
                text=text,
                font=ctk.CTkFont(size=12, weight="bold"),
                width=width
            )
            lbl.pack(side="left", padx=5, pady=5)

        # Scrollable content
        self.table_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self.table_scroll.pack(fill="both", expand=True)

        # Placeholder khi chưa có task
        self.placeholder_label = ctk.CTkLabel(
            self.table_scroll,
            text="📋 Nhấn 'Tải ảnh' hoặc 'Tạo Video' để bắt đầu",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.placeholder_label.pack(pady=50)

    def setup_log_area(self):
        """Log area nhỏ gọn"""
        log_frame = ctk.CTkFrame(self.main_frame, height=120)
        log_frame.pack(fill="x")
        log_frame.pack_propagate(False)

        # Header
        header = ctk.CTkFrame(log_frame, fg_color="transparent", height=25)
        header.pack(fill="x", padx=10, pady=(5, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="📝 Log",
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Xóa",
            command=self.clear_log,
            width=40,
            height=20,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            text_color="gray",
            hover_color=("gray85", "gray25")
        ).pack(side="right")

        # Log text
        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=80,
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        self.log_text.configure(state="disabled")
        self.add_log("Sẵn sàng!")

    # ===== TABLE MANAGEMENT =====

    def add_task_row(self, task: TaskItem):
        """Thêm 1 row vào bảng"""
        if self.placeholder_label.winfo_exists():
            self.placeholder_label.destroy()

        row_frame = ctk.CTkFrame(self.table_scroll, fg_color="transparent", height=40)
        row_frame.pack(fill="x", pady=2)
        row_frame.pack_propagate(False)

        # Mã
        code_lbl = ctk.CTkLabel(
            row_frame,
            text=task.code,
            font=ctk.CTkFont(size=12),
            width=100,
            anchor="w"
        )
        code_lbl.pack(side="left", padx=5)

        # Input status
        input_lbl = ctk.CTkLabel(
            row_frame,
            text=self.ICONS[task.input_status],
            font=ctk.CTkFont(size=14),
            width=60
        )
        input_lbl.pack(side="left", padx=5)

        # Video status
        video_lbl = ctk.CTkLabel(
            row_frame,
            text=self.ICONS[task.video_status],
            font=ctk.CTkFont(size=14),
            width=60
        )
        video_lbl.pack(side="left", padx=5)

        # Render status
        render_lbl = ctk.CTkLabel(
            row_frame,
            text=self.ICONS[task.render_status],
            font=ctk.CTkFont(size=14),
            width=60
        )
        render_lbl.pack(side="left", padx=5)

        # Progress bar
        progress_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=100)
        progress_frame.pack(side="left", padx=5)
        progress_frame.pack_propagate(False)

        progress_bar = ctk.CTkProgressBar(progress_frame, width=80, height=10)
        progress_bar.pack(pady=5)
        progress_bar.set(task.overall_progress / 100)

        progress_pct = ctk.CTkLabel(
            progress_frame,
            text=f"{task.overall_progress}%",
            font=ctk.CTkFont(size=10),
            width=40
        )
        progress_pct.pack()

        # Actions
        action_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=80)
        action_frame.pack(side="left", padx=5)

        open_btn = ctk.CTkButton(
            action_frame,
            text="📂",
            command=lambda c=task.code: self.open_output(c),
            width=30,
            height=25,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            hover_color=("gray85", "gray25"),
            state="disabled"
        )
        open_btn.pack(side="left", padx=2)

        # Save widgets reference
        self.task_widgets[task.code] = {
            "frame": row_frame,
            "input": input_lbl,
            "video": video_lbl,
            "render": render_lbl,
            "progress_bar": progress_bar,
            "progress_pct": progress_pct,
            "open_btn": open_btn,
        }

    def update_task_row(self, code: str):
        """Cập nhật UI của 1 task"""
        if code not in self.tasks or code not in self.task_widgets:
            return

        task = self.tasks[code]
        widgets = self.task_widgets[code]

        # Update icons
        widgets["input"].configure(text=self.ICONS[task.input_status])
        widgets["video"].configure(text=self.ICONS[task.video_status])
        widgets["render"].configure(text=self.ICONS[task.render_status])

        # Update progress
        progress = task.overall_progress
        widgets["progress_bar"].set(progress / 100)
        widgets["progress_pct"].configure(text=f"{progress}%")

        # Enable open button if complete
        if task.is_complete and task.output_path and task.output_path.exists():
            widgets["open_btn"].configure(
                state="normal",
                text_color=("#2E7D32", "#4CAF50")
            )

        # Update total stats
        self.update_total_stats()

    def update_total_stats(self):
        """Cập nhật stats tổng"""
        total = len(self.tasks)
        done = sum(1 for t in self.tasks.values() if t.is_complete)
        errors = sum(1 for t in self.tasks.values() if t.has_error)

        if total > 0:
            self.total_progress.set(done / total)
        self.stats_label.configure(text=f"{done}/{total}" + (f" ({errors} lỗi)" if errors else ""))

    def clear_table(self):
        """Xóa bảng"""
        for code in list(self.task_widgets.keys()):
            if "frame" in self.task_widgets[code]:
                self.task_widgets[code]["frame"].destroy()
        self.task_widgets.clear()
        self.tasks.clear()

        # Re-add placeholder
        self.placeholder_label = ctk.CTkLabel(
            self.table_scroll,
            text="📋 Nhấn 'Tải ảnh' hoặc 'Tạo Video' để bắt đầu",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        self.placeholder_label.pack(pady=50)

        self.total_progress.set(0)
        self.stats_label.configure(text="0/0")

    # ===== TASK STATUS UPDATES =====

    def set_task_input_status(self, code: str, status: str):
        """Cập nhật trạng thái tải ảnh"""
        if code in self.tasks:
            self.tasks[code].input_status = status
            self.after_safe(lambda: self.update_task_row(code))

    def set_task_video_status(self, code: str, status: str):
        """Cập nhật trạng thái tạo video"""
        if code in self.tasks:
            self.tasks[code].video_status = status
            self.after_safe(lambda: self.update_task_row(code))

    def set_task_render_status(self, code: str, status: str):
        """Cập nhật trạng thái render"""
        if code in self.tasks:
            self.tasks[code].render_status = status
            self.after_safe(lambda: self.update_task_row(code))

    def set_task_output(self, code: str, path: Path):
        """Lưu đường dẫn output"""
        if code in self.tasks:
            self.tasks[code].output_path = path
            self.after_safe(lambda: self.update_task_row(code))

    # ===== UTILITY =====

    def add_log(self, message: str, level: str = "info"):
        """Add log message"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self):
        """Clear log"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def after_safe(self, func):
        """Thread-safe UI update"""
        self.parent.after(0, func)

    def open_output(self, code: str):
        """Mở file output"""
        if code not in self.tasks:
            return

        task = self.tasks[code]
        if not task.output_path or not task.output_path.exists():
            self.add_log(f"Không tìm thấy file: {code}")
            return

        try:
            path = str(task.output_path)
            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", path], check=False)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", "-R", path], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", str(task.output_path.parent)], check=False)
            self.add_log(f"📂 Đã mở: {task.output_path.name}")
        except Exception as e:
            self.add_log(f"Lỗi mở file: {e}")

    # ===== ACTIONS =====

    def download_shopee_images(self):
        """Tải ảnh từ Shopee"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("🛒 Bắt đầu tải ảnh Shopee...")

        thread = threading.Thread(target=self._run_shopee_download, daemon=True)
        thread.start()

    def _run_shopee_download(self):
        """Background thread tải ảnh"""
        try:
            from ...shopee_downloader import ShopeeDownloader
            from ...sheets_reader import SheetsReader

            self.after_safe(lambda: self.add_log("Kết nối Google Sheets..."))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect() or not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("❌ Không thể kết nối!"))
                return

            self.after_safe(lambda: self.add_log("✓ Đã kết nối"))

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_log("Không có sản phẩm nào"))
                return

            # Tạo tasks
            for item in pending:
                code = item["code"]
                task = TaskItem(code, item["row"])
                self.tasks[code] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

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

            self.shopee_downloader = ShopeeDownloader(
                output_dir=self.app.config.input_folder,
                chrome_path=chrome_path,
                profile_path=profile_path,
                headless=True
            )

            for item in pending:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                row_idx = item["row"] - 1
                code_folder = Path(self.app.config.input_folder) / code

                self.set_task_input_status(code, TaskItem.STATUS_RUNNING)

                # Check existing
                if code_folder.exists():
                    existing = list(code_folder.glob("*.jpg")) + list(code_folder.glob("*.png"))
                    if existing:
                        self.set_task_input_status(code, TaskItem.STATUS_SKIP)
                        self.after_safe(lambda c=code: self.add_log(f"⏭️ {c}: đã có ảnh"))
                        continue

                # Get link
                if row_idx < len(all_values):
                    row_data = all_values[row_idx]
                    link = row_data[link_col_idx] if len(row_data) > link_col_idx else ""

                    if link and "shopee" in link.lower():
                        images = self.shopee_downloader.download_from_url(
                            url=link.strip(),
                            folder_name=code,
                            skip_existing=True
                        )

                        if images:
                            self.set_task_input_status(code, TaskItem.STATUS_DONE)
                            self.after_safe(lambda c=code, n=len(images): self.add_log(f"✓ {c}: {n} ảnh"))
                        else:
                            self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                            self.after_safe(lambda c=code: self.add_log(f"❌ {c}: không tải được"))
                    else:
                        self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                        self.after_safe(lambda c=code: self.add_log(f"❌ {c}: không có link Shopee"))

            self.after_safe(lambda: self.add_log("✅ Hoàn thành tải ảnh!"))

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
        finally:
            self.after_safe(self._on_process_complete)

    def start_process(self):
        """Bắt đầu tạo video"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("▶️ Bắt đầu tạo video...")

        thread = threading.Thread(target=self._run_video_creation, daemon=True)
        thread.start()

    def _run_video_creation(self):
        """Background thread tạo video"""
        try:
            from ...sheets_reader import SheetsReader
            from ...shopee_downloader import ShopeeDownloader
            from ..workers.grok_worker import GrokWorker

            self.after_safe(lambda: self.add_log("Kết nối Google Sheets..."))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect() or not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("❌ Không thể kết nối!"))
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_log("Không có sản phẩm nào"))
                return

            # Tạo tasks
            for item in pending:
                code = item["code"]
                task = TaskItem(code, item["row"])
                self.tasks[code] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

            # === BƯỚC 1: TẢI ẢNH ===
            auto_shopee = getattr(self.app.config, 'auto_shopee', True)
            if auto_shopee:
                self.after_safe(lambda: self.add_log("🛒 Kiểm tra ảnh Shopee..."))
                self._download_missing_images(reader, pending)

            # === BƯỚC 2: TẠO VIDEO ===
            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)

            # Lọc các mã có ảnh
            valid_items = []
            for item in pending:
                code = item["code"]
                code_folder = input_folder / code
                if code_folder.exists():
                    images = list(code_folder.glob("*.jpg")) + list(code_folder.glob("*.png")) + list(code_folder.glob("*.webp"))
                    if images:
                        valid_items.append(item)
                        self.set_task_input_status(code, TaskItem.STATUS_DONE)
                    else:
                        self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                        self.after_safe(lambda c=code: self.add_log(f"⚠️ {c}: không có ảnh"))
                else:
                    self.set_task_input_status(code, TaskItem.STATUS_ERROR)

            if not valid_items:
                self.after_safe(lambda: self.add_log("Không có mã nào có ảnh!"))
                return

            # Tạo worker
            worker = GrokWorker(
                config=self.app.config,
                browser_profiles=self.app.config.browser_profiles,
                on_log=lambda msg, lvl: self.after_safe(lambda: self.add_log(msg)),
                on_progress=lambda cur, tot, msg: None,
                on_video_created=self._on_video_created,
            )

            self.current_worker = worker

            # Xử lý từng mã
            for item in valid_items:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                self.set_task_video_status(code, TaskItem.STATUS_RUNNING)
                self.after_safe(lambda c=code: self.add_log(f"🎬 Tạo video: {c}"))

                try:
                    result = worker.process_single_item(item, reader)

                    if result and result.success:
                        self.set_task_video_status(code, TaskItem.STATUS_DONE)
                        self.set_task_render_status(code, TaskItem.STATUS_DONE)

                        # Lưu output path
                        if result.output_path:
                            output_path = Path(result.output_path)
                            self.tasks[code].output_path = output_path
                            self.after_safe(lambda: self.update_task_row(code))
                            self.after_safe(lambda c=code: self.add_log(f"✅ {c}: Hoàn thành!"))
                    else:
                        self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                        self.after_safe(lambda c=code: self.add_log(f"❌ {c}: Lỗi tạo video"))

                except Exception as e:
                    self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                    self.after_safe(lambda c=code, err=str(e): self.add_log(f"❌ {c}: {err}"))

            self.after_safe(lambda: self.add_log("✅ Hoàn thành tất cả!"))

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_process_complete)

    def _download_missing_images(self, reader, pending):
        """Tải ảnh cho các mã chưa có"""
        all_values = reader.sheet.get_all_values()
        shopee_link_column = getattr(self.app.config, 'shopee_link_column', 'B')
        link_col_idx = ord(shopee_link_column.upper()) - ord('A')

        chrome_path = None
        profile_path = None
        if self.app.config.browser_profiles:
            first_profile = self.app.config.browser_profiles[0]
            chrome_path = first_profile.get("chrome_path")
            profile_path = first_profile.get("profile_path")

        from ...shopee_downloader import ShopeeDownloader
        self.shopee_downloader = ShopeeDownloader(
            output_dir=self.app.config.input_folder,
            chrome_path=chrome_path,
            profile_path=profile_path,
            headless=True
        )

        input_folder = Path(self.app.config.input_folder)

        for item in pending:
            if self.stop_flag.is_set():
                break

            code = item["code"]
            row_idx = item["row"] - 1
            code_folder = input_folder / code

            # Đã có ảnh?
            if code_folder.exists():
                existing = list(code_folder.glob("*.jpg")) + list(code_folder.glob("*.png"))
                if existing:
                    self.set_task_input_status(code, TaskItem.STATUS_SKIP)
                    continue

            self.set_task_input_status(code, TaskItem.STATUS_RUNNING)

            # Lấy link Shopee
            if row_idx < len(all_values):
                row_data = all_values[row_idx]
                link = row_data[link_col_idx] if len(row_data) > link_col_idx else ""

                if link and "shopee" in link.lower():
                    images = self.shopee_downloader.download_from_url(
                        url=link.strip(),
                        folder_name=code,
                        skip_existing=True
                    )

                    if images:
                        self.set_task_input_status(code, TaskItem.STATUS_DONE)
                        self.after_safe(lambda c=code, n=len(images): self.add_log(f"✓ {c}: {n} ảnh"))
                    else:
                        self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                else:
                    self.set_task_input_status(code, TaskItem.STATUS_ERROR)

    def _on_video_created(self, code: str, output_path: str):
        """Callback khi video được tạo"""
        if code in self.tasks:
            self.tasks[code].output_path = Path(output_path)
            self.set_task_render_status(code, TaskItem.STATUS_DONE)

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
            self.add_log("⏹️ Đang dừng...")

    def show_browser(self):
        """Toggle show/hide browser windows"""
        shown = False

        if hasattr(self, 'current_worker'):
            try:
                self.current_worker.show_all_browsers()
                shown = True
            except Exception:
                pass

        if hasattr(self, 'shopee_downloader') and self.shopee_downloader:
            try:
                self.shopee_downloader.toggle_browser_visibility()
                shown = True
            except Exception:
                pass

        if shown:
            self.add_log("👁️ Đã toggle browser")
        else:
            self.add_log("Không có browser nào đang chạy")
