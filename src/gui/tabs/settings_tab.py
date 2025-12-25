"""
Settings Tab - Cài đặt ứng dụng và browser profiles
"""

import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog, messagebox
import json
import subprocess
import threading


class SettingsTab:
    """Settings Tab"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        # Scrollable frame
        self.scroll_frame = ctk.CTkScrollableFrame(self.parent)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Browser Profiles section
        self.setup_browser_profiles()

        # Google Sheets section
        self.setup_sheets_config()

        # Folders section
        self.setup_folders_config()

        # Gemini API section
        self.setup_gemini_config()

        # Advanced section
        self.setup_advanced_config()

        # Save button
        self.setup_save_button()

    def setup_browser_profiles(self):
        """Browser profiles management"""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", padx=10, pady=10)

        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(
            header,
            text="🌐 Browser Profiles",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="➕ Thêm Profile",
            command=self.add_profile,
            width=120
        ).pack(side="right")

        # Description
        ctk.CTkLabel(
            frame,
            text="Mỗi profile tương ứng với 1 tài khoản Grok. Có thể chạy song song nhiều profile.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 10))

        # Profiles list
        self.profiles_frame = ctk.CTkFrame(frame)
        self.profiles_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.refresh_profiles_list()

    def refresh_profiles_list(self):
        """Refresh the profiles list"""
        # Clear existing
        for widget in self.profiles_frame.winfo_children():
            widget.destroy()

        profiles = self.app.config.browser_profiles

        if not profiles:
            ctk.CTkLabel(
                self.profiles_frame,
                text="Chưa có profile nào. Nhấn 'Thêm Profile' để tạo mới.",
                text_color="gray"
            ).pack(pady=20)
            return

        for i, profile in enumerate(profiles):
            self.create_profile_row(i, profile)

    def create_profile_row(self, index: int, profile: dict):
        """Create a row for a profile"""
        row = ctk.CTkFrame(self.profiles_frame)
        row.pack(fill="x", pady=2)

        # Enable checkbox
        enabled_var = ctk.BooleanVar(value=profile.get("enabled", True))
        ctk.CTkCheckBox(
            row,
            text="",
            variable=enabled_var,
            command=lambda: self.toggle_profile(index, enabled_var.get()),
            width=30
        ).pack(side="left", padx=5)

        # Name
        ctk.CTkLabel(
            row,
            text=profile.get("name", "Profile"),
            font=ctk.CTkFont(size=13, weight="bold"),
            width=150
        ).pack(side="left", padx=5)

        # Path (truncated)
        path = profile.get("profile_path", "")
        short_path = f"...{path[-40:]}" if len(path) > 40 else path
        ctk.CTkLabel(
            row,
            text=short_path,
            font=ctk.CTkFont(size=11),
            text_color="gray",
            width=300
        ).pack(side="left", padx=5)

        # Buttons
        ctk.CTkButton(
            row,
            text="✏️",
            width=30,
            command=lambda: self.edit_profile(index)
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            row,
            text="🗑️",
            width=30,
            fg_color="red",
            command=lambda: self.delete_profile(index)
        ).pack(side="right", padx=2)

        # Login button - Mở browser để đăng nhập
        ctk.CTkButton(
            row,
            text="🔑 Login",
            width=70,
            fg_color="#FF9800",
            command=lambda: self.open_browser_login(index)
        ).pack(side="right", padx=2)

    def add_profile(self):
        """Add new browser profile"""
        dialog = ProfileDialog(self.parent, self.app, None)
        self.parent.wait_window(dialog)

        if dialog.result:
            self.app.config.browser_profiles.append(dialog.result)
            self.app.save_config()
            self.refresh_profiles_list()
            self.app.log(f"Đã thêm profile: {dialog.result.get('name')}")

    def edit_profile(self, index: int):
        """Edit existing profile"""
        profile = self.app.config.browser_profiles[index]
        dialog = ProfileDialog(self.parent, self.app, profile)
        self.parent.wait_window(dialog)

        if dialog.result:
            self.app.config.browser_profiles[index] = dialog.result
            self.app.save_config()
            self.refresh_profiles_list()

    def delete_profile(self, index: int):
        """Delete profile"""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa profile này?"):
            name = self.app.config.browser_profiles[index].get("name")
            del self.app.config.browser_profiles[index]
            self.app.save_config()
            self.refresh_profiles_list()
            self.app.log(f"Đã xóa profile: {name}")

    def toggle_profile(self, index: int, enabled: bool):
        """Toggle profile enabled state"""
        self.app.config.browser_profiles[index]["enabled"] = enabled
        self.app.save_config()

    def open_browser_login(self, index: int):
        """Mở browser để login - dùng undetected_chromedriver"""
        profile = self.app.config.browser_profiles[index]
        profile_name = profile.get("name", "Profile")
        profile_path = profile.get("profile_path", "")

        # Tạo đường dẫn profile nếu chưa có
        if not profile_path:
            home = Path.home()
            profile_path = str(home / ".grok_profiles" / profile_name.replace(" ", "_"))

        def run_chrome():
            try:
                import undetected_chromedriver as uc

                self.app.log(f"Mở browser để login: {profile_name}")
                self.app.log(f"   Profile: {profile_path}")

                # Tạo thư mục profile nếu chưa có
                Path(profile_path).mkdir(parents=True, exist_ok=True)

                options = uc.ChromeOptions()
                options.add_argument("--window-size=1200,800")

                driver = uc.Chrome(
                    options=options,
                    user_data_dir=profile_path,
                    use_subprocess=True
                )
                driver.get("https://grok.com")

                self.app.log("Browser đã mở. Hãy đăng nhập và đóng browser khi xong.")

            except Exception as e:
                self.app.log(f"Lỗi mở browser: {e}", "ERROR")
                import traceback
                self.app.log(traceback.format_exc(), "ERROR")

        # Chạy trong thread để không block UI
        threading.Thread(target=run_chrome, daemon=True).start()

        messagebox.showinfo(
            "Login",
            f"Đang mở Chrome...\n\n"
            f"Profile: {profile_path}\n\n"
            "1. Đăng nhập tài khoản Grok của bạn\n"
            "2. Sau khi login xong, ĐÓNG browser\n"
            "3. Lần sau chạy sẽ tự dùng tài khoản này"
        )

    def setup_sheets_config(self):
        """Google Sheets configuration"""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            frame,
            text="📊 Google Sheets",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Spreadsheet ID
        ctk.CTkLabel(frame, text="Spreadsheet ID:").pack(anchor="w", padx=15, pady=(5, 0))
        self.spreadsheet_entry = ctk.CTkEntry(frame, width=400)
        self.spreadsheet_entry.pack(anchor="w", padx=15, pady=(0, 10))
        self.spreadsheet_entry.insert(0, self.app.config.spreadsheet_id)

        # Sheet name
        ctk.CTkLabel(frame, text="Tên Sheet:").pack(anchor="w", padx=15, pady=(5, 0))
        self.sheet_name_entry = ctk.CTkEntry(frame, width=200)
        self.sheet_name_entry.pack(anchor="w", padx=15, pady=(0, 10))
        self.sheet_name_entry.insert(0, self.app.config.sheet_name)

        # Credentials file
        cred_row = ctk.CTkFrame(frame, fg_color="transparent")
        cred_row.pack(anchor="w", padx=15, pady=(5, 15))

        ctk.CTkLabel(cred_row, text="Credentials:").pack(side="left")
        self.credentials_entry = ctk.CTkEntry(cred_row, width=300)
        self.credentials_entry.pack(side="left", padx=10)
        self.credentials_entry.insert(0, self.app.config.credentials_file)

        ctk.CTkButton(
            cred_row,
            text="📁",
            width=40,
            command=self.browse_credentials
        ).pack(side="left")

        # Columns
        col_row = ctk.CTkFrame(frame, fg_color="transparent")
        col_row.pack(anchor="w", padx=15, pady=(0, 15))

        ctk.CTkLabel(col_row, text="Cột Status:").pack(side="left")
        self.status_col_entry = ctk.CTkEntry(col_row, width=50)
        self.status_col_entry.pack(side="left", padx=10)
        self.status_col_entry.insert(0, self.app.config.status_column)

        ctk.CTkLabel(col_row, text="Cột Prompt:").pack(side="left", padx=(20, 0))
        self.prompt_col_entry = ctk.CTkEntry(col_row, width=50)
        self.prompt_col_entry.pack(side="left", padx=10)
        self.prompt_col_entry.insert(0, self.app.config.prompt_column)

    def setup_folders_config(self):
        """Folders configuration"""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            frame,
            text="📁 Thư mục",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Input folder
        input_row = ctk.CTkFrame(frame, fg_color="transparent")
        input_row.pack(anchor="w", padx=15, pady=5)

        ctk.CTkLabel(input_row, text="Input:", width=80).pack(side="left")
        self.input_folder_entry = ctk.CTkEntry(input_row, width=300)
        self.input_folder_entry.pack(side="left", padx=10)
        self.input_folder_entry.insert(0, self.app.config.input_folder)

        ctk.CTkButton(
            input_row,
            text="📁",
            width=40,
            command=lambda: self.browse_folder(self.input_folder_entry)
        ).pack(side="left")

        # Output folder
        output_row = ctk.CTkFrame(frame, fg_color="transparent")
        output_row.pack(anchor="w", padx=15, pady=(5, 15))

        ctk.CTkLabel(output_row, text="Output:", width=80).pack(side="left")
        self.output_folder_entry = ctk.CTkEntry(output_row, width=300)
        self.output_folder_entry.pack(side="left", padx=10)
        self.output_folder_entry.insert(0, self.app.config.output_folder)

        ctk.CTkButton(
            output_row,
            text="📁",
            width=40,
            command=lambda: self.browse_folder(self.output_folder_entry)
        ).pack(side="left")

        # Voice folder
        voice_row = ctk.CTkFrame(frame, fg_color="transparent")
        voice_row.pack(anchor="w", padx=15, pady=(5, 15))

        ctk.CTkLabel(voice_row, text="Voice:", width=80).pack(side="left")
        self.voice_folder_entry = ctk.CTkEntry(voice_row, width=300)
        self.voice_folder_entry.pack(side="left", padx=10)
        self.voice_folder_entry.insert(0, self.app.config.voice_folder or "voice")

        ctk.CTkButton(
            voice_row,
            text="📁",
            width=40,
            command=lambda: self.browse_folder(self.voice_folder_entry)
        ).pack(side="left")

    def setup_gemini_config(self):
        """Gemini API configuration"""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            frame,
            text="🤖 Gemini API",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # API Key
        ctk.CTkLabel(frame, text="API Key:").pack(anchor="w", padx=15, pady=(5, 0))
        self.gemini_key_entry = ctk.CTkEntry(frame, width=400, show="*")
        self.gemini_key_entry.pack(anchor="w", padx=15, pady=(0, 5))
        self.gemini_key_entry.insert(0, self.app.config.gemini_api_key)

        # Show/hide button
        key_btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        key_btn_row.pack(anchor="w", padx=15, pady=(0, 10))

        self.show_key_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            key_btn_row,
            text="Hiện API Key",
            variable=self.show_key_var,
            command=self.toggle_api_key_visibility
        ).pack(side="left")

        # Help text
        ctk.CTkLabel(
            frame,
            text="Lấy API key tại: https://aistudio.google.com/apikey",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 15))

    def toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        if self.show_key_var.get():
            self.gemini_key_entry.configure(show="")
        else:
            self.gemini_key_entry.configure(show="*")

    def setup_advanced_config(self):
        """Advanced settings"""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            frame,
            text="⚙️ Nâng cao",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Max threads
        threads_row = ctk.CTkFrame(frame, fg_color="transparent")
        threads_row.pack(anchor="w", padx=15, pady=5)

        ctk.CTkLabel(threads_row, text="Số luồng tối đa:").pack(side="left")
        self.threads_entry = ctk.CTkEntry(threads_row, width=60)
        self.threads_entry.pack(side="left", padx=10)
        self.threads_entry.insert(0, str(self.app.config.max_threads))

        ctk.CTkLabel(
            threads_row,
            text="(1 luồng = 1 browser)",
            text_color="gray"
        ).pack(side="left", padx=10)

        # Wait time
        wait_row = ctk.CTkFrame(frame, fg_color="transparent")
        wait_row.pack(anchor="w", padx=15, pady=5)

        ctk.CTkLabel(wait_row, text="Chờ sau done (s):").pack(side="left")
        self.wait_entry = ctk.CTkEntry(wait_row, width=60)
        self.wait_entry.pack(side="left", padx=10)
        self.wait_entry.insert(0, str(self.app.config.wait_after_done))

        # Max retries
        retry_row = ctk.CTkFrame(frame, fg_color="transparent")
        retry_row.pack(anchor="w", padx=15, pady=5)

        ctk.CTkLabel(retry_row, text="Số lần thử lại:").pack(side="left")
        self.retry_entry = ctk.CTkEntry(retry_row, width=60)
        self.retry_entry.pack(side="left", padx=10)
        self.retry_entry.insert(0, str(self.app.config.max_retries))

        # Chrome visibility toggle
        chrome_row = ctk.CTkFrame(frame, fg_color="transparent")
        chrome_row.pack(anchor="w", padx=15, pady=(10, 15))

        self.show_chrome_var = ctk.BooleanVar(value=getattr(self.app.config, 'show_chrome', True))
        self.show_chrome_checkbox = ctk.CTkCheckBox(
            chrome_row,
            text="Hiện Chrome khi chạy",
            variable=self.show_chrome_var,
            font=ctk.CTkFont(size=13)
        )
        self.show_chrome_checkbox.pack(side="left")

        ctk.CTkLabel(
            chrome_row,
            text="(Bỏ tích để chạy ẩn, tiết kiệm tài nguyên)",
            text_color="gray",
            font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=10)

    def setup_save_button(self):
        """Save button"""
        btn_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=20)

        ctk.CTkButton(
            btn_frame,
            text="💾 Lưu cài đặt",
            command=self.save_settings,
            width=200,
            height=45,
            fg_color="green",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack()

    def browse_credentials(self):
        """Browse for credentials file"""
        file = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")]
        )
        if file:
            self.credentials_entry.delete(0, "end")
            self.credentials_entry.insert(0, file)

    def browse_folder(self, entry):
        """Browse for folder"""
        folder = filedialog.askdirectory()
        if folder:
            entry.delete(0, "end")
            entry.insert(0, folder)

    def save_settings(self):
        """Save all settings"""
        # Update config
        self.app.config.spreadsheet_id = self.spreadsheet_entry.get()
        self.app.config.sheet_name = self.sheet_name_entry.get()
        self.app.config.credentials_file = self.credentials_entry.get()
        self.app.config.status_column = self.status_col_entry.get()
        self.app.config.prompt_column = self.prompt_col_entry.get()
        self.app.config.input_folder = self.input_folder_entry.get()
        self.app.config.output_folder = self.output_folder_entry.get()
        self.app.config.voice_folder = self.voice_folder_entry.get()
        self.app.config.gemini_api_key = self.gemini_key_entry.get()

        try:
            self.app.config.max_threads = int(self.threads_entry.get())
            self.app.config.wait_after_done = int(self.wait_entry.get())
            self.app.config.max_retries = int(self.retry_entry.get())
        except ValueError:
            messagebox.showerror("Lỗi", "Giá trị số không hợp lệ!")
            return

        # Chrome visibility
        self.app.config.show_chrome = self.show_chrome_var.get()

        # Save
        self.app.save_config()
        self.app.log("Đã lưu cài đặt")
        messagebox.showinfo("Thành công", "Đã lưu cài đặt!")


class ProfileDialog(ctk.CTkToplevel):
    """Dialog for adding/editing browser profile"""

    def __init__(self, parent, app, profile=None):
        super().__init__(parent)

        self.app = app
        self.profile = profile
        self.result = None

        self.title("Thêm Browser Profile" if not profile else "Sửa Browser Profile")
        self.geometry("500x400")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self.setup_ui()
        self.center_window()

    def center_window(self):
        """Center dialog"""
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (250)
        y = (self.winfo_screenheight() // 2) - (200)
        self.geometry(f"+{x}+{y}")

    def setup_ui(self):
        """Setup dialog UI"""
        # Name
        ctk.CTkLabel(self, text="Tên Profile:").pack(anchor="w", padx=20, pady=(20, 5))
        self.name_entry = ctk.CTkEntry(self, width=400)
        self.name_entry.pack(padx=20)
        if self.profile:
            self.name_entry.insert(0, self.profile.get("name", ""))

        # Chrome path
        ctk.CTkLabel(self, text="Đường dẫn Chrome:").pack(anchor="w", padx=20, pady=(15, 5))
        chrome_row = ctk.CTkFrame(self, fg_color="transparent")
        chrome_row.pack(fill="x", padx=20)

        self.chrome_entry = ctk.CTkEntry(chrome_row, width=350)
        self.chrome_entry.pack(side="left")
        default_chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.chrome_entry.insert(0, self.profile.get("chrome_path", default_chrome) if self.profile else default_chrome)

        ctk.CTkButton(
            chrome_row,
            text="📁",
            width=40,
            command=self.browse_chrome
        ).pack(side="left", padx=5)

        # Profile path (thư mục lưu dữ liệu browser)
        ctk.CTkLabel(self, text="Thư mục Profile (tự tạo):").pack(anchor="w", padx=20, pady=(15, 5))

        profile_row = ctk.CTkFrame(self, fg_color="transparent")
        profile_row.pack(fill="x", padx=20)

        self.profile_entry = ctk.CTkEntry(profile_row, width=350)
        self.profile_entry.pack(side="left")

        # Tự động tạo đường dẫn profile
        home = Path.home()
        profile_name = self.profile.get("name", "grok_profile") if self.profile else "grok_profile"
        default_profile_path = str(home / ".grok_profiles" / profile_name.replace(" ", "_"))

        if self.profile and self.profile.get("profile_path"):
            self.profile_entry.insert(0, self.profile.get("profile_path"))
        else:
            self.profile_entry.insert(0, default_profile_path)

        ctk.CTkButton(
            profile_row,
            text="📁",
            width=40,
            command=self.browse_profile
        ).pack(side="left", padx=5)

        # Help text
        help_text = """
