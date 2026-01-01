"""
Chrome Manager - Quản lý Chrome dùng chung cho tất cả tính năng
(Shopee, Gemini, Grok, SORA, Flow...)
"""

import subprocess
import time
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


class ChromeManager:
    """Singleton Chrome Manager - dùng chung 1 Chrome cho toàn bộ app"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.chrome_process: Optional[subprocess.Popen] = None
        self.chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        self.profile_path: Optional[str] = None
        self.profile_name: Optional[str] = None
        self._is_first_tab = True

    def set_profile(self, chrome_path: str = None, profile_path: str = None, profile_name: str = None):
        """Cài đặt profile để dùng"""
        if chrome_path:
            self.chrome_path = chrome_path
        if profile_path:
            self.profile_path = profile_path
        if profile_name:
            self.profile_name = profile_name

    def is_running(self) -> bool:
        """Kiểm tra Chrome có đang chạy không"""
        if self.chrome_process is None:
            return False
        return self.chrome_process.poll() is None

    def open_chrome(self, url: str = None) -> bool:
        """
        Mở Chrome nếu chưa mở, hoặc mở tab mới nếu đã mở

        Returns:
            True nếu thành công
        """
        try:
            if self.is_running():
                # Chrome đang chạy, mở tab mới
                return self.open_new_tab(url)

            # Mở Chrome mới
            console.print(f"[cyan]🌐 Mở Chrome...[/]")

            # Profile path
            if self.profile_path:
                tool_profile = Path(self.profile_path)
            else:
                home = Path.home()
                tool_profile = home / ".tool_chrome_profile"
            tool_profile.mkdir(parents=True, exist_ok=True)

            console.print(f"[dim]Chrome: {self.chrome_path}[/]")
            console.print(f"[dim]Profile: {tool_profile}[/]")
            if self.profile_name:
                console.print(f"[dim]Account: {self.profile_name}[/]")

            cmd = [
                self.chrome_path,
                f"--user-data-dir={tool_profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                # Tắt Safe Browsing để không bị chặn download video
                "--safebrowsing-disable-download-protection",
                "--disable-features=SafeBrowsingEnhancedProtection",
                "--safebrowsing-disable-extension-blacklist",
            ]

            if url:
                cmd.append(url)

            self.chrome_process = subprocess.Popen(cmd, shell=False)
            console.print(f"[green]Chrome PID: {self.chrome_process.pid}[/]")
            self._is_first_tab = True
            time.sleep(4)  # Chờ Chrome khởi động
            return True

        except Exception as e:
            console.print(f"[red]Lỗi mở Chrome: {e}[/]")
            return False

    def open_new_tab(self, url: str = None) -> bool:
        """Mở tab mới trong Chrome đang chạy"""
        try:
            import pyautogui as pag
            import pyperclip

            console.print(f"[cyan]📑 Mở tab mới...[/]")
            self._focus_chrome()

            # Ctrl+T để mở tab mới
            pag.hotkey("ctrl", "t")
            time.sleep(0.5)

            if url:
                pyperclip.copy(url)
                pag.hotkey("ctrl", "v")
                pag.press("enter")

            return True

        except Exception as e:
            console.print(f"[red]Lỗi mở tab: {e}[/]")
            return False

    def close_current_tab(self):
        """Đóng tab hiện tại (không đóng Chrome)"""
        try:
            import pyautogui as pag

            if self._is_first_tab:
                # Không đóng tab đầu tiên
                self._is_first_tab = False
                return

            self._focus_chrome()
            pag.hotkey("ctrl", "w")
            time.sleep(0.3)
            console.print(f"[dim]Đã đóng tab[/]")

        except Exception as e:
            console.print(f"[yellow]Lỗi đóng tab: {e}[/]")

    def close_chrome(self):
        """Đóng Chrome hoàn toàn"""
        if self.chrome_process:
            try:
                # Dùng kill() thay vì terminate() để đảm bảo đóng hoàn toàn
                self.chrome_process.kill()
                self.chrome_process.wait(timeout=5)
                console.print(f"[dim]Đã đóng Chrome[/]")
            except Exception as e:
                console.print(f"[yellow]Lỗi đóng Chrome: {e}[/]")
            finally:
                self.chrome_process = None
                self._is_first_tab = True

        # Reset profile để lần sau dùng profile mới
        console.print(f"[dim]Reset chrome_manager profile[/]")

    def _focus_chrome(self) -> bool:
        """Focus vào cửa sổ Chrome"""
        try:
            import pygetwindow as gw

            # Tìm cửa sổ Chrome
            windows = gw.getWindowsWithTitle('Chrome')
            if not windows:
                windows = gw.getWindowsWithTitle('Google')

            if windows:
                win = windows[0]
                win.activate()
                time.sleep(0.3)
                return True

        except Exception:
            pass
        return False

    def run_js(self, js: str) -> str:
        """Chạy JavaScript qua DevTools Console"""
        try:
            import pyautogui as pag
            import pyperclip

            self._focus_chrome()
            time.sleep(0.3)

            # Clear clipboard
            pyperclip.copy("")

            # Mở DevTools Console
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(1)

            # Paste và chạy JS
            pyperclip.copy(js)
            time.sleep(0.2)
            pag.hotkey("ctrl", "v")
            time.sleep(0.3)
            pag.press("enter")
            time.sleep(1.5)

            # Lấy kết quả từ clipboard
            result = pyperclip.paste()

            # Đóng DevTools
            pag.hotkey("ctrl", "shift", "j")
            time.sleep(0.3)

            # Kiểm tra kết quả
            if result and result != js:
                return result
            return ""

        except Exception as e:
            console.print(f"[yellow]Lỗi run_js: {e}[/]")
            return ""

    def navigate_to(self, url: str) -> bool:
        """Điều hướng đến URL trong tab hiện tại"""
        try:
            import pyautogui as pag
            import pyperclip

            self._focus_chrome()

            # Ctrl+L để focus address bar
            pag.hotkey("ctrl", "l")
            time.sleep(0.3)

            # Nhập URL
            pyperclip.copy(url)
            pag.hotkey("ctrl", "v")
            pag.press("enter")

            return True

        except Exception as e:
            console.print(f"[red]Lỗi navigate: {e}[/]")
            return False


# Singleton instance
chrome_manager = ChromeManager()
