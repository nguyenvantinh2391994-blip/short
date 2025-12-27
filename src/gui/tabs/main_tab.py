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

        # Left: buttons container
        btn_container = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_container.pack(side="left", padx=15, pady=8)

        # === HÀNG TRÊN: Chạy Full, Dừng, Browser ===
        top_row = ctk.CTkFrame(btn_container, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 6))

        # Nút Chạy Full - Cyan (nổi bật)
        self.full_btn = ctk.CTkButton(
            top_row,
            text="▶ Chạy Full",
            command=self.run_full_workflow,
            width=120,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#0891B2",  # Cyan
            hover_color="#0E7490",
            text_color="white"
        )
        self.full_btn.pack(side="left", padx=(0, 8))

        # Nút Dừng - Red/Danger
        self.stop_btn = ctk.CTkButton(
            top_row,
            text="⏹ Dừng",
            command=self.stop_process,
            width=100,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=self.COLORS["danger"],
            hover_color=self.COLORS["danger_hover"],
            text_color="white",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(0, 8))

        # Nút Browser - Outline style
        self.show_btn = ctk.CTkButton(
            top_row,
            text="🌐 Browser",
            command=self.show_browser,
            width=100,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color="transparent",
            border_width=2,
            border_color=self.COLORS["primary"],
            text_color=(self.COLORS["text_dark"], self.COLORS["text_primary"]),
            hover_color=(self.COLORS["bg_light"], self.COLORS["bg_dark"])
        )
        self.show_btn.pack(side="left")

        # === HÀNG DƯỚI: Các nút lẻ ===
        bottom_row = ctk.CTkFrame(btn_container, fg_color="transparent")
        bottom_row.pack(fill="x")

        # Nút Login Shopee
        self.login_btn = ctk.CTkButton(
            bottom_row,
            text="Login",
            command=self.login_shopee,
            width=55,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#6B7280",
            hover_color="#4B5563",
            text_color="white"
        )
        self.login_btn.pack(side="left", padx=(0, 4))

        # Nút Tải ảnh
        self.shopee_btn = ctk.CTkButton(
            bottom_row,
            text="Tải ảnh",
            command=self.download_shopee_images,
            width=70,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=self.COLORS["warning"],
            hover_color=self.COLORS["warning_hover"],
            text_color="white"
        )
        self.shopee_btn.pack(side="left", padx=(0, 4))

        # Nút Tách SP (Gemini)
        self.extract_btn = ctk.CTkButton(
            bottom_row,
            text="Tách SP",
            command=self.start_extract_process,
            width=65,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#0891B2",
            hover_color="#0E7490",
            text_color="white"
        )
        self.extract_btn.pack(side="left", padx=(0, 4))

        # Nút Lọc ảnh
        self.filter_btn = ctk.CTkButton(
            bottom_row,
            text="Lọc",
            command=self.filter_images,
            width=50,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#EC4899",
            hover_color="#DB2777",
            text_color="white"
        )
        self.filter_btn.pack(side="left", padx=(0, 4))

        # Nút Làm kịch bản
        self.script_btn = ctk.CTkButton(
            bottom_row,
            text="Script",
            command=self.create_scripts,
            width=55,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#8B5CF6",
            hover_color="#7C3AED",
            text_color="white"
        )
        self.script_btn.pack(side="left", padx=(0, 4))

        # Nút Grok
        self.start_btn = ctk.CTkButton(
            bottom_row,
            text="Grok",
            command=self.start_process,
            width=55,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=self.COLORS["success"],
            hover_color=self.COLORS["success_hover"],
            text_color="white"
        )
        self.start_btn.pack(side="left", padx=(0, 4))

        # Nút SORA
        self.sora_btn = ctk.CTkButton(
            bottom_row,
            text="SORA",
            command=self.start_sora_process,
            width=55,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            text_color="white"
        )
        self.sora_btn.pack(side="left", padx=(0, 4))

        # Nút Flow
        self.flow_btn = ctk.CTkButton(
            bottom_row,
            text="Flow",
            command=self.start_flow_process,
            width=50,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#EC4899",
            hover_color="#DB2777",
            text_color="white"
        )
        self.flow_btn.pack(side="left", padx=(0, 4))

        # Nút Edit
        self.edit_btn = ctk.CTkButton(
            bottom_row,
            text="Edit",
            command=self.edit_videos,
            width=50,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#0D9488",
            hover_color="#0F766E",
            text_color="white"
        )
        self.edit_btn.pack(side="left")

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

        # Không cần placeholder - để trống cho tiến độ
        self.placeholder_label = None

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
        if self.placeholder_label and self.placeholder_label.winfo_exists():
            self.placeholder_label.destroy()
            self.placeholder_label = None

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

        # Không cần placeholder - để trống cho tiến độ
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

    def login_shopee(self):
        """Mở browser để đăng nhập Shopee và lưu cookies"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.add_log("🔐 Mở Shopee để đăng nhập...")
        self.add_log("   1. Đăng nhập tài khoản Shopee")
        self.add_log("   2. Giải captcha nếu có")
        self.add_log("   3. Bấm 'Lưu Cookies' khi xong")

        thread = threading.Thread(target=self._run_login_shopee, daemon=True)
        thread.start()

    def _run_login_shopee(self):
        """Background thread mở browser để login - dùng undetected_chromedriver"""
        try:
            import undetected_chromedriver as uc
            from ...shopee_downloader import ShopeeDownloader

            # Browser profile từ Settings
            chrome_path = None
            profile_path = None
            if self.app.config.browser_profiles:
                first_profile = self.app.config.browser_profiles[0]
                chrome_path = first_profile.get("chrome_path")
                profile_path = first_profile.get("profile_path")
                self.after_safe(lambda: self.add_log(f"📱 Dùng profile: {first_profile.get('name', 'Default')}"))

            # Tạo downloader - dùng Browser Profile từ Settings
            self.shopee_downloader = ShopeeDownloader(
                output_dir=self.app.config.input_folder,
                chrome_path=chrome_path,
                profile_path=profile_path,
                headless=not getattr(self.app.config, 'show_chrome', True)
            )

            # Dùng undetected_chromedriver để bypass captcha
            options = uc.ChromeOptions()

            # Tạo driver với undetected_chromedriver
            driver = uc.Chrome(
                options=options,
                user_data_dir=profile_path,
            )

            self.shopee_downloader.driver = driver
            driver.set_window_position(100, 100)
            driver.set_window_size(1200, 800)

            # Vào trang Shopee
            driver.get("https://shopee.vn")
            self.after_safe(lambda: self.add_log("✓ Đã mở Shopee"))
            self.after_safe(lambda: self.add_log("📌 Hãy đăng nhập và giải captcha nếu có"))

            # Đổi nút Login thành Lưu Cookies
            self.after_safe(lambda: self.login_btn.configure(
                text="Lưu",
                fg_color="#10B981",
                hover_color="#059669",
                command=self._save_shopee_cookies
            ))

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()

    def _save_shopee_cookies(self):
        """Lưu cookies và đóng browser"""
        try:
            if hasattr(self, 'shopee_downloader') and self.shopee_downloader and self.shopee_downloader.driver:
                # Lưu cookies
                self.shopee_downloader._save_cookies_to_file(self.shopee_downloader.driver)
                self.add_log("✓ Đã lưu cookies vào config/shopee_cookies.txt")

                # Đóng browser
                self.shopee_downloader.driver.quit()
                self.shopee_downloader.driver = None
                self.add_log("✓ Đã đóng browser")

            # Reset nút Login
            self.login_btn.configure(
                text="Login",
                fg_color="#6B7280",
                hover_color="#4B5563",
                command=self.login_shopee
            )

        except Exception as e:
            self.add_log(f"❌ Lỗi lưu cookies: {e}")

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

            # Tạo downloader - dùng Browser Profile từ Settings
            self.shopee_downloader = ShopeeDownloader(
                output_dir=self.app.config.input_folder,
                chrome_path=chrome_path,
                profile_path=profile_path,
                headless=not getattr(self.app.config, 'show_chrome', True)
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
            # Đóng Chrome sau khi xong tất cả sản phẩm
            if hasattr(self, 'shopee_downloader') and self.shopee_downloader:
                self.shopee_downloader.close_browser()
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

            # Lọc các mã có ảnh - lấy từ thư mục input/{code}/flow/
            valid_items = []
            for item in pending:
                code = item["code"]
                # Grok lấy ảnh từ thư mục flow (ảnh do Flow generate)
                flow_folder = input_folder / code / "flow"
                video_folder = input_folder / code / "video"

                if flow_folder.exists():
                    images = list(flow_folder.glob("*.jpg")) + list(flow_folder.glob("*.png")) + list(flow_folder.glob("*.webp"))
                    if images:
                        # === KIỂM TRA ĐÃ CÓ ĐỦ VIDEO GROK CHƯA ===
                        # Đếm video Grok (không tính SORA video 00_sora_*)
                        if video_folder.exists():
                            grok_videos = [v for v in video_folder.glob("*.mp4")
                                          if not v.name.startswith("00_sora_") and v.stat().st_size > 50000]
                            if len(grok_videos) >= len(images):
                                self.after_safe(lambda c=code, n=len(grok_videos):
                                    self.add_log(f"⏭️ {c}: Đã có {n} video Grok - bỏ qua"))
                                self.set_task_video_status(code, TaskItem.STATUS_SKIP)
                                continue

                        item["images"] = images  # Thêm danh sách ảnh vào item
                        valid_items.append(item)
                        self.set_task_input_status(code, TaskItem.STATUS_DONE)
                        self.after_safe(lambda c=code, n=len(images): self.add_log(f"  📷 {c}: {n} ảnh từ flow/"))
                    else:
                        self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                        self.after_safe(lambda c=code: self.add_log(f"⚠️ {c}: không có ảnh trong flow/"))
                else:
                    self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                    self.after_safe(lambda c=code: self.add_log(f"⚠️ {c}: chưa có thư mục flow/"))

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
                headless=not getattr(self.app.config, 'show_chrome', True),
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
            headless=not getattr(self.app.config, 'show_chrome', True)
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
        self.script_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.sora_btn.configure(state="normal")
        self.full_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    # ===== GEMINI PRODUCT EXTRACTION =====

    def start_extract_process(self):
        """Bat dau tach san pham bang Gemini"""
        if self.is_running:
            self.add_log("Dang chay task khac...")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.extract_btn.configure(state="disabled")
        self.script_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.full_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()

        self.add_log("Bat dau tach san pham (Gemini)...")

        thread = threading.Thread(target=self._run_extract_process, daemon=True)
        thread.start()

    def _run_extract_process(self):
        """Background thread tach san pham"""
        try:
            from ...sheets_reader import SheetsReader
            from ...gemini_extract import GeminiExtract, get_images_in_folder

            self.after_safe(lambda: self.add_log("Ket noi Google Sheets..."))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect() or not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("Khong the ket noi Google Sheets!"))
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_log("Khong co san pham nao can xu ly"))
                return

            self.after_safe(lambda n=len(pending): self.add_log(f"Tim thay {n} san pham"))

            # Tao tasks
            for item in pending:
                code = item["code"]
                task = TaskItem(code, item["row"])
                self.tasks[code] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

            # Lay browser profile
            chrome_path = None
            profile_path = None
            if self.app.config.browser_profiles:
                first_profile = self.app.config.browser_profiles[0]
                chrome_path = first_profile.get("chrome_path")
                profile_path = first_profile.get("profile_path")

            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)

            # Khoi tao Gemini Extract
            gemini = GeminiExtract(
                chrome_path=chrome_path,
                profile_path=profile_path,
                output_folder=str(output_folder),
                headless=not getattr(self.app.config, 'show_chrome', True),
            )
            self.current_gemini = gemini

            first_extract = True

            for item in pending:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                code_folder = input_folder / code

                # Output folder cho anh da tach
                extract_folder = code_folder / "extracted"

                # Kiểm tra xem đã tách chưa (thư mục extracted đã có ảnh)
                if extract_folder.exists():
                    existing_extracted = list(extract_folder.glob("*.png")) + list(extract_folder.glob("*.jpg")) + list(extract_folder.glob("*.webp"))
                    if existing_extracted:
                        self.after_safe(lambda c=code, n=len(existing_extracted): self.add_log(f"  {c}: Đã tách ({n} ảnh) - bỏ qua"))
                        continue

                # Lay danh sach anh
                images = get_images_in_folder(str(code_folder))
                if not images:
                    self.after_safe(lambda c=code: self.add_log(f"  {c}: Khong co anh"))
                    continue

                self.after_safe(lambda c=code, n=len(images): self.add_log(f"\n[{c}] Tach {n} anh..."))

                # Tach san pham
                if first_extract:
                    result = gemini.extract_product(
                        image_paths=images,
                        output_folder=str(extract_folder),
                        product_code=code
                    )
                    first_extract = False
                else:
                    result = gemini.extract_product_continue(
                        image_paths=images,
                        output_folder=str(extract_folder),
                        product_code=code
                    )

                if result and result.success:
                    self.after_safe(lambda c=code, n=len(result.images):
                        self.add_log(f"  {c}: Da tach {n} anh"))
                else:
                    error = result.error if result else "Loi"
                    self.after_safe(lambda c=code, e=error:
                        self.add_log(f"  {c}: {e}"))

            self.after_safe(lambda: self.add_log("\nHoan thanh tach san pham!"))

        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"Loi: {e}"))
            import traceback
            traceback.print_exc()

        finally:
            self.after_safe(self._on_extract_complete)

    def _on_extract_complete(self):
        """Callback khi hoan thanh extract"""
        self.is_running = False
        self.shopee_btn.configure(state="normal")
        self.extract_btn.configure(state="normal")
        self.script_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.full_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    # ===== SORA VIDEO CREATION =====

    def start_sora_process(self):
        """Bắt đầu tạo video bằng SORA"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.script_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.sora_btn.configure(state="disabled")
        self.full_btn.configure(state="disabled")
        self.filter_btn.configure(state="disabled")
        self.edit_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("🎬 Bắt đầu tạo video SORA...")

        thread = threading.Thread(target=self._run_sora_creation, daemon=True)
        thread.start()

    def _run_sora_creation(self):
        """Background thread tạo video SORA"""
        try:
            from ...sheets_reader import SheetsReader
            from ...sora_automation import SoraAutomation, find_sora_image

            self.after_safe(lambda: self.add_log("Kết nối Google Sheets..."))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect() or not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("❌ Không thể kết nối Google Sheets!"))
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_log("Không có sản phẩm nào cần tạo video"))
                return

            self.after_safe(lambda n=len(pending): self.add_log(f"📋 Tìm thấy {n} sản phẩm"))

            # Tạo tasks
            for item in pending:
                code = item["code"]
                task = TaskItem(code, item["row"])
                self.tasks[code] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

            # Lấy browser profile (dùng chung với Grok)
            chrome_path = None
            profile_path = None
            if self.app.config.browser_profiles:
                first_profile = self.app.config.browser_profiles[0]
                chrome_path = first_profile.get("chrome_path")
                profile_path = first_profile.get("profile_path")

            # Folder input/output
            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)

            # Khởi tạo SORA automation (dùng cài đặt show_chrome từ Settings)
            sora = SoraAutomation(
                chrome_path=chrome_path,
                profile_path=profile_path,
                output_folder=str(output_folder),
                input_folder=str(input_folder),  # Thêm input_folder
                headless=not getattr(self.app.config, 'show_chrome', True),
            )
            self.current_sora = sora  # Lưu để toggle visibility

            first_video = True  # Track xem đã mở Chrome chưa

            # Xử lý từng sản phẩm
            for item in pending:
                if self.stop_flag.is_set():
                    break

                code = item["code"]

                # === KIỂM TRA ĐÃ CÓ VIDEO SORA CHƯA ===
                video_folder = input_folder / code / "video"
                sora_video_path = video_folder / f"00_sora_{code}.mp4"
                if sora_video_path.exists() and sora_video_path.stat().st_size > 50000:
                    self.after_safe(lambda c=code: self.add_log(f"⏭️ {c}: Đã có video SORA - bỏ qua"))
                    self.set_task_video_status(code, TaskItem.STATUS_SKIP)
                    continue

                # Lấy SORA prompt từ cột F (sora_prompt) hoặc fallback về prompt thường
                sora_prompt = item.get("sora_prompt", "") or item.get("prompt", "")

                if not sora_prompt:
                    self.after_safe(lambda c=code: self.add_log(f"⚠️ {c}: Không có prompt SORA"))
                    self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                    continue

                # Tìm ảnh SORA trong folder input/{code}/extracted/
                image_path = find_sora_image(str(input_folder), code)
                if image_path:
                    self.after_safe(lambda c=code, p=Path(image_path).name:
                        self.add_log(f"  📷 {c}: Dùng ảnh {p}"))
                else:
                    self.after_safe(lambda c=code:
                        self.add_log(f"  ⚠️ {c}: Không tìm thấy ảnh trong input/{c}/extracted/"))

                self.after_safe(lambda c=code: self.add_log(f"\n🎬 [{c}] Tạo video SORA..."))
                self.set_task_video_status(code, TaskItem.STATUS_RUNNING)

                # Tạo video SORA (giống Grok)
                if first_video:
                    result = sora.create_video(
                        image_path=image_path or "",
                        prompt=sora_prompt,
                        product_code=code
                    )
                    first_video = False
                else:
                    result = sora.create_video_continue(
                        image_path=image_path or "",
                        prompt=sora_prompt,
                        product_code=code
                    )

                if result and result.success:
                    video_path = result.video_path
                    self.after_safe(lambda c=code, p=video_path:
                        self.add_log(f"  ✓ {c}: Video đã tạo - {Path(p).name}"))
                    self.set_task_video_status(code, TaskItem.STATUS_DONE)
                    self.set_task_render_status(code, TaskItem.STATUS_DONE)

                    # Cập nhật Google Sheets
                    try:
                        reader.update_status(item["row"], "DONE", self.app.config.status_column)
                    except Exception:
                        pass
                else:
                    error = result.error if result else "Timeout"
                    self.after_safe(lambda c=code, e=error:
                        self.add_log(f"  ✗ {c}: {e}"))
                    self.set_task_video_status(code, TaskItem.STATUS_ERROR)

            self.after_safe(lambda: self.add_log("\n✅ Hoàn thành SORA!"))

        except ImportError as e:
            self.after_safe(lambda: self.add_log(f"❌ Chưa có module SORA: {e}"))
            self.after_safe(lambda: self.add_log("💡 Module sora_automation.py chưa được tạo"))
        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_process_complete)

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
                    self.add_log("Đã ẩn browser (Shopee)")
                else:
                    self.add_log("Đã hiện browser (Shopee)")
                toggled = True
            except Exception as e:
                self.add_log(f"Lỗi toggle Shopee browser: {e}")

        # Toggle SORA browser
        if hasattr(self, 'current_sora') and self.current_sora:
            try:
                self.current_sora.toggle_chrome_visibility()
                is_hidden = getattr(self.current_sora, '_is_hidden', False)
                if is_hidden:
                    self.add_log("Da an browser (SORA)")
                else:
                    self.add_log("Da hien browser (SORA)")
                toggled = True
            except Exception as e:
                self.add_log(f"Loi toggle SORA browser: {e}")

        # Toggle Gemini browser
        if hasattr(self, 'current_gemini') and self.current_gemini:
            try:
                self.current_gemini.toggle_chrome_visibility()
                is_hidden = getattr(self.current_gemini, '_is_hidden', False)
                if is_hidden:
                    self.add_log("Da an browser (Gemini)")
                else:
                    self.add_log("Da hien browser (Gemini)")
                toggled = True
            except Exception as e:
                self.add_log(f"Loi toggle Gemini browser: {e}")

        if not toggled:
            self.add_log("Khong co browser nao dang chay")

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
            sora_prompt_col = 5  # F - SORA prompt
            script_col = 6  # G
            # Flow prompts columns
            img_prompt_1_col = 8   # I - Image prompt 1
            vid_prompt_1_col = 9   # J - Video prompt 1
            img_prompt_2_col = 10  # K - Image prompt 2
            vid_prompt_2_col = 11  # L - Video prompt 2

            # Đếm sản phẩm cần xử lý
            data_rows = all_values[1:] if len(all_values) > 1 else []
            pending = []

            for row_idx, row in enumerate(data_rows, start=2):
                code = row[code_col].strip() if len(row) > code_col else ""
                name = row[name_col].strip() if len(row) > name_col else ""
                existing_sora_prompt = row[sora_prompt_col].strip() if len(row) > sora_prompt_col else ""
                existing_script = row[script_col].strip() if len(row) > script_col else ""
                # Check existing flow prompts
                existing_img_1 = row[img_prompt_1_col].strip() if len(row) > img_prompt_1_col else ""
                existing_vid_1 = row[vid_prompt_1_col].strip() if len(row) > vid_prompt_1_col else ""
                existing_img_2 = row[img_prompt_2_col].strip() if len(row) > img_prompt_2_col else ""
                existing_vid_2 = row[vid_prompt_2_col].strip() if len(row) > vid_prompt_2_col else ""

                if not code or not name:
                    continue

                # Kiểm tra đã có voice chưa (check cả .wav và .mp3)
                voice_path_wav = voice_folder / f"{code}.wav"
                voice_path_mp3 = voice_folder / f"{code}.mp3"
                has_voice = voice_path_wav.exists() or voice_path_mp3.exists()

                # Kiểm tra đã có đủ flow prompts chưa
                has_all_flow_prompts = all([existing_img_1, existing_vid_1, existing_img_2, existing_vid_2])

                # Bỏ qua nếu đã có đầy đủ: voice, script, SORA prompt, flow prompts
                if has_voice and existing_script and existing_sora_prompt and has_all_flow_prompts:
                    continue

                pending.append({
                    "code": code,
                    "name": name,
                    "description": row[desc_col].strip() if len(row) > desc_col else "",
                    "row": row_idx,
                    "has_script": bool(existing_script),
                    "has_sora_prompt": bool(existing_sora_prompt),
                    "has_voice": has_voice,
                    "script": existing_script,
                    "has_flow_prompts": has_all_flow_prompts,
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
                                # Ghi SORA prompt vào cột F (nếu có)
                                if script_result.sora_prompt:
                                    reader.sheet.update_acell(f"F{item['row']}", script_result.sora_prompt)
                                    self.after_safe(lambda c=code: self.add_log(f"  ✓ Đã ghi SORA prompt vào F{item['row']}"))
                            except Exception as e:
                                self.after_safe(lambda e=e: self.add_log(f"  ⚠️ Lỗi ghi sheet: {e}"))
                        else:
                            self.after_safe(lambda c=code, e=script_result.error: self.add_log(f"  ❌ Lỗi kịch bản: {e}"))
                            self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                            error_count += 1
                            continue

                    # Bước 1b: Tạo SORA prompt riêng nếu chưa có (khi đã có script)
                    if not item.get("has_sora_prompt", False) and item["has_script"]:
                        self.after_safe(lambda c=code: self.add_log(f"  Tạo SORA prompt..."))
                        sora_prompt = gemini.generate_sora_prompt(
                            product_name=item["name"],
                            product_description=item["description"]
                        )
                        if sora_prompt:
                            try:
                                reader.sheet.update_acell(f"F{item['row']}", sora_prompt)
                                self.after_safe(lambda c=code: self.add_log(f"  ✓ Đã ghi SORA prompt vào F{item['row']}"))
                            except Exception as e:
                                self.after_safe(lambda e=e: self.add_log(f"  ⚠️ Lỗi ghi SORA prompt: {e}"))

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
                        else:
                            self.after_safe(lambda c=code, e=voice_result.error: self.add_log(f"  ❌ Lỗi voice: {e}"))
                    else:
                        if item["has_voice"]:
                            self.after_safe(lambda c=code: self.add_log(f"  ⏭️ Đã có voice"))

                    # Bước 3: Tạo Flow prompts (nếu chưa có đủ)
                    if not item.get("has_flow_prompts", False):
                        self.after_safe(lambda c=code: self.add_log(f"  Tạo Flow prompts (I, J, K, L)..."))
                        flow_prompts = gemini.generate_flow_prompts(
                            product_name=item["name"],
                            product_description=item["description"]
                        )

                        # Ghi vào sheet
                        try:
                            row_num = item['row']
                            if flow_prompts["image_prompt_1"]:
                                reader.sheet.update_acell(f"I{row_num}", flow_prompts["image_prompt_1"])
                            if flow_prompts["video_prompt_1"]:
                                reader.sheet.update_acell(f"J{row_num}", flow_prompts["video_prompt_1"])
                            if flow_prompts["image_prompt_2"]:
                                reader.sheet.update_acell(f"K{row_num}", flow_prompts["image_prompt_2"])
                            if flow_prompts["video_prompt_2"]:
                                reader.sheet.update_acell(f"L{row_num}", flow_prompts["video_prompt_2"])
                            self.after_safe(lambda c=code: self.add_log(f"  ✓ Đã ghi Flow prompts vào I, J, K, L"))
                        except Exception as e:
                            self.after_safe(lambda e=e: self.add_log(f"  ⚠️ Lỗi ghi Flow prompts: {e}"))
                    else:
                        self.after_safe(lambda c=code: self.add_log(f"  ⏭️ Đã có Flow prompts"))

                    self.set_task_video_status(code, TaskItem.STATUS_DONE)
                    self.set_task_render_status(code, TaskItem.STATUS_DONE)
                    self.set_task_input_status(code, TaskItem.STATUS_DONE)
                    success_count += 1

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
        self.full_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    # ===== FULL WORKFLOW =====

    def run_full_workflow(self):
        """Chạy full quy trình: Tải ảnh → Làm kịch bản → Tạo video"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        # Kiểm tra API key cho phần làm kịch bản
        if not self.app.config.gemini_api_key:
            self.add_log("⚠️ Chưa có Gemini API key! Sẽ bỏ qua bước làm kịch bản.")

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.script_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.full_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("🚀 Bắt đầu chạy FULL quy trình...")

        thread = threading.Thread(target=self._run_full_workflow, daemon=True)
        thread.start()

    def _run_full_workflow(self):
        """Background thread chạy full quy trình"""
        try:
            from ...sheets_reader import SheetsReader
            from ...shopee_downloader import ShopeeDownloader
            from ...gemini_service import GeminiService
            from ..workers.grok_worker import GrokWorker
            import time
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # === KẾT NỐI GOOGLE SHEETS ===
            self.after_safe(lambda: self.add_log("📊 Kết nối Google Sheets..."))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect() or not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("❌ Không thể kết nối Google Sheets!"))
                return

            self.after_safe(lambda: self.add_log("✓ Đã kết nối"))

            # Lấy danh sách sản phẩm pending
            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_log("Không có sản phẩm nào cần xử lý"))
                return

            self.after_safe(lambda n=len(pending): self.add_log(f"📋 Tìm thấy {n} sản phẩm"))

            # Tạo tasks cho bảng tiến độ
            for item in pending:
                code = item["code"]
                task = TaskItem(code, item["row"])
                self.tasks[code] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

            # === BƯỚC 1: TẢI ẢNH SHOPEE ===
            self.after_safe(lambda: self.add_log("\n" + "="*40))
            self.after_safe(lambda: self.add_log("📥 BƯỚC 1: TẢI ẢNH SHOPEE"))
            self.after_safe(lambda: self.add_log("="*40))

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
                headless=not getattr(self.app.config, 'show_chrome', True)
            )

            input_folder = Path(self.app.config.input_folder)

            for item in pending:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                row_idx = item["row"] - 1
                code_folder = input_folder / code

                self.set_task_input_status(code, TaskItem.STATUS_RUNNING)

                # Check existing images
                if code_folder.exists():
                    existing = list(code_folder.glob("*.jpg")) + list(code_folder.glob("*.png")) + list(code_folder.glob("*.webp"))
                    if existing:
                        self.set_task_input_status(code, TaskItem.STATUS_SKIP)
                        self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: đã có ảnh"))
                        continue

                # Get link and download
                if row_idx < len(all_values):
                    row_data = all_values[row_idx]
                    link = row_data[link_col_idx] if len(row_data) > link_col_idx else ""

                    if link and "shopee" in link.lower():
                        product, images = self.shopee_downloader.get_product_and_download(
                            url=link.strip(),
                            folder_name=code,
                            skip_existing=True
                        )

                        if images:
                            self.set_task_input_status(code, TaskItem.STATUS_DONE)
                            self.after_safe(lambda c=code, n=len(images): self.add_log(f"  ✓ {c}: {n} ảnh"))

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
                            self.after_safe(lambda c=code: self.add_log(f"  ❌ {c}: không tải được"))
                    else:
                        self.set_task_input_status(code, TaskItem.STATUS_ERROR)
                        self.after_safe(lambda c=code: self.add_log(f"  ❌ {c}: không có link Shopee"))

            if self.stop_flag.is_set():
                self.after_safe(lambda: self.add_log("⏹️ Đã dừng"))
                return

            # === BƯỚC 2: LỌC ẢNH ===
            if self.app.config.gemini_api_key:
                self.after_safe(lambda: self.add_log("\n" + "="*40))
                self.after_safe(lambda: self.add_log("🔍 BƯỚC 2: LỌC ẢNH"))
                self.after_safe(lambda: self.add_log("="*40))

                try:
                    from ...image_processor import ImageFilter
                    img_filter = ImageFilter(self.app.config.gemini_api_key)

                    total_kept = 0
                    total_deleted = 0

                    for item in pending:
                        if self.stop_flag.is_set():
                            break

                        code = item["code"]
                        code_folder = input_folder / code
                        if not code_folder.exists():
                            continue

                        extensions = {'.jpg', '.jpeg', '.png', '.webp'}
                        images = [f for f in code_folder.iterdir() if f.suffix.lower() in extensions]

                        if not images:
                            continue

                        self.after_safe(lambda c=code, n=len(images): self.add_log(f"  📁 {c}: {n} ảnh"))

                        for img_path in images:
                            if self.stop_flag.is_set():
                                break

                            try:
                                analysis = img_filter.analyze_image(str(img_path))

                                if analysis.should_keep:
                                    total_kept += 1
                                else:
                                    total_deleted += 1
                                    self.after_safe(lambda p=img_path.name: self.add_log(f"    ✗ Xóa: {p}"))
                                    try:
                                        img_path.unlink()
                                    except:
                                        pass

                                time.sleep(0.3)  # Rate limit
                            except Exception as e:
                                pass  # Bỏ qua lỗi, giữ ảnh

                    self.after_safe(lambda k=total_kept, d=total_deleted:
                        self.add_log(f"  ✓ Giữ: {k}, Xóa: {d}"))

                except Exception as e:
                    self.after_safe(lambda e=str(e): self.add_log(f"  ⚠️ Lỗi lọc ảnh: {e}"))
            else:
                self.after_safe(lambda: self.add_log("\n⚠️ Bỏ qua lọc ảnh - chưa có Gemini API key"))

            if self.stop_flag.is_set():
                self.after_safe(lambda: self.add_log("⏹️ Đã dừng"))
                return

            # === BƯỚC 3 & 4: CHẠY SONG SONG ===
            self.after_safe(lambda: self.add_log("\n" + "="*40))
            self.after_safe(lambda: self.add_log("🚀 BƯỚC 3 & 4: CHẠY SONG SONG"))
            self.after_safe(lambda: self.add_log("  • Thread 1: Làm kịch bản & voice"))
            self.after_safe(lambda: self.add_log("  • Thread 2: Tạo video"))
            self.after_safe(lambda: self.add_log("="*40))

            output_folder = Path(self.app.config.output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)

            # Lọc các mã có ảnh (sau khi đã lọc)
            valid_items = []
            for item in pending:
                code = item["code"]
                code_folder = input_folder / code
                if code_folder.exists():
                    images = list(code_folder.glob("*.jpg")) + list(code_folder.glob("*.png")) + list(code_folder.glob("*.webp"))
                    if images:
                        item["images"] = images
                        valid_items.append(item)

            if not valid_items:
                self.after_safe(lambda: self.add_log("  Không có mã nào có ảnh để tạo video"))
                return

            # Khởi tạo trạng thái
            voice_folder = Path(self.app.config.voice_folder) if self.app.config.voice_folder else Path("voice")
            voice_folder.mkdir(parents=True, exist_ok=True)

            # Định nghĩa hàm chạy song song cho kịch bản
            def run_script_generation():
                if not self.app.config.gemini_api_key:
                    self.after_safe(lambda: self.add_log("  [Script] ⚠️ Bỏ qua - chưa có API key"))
                    return

                gemini = GeminiService(self.app.config.gemini_api_key)

                # Refresh data từ sheet
                fresh_values = reader.sheet.get_all_values()

                for item in valid_items:
                    if self.stop_flag.is_set():
                        break

                    code = item["code"]
                    row_idx = item["row"] - 1

                    if row_idx >= len(fresh_values):
                        continue

                    row = fresh_values[row_idx]
                    name = row[2].strip() if len(row) > 2 else ""  # C
                    description = row[3].strip() if len(row) > 3 else ""  # D
                    existing_script = row[6].strip() if len(row) > 6 else ""  # G

                    if not name:
                        continue

                    # Check existing voice
                    voice_path_mp3 = voice_folder / f"{code}.mp3"
                    voice_path_wav = voice_folder / f"{code}.wav"
                    has_voice = voice_path_mp3.exists() or voice_path_wav.exists()

                    if has_voice:
                        self.after_safe(lambda c=code: self.add_log(f"  [Script] ⏭️ {c}: đã có voice"))
                        continue

                    try:
                        script = existing_script

                        # Tạo kịch bản nếu chưa có
                        if not existing_script:
                            self.after_safe(lambda c=code: self.add_log(f"  [Script] 📝 {c}: tạo kịch bản..."))
                            script_result = gemini.generate_script(name, description)

                            if script_result.success:
                                script = script_result.script
                                reader.sheet.update_acell(f"G{item['row']}", script)
                            else:
                                self.after_safe(lambda c=code, e=script_result.error: self.add_log(f"  [Script] ❌ {c}: {e}"))
                                continue

                        # Tạo voice
                        if script:
                            self.after_safe(lambda c=code: self.add_log(f"  [Script] 🎤 {c}: tạo voice..."))
                            voice_result = gemini.generate_voice(
                                text=script,
                                output_path=str(voice_folder / f"{code}.mp3"),
                                output_format="mp3"
                            )

                            if voice_result.success:
                                self.after_safe(lambda c=code: self.add_log(f"  [Script] ✓ {c}: xong voice"))
                            else:
                                self.after_safe(lambda c=code, e=voice_result.error: self.add_log(f"  [Script] ❌ {c}: {e}"))

                        time.sleep(1)  # Rate limit

                    except Exception as e:
                        self.after_safe(lambda c=code, e=str(e): self.add_log(f"  [Script] ❌ {c}: {e}"))

            # Định nghĩa hàm chạy song song cho video
            def run_video_creation():
                worker = GrokWorker(
                    input_folder=str(input_folder),
                    output_folder=str(output_folder),
                    music_folder=self.app.config.music_folder or "",
                    voice_folder=self.app.config.voice_folder or "",
                    config=self.app.config,
                    browser_profiles=self.app.config.browser_profiles,
                    stop_flag=self.stop_flag,
                    on_log=lambda msg, lvl: self.after_safe(lambda: self.add_log(f"  [Video] {msg}")),
                    on_progress=lambda cur, tot, msg: None,
                    headless=not getattr(self.app.config, 'show_chrome', True),
                )

                self.current_worker = worker

                for item in valid_items:
                    if self.stop_flag.is_set():
                        break

                    code = item["code"]
                    self.set_task_render_status(code, TaskItem.STATUS_RUNNING)

                    try:
                        result = worker.process_single_item(item, reader)

                        if result and result.success:
                            self.set_task_render_status(code, TaskItem.STATUS_DONE)
                            if result.output_path:
                                self.tasks[code].output_path = Path(result.output_path)
                                self.after_safe(lambda c=code: self.update_task_row(c))
                            self.after_safe(lambda c=code: self.add_log(f"  [Video] ✅ {c}: Hoàn thành!"))
                        else:
                            self.set_task_render_status(code, TaskItem.STATUS_ERROR)
                            error_msg = getattr(result, 'error', 'Lỗi') if result else 'Không có kết quả'
                            self.after_safe(lambda c=code, err=error_msg: self.add_log(f"  [Video] ❌ {c}: {err}"))

                    except Exception as e:
                        self.set_task_render_status(code, TaskItem.STATUS_ERROR)
                        self.after_safe(lambda c=code, err=str(e): self.add_log(f"  [Video] ❌ {c}: {err}"))

            # Chạy song song 2 luồng
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(run_script_generation),
                    executor.submit(run_video_creation)
                ]
                # Đợi tất cả hoàn thành
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi thread: {e}"))

            if self.stop_flag.is_set():
                self.after_safe(lambda: self.add_log("⏹️ Đã dừng"))
                return

            # === BƯỚC 5: SORA VIDEO (sau Grok) ===
            self.after_safe(lambda: self.add_log("\n" + "="*40))
            self.after_safe(lambda: self.add_log("🎬 BƯỚC 5: TẠO VIDEO SORA"))
            self.after_safe(lambda: self.add_log("="*40))

            try:
                from ...sora_automation import SoraAutomation, find_sora_image

                # Lấy browser profile
                chrome_path = None
                profile_path = None
                if self.app.config.browser_profiles:
                    first_profile = self.app.config.browser_profiles[0]
                    chrome_path = first_profile.get("chrome_path")
                    profile_path = first_profile.get("profile_path")

                # Khởi tạo SORA (dùng cài đặt show_chrome từ Settings)
                sora = SoraAutomation(
                    chrome_path=chrome_path,
                    profile_path=profile_path,
                    output_folder=str(output_folder),
                    headless=not getattr(self.app.config, 'show_chrome', True),
                )
                self.current_sora = sora  # Lưu để toggle visibility

                # Refresh data từ sheet
                fresh_values = reader.sheet.get_all_values()
                first_sora = True

                for item in valid_items:
                    if self.stop_flag.is_set():
                        break

                    code = item["code"]
                    row_idx = item["row"] - 1

                    if row_idx >= len(fresh_values):
                        continue

                    row = fresh_values[row_idx]
                    # Lấy SORA prompt từ cột E (index 4)
                    sora_prompt = row[4].strip() if len(row) > 4 else ""

                    if not sora_prompt:
                        self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: Không có SORA prompt"))
                        continue

                    # Tìm ảnh SORA
                    image_path = find_sora_image(str(input_folder), code)
                    if not image_path:
                        self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: Không có ảnh SORA"))
                        continue

                    self.after_safe(lambda c=code: self.add_log(f"  🎬 {c}: Tạo video SORA..."))

                    # Tạo video SORA
                    if first_sora:
                        result = sora.create_video(
                            image_path=image_path,
                            prompt=sora_prompt,
                            product_code=code
                        )
                        first_sora = False
                    else:
                        result = sora.create_video_continue(
                            image_path=image_path,
                            prompt=sora_prompt,
                            product_code=code
                        )

                    if result and result.success:
                        self.after_safe(lambda c=code: self.add_log(f"  ✓ {c}: Video SORA OK"))

                        # Re-merge với SORA video
                        self.after_safe(lambda c=code: self.add_log(f"  🔄 {c}: Re-merge với SORA..."))
                        try:
                            from ...video_merger import VideoMerger

                            merger = VideoMerger(
                                transition_type="crossfade",
                                transition_duration=0.5,
                                on_log=lambda msg: self.after_safe(lambda m=msg: self.add_log(f"    {m}"))
                            )

                            temp_folder = output_folder / "_temp_videos" / code
                            sora_video = temp_folder / f"00_sora_{code}.mp4"

                            # Lấy Grok videos (không phải SORA)
                            grok_videos = sorted([
                                str(v) for v in temp_folder.glob("*.mp4")
                                if "00_sora_" not in v.name
                            ])

                            if sora_video.exists() and grok_videos:
                                # Lấy voice
                                voice_path = None
                                if self.app.config.voice_folder:
                                    voice_folder = Path(self.app.config.voice_folder)
                                    for ext in ['.mp3', '.wav']:
                                        vp = voice_folder / f"{code}{ext}"
                                        if vp.exists():
                                            voice_path = str(vp)
                                            break

                                # Lấy music
                                music_path = None
                                if self.app.config.music_folder:
                                    from ...video_merger import get_music_for_index
                                    music_path = get_music_for_index(self.app.config.music_folder, 0)

                                final_video = output_folder / f"{code}.mp4"
                                success = merger.merge_with_sora(
                                    sora_video=str(sora_video),
                                    grok_videos=grok_videos,
                                    output_path=str(final_video),
                                    music_path=music_path,
                                    voice_path=voice_path,
                                    music_volume=0.6,
                                    voice_volume=1.0,
                                    mute_original=True
                                )
                                if success:
                                    self.after_safe(lambda c=code: self.add_log(f"  ✓ {c}: Re-merge OK"))
                        except Exception as me:
                            self.after_safe(lambda c=code, e=str(me): self.add_log(f"  ⚠️ {c}: Re-merge lỗi: {e}"))
                    else:
                        error = result.error if result else "Timeout"
                        self.after_safe(lambda c=code, e=error: self.add_log(f"  ✗ {c}: {e}"))

            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"  ⚠️ Lỗi SORA: {e}"))

            # === HOÀN THÀNH ===
            self.after_safe(lambda: self.add_log("\n" + "="*40))
            self.after_safe(lambda: self.add_log("🎉 HOÀN THÀNH TOÀN BỘ QUY TRÌNH!"))
            self.after_safe(lambda: self.add_log("="*40))

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_full_workflow_complete)

    def _on_full_workflow_complete(self):
        """Callback khi hoàn thành full workflow"""
        self.is_running = False
        self.shopee_btn.configure(state="normal")
        self.script_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.full_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    # ===== IMAGE FILTER =====

    def filter_images(self):
        """Lọc ảnh - loại ảnh ghép/collage, giữ ảnh có người"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.script_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.full_btn.configure(state="disabled")
        self.filter_btn.configure(state="disabled")
        self.edit_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.add_log("🔍 Bắt đầu lọc ảnh (loại ảnh ghép, giữ ảnh có người)...")

        thread = threading.Thread(target=self._run_image_filter, daemon=True)
        thread.start()

    def _run_image_filter(self):
        """Background thread lọc ảnh - sử dụng OpenCV/MediaPipe"""
        try:
            from ...image_filter import ImageFilter
            import shutil

            input_folder = Path(self.app.config.input_folder)
            if not input_folder.exists():
                self.after_safe(lambda: self.add_log(f"❌ Folder không tồn tại: {input_folder}"))
                return

            # Lấy tất cả subfolder (không lấy _rejected)
            folders = [f for f in input_folder.iterdir()
                      if f.is_dir() and not f.name.startswith('_')]

            if not folders:
                self.after_safe(lambda: self.add_log("Không có folder nào để lọc"))
                return

            self.after_safe(lambda n=len(folders): self.add_log(f"📁 Tìm thấy {n} folder"))

            # Khởi tạo filter (không cần API key)
            img_filter = ImageFilter(
                require_person=True,
                reject_collage=True
            )

            total_kept = 0
            total_rejected = 0

            try:
                for folder in folders:
                    if self.stop_flag.is_set():
                        break

                    # Đếm ảnh trong folder
                    extensions = {'.jpg', '.jpeg', '.png', '.webp'}
                    images = [f for f in folder.iterdir()
                             if f.suffix.lower() in extensions and not f.name.startswith('_')]

                    if not images:
                        continue

                    self.after_safe(lambda f=folder.name, n=len(images):
                        self.add_log(f"\n📁 {f}: {n} ảnh"))

                    # Tạo thư mục _rejected trong folder
                    rejected_folder = folder / "_rejected"

                    for img_path in images:
                        if self.stop_flag.is_set():
                            break

                        try:
                            result = img_filter.filter_image(str(img_path))

                            if result.should_keep:
                                total_kept += 1
                                self.after_safe(lambda p=img_path.name, r=result.reason:
                                    self.add_log(f"  ✓ {p}: {r}"))
                            else:
                                total_rejected += 1
                                self.after_safe(lambda p=img_path.name, r=result.reason:
                                    self.add_log(f"  ✗ {p}: {r}"))

                                # Di chuyển vào _rejected (không xóa)
                                try:
                                    rejected_folder.mkdir(exist_ok=True)
                                    shutil.move(str(img_path), str(rejected_folder / img_path.name))
                                    self.after_safe(lambda: self.add_log("    → Đã chuyển vào _rejected"))
                                except Exception as e:
                                    self.after_safe(lambda e=e: self.add_log(f"    → Lỗi: {e}"))

                        except Exception as e:
                            self.after_safe(lambda p=img_path.name, e=str(e):
                                self.add_log(f"  ⚠️ {p}: {e}"))

                # Tổng kết
                self.after_safe(lambda: self.add_log("\n" + "="*40))
                self.after_safe(lambda k=total_kept, r=total_rejected:
                    self.add_log(f"✅ Hoàn thành! Giữ: {k}, Loại: {r}"))
                self.after_safe(lambda: self.add_log("📂 Ảnh bị loại nằm trong thư mục _rejected"))

            finally:
                img_filter.close()

        except ImportError as e:
            self.after_safe(lambda: self.add_log(f"❌ Thiếu thư viện: {e}"))
            self.after_safe(lambda: self.add_log("💡 Chạy: pip install opencv-python mediapipe"))
        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_filter_complete)

    def _on_filter_complete(self):
        """Callback khi hoàn thành lọc ảnh"""
        self.is_running = False
        self.shopee_btn.configure(state="normal")
        self.script_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.full_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")
        self.flow_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    # ===== FLOW (Google Flow API) =====

    def start_flow_process(self):
        """Tạo ảnh biến thể với Google Flow API"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.script_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.full_btn.configure(state="disabled")
        self.filter_btn.configure(state="disabled")
        self.edit_btn.configure(state="disabled")
        self.flow_btn.configure(state="disabled")
        self.sora_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("🌀 Bắt đầu tạo ảnh Flow...")

        thread = threading.Thread(target=self._run_flow_process, daemon=True)
        thread.start()

    def _run_flow_process(self):
        """Background thread chạy Flow"""
        try:
            from ...sheets_reader import SheetsReader
            from ...chrome_token_extractor import ChromeTokenExtractor

            # === BƯỚC 1: Lấy Bearer Token từ Chrome ===
            self.after_safe(lambda: self.add_log("🔑 Đang lấy Bearer Token từ Chrome..."))

            # Lấy Chrome path và profile từ config
            chrome_path = None
            profile_path = None
            if self.app.config.browser_profiles:
                first_profile = self.app.config.browser_profiles[0]
                chrome_path = first_profile.get("chrome_path")
                profile_path = first_profile.get("profile_path")

            if not chrome_path or not profile_path:
                self.after_safe(lambda: self.add_log("❌ Chưa cấu hình Chrome Profile trong Settings!"))
                return

            # Callback để log progress
            def token_progress(msg):
                self.after_safe(lambda m=msg: self.add_log(f"   {m}"))

            # Tạo extractor và lấy token
            extractor = ChromeTokenExtractor(
                chrome_path=chrome_path,
                profile_path=profile_path,
                timeout=120
            )

            self.after_safe(lambda: self.add_log("   Đang mở Chrome và truy cập Google Flow..."))
            bearer_token, project_id, error = extractor.extract_token(callback=token_progress)

            if not bearer_token:
                self.after_safe(lambda e=error: self.add_log(f"❌ Không lấy được token: {e}"))
                return

            self.after_safe(lambda: self.add_log(f"✅ Đã lấy được token (project: {project_id or 'auto'})"))

            # === BƯỚC 2: Kết nối Google Sheets ===
            self.after_safe(lambda: self.add_log("📊 Kết nối Google Sheets..."))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect() or not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("❌ Không thể kết nối Google Sheets!"))
                return

            self.after_safe(lambda: self.add_log("✓ Đã kết nối"))

            # Lấy danh sách sản phẩm pending (với flow_prompt từ cột I và K)
            products = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column,
                flow_prompt_column="I",   # Cột I chứa Flow prompt 1
                flow_prompt_column_2="K"  # Cột K chứa Flow prompt 2
            ) or []
            if not products:
                self.after_safe(lambda: self.add_log("⚠️ Không có sản phẩm nào cần xử lý"))
                return

            self.after_safe(lambda: self.add_log(f"📋 Tìm thấy {len(products)} sản phẩm"))

            # === BƯỚC 3: Tạo ảnh với Chrome trigger + API call ===
            # Với mỗi sản phẩm: trigger Chrome để capture payload → gọi API trực tiếp
            self.after_safe(lambda: self.add_log("🌐 Sử dụng Chrome trigger + API call (bypass captcha)"))

            # Xử lý từng sản phẩm
            products_dir = Path(self.app.config.input_folder)
            processed = 0
            skipped = 0
            total = len(products)

            for i, product_data in enumerate(products, 1):
                if self.stop_flag.is_set():
                    self.after_safe(lambda: self.add_log("⏹️ Đã dừng theo yêu cầu"))
                    break

                code = product_data.get("code", "")
                flow_prompt_1 = product_data.get("flow_prompt", "")    # Prompt từ cột I
                flow_prompt_2 = product_data.get("flow_prompt_2", "")  # Prompt từ cột K

                if not code:
                    continue

                # Kiểm tra có ảnh extracted chưa
                extracted_folder = products_dir / code / "extracted"
                if not extracted_folder.exists():
                    self.after_safe(lambda c=code: self.add_log(f"  {c}: Chưa có extracted - bỏ qua"))
                    skipped += 1
                    continue

                extracted_images = list(extracted_folder.glob("*.png")) + \
                                   list(extracted_folder.glob("*.jpg")) + \
                                   list(extracted_folder.glob("*.webp"))
                if not extracted_images:
                    self.after_safe(lambda c=code: self.add_log(f"  {c}: Không có ảnh extracted - bỏ qua"))
                    skipped += 1
                    continue

                # Kiểm tra đã có đủ flow chưa (8 ảnh = 4 từ prompt I + 4 từ prompt K)
                flow_folder = products_dir / code / "flow"
                if flow_folder.exists():
                    existing_flow = list(flow_folder.glob("*.png")) + list(flow_folder.glob("*.jpg"))
                    # Cần đủ 8 ảnh (hoặc ít nhất 4 nếu chỉ có 1 prompt)
                    required_count = 8 if (flow_prompt_1 and flow_prompt_2) else 4
                    if len(existing_flow) >= required_count:
                        self.after_safe(lambda c=code, n=len(existing_flow): self.add_log(f"⏭️ {c}: Đã có {n} ảnh flow - bỏ qua"))
                        skipped += 1
                        continue

                # Log prompt nếu có
                self.after_safe(lambda c=code, i=i, t=total:
                    self.add_log(f"[{i}/{t}] 🌀 {c}: Đang tạo 8 ảnh flow (2 prompts x 4 ảnh)..."))

                try:
                    # Sử dụng Chrome trigger + API call để tạo ảnh
                    # Flow: trigger Chrome (capture payload, cancel request) → gọi API với payload

                    if not flow_prompt_1 and not flow_prompt_2:
                        self.after_safe(lambda c=code: self.add_log(f"  ⚠️ {c}: Không có prompt từ cột I và K - bỏ qua"))
                        skipped += 1
                        continue

                    # Tạo thư mục flow
                    flow_folder = products_dir / code / "flow"
                    flow_folder.mkdir(parents=True, exist_ok=True)

                    # Log callback
                    def chrome_log(msg, c=code):
                        self.after_safe(lambda m=msg: self.add_log(f"   {m}"))

                    # BƯỚC 1: Upload ảnh reference (input/<code>/extracted/<code>.png hoặc <code>_1.png)
                    image_ref = None
                    ref_image = None
                    # Thử các pattern và format ảnh khác nhau
                    patterns = [code, f"{code}_1"]  # <code>.png và <code>_1.png
                    for pattern in patterns:
                        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                            candidate = extracted_folder / f"{pattern}{ext}"
                            if candidate.exists():
                                ref_image = candidate
                                break
                        if ref_image:
                            break

                    if ref_image:
                        self.after_safe(lambda c=code, img=ref_image.name:
                            self.add_log(f"   Uploading reference: {img}"))
                        image_ref = extractor.upload_image(str(ref_image), callback=chrome_log)
                    elif extracted_images:
                        # Fallback: lấy ảnh đầu tiên trong folder
                        ref_image = extracted_images[0]
                        self.after_safe(lambda c=code, img=ref_image.name:
                            self.add_log(f"   Uploading reference (fallback): {img}"))
                        image_ref = extractor.upload_image(str(ref_image), callback=chrome_log)

                    total_downloaded = []

                    # === PROMPT 1 (Cột I) - Tạo 4 ảnh ===
                    if flow_prompt_1:
                        self.after_safe(lambda c=code: self.add_log(f"   📸 Prompt 1 (cột I): Tạo 4 ảnh..."))

                        # Trigger Chrome để capture payload
                        if extractor.trigger_and_capture(flow_prompt_1, callback=chrome_log):
                            # Gọi API với prompt 1
                            downloaded_1 = extractor.call_api_with_captured_payload(
                                custom_prompt=flow_prompt_1,
                                output_dir=flow_folder,
                                prefix=f"{code}_I",
                                image_ref=image_ref,
                                callback=chrome_log
                            )
                            if downloaded_1:
                                total_downloaded.extend(downloaded_1)
                                self.after_safe(lambda n=len(downloaded_1): self.add_log(f"   ✅ Prompt 1: {n} ảnh"))
                        else:
                            self.after_safe(lambda: self.add_log(f"   ⚠️ Prompt 1: Không capture được payload"))

                    # === PROMPT 2 (Cột K) - Tạo 4 ảnh ===
                    if flow_prompt_2:
                        self.after_safe(lambda c=code: self.add_log(f"   📸 Prompt 2 (cột K): Tạo 4 ảnh..."))

                        # Trigger Chrome để capture payload mới
                        if extractor.trigger_and_capture(flow_prompt_2, callback=chrome_log):
                            # Gọi API với prompt 2
                            downloaded_2 = extractor.call_api_with_captured_payload(
                                custom_prompt=flow_prompt_2,
                                output_dir=flow_folder,
                                prefix=f"{code}_K",
                                image_ref=image_ref,
                                callback=chrome_log
                            )
                            if downloaded_2:
                                total_downloaded.extend(downloaded_2)
                                self.after_safe(lambda n=len(downloaded_2): self.add_log(f"   ✅ Prompt 2: {n} ảnh"))
                        else:
                            self.after_safe(lambda: self.add_log(f"   ⚠️ Prompt 2: Không capture được payload"))

                    if total_downloaded:
                        processed += 1
                        self.after_safe(lambda c=code, n=len(total_downloaded):
                            self.add_log(f"  ✅ {c}: Đã tạo {n} ảnh flow"))
                    else:
                        self.after_safe(lambda c=code: self.add_log(f"  ⚠️ {c}: Không tạo được ảnh - có thể cần refresh token"))

                except Exception as e:
                    self.after_safe(lambda c=code, e=str(e):
                        self.add_log(f"  ❌ {c}: Lỗi - {e}"))

            # Thống kê
            self.after_safe(lambda: self.add_log(f"\n📊 Hoàn thành: {processed} sản phẩm, bỏ qua: {skipped}"))

        except Exception as e:
            import traceback
            error_msg = str(e)
            self.after_safe(lambda: self.add_log(f"❌ Lỗi Flow: {error_msg}"))
            traceback.print_exc()

        finally:
            self.after_safe(self._on_flow_complete)

    def _on_flow_complete(self):
        """Callback khi hoàn thành Flow"""
        self.is_running = False
        self.shopee_btn.configure(state="normal")
        self.script_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.full_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")
        self.flow_btn.configure(state="normal")
        self.sora_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.add_log("✓ Flow hoàn thành")

    # ===== EDIT VIDEOS =====

    def edit_videos(self):
        """Edit/merge video với music và voice"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.is_running = True
        self.shopee_btn.configure(state="disabled")
        self.script_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.full_btn.configure(state="disabled")
        self.filter_btn.configure(state="disabled")
        self.edit_btn.configure(state="disabled")
        self.flow_btn.configure(state="disabled")
        self.sora_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("🎬 Bắt đầu edit video...")

        thread = threading.Thread(target=self._run_edit_videos, daemon=True)
        thread.start()

    def _run_edit_videos(self):
        """Background thread edit video"""
        try:
            from ...sheets_reader import SheetsReader
            from ..workers.grok_worker import GrokWorker
            from ...video_merger import VideoMerger
            import random

            self.after_safe(lambda: self.add_log("📊 Kết nối Google Sheets..."))

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )

            if not reader.connect() or not reader.open_spreadsheet():
                self.after_safe(lambda: self.add_log("❌ Không thể kết nối Google Sheets!"))
                return

            self.after_safe(lambda: self.add_log("✓ Đã kết nối"))

            # Lấy danh sách sản phẩm pending
            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )

            if not pending:
                self.after_safe(lambda: self.add_log("Không có sản phẩm nào cần xử lý"))
                return

            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)

            music_folder = Path(self.app.config.music_folder) if self.app.config.music_folder else None
            voice_folder = Path(self.app.config.voice_folder) if self.app.config.voice_folder else None

            # Lọc các mã có video (trong input/{code}/video/)
            valid_items = []
            for item in pending:
                code = item["code"]

                # Tìm video trong input/{code}/video/
                code_video_folder = input_folder / code / "video"
                if code_video_folder.exists():
                    videos = list(code_video_folder.glob("*.mp4"))
                    if videos:
                        item["videos"] = videos
                        valid_items.append(item)
                        self.after_safe(lambda c=code, n=len(videos): self.add_log(f"  📹 {c}: {n} video"))

            if not valid_items:
                self.after_safe(lambda: self.add_log("❌ Không có video nào để edit"))
                self.after_safe(lambda: self.add_log(f"  Đã tìm trong: input/[mã]/video/"))
                self.after_safe(lambda: self.add_log("  💡 Chạy 'SORA' hoặc 'Tạo Video' trước để tạo video"))
                return

            self.after_safe(lambda n=len(valid_items): self.add_log(f"📋 Tìm thấy {n} sản phẩm có video"))

            # Tạo tasks
            for item in valid_items:
                code = item["code"]
                task = TaskItem(code, item["row"])
                self.tasks[code] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

            # Khởi tạo VideoMerger
            merger = VideoMerger()

            for item in valid_items:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                videos = item["videos"]

                self.set_task_input_status(code, TaskItem.STATUS_DONE)
                self.set_task_video_status(code, TaskItem.STATUS_RUNNING)
                self.after_safe(lambda c=code: self.add_log(f"🎬 Edit video: {c}"))

                try:
                    # Tìm voice
                    voice_path = None
                    if voice_folder:
                        for ext in ['.mp3', '.wav']:
                            vp = voice_folder / f"{code}{ext}"
                            if vp.exists():
                                voice_path = str(vp)
                                break

                    # Tìm music ngẫu nhiên
                    music_path = None
                    if music_folder and music_folder.exists():
                        music_files = list(music_folder.glob("*.mp3"))
                        if music_files:
                            music_path = str(random.choice(music_files))

                    # Tìm ảnh từ INPUT folder để thêm cuối video
                    image_paths = []
                    code_input_folder = input_folder / code
                    if code_input_folder.exists():
                        for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                            image_paths.extend([str(p) for p in code_input_folder.glob(ext)])
                        image_paths.sort()  # Sắp xếp theo tên
                        if image_paths:
                            self.after_safe(lambda c=code, n=len(image_paths): self.add_log(f"  📷 Thêm {n} ảnh cuối video"))

                    # Output path
                    final_video = output_folder / f"{code}_final.mp4"

                    # Merge videos với music/voice + ảnh cuối
                    # Nếu có voice -> nhạc 0.5, không có voice -> nhạc full (1.0)
                    music_vol = 0.5 if voice_path else 1.0

                    success = merger.merge_videos_with_images(
                        video_paths=[str(v) for v in videos],
                        image_paths=image_paths,
                        output_path=str(final_video),
                        music_path=music_path,
                        voice_path=voice_path,
                        music_volume=music_vol,
                        voice_volume=1.0,
                        mute_original=True,
                        image_duration=1.0,  # Mỗi ảnh 1 giây
                        target_width=1080,
                        target_height=1920
                    )

                    if success:
                        self.set_task_video_status(code, TaskItem.STATUS_DONE)
                        self.set_task_render_status(code, TaskItem.STATUS_DONE)
                        self.tasks[code].output_path = final_video
                        self.after_safe(lambda: self.update_task_row(code))
                        self.after_safe(lambda c=code: self.add_log(f"✅ {c}: Hoàn thành!"))

                        # Update status trong sheet
                        try:
                            status_col = self.app.config.status_column or "F"
                            reader.sheet.update_acell(f"{status_col}{item['row']}", "DONE")
                        except Exception:
                            pass
                    else:
                        self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                        self.after_safe(lambda c=code: self.add_log(f"❌ {c}: Lỗi merge video"))

                except Exception as e:
                    self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                    self.after_safe(lambda c=code, e=str(e): self.add_log(f"❌ {c}: {e}"))

            self.after_safe(lambda: self.add_log("✅ Hoàn thành edit video!"))

        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_edit_complete)

    def _on_edit_complete(self):
        """Callback khi hoàn thành edit video"""
        self.is_running = False
        self.shopee_btn.configure(state="normal")
        self.script_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.full_btn.configure(state="normal")
        self.filter_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")
        self.flow_btn.configure(state="normal")
        self.sora_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def cleanup_browsers(self):
        """Đóng tất cả browser khi thoát ứng dụng"""
        try:
            # Đóng Shopee downloader browser
            if hasattr(self, 'shopee_downloader') and self.shopee_downloader:
                if hasattr(self.shopee_downloader, 'driver') and self.shopee_downloader.driver:
                    try:
                        self.shopee_downloader.driver.quit()
                        self.shopee_downloader.driver = None
                        print("✓ Đã đóng browser Shopee")
                    except Exception as e:
                        print(f"⚠️ Lỗi đóng browser Shopee: {e}")
        except Exception as e:
            print(f"⚠️ Lỗi cleanup browsers: {e}")