Thư mục Profile:
• Tool sẽ TẠO MỚI thư mục này để lưu dữ liệu browser
• KHÔNG dùng profile Chrome có sẵn
• Lần đầu cần Login để đăng nhập Grok
• Các lần sau sẽ tự động dùng tài khoản đã login
        """
        ctk.CTkLabel(
            self,
            text=help_text.strip(),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left"
        ).pack(anchor="w", padx=20, pady=15)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkButton(
            btn_frame,
            text="💾 Lưu",
            command=self.save,
            width=100,
            fg_color="green"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="🔑 Login ngay",
            command=self.open_login,
            width=100,
            fg_color="#FF9800"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="❌ Hủy",
            command=self.cancel,
            width=100
        ).pack(side="left", padx=5)

    def browse_chrome(self):
        """Browse for Chrome executable"""
        file = filedialog.askopenfilename(
            filetypes=[("Executable", "*.exe")]
        )
        if file:
            self.chrome_entry.delete(0, "end")
            self.chrome_entry.insert(0, file)

    def browse_profile(self):
        """Browse for profile folder"""
        folder = filedialog.askdirectory()
        if folder:
            self.profile_entry.delete(0, "end")
            self.profile_entry.insert(0, folder)

    def save(self):
        """Save profile"""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Lỗi", "Vui lòng nhập tên profile!")
            return

        self.result = {
            "name": name,
            "chrome_path": self.chrome_entry.get(),
            "profile_path": self.profile_entry.get(),
            "enabled": True
        }
        self.destroy()

    def open_login(self):
        """Mở browser để login - dùng undetected_chromedriver"""
        profile_path = self.profile_entry.get().strip()
        if not profile_path:
            home = Path.home()
            profile_name = self.name_entry.get().strip() or "grok_profile"
            profile_path = str(home / ".grok_profiles" / profile_name.replace(" ", "_"))

        def run_chrome():
            try:
                import undetected_chromedriver as uc

                # Tạo thư mục profile nếu chưa có
                Path(profile_path).mkdir(parents=True, exist_ok=True)

                options = uc.ChromeOptions()
                options.add_argument("--window-size=1200,800")

                driver = uc.Chrome(
                    options=options,
                    user_data_dir=profile_path,
                    use_subprocess=True
                )
                driver.get("https://grok.com")

            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở browser: {e}")

        threading.Thread(target=run_chrome, daemon=True).start()

        messagebox.showinfo(
            "Login",
            f"Đang mở Chrome...\n\n"
            f"Profile: {profile_path}\n\n"
            "1. Đăng nhập tài khoản Grok\n"
            "2. Đóng browser khi xong\n"
            "3. Nhấn 'Lưu' để lưu profile"
        )

    def cancel(self):
        """Cancel and close"""
        self.destroy()
