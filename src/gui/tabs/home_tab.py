"""
Home Tab - Trang chủ với overview và quick actions
"""

import customtkinter as ctk
from pathlib import Path


class HomeTab:
    """Home Tab với overview và quick actions"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        # Main scroll frame
        self.scroll_frame = ctk.CTkScrollableFrame(self.parent)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Welcome section
        self.setup_welcome()

        # Quick stats
        self.setup_stats()

        # Quick actions
        self.setup_quick_actions()

        # Recent activity
        self.setup_recent()

    def setup_welcome(self):
        """Welcome section"""
        welcome_frame = ctk.CTkFrame(self.scroll_frame)
        welcome_frame.pack(fill="x", padx=10, pady=10)

        title = ctk.CTkLabel(
            welcome_frame,
            text="Chào mừng đến với Video Creator Tool!",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(padx=20, pady=(20, 5))

        desc = ctk.CTkLabel(
            welcome_frame,
            text="Công cụ tự động tạo video từ ảnh sản phẩm sử dụng AI (Grok, Sora, ...)",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        desc.pack(padx=20, pady=(0, 20))

    def setup_stats(self):
        """Statistics section"""
        stats_frame = ctk.CTkFrame(self.scroll_frame)
        stats_frame.pack(fill="x", padx=10, pady=10)

        title = ctk.CTkLabel(
            stats_frame,
            text="📊 Thống kê",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(anchor="w", padx=20, pady=(15, 10))

        # Stats grid
        stats_grid = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_grid.pack(fill="x", padx=20, pady=(0, 15))

        # Count files
        input_folder = Path(self.app.config.input_folder)
        output_folder = Path(self.app.config.output_folder)

        input_count = len(list(input_folder.glob("*.jpg"))) + len(list(input_folder.glob("*.png"))) if input_folder.exists() else 0
        output_count = len(list(output_folder.glob("*.mp4"))) if output_folder.exists() else 0

        stats = [
            ("🖼️ Ảnh input", str(input_count)),
            ("🎬 Video đã tạo", str(output_count)),
            ("📁 Browser profiles", str(len(self.app.config.browser_profiles))),
            ("🔄 Max threads", str(self.app.config.max_threads)),
        ]

        for i, (label, value) in enumerate(stats):
            stat_frame = ctk.CTkFrame(stats_grid)
            stat_frame.grid(row=0, column=i, padx=10, pady=5, sticky="nsew")
            stats_grid.columnconfigure(i, weight=1)

            ctk.CTkLabel(
                stat_frame,
                text=value,
                font=ctk.CTkFont(size=28, weight="bold")
            ).pack(padx=20, pady=(15, 5))

            ctk.CTkLabel(
                stat_frame,
                text=label,
                font=ctk.CTkFont(size=12),
                text_color="gray"
            ).pack(padx=20, pady=(0, 15))

    def setup_quick_actions(self):
        """Quick actions section"""
        actions_frame = ctk.CTkFrame(self.scroll_frame)
        actions_frame.pack(fill="x", padx=10, pady=10)

        title = ctk.CTkLabel(
            actions_frame,
            text="⚡ Thao tác nhanh",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(anchor="w", padx=20, pady=(15, 10))

        # Buttons grid
        btn_frame = ctk.CTkFrame(actions_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))

        actions = [
            ("🎬 Tạo Video Grok", self.go_to_grok, "green"),
            ("📋 Xem Logs", self.go_to_logs, "blue"),
            ("⚙️ Cài đặt", self.go_to_settings, "gray"),
            ("🔄 Refresh", self.refresh_stats, "orange"),
        ]

        for i, (text, command, color) in enumerate(actions):
            btn = ctk.CTkButton(
                btn_frame,
                text=text,
                command=command,
                width=150,
                height=40,
                fg_color=color if color != "gray" else None
            )
            btn.grid(row=0, column=i, padx=10, pady=5)

    def setup_recent(self):
        """Recent activity section"""
        recent_frame = ctk.CTkFrame(self.scroll_frame)
        recent_frame.pack(fill="x", padx=10, pady=10)

        title = ctk.CTkLabel(
            recent_frame,
            text="📜 Hướng dẫn sử dụng",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(anchor="w", padx=20, pady=(15, 10))

        instructions = """
1. Vào tab "⚙️ Cài đặt" để:
   • Thêm Browser Profile (mỗi profile = 1 tài khoản Grok)
   • Cấu hình Google Sheets (spreadsheet ID, credentials)
   • Chọn thư mục input/output

2. Chuẩn bị dữ liệu:
   • Ảnh sản phẩm đặt trong thư mục input/ với tên = mã sản phẩm
   • Google Sheets: Cột A = mã, E = trạng thái, F = prompt

3. Vào tab "🎬 Grok Video" để:
   • Chọn browser profile
   • Nhấn "Bắt đầu" để tạo video tự động
   • Theo dõi tiến trình trong tab "📋 Logs"

4. Kết quả:
   • Video được lưu vào thư mục outputs/
   • Cột E trong Sheets được cập nhật thành "VIDEO"
        """

        text = ctk.CTkTextbox(recent_frame, height=250, font=ctk.CTkFont(size=13))
        text.pack(fill="x", padx=20, pady=(0, 15))
        text.insert("1.0", instructions.strip())
        text.configure(state="disabled")

    def go_to_grok(self):
        """Switch to Grok tab"""
        self.app.tabview.set("🎬 Grok Video")

    def go_to_logs(self):
        """Switch to Logs tab"""
        self.app.tabview.set("📋 Logs")

    def go_to_settings(self):
        """Switch to Settings tab"""
        self.app.tabview.set("⚙️ Cài đặt")

    def refresh_stats(self):
        """Refresh statistics"""
        # Rebuild stats section
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.setup_welcome()
        self.setup_stats()
        self.setup_quick_actions()
        self.setup_recent()

        self.app.set_status("Đã refresh thống kê")
