"""
Video Creator Tool - Main Application
Giao diện đơn giản, gọn gàng, dễ sử dụng
"""

import customtkinter as ctk
from pathlib import Path
import json
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Import các tab
from .tabs.main_tab import MainTab
from .tabs.settings_tab import SettingsTab

# Config
CONFIG_FILE = Path(__file__).parent.parent.parent / "config" / "gui_config.json"


@dataclass
class BrowserProfile:
    """Cấu hình 1 browser profile"""
    name: str
    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    profile_path: str = ""
    enabled: bool = True


@dataclass
class AppConfig:
    """Cấu hình ứng dụng"""
    # Thư mục
    input_folder: str = "input"
    output_folder: str = "outputs"
    music_folder: str = ""
    voice_folder: str = ""

    # Google Sheets
    spreadsheet_id: str = ""
    sheet_name: str = "NGUON"
    credentials_file: str = "config/credentials.json"
    status_column: str = "E"
    prompt_column: str = "F"

    # Shopee settings
    auto_shopee: bool = True
    shopee_link_column: str = "B"

    # Gemini API
    gemini_api_key: str = ""

    # Browser profiles
    browser_profiles: List[Dict] = field(default_factory=list)

    # Cài đặt chạy
    max_threads: int = 1
    wait_after_done: int = 15
    max_retries: int = 3

    # Giao diện
    theme: str = "dark"

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "AppConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class VideoCreatorApp(ctk.CTk):
    """Main Application Window - Giao diện tối giản"""

    APP_NAME = "Video Creator"
    APP_VERSION = "2.0"

    def __init__(self):
        super().__init__()

        # Load config
        self.config = self.load_config()

        # Setup theme - màu nhẹ nhàng hơn
        ctk.set_appearance_mode(self.config.theme)
        ctk.set_default_color_theme("blue")

        # Setup window
        self.title(f"{self.APP_NAME}")
        self.geometry("1000x700")
        self.minsize(800, 550)

        # Center window
        self.center_window()

        # Setup UI
        self.setup_ui()

        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def center_window(self):
        """Center window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

    def setup_ui(self):
        """Setup main UI - đơn giản, gọn gàng"""
        # Main container
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # Header nhỏ gọn
        self.setup_header()

        # Tab view - chỉ 2 tabs
        self.setup_tabs()

        # Status bar nhỏ
        self.setup_statusbar()

    def setup_header(self):
        """Header nhỏ gọn"""
        header = ctk.CTkFrame(self.main_container, height=45, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)

        # Title
        title_label = ctk.CTkLabel(
            header,
            text=f"🎬 {self.APP_NAME}",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(side="left")

        # Buttons bên phải
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        # Help button
        help_btn = ctk.CTkButton(
            btn_frame,
            text="❓",
            width=35,
            height=35,
            command=self.show_help,
            fg_color="transparent",
            hover_color=("gray85", "gray25")
        )
        help_btn.pack(side="left", padx=5)

        # Theme toggle
        self.theme_btn = ctk.CTkButton(
            btn_frame,
            text="🌙" if self.config.theme == "dark" else "☀️",
            width=35,
            height=35,
            command=self.toggle_theme,
            fg_color="transparent",
            hover_color=("gray85", "gray25")
        )
        self.theme_btn.pack(side="left", padx=5)

    def setup_tabs(self):
        """Setup tab view - chỉ 2 tabs chính"""
        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.pack(fill="both", expand=True)

        # Chỉ 2 tabs
        self.tabview.add("🎬 Tạo Video")
        self.tabview.add("⚙️ Cài đặt")

        # Initialize tabs
        self.main_tab = MainTab(self.tabview.tab("🎬 Tạo Video"), self)
        self.settings_tab = SettingsTab(self.tabview.tab("⚙️ Cài đặt"), self)

    def setup_statusbar(self):
        """Status bar nhỏ gọn"""
        self.statusbar = ctk.CTkFrame(self.main_container, height=25, fg_color="transparent")
        self.statusbar.pack(fill="x", pady=(10, 0))
        self.statusbar.pack_propagate(False)

        # Status label
        self.status_label = ctk.CTkLabel(
            self.statusbar,
            text="Sẵn sàng",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.status_label.pack(side="left")

        # Progress
        self.progress_label = ctk.CTkLabel(
            self.statusbar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.progress_label.pack(side="right")

    def set_status(self, text: str, progress: str = ""):
        """Update status bar"""
        self.status_label.configure(text=text)
        self.progress_label.configure(text=progress)

    def toggle_theme(self):
        """Toggle dark/light theme"""
        if self.config.theme == "dark":
            ctk.set_appearance_mode("light")
            self.config.theme = "light"
            self.theme_btn.configure(text="☀️")
        else:
            ctk.set_appearance_mode("dark")
            self.config.theme = "dark"
            self.theme_btn.configure(text="🌙")
        self.save_config()

    def show_help(self):
        """Hiển thị hướng dẫn sử dụng"""
        help_window = ctk.CTkToplevel(self)
        help_window.title("Hướng dẫn sử dụng")
        help_window.geometry("500x400")
        help_window.transient(self)
        help_window.grab_set()

        # Center
        help_window.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 500) // 2
        y = self.winfo_y() + (self.winfo_height() - 400) // 2
        help_window.geometry(f"+{x}+{y}")

        # Content
        content = ctk.CTkScrollableFrame(help_window)
        content.pack(fill="both", expand=True, padx=20, pady=20)

        title = ctk.CTkLabel(
            content,
            text="📖 Hướng dẫn sử dụng",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(pady=(0, 15))

        instructions = """
