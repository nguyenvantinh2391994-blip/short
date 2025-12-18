"""
Video Creator Tool - Main Application
GUI chính để tạo video từ Grok, Sora, v.v.
"""

import customtkinter as ctk
from pathlib import Path
import json
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Import các tab
from .tabs.home_tab import HomeTab
from .tabs.grok_tab import GrokTab
from .tabs.settings_tab import SettingsTab
from .tabs.logs_tab import LogsTab

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
    """Main Application Window"""

    APP_NAME = "Video Creator Tool"
    APP_VERSION = "1.0.0"

    def __init__(self):
        super().__init__()

        # Load config
        self.config = self.load_config()

        # Setup theme
        ctk.set_appearance_mode(self.config.theme)
        ctk.set_default_color_theme("blue")

        # Setup window
        self.title(f"{self.APP_NAME} v{self.APP_VERSION}")
        self.geometry("1200x800")
        self.minsize(900, 600)

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
        """Setup main UI"""
        # Main container
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Header
        self.setup_header()

        # Tab view
        self.setup_tabs()

        # Status bar
        self.setup_statusbar()

    def setup_header(self):
        """Setup header với logo và title"""
        header = ctk.CTkFrame(self.main_container, height=60)
        header.pack(fill="x", padx=5, pady=(5, 10))
        header.pack_propagate(False)

        # Title
        title_label = ctk.CTkLabel(
            header,
            text=f"🎬 {self.APP_NAME}",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side="left", padx=20, pady=10)

        # Version
        version_label = ctk.CTkLabel(
            header,
            text=f"v{self.APP_VERSION}",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        version_label.pack(side="left", pady=10)

        # Theme toggle
        self.theme_switch = ctk.CTkSwitch(
            header,
            text="Dark Mode",
            command=self.toggle_theme,
            onvalue="dark",
            offvalue="light"
        )
        self.theme_switch.pack(side="right", padx=20, pady=10)
        if self.config.theme == "dark":
            self.theme_switch.select()

    def setup_tabs(self):
        """Setup tab view"""
        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.pack(fill="both", expand=True, padx=5, pady=5)

        # Add tabs
        self.tabview.add("🏠 Trang chủ")
        self.tabview.add("🎬 Grok Video")
        self.tabview.add("⚙️ Cài đặt")
        self.tabview.add("📋 Logs")

        # Initialize tab contents
        self.home_tab = HomeTab(self.tabview.tab("🏠 Trang chủ"), self)
        self.grok_tab = GrokTab(self.tabview.tab("🎬 Grok Video"), self)
        self.settings_tab = SettingsTab(self.tabview.tab("⚙️ Cài đặt"), self)
        self.logs_tab = LogsTab(self.tabview.tab("📋 Logs"), self)

    def setup_statusbar(self):
        """Setup status bar"""
        self.statusbar = ctk.CTkFrame(self.main_container, height=30)
        self.statusbar.pack(fill="x", padx=5, pady=(5, 0))
        self.statusbar.pack_propagate(False)

        # Status label
        self.status_label = ctk.CTkLabel(
            self.statusbar,
            text="Sẵn sàng",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=10)

        # Progress
        self.progress_label = ctk.CTkLabel(
            self.statusbar,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.progress_label.pack(side="right", padx=10)

    def set_status(self, text: str, progress: str = ""):
        """Update status bar"""
        self.status_label.configure(text=text)
        self.progress_label.configure(text=progress)

    def toggle_theme(self):
        """Toggle dark/light theme"""
        if self.theme_switch.get() == "dark":
            ctk.set_appearance_mode("dark")
            self.config.theme = "dark"
        else:
            ctk.set_appearance_mode("light")
            self.config.theme = "light"
        self.save_config()

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
        """Add log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_text = f"[{timestamp}] [{level}] {message}"

        # Add to logs tab
        if hasattr(self, 'logs_tab'):
            self.logs_tab.add_log(log_text, level)

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
