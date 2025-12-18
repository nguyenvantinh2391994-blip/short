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

    # Color scheme - Modern & Professional
    COLORS = {
        # Primary colors
        "primary": "#3B82F6",        # Blue
        "primary_hover": "#2563EB",
        "success": "#10B981",        # Green
        "success_hover": "#059669",
        "warning": "#F59E0B",        # Orange/Amber
        "warning_hover": "#D97706",
        "danger": "#EF4444",         # Red
        "danger_hover": "#DC2626",

        # Background colors
        "bg_dark": "#1F2937",        # Dark gray
        "bg_card": "#374151",        # Card background
        "bg_header": "#111827",      # Header dark
        "bg_light": "#F3F4F6",       # Light mode bg

        # Text colors
        "text_primary": "#F9FAFB",   # White text
        "text_secondary": "#9CA3AF", # Gray text
        "text_dark": "#1F2937",      # Dark text for light mode

        # Status colors
        "status_pending": "#6B7280",
        "status_running": "#3B82F6",
        "status_done": "#10B981",
        "status_error": "#EF4444",
        "status_skip": "#8B5CF6",    # Purple
    }

    # Status icons với màu
    ICONS = {
        TaskItem.STATUS_PENDING: ("○", "status_pending"),
        TaskItem.STATUS_RUNNING: ("◉", "status_running"),
        TaskItem.STATUS_DONE: ("✓", "status_done"),
        TaskItem.STATUS_ERROR: ("✗", "status_error"),
        TaskItem.STATUS_SKIP: ("⊘", "status_skip"),
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

        # Row counter for alternating colors
        self.row_count = 0

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
        """Action bar - Modern style với gradient feel"""
        action_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=(self.COLORS["bg_light"], self.COLORS["bg_card"]),
            corner_radius=12
        )
        action_frame.pack(fill="x", pady=(0, 12))

        # Left: buttons
        btn_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_frame.pack(side="left", padx=15, pady=12)

        # Nút Tải ảnh - Orange/Amber
        self.shopee_btn = ctk.CTkButton(
            btn_frame,
            text="Tải ảnh Shopee",
            command=self.download_shopee_images,
            width=130,
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=self.COLORS["warning"],
            hover_color=self.COLORS["warning_hover"],
            text_color="white"
        )
        self.shopee_btn.pack(side="left", padx=(0, 10))

        # Nút Làm kịch bản - Purple
        self.script_btn = ctk.CTkButton(
            btn_frame,
            text="Làm kịch bản",
            command=self.create_scripts,
            width=120,
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#8B5CF6",  # Purple
            hover_color="#7C3AED",
            text_color="white"
        )
        self.script_btn.pack(side="left", padx=(0, 10))

        # Nút Tạo Video - Green/Success
        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="Tạo Video",
            command=self.start_process,
            width=120,
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=self.COLORS["success"],
            hover_color=self.COLORS["success_hover"],
            text_color="white"
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        # Nút Dừng - Red/Danger
        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="Dừng",
            command=self.stop_process,
            width=80,
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=self.COLORS["danger"],
            hover_color=self.COLORS["danger_hover"],
            text_color="white",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(0, 10))

        # Nút Browser - Outline style
        self.show_btn = ctk.CTkButton(
            btn_frame,
            text="Browser",
            command=self.show_browser,
            width=80,
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            border_width=2,
            border_color=self.COLORS["primary"],
            text_color=(self.COLORS["text_dark"], self.COLORS["text_primary"]),
            hover_color=(self.COLORS["bg_light"], self.COLORS["bg_dark"])
        )
        self.show_btn.pack(side="left")

        # Right: stats với style đẹp hơn
        stats_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        stats_frame.pack(side="right", padx=15, pady=12)

        # Label "Tiến độ:"
        progress_label = ctk.CTkLabel(
            stats_frame,
            text="Tiến độ:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=(self.COLORS["text_dark"], self.COLORS["text_secondary"])
        )
        progress_label.pack(side="left", padx=(0, 8))

        # Progress bar với màu đẹp
        self.total_progress = ctk.CTkProgressBar(
            stats_frame,
            width=160,
            height=14,
            corner_radius=7,
            progress_color=self.COLORS["success"],
            fg_color=(self.COLORS["bg_light"], self.COLORS["bg_dark"])
        )
        self.total_progress.pack(side="left", padx=(0, 12))
        self.total_progress.set(0)

        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="0/0",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=(self.COLORS["text_dark"], self.COLORS["success"])
        )
        self.stats_label.pack(side="left")

    def setup_progress_table(self):
        """Bảng tiến độ chi tiết - Modern card style"""
        table_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color=(self.COLORS["bg_light"], self.COLORS["bg_dark"]),
            corner_radius=12
        )
        table_frame.pack(fill="both", expand=True, pady=(0, 12))

        # Header với màu tối hơn
        header_frame = ctk.CTkFrame(
            table_frame,
            fg_color=(self.COLORS["text_dark"], self.COLORS["bg_header"]),
            height=42,
            corner_radius=0
        )
        header_frame.pack(fill="x", padx=2, pady=(2, 0))
        header_frame.pack_propagate(False)

        # Headers với style mới
        headers = [
            ("Mã sản phẩm", 130),
            ("Tải ảnh", 70),
            ("Video", 70),
            ("Render", 70),
            ("Tiến độ", 120),
            ("Mở file", 80),
        ]

        for text, width in headers:
            lbl = ctk.CTkLabel(
                header_frame,
                text=text,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                width=width,
                text_color="white"
            )
            lbl.pack(side="left", padx=8, pady=10)

        # Scrollable content với background
        self.table_scroll = ctk.CTkScrollableFrame(
            table_frame,
            fg_color="transparent",
            scrollbar_button_color=self.COLORS["primary"],
            scrollbar_button_hover_color=self.COLORS["primary_hover"]
        )
        self.table_scroll.pack(fill="both", expand=True, padx=2, pady=2)

        # Placeholder với style mới
        self.placeholder_label = ctk.CTkLabel(
            self.table_scroll,
            text="Chưa có task nào\nNhấn 'Tải ảnh Shopee' hoặc 'Tạo Video' để bắt đầu",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=self.COLORS["text_secondary"],
            justify="center"
        )
        self.placeholder_label.pack(pady=60)

    def setup_log_area(self):
        """Log area - Modern terminal style"""
        log_frame = ctk.CTkFrame(
            self.main_frame,
            height=130,
            fg_color=(self.COLORS["bg_light"], self.COLORS["bg_card"]),
            corner_radius=12
        )
        log_frame.pack(fill="x")
        log_frame.pack_propagate(False)

        # Header với style terminal
        header = ctk.CTkFrame(log_frame, fg_color="transparent", height=30)
        header.pack(fill="x", padx=12, pady=(8, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Console Output",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=(self.COLORS["text_dark"], self.COLORS["text_primary"])
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="Xóa log",
            command=self.clear_log,
            width=60,
            height=24,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            border_width=1,
            border_color=self.COLORS["text_secondary"],
            text_color=self.COLORS["text_secondary"],
            hover_color=(self.COLORS["bg_light"], self.COLORS["bg_dark"])
        ).pack(side="right")

        # Log text với style terminal
        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            height=85,
            wrap="word",
            fg_color=(self.COLORS["bg_light"], self.COLORS["bg_dark"]),
            text_color=(self.COLORS["text_dark"], "#A3E635"),  # Lime green for dark mode
            corner_radius=8
        )
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(5, 10))
        self.log_text.configure(state="disabled")
        self.add_log("Sẵn sàng! Chọn một hành động để bắt đầu.")

    # ===== TABLE MANAGEMENT =====

    def _get_status_icon_and_color(self, status: str):
        """Lấy icon và màu cho status"""
        icon_data = self.ICONS.get(status, ("?", "status_pending"))
        icon, color_key = icon_data
        color = self.COLORS.get(color_key, "#6B7280")
        return icon, color

    def add_task_row(self, task: TaskItem):
        """Thêm 1 row vào bảng - Modern style với alternating colors"""
        if self.placeholder_label.winfo_exists():
            self.placeholder_label.destroy()

        # Alternating row colors
        self.row_count += 1
        is_even = self.row_count % 2 == 0
        row_bg = ("#E5E7EB", "#2D3748") if is_even else ("#F3F4F6", "#374151")

        row_frame = ctk.CTkFrame(
            self.table_scroll,
            fg_color=row_bg,
            height=44,
            corner_radius=6
        )
        row_frame.pack(fill="x", pady=2, padx=4)
        row_frame.pack_propagate(False)

        # Mã sản phẩm - Bold và dễ nhìn
        code_lbl = ctk.CTkLabel(
            row_frame,
            text=task.code,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=130,
            anchor="w",
            text_color=(self.COLORS["text_dark"], self.COLORS["text_primary"])
        )
        code_lbl.pack(side="left", padx=8)

        # Input status với màu
        input_icon, input_color = self._get_status_icon_and_color(task.input_status)
        input_lbl = ctk.CTkLabel(
            row_frame,
            text=input_icon,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            width=70,
            text_color=input_color
        )
        input_lbl.pack(side="left", padx=5)

        # Video status với màu
        video_icon, video_color = self._get_status_icon_and_color(task.video_status)
        video_lbl = ctk.CTkLabel(
            row_frame,
            text=video_icon,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            width=70,
            text_color=video_color
        )
        video_lbl.pack(side="left", padx=5)

        # Render status với màu
        render_icon, render_color = self._get_status_icon_and_color(task.render_status)
        render_lbl = ctk.CTkLabel(
            row_frame,
            text=render_icon,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            width=70,
            text_color=render_color
        )
        render_lbl.pack(side="left", padx=5)

        # Progress bar với style mới
        progress_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=120)
        progress_frame.pack(side="left", padx=5)
        progress_frame.pack_propagate(False)

        # Determine progress color based on value
        progress_val = task.overall_progress
        if progress_val >= 100:
            prog_color = self.COLORS["success"]
        elif progress_val > 50:
            prog_color = self.COLORS["primary"]
        elif progress_val > 0:
            prog_color = self.COLORS["warning"]
        else:
            prog_color = self.COLORS["status_pending"]

        progress_bar = ctk.CTkProgressBar(
            progress_frame,
            width=90,
            height=12,
            corner_radius=6,
            progress_color=prog_color,
            fg_color=("#D1D5DB", "#4B5563")
        )
        progress_bar.pack(pady=8)
        progress_bar.set(progress_val / 100)

        progress_pct = ctk.CTkLabel(
            progress_frame,
            text=f"{progress_val}%",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            width=40,
            text_color=prog_color
        )
        progress_pct.pack()

        # Actions - Mở file button
        action_frame = ctk.CTkFrame(row_frame, fg_color="transparent", width=80)
        action_frame.pack(side="left", padx=5)

        open_btn = ctk.CTkButton(
            action_frame,
            text="Mở",
            command=lambda c=task.code: self.open_output(c),
            width=50,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=self.COLORS["primary"],
            hover_color=self.COLORS["primary_hover"],
            text_color="white",
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
        """Cập nhật UI của 1 task với màu sắc phù hợp"""
        if code not in self.tasks or code not in self.task_widgets:
            return

        task = self.tasks[code]
        widgets = self.task_widgets[code]

        # Update icons với màu
        input_icon, input_color = self._get_status_icon_and_color(task.input_status)
        widgets["input"].configure(text=input_icon, text_color=input_color)

        video_icon, video_color = self._get_status_icon_and_color(task.video_status)
        widgets["video"].configure(text=video_icon, text_color=video_color)

        render_icon, render_color = self._get_status_icon_and_color(task.render_status)
        widgets["render"].configure(text=render_icon, text_color=render_color)

        # Update progress với màu động
        progress = task.overall_progress
        if progress >= 100:
            prog_color = self.COLORS["success"]
        elif progress > 50:
            prog_color = self.COLORS["primary"]
        elif progress > 0:
            prog_color = self.COLORS["warning"]
        else:
            prog_color = self.COLORS["status_pending"]

        widgets["progress_bar"].configure(progress_color=prog_color)
        widgets["progress_bar"].set(progress / 100)
        widgets["progress_pct"].configure(text=f"{progress}%", text_color=prog_color)

        # Enable open button if complete
        if task.is_complete and task.output_path and task.output_path.exists():
            widgets["open_btn"].configure(
                state="normal",
                fg_color=self.COLORS["success"],
                hover_color=self.COLORS["success_hover"]
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
        self.row_count = 0  # Reset row counter

        # Re-add placeholder với style mới
        self.placeholder_label = ctk.CTkLabel(
            self.table_scroll,
            text="Chưa có task nào\nNhấn 'Tải ảnh Shopee' hoặc 'Tạo Video' để bắt đầu",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=self.COLORS["text_secondary"],
            justify="center"
        )
        self.placeholder_label.pack(pady=60)

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
                        # Dùng get_product_and_download để lấy cả thông tin sản phẩm
                        product, images = self.shopee_downloader.get_product_and_download(
                            url=link.strip(),
                            folder_name=code,
                            skip_existing=True
                        )

                        if images:
                            self.set_task_input_status(code, TaskItem.STATUS_DONE)
                            self.after_safe(lambda c=code, n=len(images): self.add_log(f"✓ {c}: {n} ảnh"))

                            # Ghi tên và mô tả vào sheet
                            if product:
                                try:
                                    sheet_row = item["row"]  # Row trong sheet (1-indexed)
                                    if product.name:
                                        reader.sheet.update_acell(f"C{sheet_row}", product.name)
                                        self.after_safe(lambda c=code: self.add_log(f"  ✓ Đã ghi tên vào C{sheet_row}"))
                                    if product.description:
                                        reader.sheet.update_acell(f"D{sheet_row}", product.description)
                                        self.after_safe(lambda c=code: self.add_log(f"  ✓ Đã ghi mô tả vào D{sheet_row}"))
                                except Exception as e:
                                    self.after_safe(lambda e=e: self.add_log(f"  ⚠️ Lỗi ghi sheet: {e}"))
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
                        item["images"] = images  # Thêm danh sách ảnh vào item
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
                input_folder=str(input_folder),
                output_folder=str(output_folder),
                music_folder=self.app.config.music_folder or "",
                voice_folder=self.app.config.voice_folder or "",
                config=self.app.config,
                browser_profiles=self.app.config.browser_profiles,
                stop_flag=self.stop_flag,
                on_log=lambda msg, lvl: self.after_safe(lambda: self.add_log(msg)),
                on_progress=lambda cur, tot, msg: None,
                headless=True,
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
                        error_msg = getattr(result, 'error', 'Lỗi không xác định') if result else 'Không có kết quả'
                        self.after_safe(lambda c=code, err=error_msg: self.add_log(f"❌ {c}: {err}"))

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
                    # Dùng get_product_and_download để lấy cả thông tin sản phẩm
                    product, images = self.shopee_downloader.get_product_and_download(
                        url=link.strip(),
                        folder_name=code,
                        skip_existing=True
                    )

                    if images:
                        self.set_task_input_status(code, TaskItem.STATUS_DONE)
                        self.after_safe(lambda c=code, n=len(images): self.add_log(f"✓ {c}: {n} ảnh"))

                        # Ghi tên và mô tả vào sheet
                        if product:
                            try:
                                sheet_row = item["row"]
                                if product.name:
                                    reader.sheet.update_acell(f"C{sheet_row}", product.name)
                                if product.description:
                                    reader.sheet.update_acell(f"D{sheet_row}", product.description)
                            except Exception:
                                pass
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
        toggled = False

        # Toggle GrokWorker browsers
        if hasattr(self, 'current_worker'):
            try:
                # Check trạng thái và toggle
                if hasattr(self.current_worker, '_browser_hidden') and self.current_worker._browser_hidden:
                    self.current_worker.show_all_browsers()
                    self.current_worker._browser_hidden = False
                    self.add_log("👁️ Đã hiện browser (Grok)")
                else:
                    self.current_worker.hide_all_browsers()
                    self.current_worker._browser_hidden = True
                    self.add_log("🙈 Đã ẩn browser (Grok)")
                toggled = True
            except Exception as e:
                self.add_log(f"⚠️ Lỗi toggle Grok browser: {e}")

        # Toggle Shopee browser
        if hasattr(self, 'shopee_downloader') and self.shopee_downloader:
            try:
                self.shopee_downloader.toggle_browser_visibility()
                is_hidden = getattr(self.shopee_downloader, '_is_hidden', False)
                if is_hidden:
                    self.add_log("🙈 Đã ẩn browser (Shopee)")
                else:
                    self.add_log("👁️ Đã hiện browser (Shopee)")
                toggled = True
            except Exception as e:
                self.add_log(f"⚠️ Lỗi toggle Shopee browser: {e}")

        if not toggled:
            self.add_log("Không có browser nào đang chạy")

    def create_scripts(self):
        """Tạo kịch bản và voice cho các sản phẩm"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        # Kiểm tra API key
        if not self.app.config.gemini_api_key:
            self.add_log("❌ Chưa có Gemini API key! Vào Settings để cấu hình.")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.script_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("📝 Bắt đầu tạo kịch bản và voice...")

        thread = threading.Thread(target=self._run_script_creation, daemon=True)
        thread.start()

    def _run_script_creation(self):
        """Background thread tạo kịch bản và voice"""
        try:
            from ...sheets_reader import SheetsReader
            from ...gemini_service import GeminiService

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

            # Khởi tạo Gemini service
            gemini = GeminiService(self.app.config.gemini_api_key)

            # Lấy tất cả dữ liệu từ sheet
            all_values = reader.sheet.get_all_values()
            if not all_values:
                self.after_safe(lambda: self.add_log("Sheet trống!"))
                return

            # Tạo thư mục voice
            voice_folder = Path(self.app.config.voice_folder) if self.app.config.voice_folder else Path("voice")
            voice_folder.mkdir(parents=True, exist_ok=True)

            # Column indexes
            code_col = 0  # A
            name_col = 2  # C
            desc_col = 3  # D
            script_col = 6  # G

            # Đếm sản phẩm cần xử lý
            data_rows = all_values[1:] if len(all_values) > 1 else []
            pending = []

            for row_idx, row in enumerate(data_rows, start=2):
                code = row[code_col].strip() if len(row) > code_col else ""
                name = row[name_col].strip() if len(row) > name_col else ""
                existing_script = row[script_col].strip() if len(row) > script_col else ""

                if not code or not name:
                    continue

                # Kiểm tra đã có voice chưa
                voice_path = voice_folder / f"{code}.wav"
                if voice_path.exists() and existing_script:
                    continue  # Bỏ qua nếu đã có cả voice và script

                pending.append({
                    "code": code,
                    "name": name,
                    "description": row[desc_col].strip() if len(row) > desc_col else "",
                    "row": row_idx,
                    "has_script": bool(existing_script),
                    "has_voice": voice_path.exists(),
                    "script": existing_script,
                })

            if not pending:
                self.after_safe(lambda: self.add_log("Không có sản phẩm nào cần xử lý"))
                return

            self.after_safe(lambda n=len(pending): self.add_log(f"📋 Tìm thấy {n} sản phẩm cần xử lý"))

            # Tạo tasks cho bảng tiến độ
            for item in pending:
                task = TaskItem(item["code"], item["row"])
                self.tasks[item["code"]] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

            success_count = 0
            error_count = 0

            # Xử lý từng sản phẩm
            for item in pending:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                self.set_task_input_status(code, TaskItem.STATUS_RUNNING)
                self.after_safe(lambda c=code: self.add_log(f"📝 Đang xử lý: {c}"))

                try:
                    script = item["script"]

                    # Bước 1: Tạo kịch bản (nếu chưa có)
                    if not item["has_script"]:
                        self.after_safe(lambda c=code: self.add_log(f"  Tạo kịch bản..."))
                        script_result = gemini.generate_script(
                            product_name=item["name"],
                            product_description=item["description"]
                        )

                        if script_result.success:
                            script = script_result.script
                            # Ghi vào sheet
                            try:
                                reader.sheet.update_acell(f"G{item['row']}", script)
                                self.after_safe(lambda c=code: self.add_log(f"  ✓ Đã ghi kịch bản vào G{item['row']}"))
                            except Exception as e:
                                self.after_safe(lambda e=e: self.add_log(f"  ⚠️ Lỗi ghi sheet: {e}"))
                        else:
                            self.after_safe(lambda c=code, e=script_result.error: self.add_log(f"  ❌ Lỗi kịch bản: {e}"))
                            self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                            error_count += 1
                            continue

                    self.set_task_video_status(code, TaskItem.STATUS_RUNNING)

                    # Bước 2: Tạo voice (nếu chưa có)
                    if not item["has_voice"] and script:
                        self.after_safe(lambda c=code: self.add_log(f"  Tạo voice..."))
                        voice_path = voice_folder / f"{code}.wav"
                        voice_result = gemini.generate_voice(
                            text=script,
                            output_path=str(voice_path),
                            voice_name="Aoede"  # Giọng nữ tự nhiên
                        )

                        if voice_result.success:
                            self.after_safe(lambda c=code: self.add_log(f"  ✓ Đã tạo voice: {code}.wav"))
                            self.set_task_video_status(code, TaskItem.STATUS_DONE)
                            self.set_task_render_status(code, TaskItem.STATUS_DONE)
                            success_count += 1
                        else:
                            self.after_safe(lambda c=code, e=voice_result.error: self.add_log(f"  ❌ Lỗi voice: {e}"))
                            self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                            error_count += 1
                    else:
                        # Đã có voice hoặc không có script
                        if item["has_voice"]:
                            self.after_safe(lambda c=code: self.add_log(f"  ⏭️ Đã có voice"))
                        self.set_task_video_status(code, TaskItem.STATUS_DONE)
                        self.set_task_render_status(code, TaskItem.STATUS_DONE)
                        success_count += 1

                    self.set_task_input_status(code, TaskItem.STATUS_DONE)

                    # Delay để tránh rate limit
                    import time
                    time.sleep(1)

                except Exception as e:
                    self.after_safe(lambda c=code, e=str(e): self.add_log(f"  ❌ Lỗi: {e}"))
                    self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                    error_count += 1

            # Tổng kết
            self.after_safe(lambda s=success_count, e=error_count: self.add_log(
                f"✅ Hoàn thành! Thành công: {s}, Lỗi: {e}"
            ))

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_script_complete)

    def _on_script_complete(self):
        """Callback khi hoàn thành tạo kịch bản"""
        self.is_running = False
        self.shopee_btn.configure(state="normal")
        self.script_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