1️⃣ CÀI ĐẶT (làm 1 lần):
   • Vào tab "Cài đặt"
   • Thêm Browser Profile (đã đăng nhập Grok)
   • Nhập Google Sheets ID
   • Đặt credentials.json vào thư mục config/

2️⃣ CHUẨN BỊ DỮ LIỆU:
   • Google Sheet: Cột A = mã, Cột B = link Shopee
   • Cột E = trạng thái (để trống = chưa làm)
   • Cột F = prompt cho Grok

3️⃣ TẠO VIDEO:
   • Nhấn "🛒 Tải ảnh Shopee" để tải ảnh trước
   • Nhấn "▶️ Tạo Video" để bắt đầu
   • Video sẽ lưu vào thư mục outputs/

4️⃣ TIPS:
   • Dùng ảnh tỷ lệ 9:16 để đẹp nhất
   • Có thể thêm nhạc vào thư mục music/
   • Kiểm tra trạng thái ở Google Sheet
        """

        text = ctk.CTkLabel(
            content,
            text=instructions.strip(),
            font=ctk.CTkFont(size=13),
            justify="left",
            anchor="w"
        )
        text.pack(fill="x")

        # Close button
        close_btn = ctk.CTkButton(
            help_window,
            text="Đóng",
            command=help_window.destroy,
            width=100
        )
        close_btn.pack(pady=15)

    def load_config(self) -> AppConfig:
        """Load config từ file"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AppConfig.from_dict(data)
            except Exception as e:
                print(f"Lỗi load config: {e}")
        return AppConfig()

    def save_config(self):
        """Save config ra file"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Lỗi save config: {e}")

    def log(self, message: str, level: str = "INFO"):
        """Add log message - gửi đến main_tab"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_text = f"[{timestamp}] {message}"

        # Add to main tab
        if hasattr(self, 'main_tab'):
            self.main_tab.add_log(log_text, level)

        print(log_text)

    def on_closing(self):
        """Handle window close"""
        self.save_config()
        self.destroy()


def run_app():
    """Run the application"""
    app = VideoCreatorApp()
    app.mainloop()


if __name__ == "__main__":
    run_app()
