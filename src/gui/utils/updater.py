"""
Auto Updater - Tự động cập nhật code từ git
"""

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple


class AutoUpdater:
    """Tự động cập nhật code từ git repository"""

    def __init__(self, repo_path: str = None, on_log: Callable[[str, str], None] = None):
        self.repo_path = Path(repo_path) if repo_path else Path(__file__).parent.parent.parent.parent
        self.on_log = on_log

    def log(self, msg: str, level: str = "info"):
        """Log message"""
        if self.on_log:
            self.on_log(msg, level)
        print(f"[Updater] {msg}")

    def is_git_repo(self) -> bool:
        """Kiểm tra có phải git repo không"""
        git_dir = self.repo_path / ".git"
        return git_dir.exists()

    def run_git(self, *args) -> Tuple[bool, str]:
        """Chạy lệnh git"""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout.strip() or result.stderr.strip()
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except FileNotFoundError:
            return False, "Git không được cài đặt"
        except Exception as e:
            return False, str(e)

    def get_current_branch(self) -> str:
        """Lấy tên branch hiện tại"""
        success, output = self.run_git("rev-parse", "--abbrev-ref", "HEAD")
        return output if success else "unknown"

    def check_for_updates(self) -> Tuple[bool, int]:
        """
        Kiểm tra có update mới không
        Returns: (success, số commit phía sau)
        """
        if not self.is_git_repo():
            self.log("Không phải git repository", "warning")
            return False, 0

        # Fetch từ remote
        self.log("Đang kiểm tra cập nhật...", "progress")
        success, output = self.run_git("fetch", "origin")
        if not success:
            self.log(f"Không thể fetch: {output}", "warning")
            return False, 0

        # Kiểm tra số commit phía sau
        branch = self.get_current_branch()
        success, output = self.run_git(
            "rev-list", "--count", f"HEAD..origin/{branch}"
        )

        if success and output.isdigit():
            behind = int(output)
            if behind > 0:
                self.log(f"Có {behind} commit mới", "info")
            return True, behind

        return True, 0

    def pull_updates(self) -> Tuple[bool, str]:
        """
        Pull updates từ remote
        Returns: (success, message)
        """
        if not self.is_git_repo():
            return False, "Không phải git repository"

        self.log("Đang cập nhật...", "progress")

        # Stash local changes nếu có
        self.run_git("stash")

        # Pull
        success, output = self.run_git("pull", "origin", self.get_current_branch())

        if success:
            self.log("Cập nhật thành công!", "success")
            return True, output
        else:
            self.log(f"Lỗi cập nhật: {output}", "error")
            # Restore stash
            self.run_git("stash", "pop")
            return False, output

    def update_if_available(self) -> Tuple[bool, str]:
        """
        Kiểm tra và cập nhật nếu có bản mới
        Returns: (đã cập nhật, message)
        """
        success, behind = self.check_for_updates()

        if not success:
            return False, "Không thể kiểm tra cập nhật"

        if behind == 0:
            self.log("Đã là phiên bản mới nhất", "success")
            return False, "Đã là phiên bản mới nhất"

        # Có update, tiến hành pull
        success, msg = self.pull_updates()
        return success, msg

    def get_version_info(self) -> dict:
        """Lấy thông tin phiên bản"""
        info = {
            "branch": self.get_current_branch(),
            "commit": "unknown",
            "date": "unknown"
        }

        # Get latest commit hash
        success, output = self.run_git("rev-parse", "--short", "HEAD")
        if success:
            info["commit"] = output

        # Get commit date
        success, output = self.run_git("log", "-1", "--format=%ci")
        if success:
            info["date"] = output[:10]  # YYYY-MM-DD

        return info


def auto_update(repo_path: str = None, on_log: Callable = None) -> bool:
    """
    Hàm tiện ích để auto update
    Returns: True nếu đã cập nhật, False nếu không có gì mới
    """
    updater = AutoUpdater(repo_path, on_log)
    updated, msg = updater.update_if_available()
    return updated
