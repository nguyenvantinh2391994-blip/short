"""
Token Extractor - Hướng dẫn và quản lý token từ Grok
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()


class TokenExtractor:
    """Quản lý token từ Grok"""

    def __init__(self, tokens_file: str = "config/grok_tokens.json"):
        self.tokens_file = Path(tokens_file)
        self.tokens: List[Dict] = self._load_tokens()

    def _load_tokens(self) -> List[Dict]:
        """Load tokens từ file"""
        if self.tokens_file.exists():
            with open(self.tokens_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("tokens", [])
        return []

    def _save_tokens(self) -> None:
        """Lưu tokens ra file"""
        self.tokens_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.tokens_file, "w", encoding="utf-8") as f:
            json.dump({
                "tokens": self.tokens,
                "updated_at": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)

    def show_instructions(self) -> None:
        """Hiển thị hướng dẫn lấy token"""
        instructions = """
# Hướng dẫn lấy Token từ Grok

## Bước 1: Mở Grok Imagine
1. Mở Chrome với profile đã đăng nhập
2. Truy cập: https://grok.com/imagine

## Bước 2: Mở Developer Tools
1. Nhấn `F12` hoặc `Ctrl + Shift + I`
2. Chuyển sang tab **Network**
3. Tick chọn **Preserve log**

## Bước 3: Tạo 1 ảnh/video thử
1. Nhập prompt bất kỳ (ví dụ: "a cat")
2. Nhấn Generate/Create

## Bước 4: Tìm Request API
1. Trong Network tab, filter theo **Fetch/XHR**
2. Tìm request có tên như:
   - `imagine` hoặc `generate`
   - `api/imagine` hoặc `api/2/grok/...`
3. Click vào request đó

## Bước 5: Copy thông tin cần thiết
Trong tab **Headers**, copy các giá trị sau:

### Authorization (Bearer Token):
```
Authorization: Bearer eyJhbGciOiJS...
```

### Cookies (nếu có):
```
Cookie: auth_token=...; ct0=...
```

### X-CSRF-Token hoặc X-Auth-Token (nếu có):
```
x-csrf-token: abc123...
```

## Bước 6: Lưu token
Chạy lệnh sau và paste thông tin:
```bash
python -m src.main add-token
```

---
**Lưu ý:** Token có thể hết hạn sau vài giờ. Cần cập nhật lại khi gặp lỗi 401/403.
"""
        console.print(Panel(Markdown(instructions), title="[bold cyan]Hướng dẫn lấy Token[/]"))

    def add_token(
        self,
        bearer_token: str,
        cookies: Optional[str] = None,
        csrf_token: Optional[str] = None,
        profile_name: str = "Default",
        note: str = ""
    ) -> None:
        """Thêm token mới"""
        # Chuẩn hóa bearer token
        if bearer_token.startswith("Bearer "):
            bearer_token = bearer_token[7:]

        token_entry = {
            "id": len(self.tokens) + 1,
            "bearer_token": bearer_token,
            "cookies": cookies,
            "csrf_token": csrf_token,
            "profile_name": profile_name,
            "note": note,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "status": "active",
            "usage_count": 0
        }

        self.tokens.append(token_entry)
        self._save_tokens()
        console.print(f"[green]✅ Đã thêm token #{token_entry['id']} ({profile_name})[/]")

    def get_active_token(self) -> Optional[Dict]:
        """Lấy token active đầu tiên"""
        for token in self.tokens:
            if token.get("status") == "active":
                return token
        return None

    def get_all_active_tokens(self) -> List[Dict]:
        """Lấy tất cả tokens đang active"""
        return [t for t in self.tokens if t.get("status") == "active"]

    def mark_token_used(self, token_id: int) -> None:
        """Đánh dấu token đã sử dụng"""
        for token in self.tokens:
            if token["id"] == token_id:
                token["last_used"] = datetime.now().isoformat()
                token["usage_count"] = token.get("usage_count", 0) + 1
                self._save_tokens()
                break

    def mark_token_expired(self, token_id: int) -> None:
        """Đánh dấu token đã hết hạn"""
        for token in self.tokens:
            if token["id"] == token_id:
                token["status"] = "expired"
                self._save_tokens()
                console.print(f"[yellow]⚠️ Token #{token_id} đã hết hạn[/]")
                break

    def list_tokens(self) -> None:
        """Hiển thị danh sách tokens"""
        if not self.tokens:
            console.print("[yellow]Chưa có token nào. Chạy 'add-token' để thêm.[/]")
            return

        console.print("\n[bold]📋 Danh sách Tokens:[/]\n")
        for token in self.tokens:
            status_color = "green" if token["status"] == "active" else "red"
            status_icon = "✅" if token["status"] == "active" else "❌"

            console.print(f"  [{status_color}]{status_icon}[/] Token #{token['id']}")
            console.print(f"     Profile: {token['profile_name']}")
            console.print(f"     Status: [{status_color}]{token['status']}[/]")
            console.print(f"     Đã dùng: {token.get('usage_count', 0)} lần")
            if token.get('last_used'):
                console.print(f"     Lần cuối: {token['last_used']}")
            if token.get('note'):
                console.print(f"     Ghi chú: {token['note']}")
            console.print()

    def rotate_token(self) -> Optional[Dict]:
        """Xoay vòng qua các token (để phân tải)"""
        active_tokens = self.get_all_active_tokens()
        if not active_tokens:
            return None

        # Sắp xếp theo usage_count để dùng token ít dùng nhất
        active_tokens.sort(key=lambda t: t.get("usage_count", 0))
        return active_tokens[0]


def interactive_add_token():
    """Thêm token tương tác qua CLI"""
    extractor = TokenExtractor()

    console.print("\n[bold cyan]🔐 Thêm Token mới[/]\n")

    # Hiển thị hướng dẫn trước
    show_guide = console.input("Hiển thị hướng dẫn lấy token? [Y/n]: ").strip().lower()
    if show_guide != "n":
        extractor.show_instructions()
        console.print()

    # Nhập thông tin
    bearer = console.input("[bold]Bearer Token[/] (bắt buộc): ").strip()
    if not bearer:
        console.print("[red]❌ Bearer token không được để trống![/]")
        return

    cookies = console.input("[bold]Cookies[/] (optional, Enter để bỏ qua): ").strip() or None
    csrf = console.input("[bold]CSRF Token[/] (optional, Enter để bỏ qua): ").strip() or None
    profile = console.input("[bold]Tên profile[/] (default: Default): ").strip() or "Default"
    note = console.input("[bold]Ghi chú[/] (optional): ").strip() or ""

    extractor.add_token(
        bearer_token=bearer,
        cookies=cookies,
        csrf_token=csrf,
        profile_name=profile,
        note=note
    )


if __name__ == "__main__":
    interactive_add_token()
