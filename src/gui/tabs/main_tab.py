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

        # Nút Lọc ảnh (sau Tải ảnh)
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

        # Dropdown chọn danh mục Script
        self.script_category_var = ctk.StringVar(value=getattr(self.app.config, 'selected_category', 'Mặc định'))
        category_names = [c.get("name", "?") for c in getattr(self.app.config, 'script_categories', [])]
        if not category_names:
            category_names = ["Mặc định"]
        self.script_category_dropdown = ctk.CTkOptionMenu(
            bottom_row,
            variable=self.script_category_var,
            values=category_names,
            width=100,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#4B5563",
            button_color="#374151",
            button_hover_color="#1F2937",
            command=self.on_script_category_changed
        )
        self.script_category_dropdown.pack(side="left", padx=(0, 2))

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

        # Nút Flow (tạo ảnh AI)
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

        # Nút SORA (tạo video từ ảnh extracted)
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

        # Nút Xóa Logo (xóa watermark Sora)
        self.clean_logo_btn = ctk.CTkButton(
            bottom_row,
            text="Xóa Logo",
            command=self.clean_sora_watermark,
            width=70,
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#DC2626",
            hover_color="#B91C1C",
            text_color="white"
        )
        self.clean_logo_btn.pack(side="left", padx=(0, 4))

        # Nút Grok (tạo video từ ảnh flow)
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

        # Nút Edit (ghép video)
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
        """Background thread mở browser để login - dùng DrissionPage hoặc undetected_chromedriver"""
        try:
            # Chọn mode dựa trên Settings
            browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
            use_drission = False

            if browser_mode == "drission":
                try:
                    from ...shopee_drission import ShopeeDrission as ShopeeDownloader
                    use_drission = True
                except ImportError:
                    from ...shopee_downloader import ShopeeDownloader
            else:
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
                headless=False  # Cần hiện browser để login
            )

            if use_drission:
                # DrissionPage - setup và navigate
                if self.shopee_downloader.setup():
                    self.shopee_downloader.manager.show_window()
                    self.shopee_downloader.manager.navigate("https://shopee.vn", wait=3)
                else:
                    self.after_safe(lambda: self.add_log("❌ Không thể khởi tạo DrissionPage"))
                    return
            else:
                # Fallback: undetected_chromedriver
                import undetected_chromedriver as uc
                options = uc.ChromeOptions()
                driver = uc.Chrome(
                    options=options,
                    user_data_dir=profile_path,
                )
                self.shopee_downloader.driver = driver
                driver.set_window_position(100, 100)
                driver.set_window_size(1200, 800)
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
            if hasattr(self, 'shopee_downloader') and self.shopee_downloader:
                # DrissionPage version
                if hasattr(self.shopee_downloader, 'manager') and self.shopee_downloader.manager:
                    self.shopee_downloader.close()
                    self.add_log("✓ Đã đóng browser (DrissionPage)")
                # Selenium/old version
                elif hasattr(self.shopee_downloader, 'driver') and self.shopee_downloader.driver:
                    self.shopee_downloader._save_cookies_to_file(self.shopee_downloader.driver)
                    self.add_log("✓ Đã lưu cookies vào config/shopee_cookies.txt")
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
            # Chọn mode dựa trên Settings
            browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
            if browser_mode == "drission":
                try:
                    from ...shopee_drission import ShopeeDrission as ShopeeDownloader
                except ImportError:
                    from ...shopee_downloader import ShopeeDownloader
            else:
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
                    existing = (list(code_folder.glob("*.jpg")) +
                               list(code_folder.glob("*.jpeg")) +
                               list(code_folder.glob("*.png")) +
                               list(code_folder.glob("*.webp")))
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
            # Chọn mode dựa trên Settings
            browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
            if browser_mode == "drission":
                try:
                    from ...shopee_drission import ShopeeDrission as ShopeeDownloader
                except ImportError:
                    from ...shopee_downloader import ShopeeDownloader
            else:
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
                    images = (list(flow_folder.glob("*.jpg")) +
                             list(flow_folder.glob("*.jpeg")) +
                             list(flow_folder.glob("*.png")) +
                             list(flow_folder.glob("*.webp")))
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
                on_log=lambda msg, lvl: self.after_safe(lambda m=msg: self.add_log(m)),
                on_progress=lambda cur, tot, msg: None,
                headless=not getattr(self.app.config, 'show_chrome', True),
            )

            self.current_worker = worker

            # === RATE LIMIT HANDLING ===
            # Track profile rate limits
            profiles = self.app.config.browser_profiles or []
            for p in profiles:
                p["rate_limited"] = False

            current_profile_idx = 0

            def get_available_profile():
                nonlocal current_profile_idx
                for i in range(len(profiles)):
                    idx = (current_profile_idx + i) % len(profiles)
                    if not profiles[idx].get("rate_limited", False):
                        current_profile_idx = idx
                        return profiles[idx]
                return None

            # Queue items
            pending_queue = list(valid_items)

            while pending_queue and not self.stop_flag.is_set():
                profile = get_available_profile()
                if not profile:
                    self.after_safe(lambda: self.add_log("❌ Tất cả profile đều bị rate limit!"))
                    break

                item = pending_queue.pop(0)
                code = item["code"]
                self.set_task_video_status(code, TaskItem.STATUS_RUNNING)
                self.after_safe(lambda c=code, p=profile.get("name", "?"):
                    self.add_log(f"🎬 Tạo video: {c} (Profile: {p})"))

                try:
                    result = worker.process_single_item(item, reader, profile)

                    if result:
                        if hasattr(result, 'error') and result.error == "RATE_LIMIT":
                            # Mark profile as rate limited
                            profile["rate_limited"] = True
                            self.after_safe(lambda p=profile.get("name"):
                                self.add_log(f"🚫 Profile '{p}' bị RATE LIMIT!"))

                            # Re-queue item
                            if hasattr(result, 'remaining_images') and result.remaining_images:
                                new_item = item.copy()
                                new_item["images"] = result.remaining_images
                                pending_queue.insert(0, new_item)
                            else:
                                pending_queue.insert(0, item)

                            # Move to next profile
                            current_profile_idx = (current_profile_idx + 1) % len(profiles)
                            continue

                        if result.success:
                            self.set_task_video_status(code, TaskItem.STATUS_DONE)
                            self.after_safe(lambda c=code: self.add_log(f"✅ {c}: Hoàn thành!"))
                        else:
                            self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                            error_msg = getattr(result, 'error', 'Lỗi') if result else 'Lỗi'
                            self.after_safe(lambda c=code, e=error_msg: self.add_log(f"❌ {c}: {e}"))

                except Exception as e:
                    self.set_task_video_status(code, TaskItem.STATUS_ERROR)
                    self.after_safe(lambda c=code, e=str(e): self.add_log(f"❌ {c}: {e}"))

            self.after_safe(lambda: self.add_log("✅ Grok hoàn thành!"))

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

        # Chọn mode dựa trên Settings
        browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
        if browser_mode == "drission":
            try:
                from ...shopee_drission import ShopeeDrission as ShopeeDownloader
            except ImportError:
                from ...shopee_downloader import ShopeeDownloader
        else:
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
                existing = (list(code_folder.glob("*.jpg")) +
                           list(code_folder.glob("*.jpeg")) +
                           list(code_folder.glob("*.png")) +
                           list(code_folder.glob("*.webp")))
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
        self.clean_logo_btn.configure(state="normal")
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

        # Get extract prompt from selected category
        all_prompts = self.get_selected_prompts()
        extract_prompt = all_prompts.get("extract") if all_prompts else None

        thread = threading.Thread(target=self._run_extract_process, args=(extract_prompt,), daemon=True)
        thread.start()

    def _run_extract_process(self, extract_prompt: str = None):
        """Background thread tach san pham"""
        try:
            from ...sheets_reader import SheetsReader
            from ...gemini_extract import GeminiExtract, get_images_in_folder
            from ...chrome_manager import chrome_manager

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

            # Lay browser profiles
            profiles = self.app.config.browser_profiles or []
            if not profiles:
                self.after_safe(lambda: self.add_log("⚠️ Chưa cấu hình Chrome profile!"))
                return

            current_profile_idx = 0
            gemini = None

            def init_gemini(profile_idx):
                """Khởi tạo GeminiExtract với profile chỉ định"""
                nonlocal gemini
                if profile_idx >= len(profiles):
                    return False

                # Đóng Chrome cũ
                chrome_manager.close_chrome()
                import time
                time.sleep(2)

                profile = profiles[profile_idx]
                chrome_path = profile.get("chrome_path")
                profile_path = profile.get("profile_path")
                self.after_safe(lambda n=profile.get("name", f"Profile {profile_idx+1}"):
                    self.add_log(f"🔄 Dùng Chrome: {n}"))

                gemini = GeminiExtract(
                    chrome_path=chrome_path,
                    profile_path=profile_path,
                    output_folder=str(Path(self.app.config.output_folder)),
                    headless=not getattr(self.app.config, 'show_chrome', True),
                    custom_extract_prompt=extract_prompt,
                )
                return True

            input_folder = Path(self.app.config.input_folder)

            # Khởi tạo với profile đầu tiên
            if not init_gemini(current_profile_idx):
                return

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
                    existing_extracted = (list(extract_folder.glob("*.png")) +
                                         list(extract_folder.glob("*.jpg")) +
                                         list(extract_folder.glob("*.jpeg")) +
                                         list(extract_folder.glob("*.webp")))
                    if existing_extracted:
                        self.after_safe(lambda c=code, n=len(existing_extracted): self.add_log(f"  {c}: Đã tách ({n} ảnh) - bỏ qua"))
                        continue

                # Lay danh sach anh
                images = get_images_in_folder(str(code_folder))
                if not images:
                    self.after_safe(lambda c=code: self.add_log(f"  {c}: Khong co anh"))
                    continue

                self.after_safe(lambda c=code, n=len(images): self.add_log(f"\n[{c}] Tach {n} anh..."))

                # Tach san pham - lấy tên sản phẩm từ cột C (index 2 trong data)
                product_name = item["data"][2] if len(item.get("data", [])) > 2 else ""

                # Retry với profile switching
                max_retries = len(profiles)
                success = False

                for retry in range(max_retries):
                    if self.stop_flag.is_set():
                        break

                    if first_extract:
                        result = gemini.extract_product(
                            image_paths=images,
                            output_folder=str(extract_folder),
                            product_code=code,
                            product_name=product_name
                        )
                        first_extract = False
                    else:
                        result = gemini.extract_product_continue(
                            image_paths=images,
                            output_folder=str(extract_folder),
                            product_code=code,
                            product_name=product_name
                        )

                    if result and result.success:
                        self.after_safe(lambda c=code, n=len(result.images):
                            self.add_log(f"  {c}: Da tach {n} anh"))
                        success = True
                        break

                    # Nếu RATE_LIMIT hoặc Timeout → switch profile
                    if result and result.error in ("RATE_LIMIT", "Timeout"):
                        self.after_safe(lambda e=result.error: self.add_log(f"  ⚠️ {e}! Đổi profile..."))
                        current_profile_idx += 1
                        if current_profile_idx < len(profiles):
                            if init_gemini(current_profile_idx):
                                self.current_gemini = gemini
                                first_extract = True  # Profile mới cần extract_product (không continue)
                                continue
                        self.after_safe(lambda: self.add_log(f"  ❌ Hết profile để thử"))
                        break
                    else:
                        # Lỗi khác
                        error = result.error if result else "Loi"
                        self.after_safe(lambda c=code, e=error:
                            self.add_log(f"  {c}: {e}"))
                        break

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
        self.clean_logo_btn.configure(state="disabled")
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
        """Background thread tạo video SORA - hỗ trợ đổi profile khi rate limit"""
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

            # Lấy TẤT CẢ browser profiles (để đổi khi rate limit)
            profiles = self.app.config.browser_profiles or []
            if not profiles:
                self.after_safe(lambda: self.add_log("❌ Chưa cấu hình browser profile!"))
                return

            # Đánh dấu profile nào bị rate limit
            for p in profiles:
                p["rate_limited"] = False

            self.after_safe(lambda n=len(profiles): self.add_log(f"🌐 Có {n} browser profile(s)"))

            # Folder input/output
            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)

            # Hàm lấy profile khả dụng
            def get_available_profile():
                available = [p for p in profiles if not p.get("rate_limited", False)]
                return available[0] if available else None

            current_profile = get_available_profile()
            if not current_profile:
                self.after_safe(lambda: self.add_log("❌ Không có profile nào khả dụng!"))
                return

            # Khởi tạo SORA automation với profile đầu tiên
            sora = SoraAutomation(
                chrome_path=current_profile.get("chrome_path"),
                profile_path=current_profile.get("profile_path"),
                output_folder=str(output_folder),
                input_folder=str(input_folder),
                headless=not getattr(self.app.config, 'show_chrome', True),
            )
            self.current_sora = sora
            self.after_safe(lambda n=current_profile.get("name", "Default"):
                self.add_log(f"🔹 Dùng profile: {n}"))

            first_video = True  # Track xem đã mở Chrome chưa

            # Queue các item cần xử lý
            pending_queue = list(pending)

            while pending_queue and not self.stop_flag.is_set():
                item = pending_queue.pop(0)
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

                # Tìm ảnh SORA (extracted/ → sora/ → code/)
                image_path = find_sora_image(str(input_folder), code)
                if image_path:
                    self.after_safe(lambda c=code, p=image_path:
                        self.add_log(f"  📷 {c}: Dùng ảnh {Path(p).name}"))
                else:
                    self.after_safe(lambda c=code:
                        self.add_log(f"  ⚠️ {c}: Không tìm thấy ảnh"))

                self.after_safe(lambda c=code: self.add_log(f"\n🎬 [{c}] Tạo video SORA..."))
                self.set_task_video_status(code, TaskItem.STATUS_RUNNING)

                # Tạo video SORA
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

                # === XỬ LÝ RATE LIMIT ===
                if result and result.error == "RATE_LIMIT":
                    self.after_safe(lambda: self.add_log(f"🚫 RATE LIMIT - Hết lượt tạo video!"))

                    # Đánh dấu profile hiện tại bị rate limit
                    current_profile["rate_limited"] = True
                    self.after_safe(lambda n=current_profile.get("name", "Default"):
                        self.add_log(f"   ❌ Profile '{n}' bị rate limit"))

                    # Thêm item lại vào đầu queue
                    pending_queue.insert(0, item)

                    # Tìm profile mới
                    new_profile = get_available_profile()
                    if not new_profile:
                        self.after_safe(lambda: self.add_log("❌ Tất cả profile đều bị rate limit!"))
                        self.after_safe(lambda: self.add_log("💡 Thêm profile mới trong Settings"))
                        break

                    # Đổi sang profile mới
                    self.after_safe(lambda n=new_profile.get("name", "Default"):
                        self.add_log(f"   ↪ Chuyển sang profile: {n}"))

                    current_profile = new_profile
                    sora = SoraAutomation(
                        chrome_path=current_profile.get("chrome_path"),
                        profile_path=current_profile.get("profile_path"),
                        output_folder=str(output_folder),
                        input_folder=str(input_folder),
                        headless=not getattr(self.app.config, 'show_chrome', True),
                    )
                    self.current_sora = sora
                    first_video = True  # Reset để mở Chrome mới
                    continue

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

            # Báo cáo profiles bị rate limit
            rate_limited = [p.get("name", "?") for p in profiles if p.get("rate_limited")]
            if rate_limited:
                self.after_safe(lambda names=rate_limited:
                    self.add_log(f"⚠️ Profiles bị rate limit: {', '.join(names)}"))

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

    # ===== SORA WATERMARK CLEANER =====

    def clean_sora_watermark(self):
        """Xóa watermark Sora từ các video đã tạo"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        self.is_running = True
        self.clean_logo_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.add_log("🧹 Bắt đầu xóa logo Sora...")

        thread = threading.Thread(target=self._run_clean_watermark, daemon=True)
        thread.start()

    def _run_clean_watermark(self):
        """Background thread xóa watermark"""
        try:
            from ...sora_watermark_cleaner import SoraWatermarkRemover

            input_folder = Path(self.app.config.input_folder)

            if not input_folder.exists():
                self.after_safe(lambda: self.add_log(f"❌ Thư mục không tồn tại: {input_folder}"))
                return

            # Khởi tạo remover
            def log_callback(msg):
                self.after_safe(lambda m=msg: self.add_log(f"   {m}"))

            remover = SoraWatermarkRemover(
                cleaner_type="lama",  # Dùng LAMA cho nhanh
                on_log=log_callback
            )

            # Đếm số video SORA cần xử lý
            sora_videos = []
            for code_folder in input_folder.iterdir():
                if not code_folder.is_dir():
                    continue

                video_folder = code_folder / "video"
                if not video_folder.exists():
                    continue

                # Tìm video SORA (chưa có _clean)
                for video in video_folder.glob("*sora*.mp4"):
                    if "_clean" not in video.stem:
                        output_path = video.parent / f"{video.stem}_clean{video.suffix}"
                        if not output_path.exists():
                            sora_videos.append((video, output_path))

            if not sora_videos:
                self.after_safe(lambda: self.add_log("⚠️ Không tìm thấy video SORA nào cần xử lý"))
                self.after_safe(lambda: self.add_log("   (Video đã xóa logo có đuôi _clean.mp4)"))
                return

            self.after_safe(lambda n=len(sora_videos): self.add_log(f"📹 Tìm thấy {n} video cần xóa logo"))

            # Xử lý từng video
            success_count = 0
            for i, (video, output) in enumerate(sora_videos, 1):
                if self.stop_flag.is_set():
                    break

                code = video.parent.parent.name
                self.after_safe(lambda c=code, idx=i, t=len(sora_videos):
                    self.add_log(f"\n[{idx}/{t}] {c}: {video.name}"))

                result = remover.clean_video(str(video), str(output))

                if result.success:
                    self.after_safe(lambda c=code: self.add_log(f"   ✓ Đã xóa logo"))
                    success_count += 1
                else:
                    self.after_safe(lambda c=code, e=result.error:
                        self.add_log(f"   ✗ Lỗi: {e}"))

            self.after_safe(lambda s=success_count, t=len(sora_videos):
                self.add_log(f"\n✅ Hoàn thành: {s}/{t} video"))

        except ImportError as e:
            self.after_safe(lambda: self.add_log(f"❌ Chưa cài đặt SoraWatermarkCleaner: {e}"))
            self.after_safe(lambda: self.add_log("💡 Cài đặt bằng lệnh:"))
            self.after_safe(lambda: self.add_log("   pip install git+https://github.com/linkedlist771/SoraWatermarkCleaner.git"))
            self.after_safe(lambda: self.add_log("📋 Yêu cầu: Python >= 3.12, FFmpeg, GPU CUDA"))
        except Exception as e:
            self.after_safe(lambda: self.add_log(f"❌ Lỗi: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after_safe(self._on_clean_complete)

    def _on_clean_complete(self):
        """Callback khi xóa logo hoàn thành"""
        self.is_running = False
        self.clean_logo_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def stop_process(self):
        """Stop current process"""
        if self.is_running:
            self.stop_flag.set()
            self.add_log("⏹️ Đang dừng...")

    def on_script_category_changed(self, selected: str):
        """Callback when script category is changed"""
        self.app.config.selected_category = selected
        self.app.save_config()
        self.add_log(f"📝 Đã chọn danh mục Script: {selected}")

    def get_selected_script_prompt(self) -> str:
        """Get the script prompt template for selected category (backward compatible)"""
        prompts = self.get_selected_prompts()
        return prompts.get("script", "") if prompts else None

    def get_selected_prompts(self) -> dict:
        """Get all prompts for selected category"""
        selected = self.script_category_var.get() if hasattr(self, 'script_category_var') else "Mặc định"
        categories = getattr(self.app.config, 'script_categories', [])

        for cat in categories:
            if cat.get("name") == selected:
                return cat.get("prompts", {})

        # Fallback to first category
        if categories:
            return categories[0].get("prompts", {})
        return {}

    def refresh_script_categories(self):
        """Refresh the script categories dropdown"""
        if hasattr(self, 'script_category_dropdown'):
            categories = getattr(self.app.config, 'script_categories', [])
            category_names = [c.get("name", "?") for c in categories]
            if not category_names:
                category_names = ["Mặc định"]
            self.script_category_dropdown.configure(values=category_names)
            # Update selection if current is not valid
            current = self.script_category_var.get()
            if current not in category_names:
                self.script_category_var.set(category_names[0])

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

        # Get all prompts from selected category before starting thread
        all_prompts = self.get_selected_prompts()
        selected_category = self.script_category_var.get() if hasattr(self, 'script_category_var') else "Mặc định"
        self.add_log(f"   Sử dụng danh mục: {selected_category}")

        thread = threading.Thread(target=self._run_script_creation, args=(all_prompts,), daemon=True)
        thread.start()

    def _run_script_creation(self, all_prompts: dict = None):
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

            # Thư mục input (voice sẽ lưu trong input/{code}/)
            input_folder = Path(self.app.config.input_folder)
            input_folder.mkdir(parents=True, exist_ok=True)

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

                # Kiểm tra đã có voice chưa (check trong input/{code}/)
                code_folder = input_folder / code
                voice_path_wav = code_folder / f"{code}.wav"
                voice_path_mp3 = code_folder / f"{code}.mp3"
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
                            product_description=item["description"],
                            custom_prompt=all_prompts.get("script") if all_prompts else None,
                            sora_custom_prompt=all_prompts.get("sora") if all_prompts else None
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

                    # Bước 2: Tạo voice (nếu chưa có) - lưu trong input/{code}/
                    if not item["has_voice"] and script:
                        self.after_safe(lambda c=code: self.add_log(f"  Tạo voice..."))
                        code_folder = input_folder / code
                        code_folder.mkdir(parents=True, exist_ok=True)
                        voice_path = code_folder / f"{code}.wav"
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
                            product_description=item["description"],
                            custom_prompts=all_prompts
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
        """Chạy full quy trình: TẢI ẢNH → LỌC → TÁCH → SCRIPT → FLOW → SORA → XÓA LOGO → GROK → EDIT"""
        if self.is_running:
            self.add_log("Đang chạy task khác...")
            return

        # Kiểm tra API key
        if not self.app.config.gemini_api_key:
            self.add_log("⚠️ Chưa có Gemini API key! Một số bước sẽ bị bỏ qua.")

        self.is_running = True
        # Disable tất cả nút
        for btn in [self.shopee_btn, self.extract_btn, self.filter_btn, self.script_btn,
                    self.flow_btn, self.sora_btn, self.clean_logo_btn, self.start_btn, self.edit_btn, self.full_btn]:
            btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("🚀 Bắt đầu chạy FULL quy trình...")
        self.add_log("📋 Thứ tự: TẢI ẢNH → LỌC → TÁCH → SCRIPT → FLOW → SORA → XÓA LOGO → GROK → EDIT")

        # Get all prompts for script generation
        all_prompts = self.get_selected_prompts()
        selected_category = self.script_category_var.get() if hasattr(self, 'script_category_var') else "Mặc định"
        self.add_log(f"   Danh mục Script: {selected_category}")

        thread = threading.Thread(target=self._run_full_workflow, args=(all_prompts,), daemon=True)
        thread.start()

    def _run_full_workflow(self, all_prompts: dict = None):
        """Background thread chạy full quy trình

        Luồng chạy TUẦN TỰ:
        1. TẢI ẢNH
        2. LỌC
        3. TÁCH SP
        4. SCRIPT
        5. FLOW
        6. SORA
        7. XÓA LOGO SORA
        8. GROK
        9. EDIT
        """
        import time

        try:
            # === BƯỚC 1: TẢI ẢNH ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n📥 BƯỚC 1/9: TẢI ẢNH\n{'='*40}"))
            try:
                self._run_shopee_download_internal()
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi tải ảnh: {e}"))
            time.sleep(1)

            # === BƯỚC 2: LỌC ẢNH ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n🔍 BƯỚC 2/9: LỌC ẢNH\n{'='*40}"))
            try:
                self._run_filter_internal()
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi lọc: {e}"))
            time.sleep(1)

            # === BƯỚC 3: TÁCH SẢN PHẨM ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n🔬 BƯỚC 3/9: TÁCH SẢN PHẨM\n{'='*40}"))
            try:
                extract_prompt = all_prompts.get("extract") if all_prompts else None
                self._run_extract_internal(extract_prompt)
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi tách SP: {e}"))
            time.sleep(1)

            # === BƯỚC 4: TẠO SCRIPT ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n📝 BƯỚC 4/9: TẠO SCRIPT\n{'='*40}"))
            try:
                self._run_script_creation_internal(all_prompts)
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi Script: {e}"))
            time.sleep(1)

            # === BƯỚC 5: TẠO ẢNH FLOW ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n🌀 BƯỚC 5/9: TẠO ẢNH FLOW\n{'='*40}"))
            try:
                self._run_flow_internal()
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi Flow: {e}"))
            time.sleep(1)

            # === BƯỚC 6: TẠO VIDEO SORA ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n🎬 BƯỚC 6/9: TẠO VIDEO SORA\n{'='*40}"))
            try:
                self._run_sora_internal()
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi SORA: {e}"))
            time.sleep(1)

            # === BƯỚC 7: XÓA LOGO SORA ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n🧹 BƯỚC 7/9: XÓA LOGO SORA\n{'='*40}"))
            try:
                self._run_clean_watermark_internal()
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi xóa logo: {e}"))
            time.sleep(1)

            # === BƯỚC 8: TẠO VIDEO GROK ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n🎥 BƯỚC 8/9: TẠO VIDEO GROK\n{'='*40}"))
            try:
                self._run_grok_internal()
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi Grok: {e}"))
            time.sleep(1)

            # === BƯỚC 9: EDIT VIDEO ===
            if self.stop_flag.is_set():
                return
            self.after_safe(lambda: self.add_log(f"\n{'='*40}\n✂️ BƯỚC 9/9: EDIT VIDEO\n{'='*40}"))
            try:
                self._run_edit_internal()
            except Exception as e:
                self.after_safe(lambda e=str(e): self.add_log(f"⚠️ Lỗi Edit: {e}"))

            self.after_safe(lambda: self.add_log("\n🎉 HOÀN THÀNH TOÀN BỘ QUY TRÌNH!"))

        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"❌ Lỗi: {e}"))
        finally:
            self.after_safe(self._on_full_workflow_complete)

    def _run_shopee_download_internal(self):
        """Chạy tải ảnh Shopee (internal - không quản lý state)"""
        from ...sheets_reader import SheetsReader
        # Chọn mode dựa trên Settings
        browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
        if browser_mode == "drission":
            try:
                from ...shopee_drission import ShopeeDrission as ShopeeDownloader
            except ImportError:
                from ...shopee_downloader import ShopeeDownloader
        else:
            from ...shopee_downloader import ShopeeDownloader
        from pathlib import Path

        reader = SheetsReader(
            credentials_file=self.app.config.credentials_file,
            spreadsheet_id=self.app.config.spreadsheet_id,
            sheet_name=self.app.config.sheet_name
        )
        if not reader.connect() or not reader.open_spreadsheet():
            self.after_safe(lambda: self.add_log("❌ Không kết nối được Sheet"))
            return

        pending = reader.get_pending_products(
            status_column=self.app.config.status_column,
            prompt_column=self.app.config.prompt_column
        )
        if not pending:
            self.after_safe(lambda: self.add_log("Không có sản phẩm nào"))
            return

        # Browser profile
        chrome_path, profile_path = None, None
        if self.app.config.browser_profiles:
            chrome_path = self.app.config.browser_profiles[0].get("chrome_path")
            profile_path = self.app.config.browser_profiles[0].get("profile_path")

        downloader = ShopeeDownloader(
            output_dir=self.app.config.input_folder,
            chrome_path=chrome_path,
            profile_path=profile_path,
            headless=not getattr(self.app.config, 'show_chrome', True)
        )

        input_folder = Path(self.app.config.input_folder)
        all_values = reader.sheet.get_all_values()
        link_col_idx = ord(getattr(self.app.config, 'shopee_link_column', 'B').upper()) - ord('A')

        for item in pending:
            if self.stop_flag.is_set():
                break
            code = item["code"]
            code_folder = input_folder / code

            # Skip nếu đã có ảnh (kiểm tra tất cả định dạng)
            if code_folder.exists():
                existing = (list(code_folder.glob("*.jpg")) +
                           list(code_folder.glob("*.jpeg")) +
                           list(code_folder.glob("*.png")) +
                           list(code_folder.glob("*.webp")))
                if existing:
                    self.after_safe(lambda c=code, n=len(existing): self.add_log(f"  ⏭️ {c}: đã có {n} ảnh"))
                    continue

            row_idx = item["row"] - 1
            if row_idx < len(all_values):
                link = all_values[row_idx][link_col_idx] if len(all_values[row_idx]) > link_col_idx else ""
                if link and "shopee" in link.lower():
                    product, images = downloader.get_product_and_download(link.strip(), code, True)
                    if images:
                        self.after_safe(lambda c=code, n=len(images): self.add_log(f"  ✓ {c}: tải {n} ảnh"))
                        if product:
                            try:
                                if product.name:
                                    reader.sheet.update_acell(f"C{item['row']}", product.name)
                                if product.description:
                                    reader.sheet.update_acell(f"D{item['row']}", product.description)
                            except:
                                pass

    def _run_extract_internal(self, extract_prompt: str = None):
        """Chạy tách sản phẩm (internal) - dùng GeminiExtract với Chrome
        Tự động chuyển Chrome profile khác khi bị rate limit
        """
        try:
            from ...gemini_extract import GeminiExtract
            from ...sheets_reader import SheetsReader
            from pathlib import Path
            import time

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )
            if not reader.connect() or not reader.open_spreadsheet():
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )
            if not pending:
                return

            input_folder = Path(self.app.config.input_folder)
            profiles = self.app.config.browser_profiles or []

            # Log số profiles để debug
            self.after_safe(lambda n=len(profiles): self.add_log(f"  📊 Có {n} Chrome profile trong cài đặt"))
            for i, p in enumerate(profiles):
                self.after_safe(lambda idx=i, name=p.get("name", "Unknown"):
                    self.add_log(f"     Profile {idx+1}: {name}"))

            if not profiles:
                self.after_safe(lambda: self.add_log("  ⚠️ Chưa cấu hình Chrome profile"))
                return

            current_profile_idx = 0
            extractor = None

            def init_extractor(profile_idx):
                """Khởi tạo extractor với profile chỉ định"""
                nonlocal extractor
                self.after_safe(lambda idx=profile_idx: self.add_log(f"  🔧 init_extractor(profile_idx={idx})"))

                if profile_idx >= len(profiles):
                    self.after_safe(lambda: self.add_log(f"  ❌ profile_idx >= len(profiles)"))
                    return False

                # Đóng Chrome cũ trước khi switch profile
                from ...chrome_manager import chrome_manager
                self.after_safe(lambda: self.add_log(f"  🔄 Đóng Chrome cũ..."))
                chrome_manager.close_chrome()
                time.sleep(2)

                profile = profiles[profile_idx]
                chrome_path = profile.get("chrome_path")
                profile_path = profile.get("profile_path")
                self.after_safe(lambda n=profile.get("name", f"Profile {profile_idx+1}"), p=profile_path:
                    self.add_log(f"  🔄 Dùng Chrome: {n} ({p})"))
                extractor = GeminiExtract(
                    chrome_path=chrome_path,
                    profile_path=profile_path,
                    headless=not getattr(self.app.config, 'show_chrome', True),
                    custom_extract_prompt=extract_prompt,
                )
                return True

            # Khởi tạo với profile đầu tiên
            if not init_extractor(current_profile_idx):
                return

            for item in pending:
                if self.stop_flag.is_set():
                    break
                code = item["code"]
                # Lấy tên sản phẩm từ cột C (index 2)
                product_name = item["data"][2] if len(item.get("data", [])) > 2 else ""
                code_folder = input_folder / code
                extracted_folder = code_folder / "extracted"

                # Skip nếu đã có ảnh extracted
                if extracted_folder.exists():
                    existing_extracted = (list(extracted_folder.glob("*.png")) +
                                         list(extracted_folder.glob("*.jpg")) +
                                         list(extracted_folder.glob("*.jpeg")) +
                                         list(extracted_folder.glob("*.webp")))
                    if existing_extracted:
                        self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: đã tách"))
                        continue

                if not code_folder.exists():
                    continue

                images = (list(code_folder.glob("*.jpg")) +
                         list(code_folder.glob("*.jpeg")) +
                         list(code_folder.glob("*.png")) +
                         list(code_folder.glob("*.webp")))
                if not images:
                    continue

                self.after_safe(lambda c=code: self.add_log(f"  🔬 {c}: đang tách..."))
                extracted_folder.mkdir(parents=True, exist_ok=True)

                for img in images[:3]:  # Tối đa 3 ảnh
                    if self.stop_flag.is_set():
                        break

                    max_profile_tries = len(profiles)
                    success = False

                    for try_count in range(max_profile_tries):
                        try:
                            result = extractor.extract_product(
                                image_paths=[str(img)],
                                output_folder=str(extracted_folder),
                                product_code=code,
                                product_name=product_name
                            )
                            if result and result.success:
                                self.after_safe(lambda c=code: self.add_log(f"    ✓ Tách xong 1 ảnh"))
                                success = True
                                break

                            # Kiểm tra nếu bị rate limit hoặc timeout → chuyển profile
                            if result and result.error in ("RATE_LIMIT", "Timeout"):
                                self.after_safe(lambda e=result.error: self.add_log(f"    ⚠️ {e}! Đổi profile..."))
                                # Thử Chrome profile khác
                                current_profile_idx += 1
                                if current_profile_idx < len(profiles):
                                    if init_extractor(current_profile_idx):
                                        time.sleep(2)
                                        continue
                                self.after_safe(lambda: self.add_log(f"    ❌ Hết profile để thử"))
                                break

                            time.sleep(1)
                        except Exception as e:
                            error_str = str(e).lower()
                            # Kiểm tra nếu bị rate limit
                            if "limit" in error_str or "quota" in error_str or "429" in error_str:
                                self.after_safe(lambda e=str(e): self.add_log(f"    ⚠️ Rate limit: {e}"))
                                # Thử Chrome profile khác
                                current_profile_idx += 1
                                if current_profile_idx < len(profiles):
                                    if init_extractor(current_profile_idx):
                                        continue
                                self.after_safe(lambda: self.add_log(f"    ❌ Hết profile để thử"))
                                break
                            else:
                                self.after_safe(lambda c=code, e=str(e): self.add_log(f"    ⚠️ Lỗi: {e}"))
                                break

        except ImportError as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ⚠️ Module GeminiExtract không có: {e}"))
        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi tách SP: {e}"))

    def _run_filter_internal(self):
        """Chạy lọc ảnh (internal) - giữ tối đa 5 ảnh mỗi sản phẩm"""
        try:
            from ...sheets_reader import SheetsReader
            from pathlib import Path

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )
            if not reader.connect() or not reader.open_spreadsheet():
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )
            if not pending:
                return

            input_folder = Path(self.app.config.input_folder)
            MAX_IMAGES = 5  # Giữ tối đa 5 ảnh

            total_codes = len(pending)
            for idx, item in enumerate(pending, 1):
                if self.stop_flag.is_set():
                    break
                code = item["code"]
                code_folder = input_folder / code
                if not code_folder.exists():
                    continue

                images = (list(code_folder.glob("*.jpg")) +
                         list(code_folder.glob("*.jpeg")) +
                         list(code_folder.glob("*.png")) +
                         list(code_folder.glob("*.webp")))

                if len(images) <= MAX_IMAGES:
                    continue  # Đã ít hơn hoặc bằng 5 ảnh, không cần lọc

                # Sắp xếp theo thời gian sửa đổi (mới nhất trước)
                images.sort(key=lambda x: x.stat().st_mtime, reverse=True)

                # Xóa các ảnh thừa (giữ 5 ảnh đầu)
                to_delete = images[MAX_IMAGES:]
                for img in to_delete:
                    try:
                        img.unlink()
                    except:
                        pass

                self.after_safe(lambda c=code, i=idx, t=total_codes, d=len(to_delete):
                    self.add_log(f"  [{i}/{t}] {c}: xóa {d} ảnh (giữ {MAX_IMAGES})"))

            self.after_safe(lambda: self.add_log("  ✓ Lọc xong"))
        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ⚠️ Lỗi lọc: {e}"))

    def _run_script_creation_internal(self, all_prompts: dict = None):
        """Chạy tạo script (internal)"""
        try:
            from ...gemini_service import GeminiService
            from ...sheets_reader import SheetsReader
            from pathlib import Path
            import time

            if not self.app.config.gemini_api_key:
                self.after_safe(lambda: self.add_log("  ⚠️ Chưa có Gemini API - bỏ qua"))
                return

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )
            if not reader.connect() or not reader.open_spreadsheet():
                return

            gemini = GeminiService(self.app.config.gemini_api_key)
            input_folder = Path(self.app.config.input_folder)
            input_folder.mkdir(parents=True, exist_ok=True)

            all_values = reader.sheet.get_all_values()
            for row_idx, row in enumerate(all_values[1:], start=2):
                if self.stop_flag.is_set():
                    break

                code = row[0].strip() if row else ""
                name = row[2].strip() if len(row) > 2 else ""
                desc = row[3].strip() if len(row) > 3 else ""
                script = row[6].strip() if len(row) > 6 else ""

                if not code or not name:
                    continue

                # Check voice trong input/{code}/
                code_folder = input_folder / code
                has_voice = (code_folder / f"{code}.mp3").exists() or (code_folder / f"{code}.wav").exists()
                if has_voice and script:
                    continue

                self.after_safe(lambda c=code: self.add_log(f"  📝 {c}..."))

                # Tạo script nếu chưa có
                if not script:
                    result = gemini.generate_script(
                        name, desc,
                        custom_prompt=all_prompts.get("script") if all_prompts else None,
                        sora_custom_prompt=all_prompts.get("sora") if all_prompts else None
                    )
                    if result.success:
                        script = result.script
                        reader.sheet.update_acell(f"G{row_idx}", script)
                        if result.sora_prompt:
                            reader.sheet.update_acell(f"F{row_idx}", result.sora_prompt)

                # Tạo voice nếu chưa có - lưu trong input/{code}/
                if script and not has_voice:
                    code_folder.mkdir(parents=True, exist_ok=True)
                    voice_result = gemini.generate_voice(script, str(code_folder / f"{code}.mp3"))
                    if voice_result.success:
                        self.after_safe(lambda c=code: self.add_log(f"    ✓ Voice xong"))

                time.sleep(1)
        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi: {e}"))

    def _run_flow_internal(self):
        """Chạy Flow tạo ảnh (internal) - có retry và chuyển Chrome khi rate limit"""
        import time

        MAX_RETRIES = 5
        RETRY_DELAY = 30  # giây

        try:
            # Chọn mode dựa trên Settings
            browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
            if browser_mode == "drission":
                try:
                    from ...flow_drission import FlowDrission as ChromeTokenExtractor
                except ImportError:
                    from ...chrome_token_extractor import ChromeTokenExtractor
            else:
                from ...chrome_token_extractor import ChromeTokenExtractor
            from ...sheets_reader import SheetsReader
            from pathlib import Path

            profiles = self.app.config.browser_profiles or []
            if not profiles:
                self.after_safe(lambda: self.add_log("  ⚠️ Chưa cấu hình Chrome - bỏ qua"))
                return

            current_profile_idx = 0

            def get_current_profile():
                if current_profile_idx < len(profiles):
                    return profiles[current_profile_idx]
                return None

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )
            if not reader.connect() or not reader.open_spreadsheet():
                return

            products = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column,
                flow_prompt_column="I",
                flow_prompt_column_2="K"
            )
            if not products:
                return

            input_folder = Path(self.app.config.input_folder)

            # Hàm kiểm tra sản phẩm còn thiếu ảnh
            def get_missing_products():
                missing = []
                for product in products:
                    code = product.get("code", "")
                    flow_prompt_1 = product.get("flow_prompt", "")
                    flow_prompt_2 = product.get("flow_prompt_2", "")

                    if not code or (not flow_prompt_1 and not flow_prompt_2):
                        continue

                    flow_folder = input_folder / code / "flow"
                    extracted_folder = input_folder / code / "extracted"

                    if not extracted_folder.exists():
                        continue

                    # Kiểm tra số ảnh cần có
                    required = 8 if (flow_prompt_1 and flow_prompt_2) else 4
                    existing = []
                    if flow_folder.exists():
                        existing = (list(flow_folder.glob("*.png")) +
                                   list(flow_folder.glob("*.jpg")) +
                                   list(flow_folder.glob("*.jpeg")) +
                                   list(flow_folder.glob("*.webp")))

                    if len(existing) < required:
                        missing.append(product)

                return missing

            # Retry loop - chuyển Chrome khi rate limit
            for attempt in range(MAX_RETRIES + 1):
                if self.stop_flag.is_set():
                    break

                # Lấy danh sách sản phẩm còn thiếu ảnh
                missing_products = get_missing_products()

                if not missing_products:
                    self.after_safe(lambda: self.add_log("  ✅ Tất cả sản phẩm đã có đủ ảnh Flow"))
                    break

                if attempt > 0:
                    self.after_safe(lambda a=attempt, n=len(missing_products):
                        self.add_log(f"  🔄 Retry {a}/{MAX_RETRIES}: còn {n} sản phẩm thiếu ảnh"))
                    time.sleep(RETRY_DELAY)

                # Lấy Chrome profile hiện tại
                profile = get_current_profile()
                if not profile:
                    self.after_safe(lambda: self.add_log("  ❌ Hết Chrome profile để thử"))
                    break

                chrome_path = profile.get("chrome_path")
                profile_path = profile.get("profile_path")
                profile_name = profile.get("name", f"Profile {current_profile_idx + 1}")
                self.after_safe(lambda n=profile_name: self.add_log(f"  🔄 Dùng Chrome: {n}"))

                # Lấy token mới cho mỗi lần thử
                extractor = ChromeTokenExtractor(chrome_path, profile_path, timeout=120)
                self.after_safe(lambda: self.add_log("  Đang lấy token..."))
                bearer_token, project_id, error = extractor.extract_token()
                if not bearer_token:
                    error_lower = error.lower() if error else ""
                    if "limit" in error_lower or "quota" in error_lower or "429" in error_lower:
                        self.after_safe(lambda e=error: self.add_log(f"  ⚠️ Rate limit: {e}"))
                        current_profile_idx += 1
                        continue
                    self.after_safe(lambda e=error: self.add_log(f"  ⚠️ Không lấy được token: {e}"))
                    continue

                # Xử lý từng sản phẩm thiếu ảnh
                rate_limited = False
                for product in missing_products:
                    if self.stop_flag.is_set() or rate_limited:
                        break

                    code = product.get("code", "")
                    flow_prompt_1 = product.get("flow_prompt", "")
                    flow_prompt_2 = product.get("flow_prompt_2", "")

                    flow_folder = input_folder / code / "flow"
                    extracted_folder = input_folder / code / "extracted"

                    self.after_safe(lambda c=code: self.add_log(f"  🌀 {c}: tạo ảnh flow..."))
                    flow_folder.mkdir(parents=True, exist_ok=True)

                    # Upload reference image
                    ref_images = (list(extracted_folder.glob("*.png")) +
                                 list(extracted_folder.glob("*.jpg")) +
                                 list(extracted_folder.glob("*.jpeg")) +
                                 list(extracted_folder.glob("*.webp")))
                    image_ref = None
                    if ref_images:
                        image_ref = extractor.upload_image(str(ref_images[0]))

                    # Tạo ảnh với mỗi prompt
                    def chrome_log(msg):
                        self.after_safe(lambda m=msg: self.add_log(f"    {m}"))
                        # Kiểm tra rate limit trong log
                        if "limit" in msg.lower() or "quota" in msg.lower() or "429" in msg.lower():
                            nonlocal rate_limited, current_profile_idx
                            rate_limited = True
                            current_profile_idx += 1

                    for i, prompt in enumerate([flow_prompt_1, flow_prompt_2], 1):
                        if not prompt or self.stop_flag.is_set() or rate_limited:
                            continue

                        prefix = f"{code}_I" if i == 1 else f"{code}_K"

                        # Kiểm tra đã có đủ ảnh cho prompt này chưa
                        existing_for_prefix = (list(flow_folder.glob(f"{prefix}*.png")) +
                                              list(flow_folder.glob(f"{prefix}*.jpg")) +
                                              list(flow_folder.glob(f"{prefix}*.jpeg")) +
                                              list(flow_folder.glob(f"{prefix}*.webp")))
                        if len(existing_for_prefix) >= 4:
                            continue

                        try:
                            if extractor.trigger_and_capture(prompt, callback=chrome_log):
                                result = extractor.call_api_with_captured_payload(
                                    custom_prompt=prompt,
                                    output_dir=flow_folder,
                                    prefix=prefix,
                                    image_ref=image_ref,
                                    callback=chrome_log
                                )
                                # Nếu không có kết quả, có thể bị rate limit
                                if not result:
                                    rate_limited = True
                                    current_profile_idx += 1
                        except Exception as e:
                            error_str = str(e).lower()
                            if "limit" in error_str or "quota" in error_str or "429" in error_str:
                                self.after_safe(lambda e=str(e): self.add_log(f"    ⚠️ Rate limit: {e}"))
                                rate_limited = True
                                current_profile_idx += 1
                                break

                if rate_limited:
                    self.after_safe(lambda: self.add_log("  🔄 Chuyển sang Chrome profile khác..."))

            # Báo cáo cuối
            final_missing = get_missing_products()
            if final_missing:
                self.after_safe(lambda n=len(final_missing):
                    self.add_log(f"  ⚠️ Vẫn còn {n} sản phẩm thiếu ảnh sau {MAX_RETRIES} lần thử"))
            else:
                self.after_safe(lambda: self.add_log("  ✅ Đã tạo đủ ảnh Flow cho tất cả sản phẩm"))

        except ImportError:
            self.after_safe(lambda: self.add_log("  ⚠️ Module ChromeTokenExtractor không có"))
        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi: {e}"))

    def _run_sora_internal(self):
        """Chạy SORA tạo video (internal) - chuyển Chrome khi rate limit"""
        try:
            from ...sora_automation import SoraAutomation, find_sora_image
            from ...sheets_reader import SheetsReader
            from pathlib import Path

            profiles = self.app.config.browser_profiles or []
            if not profiles:
                self.after_safe(lambda: self.add_log("  ⚠️ Chưa cấu hình Chrome"))
                return

            current_profile_idx = 0
            sora = None

            def init_sora(profile_idx):
                """Khởi tạo SORA với profile chỉ định"""
                nonlocal sora
                if profile_idx >= len(profiles):
                    return False
                profile = profiles[profile_idx]
                chrome_path = profile.get("chrome_path")
                profile_path = profile.get("profile_path")
                profile_name = profile.get("name", f"Profile {profile_idx + 1}")
                self.after_safe(lambda n=profile_name: self.add_log(f"  🔄 SORA dùng Chrome: {n}"))
                sora = SoraAutomation(
                    chrome_path=chrome_path,
                    profile_path=profile_path,
                    output_folder=str(output_folder),
                    input_folder=str(input_folder),
                    headless=not getattr(self.app.config, 'show_chrome', True)
                )
                return True

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )
            if not reader.connect() or not reader.open_spreadsheet():
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )
            if not pending:
                return

            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)

            # Khởi tạo với profile đầu tiên
            if not init_sora(current_profile_idx):
                return

            first_video = True
            for item in pending:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                sora_prompt = item.get("sora_prompt", "") or item.get("prompt", "")

                # Skip nếu đã có video
                video_folder = input_folder / code / "video"
                if (video_folder / f"00_sora_{code}.mp4").exists():
                    self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: đã có video SORA"))
                    continue

                if not sora_prompt:
                    continue

                image_path = find_sora_image(str(input_folder), code)
                if not image_path:
                    continue

                self.after_safe(lambda c=code: self.add_log(f"  🎬 {c}: tạo video SORA..."))

                # Thử tạo video, chuyển profile nếu rate limit
                max_tries = len(profiles)
                for try_count in range(max_tries):
                    try:
                        if first_video:
                            result = sora.create_video(image_path, sora_prompt, code)
                            first_video = False
                        else:
                            result = sora.create_video_continue(image_path, sora_prompt, code)

                        if result and result.success:
                            self.after_safe(lambda c=code: self.add_log(f"    ✓ {c}: SORA xong"))
                            break
                        elif result and hasattr(result, 'error'):
                            error_str = str(result.error).lower()
                            if "limit" in error_str or "quota" in error_str or "429" in error_str:
                                current_profile_idx += 1
                                if init_sora(current_profile_idx):
                                    first_video = True  # Reset cho profile mới
                                    continue
                            break
                        else:
                            break
                    except Exception as e:
                        error_str = str(e).lower()
                        if "limit" in error_str or "quota" in error_str or "429" in error_str:
                            self.after_safe(lambda e=str(e): self.add_log(f"    ⚠️ Rate limit: {e}"))
                            current_profile_idx += 1
                            if init_sora(current_profile_idx):
                                first_video = True
                                continue
                        self.after_safe(lambda e=str(e): self.add_log(f"    ⚠️ Lỗi: {e}"))
                        break

        except ImportError:
            self.after_safe(lambda: self.add_log("  ⚠️ Module SoraAutomation không có"))
        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi: {e}"))

    def _run_grok_internal(self):
        """Chạy Grok tạo video (internal)"""
        try:
            from ..workers.grok_worker import GrokWorker
            from ...sheets_reader import SheetsReader
            from pathlib import Path

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )
            if not reader.connect() or not reader.open_spreadsheet():
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )
            if not pending:
                return

            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)

            # Lọc mã có ảnh flow
            valid_items = []
            for item in pending:
                code = item["code"]
                flow_folder = input_folder / code / "flow"
                video_folder = input_folder / code / "video"

                if flow_folder.exists():
                    images = (list(flow_folder.glob("*.jpg")) +
                             list(flow_folder.glob("*.jpeg")) +
                             list(flow_folder.glob("*.png")) +
                             list(flow_folder.glob("*.webp")))
                    if images:
                        # Skip nếu đã có đủ video
                        if video_folder.exists():
                            grok_videos = [v for v in video_folder.glob("*.mp4")
                                          if not v.name.startswith("00_sora_")]
                            if len(grok_videos) >= len(images):
                                self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: đã có video Grok"))
                                continue
                        item["images"] = images
                        valid_items.append(item)

            if not valid_items:
                self.after_safe(lambda: self.add_log("  Không có mã nào cần tạo video"))
                return

            worker = GrokWorker(
                input_folder=str(input_folder),
                output_folder=str(output_folder),
                music_folder=self.app.config.music_folder or "",
                voice_folder=self.app.config.voice_folder or "",
                config=self.app.config,
                browser_profiles=self.app.config.browser_profiles,
                stop_flag=self.stop_flag,
                on_log=lambda msg, lvl: self.after_safe(lambda m=msg: self.add_log(f"    {m}")),
                on_progress=lambda cur, tot, msg: None,
                headless=not getattr(self.app.config, 'show_chrome', True)
            )

            for item in valid_items:
                if self.stop_flag.is_set():
                    break
                code = item["code"]
                self.after_safe(lambda c=code: self.add_log(f"  🎥 {c}: tạo video Grok..."))
                worker.process_single_item(item, reader)

        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi: {e}"))

    def _run_clean_watermark_internal(self):
        """Chạy xóa logo SORA (internal - không quản lý state)"""
        try:
            from ...sora_watermark_cleaner import SoraWatermarkRemover

            input_folder = Path(self.app.config.input_folder)

            if not input_folder.exists():
                self.after_safe(lambda: self.add_log(f"  ⚠️ Thư mục không tồn tại: {input_folder}"))
                return

            # Khởi tạo remover
            def log_callback(msg):
                self.after_safe(lambda m=msg: self.add_log(f"   {m}"))

            remover = SoraWatermarkRemover(
                cleaner_type="lama",
                on_log=log_callback
            )

            # Đếm số video SORA cần xử lý
            sora_videos = []
            for code_folder in input_folder.iterdir():
                if not code_folder.is_dir():
                    continue

                video_folder = code_folder / "video"
                if not video_folder.exists():
                    continue

                # Tìm video SORA (chưa có _clean)
                for video in video_folder.glob("*sora*.mp4"):
                    if "_clean" not in video.stem:
                        output_path = video.parent / f"{video.stem}_clean{video.suffix}"
                        if not output_path.exists():
                            sora_videos.append((video, output_path))

            if not sora_videos:
                self.after_safe(lambda: self.add_log("  ⚠️ Không có video SORA nào cần xóa logo"))
                return

            self.after_safe(lambda n=len(sora_videos): self.add_log(f"  📹 Tìm thấy {n} video cần xóa logo"))

            # Xử lý từng video
            success_count = 0
            for i, (video, output) in enumerate(sora_videos, 1):
                if self.stop_flag.is_set():
                    break

                code = video.parent.parent.name
                self.after_safe(lambda c=code, idx=i, t=len(sora_videos):
                    self.add_log(f"  [{idx}/{t}] {c}: {video.name}"))

                result = remover.clean_video(str(video), str(output))

                if result.success:
                    success_count += 1

            self.after_safe(lambda s=success_count, t=len(sora_videos):
                self.add_log(f"  ✅ Đã xóa logo: {s}/{t} video"))

        except ImportError:
            self.after_safe(lambda: self.add_log("  ⚠️ SoraWatermarkCleaner chưa được cài đặt, bỏ qua"))
        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi xóa logo: {e}"))

    def _run_edit_internal(self):
        """Chạy Edit ghép video (internal) - Voice First Mode

        Logic mới (merge_voice_first):
        - Voice bắt đầu từ đầu, thời lượng video = voice + ảnh cuối
        - Video clips (SORA + Grok) chia đều theo voice, cắt giữa
        - Tắt âm thanh gốc video (chỉ Voice + Music)
        - Sau voice → hiển thị ảnh Flow (mỗi ảnh 0.5s)
        - Music fade out 3s cuối
        """
        try:
            from ...video_merger import VideoMerger, get_random_music, get_voice_for_code
            from ...sheets_reader import SheetsReader
            from pathlib import Path

            reader = SheetsReader(
                credentials_file=self.app.config.credentials_file,
                spreadsheet_id=self.app.config.spreadsheet_id,
                sheet_name=self.app.config.sheet_name
            )
            if not reader.connect() or not reader.open_spreadsheet():
                return

            pending = reader.get_pending_products(
                status_column=self.app.config.status_column,
                prompt_column=self.app.config.prompt_column
            )
            if not pending:
                return

            input_folder = Path(self.app.config.input_folder)
            output_folder = Path(self.app.config.output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)
            music_folder = self.app.config.music_folder
            voice_folder = self.app.config.voice_folder

            merger = VideoMerger(
                transition_duration=0.3,
                on_log=lambda msg: self.after_safe(lambda m=msg: self.add_log(f"    {m}"))
            )

            for item in pending:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                video_folder = input_folder / code / "video"
                final_output = output_folder / f"{code}.mp4"

                # Skip nếu đã có output
                if final_output.exists():
                    self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: đã có video final"))
                    continue

                # Lấy voice - TÌM TRONG input/{code}/ (nơi voice được lưu)
                voice_path = None
                code_folder = input_folder / code
                for ext in ['.mp3', '.wav']:
                    vp = code_folder / f"{code}{ext}"
                    if vp.exists():
                        voice_path = str(vp)
                        break

                if not voice_path:
                    self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: không có voice, bỏ qua"))
                    continue

                if not video_folder.exists():
                    self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: không có video folder"))
                    continue

                all_videos = list(video_folder.glob("*.mp4"))
                if not all_videos:
                    self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: không có video"))
                    continue

                # Ưu tiên Grok videos, fallback sang SORA nếu không có Grok
                grok_videos = sorted([str(v) for v in all_videos if "00_sora_" not in v.name])

                # SORA videos: ưu tiên bản _clean nếu có
                sora_videos = []
                for v in all_videos:
                    if "00_sora_" in v.name and "_clean" not in v.name:
                        clean_version = v.parent / f"{v.stem}_clean{v.suffix}"
                        if clean_version.exists():
                            sora_videos.append(str(clean_version))
                        else:
                            sora_videos.append(str(v))
                sora_videos = sorted(sora_videos)

                if grok_videos:
                    video_paths = grok_videos
                    self.after_safe(lambda c=code, n=len(grok_videos): self.add_log(f"  📹 {c}: dùng {n} Grok videos"))
                elif sora_videos:
                    video_paths = sora_videos
                    self.after_safe(lambda c=code, n=len(sora_videos): self.add_log(f"  📹 {c}: dùng {n} SORA videos (fallback)"))
                else:
                    self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: không có video hợp lệ"))
                    continue

                # Tìm ảnh Flow từ input/{code}/flow/
                flow_images = []
                flow_folder = input_folder / code / "flow"
                if flow_folder.exists():
                    for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                        flow_images.extend([str(p) for p in flow_folder.glob(ext)])
                    flow_images.sort()

                self.after_safe(lambda c=code, v=len(video_paths), f=len(flow_images):
                    self.add_log(f"  ✂️ {c}: {v} videos + {f} ảnh Flow"))

                # Lấy music
                music_path = get_random_music(music_folder) if music_folder else None
                if music_path:
                    self.after_safe(lambda p=Path(music_path).name: self.add_log(f"    🎵 Nhạc: {p}"))

                # Sử dụng merge_voice_first
                success = merger.merge_voice_first(
                    video_paths=video_paths,
                    image_paths=flow_images,
                    output_path=str(final_output),
                    voice_path=voice_path,
                    music_path=music_path,
                    music_volume=0.3,  # 30% để voice rõ hơn
                    voice_volume=1.0,
                    image_duration=0.5  # Mỗi ảnh 0.5s
                )

                if success and final_output.exists():
                    self.after_safe(lambda c=code: self.add_log(f"    ✓ {c}: Edit xong"))
                    reader.update_status(item["row"], "DONE", self.app.config.status_column)
                else:
                    self.after_safe(lambda c=code: self.add_log(f"    ✗ {c}: Edit thất bại"))

        except Exception as e:
            self.after_safe(lambda e=str(e): self.add_log(f"  ❌ Lỗi: {e}"))

    def _run_full_workflow_old(self):
        """Background thread chạy full quy trình (OLD - kept for reference)"""
        try:
            from ...sheets_reader import SheetsReader
            # Chọn mode dựa trên Settings
            browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
            if browser_mode == "drission":
                try:
                    from ...shopee_drission import ShopeeDrission as ShopeeDownloader
                except ImportError:
                    from ...shopee_downloader import ShopeeDownloader
            else:
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
                    existing = (list(code_folder.glob("*.jpg")) +
                               list(code_folder.glob("*.jpeg")) +
                               list(code_folder.glob("*.png")) +
                               list(code_folder.glob("*.webp")))
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
                    images = (list(code_folder.glob("*.jpg")) +
                             list(code_folder.glob("*.jpeg")) +
                             list(code_folder.glob("*.png")) +
                             list(code_folder.glob("*.webp")))
                    if images:
                        item["images"] = images
                        valid_items.append(item)

            if not valid_items:
                self.after_safe(lambda: self.add_log("  Không có mã nào có ảnh để tạo video"))
                return

            # Voice sẽ lưu trong input/{code}/ (không cần voice_folder riêng)

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

                    # Check existing voice trong input/{code}/
                    code_folder = input_folder / code
                    voice_path_mp3 = code_folder / f"{code}.mp3"
                    voice_path_wav = code_folder / f"{code}.wav"
                    has_voice = voice_path_mp3.exists() or voice_path_wav.exists()

                    if has_voice:
                        self.after_safe(lambda c=code: self.add_log(f"  [Script] ⏭️ {c}: đã có voice"))
                        continue

                    try:
                        script = existing_script

                        # Tạo kịch bản nếu chưa có
                        if not existing_script:
                            self.after_safe(lambda c=code: self.add_log(f"  [Script] 📝 {c}: tạo kịch bản..."))
                            # Note: _run_full_workflow_old doesn't have prompts access
                            script_result = gemini.generate_script(name, description)

                            if script_result.success:
                                script = script_result.script
                                reader.sheet.update_acell(f"G{item['row']}", script)
                            else:
                                self.after_safe(lambda c=code, e=script_result.error: self.add_log(f"  [Script] ❌ {c}: {e}"))
                                continue

                        # Tạo voice - lưu trong input/{code}/
                        if script:
                            self.after_safe(lambda c=code: self.add_log(f"  [Script] 🎤 {c}: tạo voice..."))
                            code_folder.mkdir(parents=True, exist_ok=True)
                            voice_result = gemini.generate_voice(
                                text=script,
                                output_path=str(code_folder / f"{code}.mp3"),
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

            # Khởi tạo filter với tham số mới:
            # - reject_logo=True: Loại ảnh logo/icon
            # - reject_collage=False: Giữ ảnh ghép
            # - require_person=True: Yêu cầu có người
            # - max_images=5: Giữ tối đa 5 ảnh/folder
            MAX_IMAGES = 5

            img_filter = ImageFilter(
                require_person=True,
                reject_collage=False,  # Giữ ảnh ghép
                reject_logo=True,      # Loại logo/icon
                max_images=MAX_IMAGES
            )

            total_kept = 0
            total_rejected = 0

            try:
                for folder in folders:
                    if self.stop_flag.is_set():
                        break

                    # Đếm ảnh trong folder
                    extensions = {'.jpg', '.jpeg', '.png', '.webp'}
                    images = sorted([f for f in folder.iterdir()
                             if f.suffix.lower() in extensions and not f.name.startswith('_')])

                    if not images:
                        continue

                    self.after_safe(lambda f=folder.name, n=len(images):
                        self.add_log(f"\n📁 {f}: {n} ảnh"))

                    # Tạo thư mục _rejected trong folder
                    rejected_folder = folder / "_rejected"

                    # Đếm số ảnh đã giữ trong folder này
                    folder_kept_count = 0

                    for img_path in images:
                        if self.stop_flag.is_set():
                            break

                        try:
                            result = img_filter.filter_image(str(img_path))

                            # Kiểm tra giới hạn max_images cho folder này
                            if result.should_keep:
                                if folder_kept_count >= MAX_IMAGES:
                                    result.should_keep = False
                                    result.reason = f"Vượt quá giới hạn {MAX_IMAGES} ảnh"

                            if result.should_keep:
                                folder_kept_count += 1
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
        self.clean_logo_btn.configure(state="disabled")
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
            # Chọn mode dựa trên Settings
            browser_mode = getattr(self.app.config, 'browser_mode', 'selenium')
            if browser_mode == "drission":
                try:
                    from ...flow_drission import FlowDrission as ChromeTokenExtractor
                except ImportError:
                    from ...chrome_token_extractor import ChromeTokenExtractor
            else:
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

                extracted_images = (list(extracted_folder.glob("*.png")) +
                                   list(extracted_folder.glob("*.jpg")) +
                                   list(extracted_folder.glob("*.jpeg")) +
                                   list(extracted_folder.glob("*.webp")))
                if not extracted_images:
                    self.after_safe(lambda c=code: self.add_log(f"  {c}: Không có ảnh extracted - bỏ qua"))
                    skipped += 1
                    continue

                # Kiểm tra ảnh đã có cho từng prompt (cho phép chạy lại để bổ sung thiếu)
                flow_folder = products_dir / code / "flow"
                existing_I = []
                existing_K = []
                if flow_folder.exists():
                    existing_I = [f for f in flow_folder.glob(f"{code}_I*") if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']]
                    existing_K = [f for f in flow_folder.glob(f"{code}_K*") if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']]

                # Kiểm tra đủ ảnh cho từng prompt (mỗi prompt cần 4 ảnh)
                need_prompt_1 = flow_prompt_1 and len(existing_I) < 4
                need_prompt_2 = flow_prompt_2 and len(existing_K) < 4

                # Nếu không có prompt nào thì bỏ qua
                if not flow_prompt_1 and not flow_prompt_2:
                    self.after_safe(lambda c=code: self.add_log(f"⏭️ {c}: Không có prompt (cột I, K trống) - bỏ qua"))
                    skipped += 1
                    continue

                # Nếu đã đủ ảnh cho tất cả prompt thì bỏ qua
                if not need_prompt_1 and not need_prompt_2:
                    total_existing = len(existing_I) + len(existing_K)
                    self.after_safe(lambda c=code, n=total_existing: self.add_log(f"⏭️ {c}: Đã đủ {n} ảnh flow - bỏ qua"))
                    skipped += 1
                    continue

                # Log số ảnh còn thiếu
                missing_info = []
                if need_prompt_1:
                    missing_info.append(f"I: cần thêm {4 - len(existing_I)} ảnh")
                if need_prompt_2:
                    missing_info.append(f"K: cần thêm {4 - len(existing_K)} ảnh")
                self.after_safe(lambda c=code, i=i, t=total, info=", ".join(missing_info):
                    self.add_log(f"[{i}/{t}] 🌀 {c}: Tạo ảnh flow ({info})..."))

                try:
                    # Sử dụng Chrome trigger + API call để tạo ảnh
                    # Flow: trigger Chrome (capture payload, cancel request) → gọi API với payload

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
                    max_retries = 5
                    retry_delays = [30, 45, 60, 90, 120]

                    # === PROMPT 1 (Cột I) - Tạo 4 ảnh (chỉ nếu thiếu) ===
                    if need_prompt_1:
                        self.after_safe(lambda c=code, n=len(existing_I): self.add_log(f"   📸 Prompt 1 (cột I): Đã có {n}/4, tạo thêm..."))

                        downloaded_1 = None
                        for attempt in range(max_retries + 1):
                            # Trigger Chrome để capture payload (mỗi lần retry đều capture mới)
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
                                    self.after_safe(lambda n=len(downloaded_1): self.add_log(f"   ✅ Prompt 1: +{n} ảnh"))
                                    break  # Thành công, thoát vòng lặp
                                else:
                                    # API call thất bại, thử lại
                                    if attempt < max_retries:
                                        wait_time = retry_delays[attempt]
                                        self.after_safe(lambda w=wait_time, a=attempt+1:
                                            self.add_log(f"   🔄 Thử lại Prompt 1 ({a}/{max_retries}) - đợi {w}s..."))
                                        import time
                                        time.sleep(wait_time)
                            else:
                                self.after_safe(lambda: self.add_log(f"   ⚠️ Prompt 1: Không capture được payload"))
                                break  # Không capture được, thoát

                    # === PROMPT 2 (Cột K) - Tạo 4 ảnh (chỉ nếu thiếu) ===
                    if need_prompt_2:
                        self.after_safe(lambda c=code, n=len(existing_K): self.add_log(f"   📸 Prompt 2 (cột K): Đã có {n}/4, tạo thêm..."))

                        downloaded_2 = None
                        for attempt in range(max_retries + 1):
                            # Trigger Chrome để capture payload mới (mỗi lần retry đều capture mới)
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
                                    self.after_safe(lambda n=len(downloaded_2): self.add_log(f"   ✅ Prompt 2: +{n} ảnh"))
                                    break  # Thành công, thoát vòng lặp
                                else:
                                    # API call thất bại, thử lại
                                    if attempt < max_retries:
                                        wait_time = retry_delays[attempt]
                                        self.after_safe(lambda w=wait_time, a=attempt+1:
                                            self.add_log(f"   🔄 Thử lại Prompt 2 ({a}/{max_retries}) - đợi {w}s..."))
                                        import time
                                        time.sleep(wait_time)
                            else:
                                self.after_safe(lambda: self.add_log(f"   ⚠️ Prompt 2: Không capture được payload"))
                                break  # Không capture được, thoát

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
        self.clean_logo_btn.configure(state="normal")
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
        self.clean_logo_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.stop_flag.clear()
        self.clear_table()
        self.add_log("🎬 Bắt đầu edit video...")

        thread = threading.Thread(target=self._run_edit_videos, daemon=True)
        thread.start()

    def _run_edit_videos(self):
        """Background thread edit video - Full Merge Mode

        Logic mới (merge_full):
        - THỨ TỰ: SORA → GROK → ẢNH
        - MUSIC: Từ đầu video (bao gồm SORA)
        - VOICE: Bắt đầu từ GROK (sau SORA)
        - GROK audio: TẮT (mute)
        - Ảnh Flow: 0.5s mỗi ảnh, cuối video
        """
        try:
            from ...sheets_reader import SheetsReader
            from ...video_merger import VideoMerger, get_random_music

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

            music_folder = self.app.config.music_folder
            voice_folder = Path(self.app.config.voice_folder) if self.app.config.voice_folder else None

            # Lọc các mã có video VÀ voice (bắt buộc phải có voice)
            valid_items = []
            for item in pending:
                code = item["code"]

                # Kiểm tra voice - TÌM TRONG input/{code}/ (nơi voice được lưu)
                voice_path = None
                code_folder = input_folder / code
                for ext in ['.mp3', '.wav']:
                    vp = code_folder / f"{code}{ext}"
                    if vp.exists():
                        voice_path = str(vp)
                        break

                if not voice_path:
                    self.after_safe(lambda c=code: self.add_log(f"  ⏭️ {c}: không có voice, bỏ qua"))
                    continue

                # Tìm video trong input/{code}/video/
                code_video_folder = input_folder / code / "video"
                if code_video_folder.exists():
                    all_videos = list(code_video_folder.glob("*.mp4"))
                    if all_videos:
                        # Tách SORA và GROK videos
                        grok_videos = sorted([str(v) for v in all_videos if "00_sora_" not in v.name])

                        # SORA videos: ưu tiên bản _clean nếu có
                        sora_videos = []
                        for v in all_videos:
                            if "00_sora_" in v.name and "_clean" not in v.name:
                                # Kiểm tra có bản _clean không
                                clean_version = v.parent / f"{v.stem}_clean{v.suffix}"
                                if clean_version.exists():
                                    sora_videos.append(str(clean_version))
                                else:
                                    sora_videos.append(str(v))
                        sora_videos = sorted(sora_videos)

                        # Cần ít nhất GROK video (SORA optional)
                        if grok_videos:
                            item["sora_videos"] = sora_videos
                            item["grok_videos"] = grok_videos
                            item["voice_path"] = voice_path
                            valid_items.append(item)
                            self.after_safe(lambda c=code, s=len(sora_videos), g=len(grok_videos):
                                self.add_log(f"  📹 {c}: {s} SORA + {g} GROK videos"))
                        elif sora_videos:
                            # Fallback: chỉ có SORA
                            item["sora_videos"] = []
                            item["grok_videos"] = sora_videos  # Dùng SORA làm GROK
                            item["voice_path"] = voice_path
                            valid_items.append(item)
                            self.after_safe(lambda c=code, n=len(sora_videos):
                                self.add_log(f"  📹 {c}: {n} SORA videos (fallback)"))

            if not valid_items:
                self.after_safe(lambda: self.add_log("❌ Không có video nào để edit"))
                self.after_safe(lambda: self.add_log(f"  Đã tìm trong: input/[mã]/video/"))
                self.after_safe(lambda: self.add_log("  💡 Cần có cả video VÀ voice để edit"))
                return

            self.after_safe(lambda n=len(valid_items): self.add_log(f"📋 Tìm thấy {n} sản phẩm có video + voice"))
            self.after_safe(lambda: self.add_log("📐 Flow: SORA → GROK → ẢNH"))
            self.after_safe(lambda: self.add_log("🎵 Music: từ đầu video | 🎤 Voice: từ GROK"))

            # Tạo tasks
            for item in valid_items:
                code = item["code"]
                task = TaskItem(code, item["row"])
                self.tasks[code] = task
                self.after_safe(lambda t=task: self.add_task_row(t))

            # Khởi tạo VideoMerger
            merger = VideoMerger(
                transition_duration=0.3,
                on_log=lambda msg: self.after_safe(lambda m=msg: self.add_log(f"    {m}"))
            )

            for item in valid_items:
                if self.stop_flag.is_set():
                    break

                code = item["code"]
                sora_videos = item["sora_videos"]
                grok_videos = item["grok_videos"]
                voice_path = item["voice_path"]

                self.set_task_input_status(code, TaskItem.STATUS_DONE)
                self.set_task_video_status(code, TaskItem.STATUS_RUNNING)
                self.after_safe(lambda c=code: self.add_log(f"🎬 Edit video (SORA→GROK→ẢNH): {c}"))

                try:
                    # Tìm music RANDOM từ music folder
                    music_path = get_random_music(music_folder) if music_folder else None
                    if music_path:
                        self.after_safe(lambda p=Path(music_path).name: self.add_log(f"  🎵 Nhạc (từ đầu): {p}"))

                    # Tìm ảnh Flow từ input/{code}/flow/
                    flow_images = []
                    flow_folder = input_folder / code / "flow"
                    if flow_folder.exists():
                        for ext in ['*.jpg', '*.jpeg', '*.png', '*.webp']:
                            flow_images.extend([str(p) for p in flow_folder.glob(ext)])
                        flow_images.sort()
                        if flow_images:
                            self.after_safe(lambda c=code, n=len(flow_images):
                                self.add_log(f"  📷 {n} ảnh Flow (cuối video, 0.5s/ảnh)"))

                    # Output path
                    final_video = output_folder / f"{code}.mp4"

                    # Sử dụng merge_full: SORA → GROK → ẢNH
                    # Music từ đầu, Voice từ GROK, GROK audio mute
                    success = merger.merge_full(
                        sora_videos=sora_videos,
                        grok_videos=grok_videos,
                        flow_images=flow_images,
                        output_path=str(final_video),
                        music_path=music_path,
                        voice_path=voice_path,
                        music_volume=0.3,  # 30% để voice rõ hơn
                        voice_volume=1.0,
                        image_duration=0.5,  # Mỗi ảnh 0.5s
                        mute_original=True  # Tắt audio gốc của GROK
                    )

                    if success:
                        self.set_task_video_status(code, TaskItem.STATUS_DONE)
                        self.set_task_render_status(code, TaskItem.STATUS_DONE)
                        self.tasks[code].output_path = final_video
                        self.after_safe(lambda: self.update_task_row(code))
                        self.after_safe(lambda c=code: self.add_log(f"✅ {c}: Hoàn thành!"))

                        # Update status trong sheet
                        try:
                            status_col = self.app.config.status_column or "E"
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
        self.clean_logo_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def cleanup_browsers(self):
        """Đóng tất cả browser khi thoát ứng dụng"""
        try:
            # Đóng Shopee downloader browser
            if hasattr(self, 'shopee_downloader') and self.shopee_downloader:
                # DrissionPage version
                if hasattr(self.shopee_downloader, 'manager') and self.shopee_downloader.manager:
                    try:
                        self.shopee_downloader.close()
                        print("✓ Đã đóng browser Shopee (DrissionPage)")
                    except Exception as e:
                        print(f"⚠️ Lỗi đóng browser Shopee: {e}")
                # Selenium/old version
                elif hasattr(self.shopee_downloader, 'driver') and self.shopee_downloader.driver:
                    try:
                        self.shopee_downloader.driver.quit()
                        self.shopee_downloader.driver = None
                        print("✓ Đã đóng browser Shopee")
                    except Exception as e:
                        print(f"⚠️ Lỗi đóng browser Shopee: {e}")
        except Exception as e:
            print(f"⚠️ Lỗi cleanup browsers: {e}")
