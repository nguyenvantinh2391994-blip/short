"""
Logs Tab - Hiển thị log hoạt động
"""

import customtkinter as ctk
from datetime import datetime


class LogsTab:
    """Logs Tab"""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        # Main frame
        main_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Header
        header = ctk.CTkFrame(main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            header,
            text="📋 Logs",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        # Clear button
        ctk.CTkButton(
            header,
            text="🗑️ Xóa logs",
            command=self.clear_logs,
            width=100
        ).pack(side="right")

        # Export button
        ctk.CTkButton(
            header,
            text="📤 Xuất file",
            command=self.export_logs,
            width=100
        ).pack(side="right", padx=5)

        # Filter
        filter_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        filter_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(filter_frame, text="Lọc:").pack(side="left")

        self.filter_var = ctk.StringVar(value="ALL")
        filters = ["ALL", "INFO", "SUCCESS", "WARNING", "ERROR"]

        for f in filters:
            ctk.CTkRadioButton(
                filter_frame,
                text=f,
                variable=self.filter_var,
                value=f,
                command=self.apply_filter
            ).pack(side="left", padx=10)

        # Log textbox
        self.log_text = ctk.CTkTextbox(
            main_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)

        # Store all logs for filtering
        self.all_logs = []

    def add_log(self, message: str, level: str = "INFO"):
        """Add log message"""
        # Store log
        self.all_logs.append((message, level))

        # Check filter
        current_filter = self.filter_var.get()
        if current_filter != "ALL" and level.upper() != current_filter:
            return

        # Color based on level
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")

    def apply_filter(self):
        """Apply filter to logs"""
        self.log_text.delete("1.0", "end")

        current_filter = self.filter_var.get()

        for message, level in self.all_logs:
            if current_filter == "ALL" or level.upper() == current_filter:
                self.log_text.insert("end", f"{message}\n")

        self.log_text.see("end")

    def clear_logs(self):
        """Clear all logs"""
        self.log_text.delete("1.0", "end")
        self.all_logs.clear()

    def export_logs(self):
        """Export logs to file"""
        from tkinter import filedialog

        file = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfilename=f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if file:
            try:
                with open(file, "w", encoding="utf-8") as f:
                    for message, level in self.all_logs:
                        f.write(f"{message}\n")

                self.app.log(f"Đã xuất logs ra: {file}")
            except Exception as e:
                self.app.log(f"Lỗi xuất logs: {e}", "ERROR")
