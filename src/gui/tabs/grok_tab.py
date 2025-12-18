"""
Grok Tab - Tạo video từ Grok AI
"""

import customtkinter as ctk
from pathlib import Path
import threading
from typing import Optional
import queue


class GrokTab:
    """Grok Video Creation Tab"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.is_running = False
        self.current_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self.task_queue = queue.Queue()

        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        # Main container with 2 columns
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Left column - Controls
        self.setup_controls()

        # Right column - Progress
        self.setup_progress()

    def setup_controls(self):
        """Setup control panel"""
        controls_frame = ctk.CTkFrame(self.main_frame)
        controls_frame.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=0)

        # Title
        title = ctk.CTkLabel(
            controls_frame,
            text="🎬 Grok Video Creator",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(padx=20, pady=(20, 10))

        # Browser profile selection
        profile_frame = ctk.CTkFrame(controls_frame)
        profile_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            profile_frame,
            text="Browser Profile:",
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.profile_var = ctk.StringVar(value="Default")
        self.profile_dropdown = ctk.CTkOptionMenu(
            profile_frame,
            variable=self.profile_var,
            values=self.get_profile_names(),
            width=300
        )
        self.profile_dropdown.pack(padx=15, pady=(0, 10))

        # Input/Output folders
        folder_frame = ctk.CTkFrame(controls_frame)
        folder_frame.pack(fill="x", padx=20, pady=10)

        # Thư mục ảnh (chứa thư mục con theo mã)
        ctk.CTkLabel(
            folder_frame,
            text="📁 Thư mục ảnh (chứa thư mục con theo mã):",
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", padx=15, pady=(10, 5))

        input_row = ctk.CTkFrame(folder_frame, fg_color="transparent")
        input_row.pack(fill="x", padx=15)

        self.input_entry = ctk.CTkEntry(input_row, width=250)
        self.input_entry.pack(side="left")
        self.input_entry.insert(0, self.app.config.input_folder)

        ctk.CTkButton(
            input_row,
            text="📁",
            width=40,
            command=lambda: self.browse_folder("input")
        ).pack(side="left", padx=5)

        # Thư mục nhạc
        ctk.CTkLabel(
            folder_frame,
            text="🎵 Thư mục nhạc (lấy lần lượt):",
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", padx=15, pady=(10, 5))

        music_row = ctk.CTkFrame(folder_frame, fg_color="transparent")
        music_row.pack(fill="x", padx=15)

        self.music_entry = ctk.CTkEntry(music_row, width=250)
        self.music_entry.pack(side="left")
        self.music_entry.insert(0, getattr(self.app.config, 'music_folder', ''))

        ctk.CTkButton(
            music_row,
            text="📁",
            width=40,
            command=lambda: self.browse_folder("music")
        ).pack(side="left", padx=5)

        # Thư mục voice
        ctk.CTkLabel(
            folder_frame,
            text="🎤 Thư mục voice (theo mã sản phẩm):",
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", padx=15, pady=(10, 5))

        voice_row = ctk.CTkFrame(folder_frame, fg_color="transparent")
        voice_row.pack(fill="x", padx=15)

        self.voice_entry = ctk.CTkEntry(voice_row, width=250)
        self.voice_entry.pack(side="left")
        self.voice_entry.insert(0, getattr(self.app.config, 'voice_folder', ''))

        ctk.CTkButton(
            voice_row,
            text="📁",
            width=40,
            command=lambda: self.browse_folder("voice")
        ).pack(side="left", padx=5)

        # Thư mục done (output video hoàn chỉnh)
        ctk.CTkLabel(
            folder_frame,
            text="✅ Thư mục Done (video hoàn chỉnh):",
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", padx=15, pady=(10, 5))

        output_row = ctk.CTkFrame(folder_frame, fg_color="transparent")
        output_row.pack(fill="x", padx=15, pady=(0, 10))

        self.output_entry = ctk.CTkEntry(output_row, width=250)
        self.output_entry.pack(side="left")
        self.output_entry.insert(0, self.app.config.output_folder)

        ctk.CTkButton(
            output_row,
            text="📁",
            width=40,
            command=lambda: self.browse_folder("output")
        ).pack(side="left", padx=5)

        # Options
        options_frame = ctk.CTkFrame(controls_frame)
        options_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            options_frame,
            text="Tùy chọn:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Transition type (chuyển cảnh)
        transition_row = ctk.CTkFrame(options_frame, fg_color="transparent")
        transition_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(transition_row, text="Chuyển cảnh:").pack(side="left")
        self.transition_var = ctk.StringVar(value="fade_black")
        self.transition_dropdown = ctk.CTkOptionMenu(
            transition_row,
            variable=self.transition_var,
            values=["fade_black", "crossfade"],
            width=120
        )
        self.transition_dropdown.pack(side="left", padx=10)

        # Max retries
        retry_row = ctk.CTkFrame(options_frame, fg_color="transparent")
        retry_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(retry_row, text="Số lần thử lại:").pack(side="left")
        self.retry_spinbox = ctk.CTkEntry(retry_row, width=60)
        self.retry_spinbox.pack(side="left", padx=10)
        self.retry_spinbox.insert(0, str(self.app.config.max_retries))

        # Wait time
        wait_row = ctk.CTkFrame(options_frame, fg_color="transparent")
        wait_row.pack(fill="x", padx=15, pady=(5, 10))

        ctk.CTkLabel(wait_row, text="Chờ sau done (s):").pack(side="left")
        self.wait_spinbox = ctk.CTkEntry(wait_row, width=60)
        self.wait_spinbox.pack(side="left", padx=10)
        self.wait_spinbox.insert(0, str(self.app.config.wait_after_done))

        # Hidden mode checkbox - MẶC ĐỊNH BẬT
        self.hidden_var = ctk.BooleanVar(value=True)
        self.hidden_check = ctk.CTkCheckBox(
            options_frame,
            text="🔒 Chạy ẩn (headless - không hiện browser)",
            variable=self.hidden_var,
            font=ctk.CTkFont(size=13)
        )
        self.hidden_check.pack(anchor="w", padx=15, pady=(0, 5))
        self.hidden_check.select()  # Mặc định chọn

        # Auto-update checkbox - MẶC ĐỊNH BẬT
        self.auto_update_var = ctk.BooleanVar(value=True)
        self.auto_update_check = ctk.CTkCheckBox(
            options_frame,
            text="🔄 Tự động cập nhật trước khi chạy",
            variable=self.auto_update_var,
            font=ctk.CTkFont(size=13)
        )
        self.auto_update_check.pack(anchor="w", padx=15, pady=(0, 10))
        self.auto_update_check.select()  # Mặc định chọn

        # Action buttons
        btn_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)

        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="▶️ Bắt đầu",
            command=self.start_process,
            width=150,
            height=45,
            fg_color="green",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="⏹️ Dừng",
            command=self.stop_process,
            width=150,
            height=45,
            fg_color="red",
            state="disabled",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.stop_btn.pack(side="left", padx=5)

        # Nút ẩn/hiện browser
        self.show_btn = ctk.CTkButton(
            btn_frame,
            text="👁️ Hiện Browser",
            command=self.toggle_browser_visibility,
            width=130,
            height=45,
            fg_color="#FF9800",
            state="disabled",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.show_btn.pack(side="left", padx=5)

        # Biến lưu automation object để có thể ẩn/hiện
        self.current_automation = None
        self._browser_visible = False

    def setup_progress(self):
        """Setup progress panel"""
        progress_frame = ctk.CTkFrame(self.main_frame, width=400)
        progress_frame.pack(side="right", fill="both", padx=(5, 0), pady=0)
        progress_frame.pack_propagate(False)

        # Title
        title = ctk.CTkLabel(
            progress_frame,
            text="📊 Tiến trình",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.pack(padx=20, pady=(20, 10))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=350)
        self.progress_bar.pack(padx=20, pady=10)
        self.progress_bar.set(0)

        # Progress label
        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="0/0 video",
            font=ctk.CTkFont(size=14)
        )
        self.progress_label.pack(pady=5)

        # Current task
        self.current_task_label = ctk.CTkLabel(
            progress_frame,
            text="Chưa bắt đầu",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.current_task_label.pack(pady=5)

        # Task list
        ctk.CTkLabel(
            progress_frame,
            text="Danh sách task:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))

        self.task_list = ctk.CTkTextbox(progress_frame, height=300)
        self.task_list.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def get_profile_names(self) -> list:
        """Get list of browser profile names"""
        profiles = self.app.config.browser_profiles
        if not profiles:
            return ["Default"]
        return [p.get("name", "Profile") for p in profiles]

    def refresh_profiles(self):
        """Refresh profile dropdown"""
        self.profile_dropdown.configure(values=self.get_profile_names())

    def browse_folder(self, folder_type: str):
        """Browse for folder"""
        from tkinter import filedialog
        folder = filedialog.askdirectory()
        if folder:
            if folder_type == "input":
                self.input_entry.delete(0, "end")
                self.input_entry.insert(0, folder)
            elif folder_type == "music":
                self.music_entry.delete(0, "end")
                self.music_entry.insert(0, folder)
            elif folder_type == "voice":
                self.voice_entry.delete(0, "end")
                self.voice_entry.insert(0, folder)
            else:  # output
                self.output_entry.delete(0, "end")
                self.output_entry.insert(0, folder)

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
            self.progress_label.configure(text=f"{current}/{total} video")
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
        self.stop_btn.configure(state="normal")
        self.task_list.delete("1.0", "end")
        self.progress_bar.set(0)

        # Get settings
        input_folder = self.input_entry.get()
        output_folder = self.output_entry.get()
        music_folder = self.music_entry.get()
        voice_folder = self.voice_entry.get()
        profile_name = self.profile_var.get()
        transition_type = self.transition_var.get()

        # Save to config
        self.app.config.input_folder = input_folder
        self.app.config.output_folder = output_folder
        self.app.config.music_folder = music_folder
        self.app.config.voice_folder = voice_folder
        self.app.save_config()

        # Start thread
        self.current_thread = threading.Thread(
            target=self.run_grok_process,
            args=(input_folder, output_folder, music_folder, voice_folder, profile_name, transition_type),
            daemon=True
        )
        self.current_thread.start()

        self.app.log("Bắt đầu tạo video Grok")
        self.add_task_log("Bắt đầu quá trình tạo video...", "progress")

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
        profile_name: str,
        transition_type: str
    ):
        """Run Grok video creation (in background thread)"""
        try:
            # Auto-update nếu được bật
            if self.auto_update_var.get():
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

            # Get browser profile
            profile = None
            for p in self.app.config.browser_profiles:
                if p.get("name") == profile_name:
                    profile = p
                    break

            # Get headless setting
            headless = self.hidden_var.get()

            # Create worker
            worker = GrokWorker(
                input_folder=input_folder,
                output_folder=output_folder,
                music_folder=music_folder,
                voice_folder=voice_folder,
                transition_type=transition_type,
                browser_profile=profile,
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
        self.stop_btn.configure(state="disabled")
        self.show_btn.configure(state="disabled")
        self.current_task_label.configure(text="Hoàn thành")
        self.app.set_status("Hoàn thành tạo video")
        self.add_task_log("Hoàn thành!", "success")
        self.current_automation = None

    def toggle_browser_visibility(self):
        """Toggle ẩn/hiện browser"""
        if self.current_automation:
            try:
                if self._browser_visible:
                    self.current_automation._hide_chrome_window()
                    self.show_btn.configure(text="👁️ Hiện Browser")
                    self._browser_visible = False
                    self.add_task_log("Đã ẩn browser", "info")
                else:
                    self.current_automation.show_chrome_window()
                    self.show_btn.configure(text="🙈 Ẩn Browser")
                    self._browser_visible = True
                    self.add_task_log("Đã hiện browser", "info")
            except Exception as e:
                self.add_task_log(f"Lỗi toggle browser: {e}", "error")

    def set_automation(self, automation):
        """Lưu reference đến automation object để có thể ẩn/hiện"""
        self.current_automation = automation
        # Kích hoạt nút ẩn/hiện
        self.after_safe(lambda: self.show_btn.configure(state="normal"))
        # Cập nhật trạng thái nút
        if hasattr(automation, '_is_hidden') and automation._is_hidden:
            self._browser_visible = False
            self.after_safe(lambda: self.show_btn.configure(text="👁️ Hiện Browser"))
        else:
            self._browser_visible = True
            self.after_safe(lambda: self.show_btn.configure(text="🙈 Ẩn Browser"))

    def after_safe(self, func):
        """Safely call function on main thread"""
        try:
            self.parent.after(0, func)
        except:
            pass
