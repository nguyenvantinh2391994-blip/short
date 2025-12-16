"""
x.ai Official API Client
Sử dụng API chính thức của x.ai để tạo ảnh/video với Grok
"""

import requests
import json
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@dataclass
class XAIResponse:
    """Response từ x.ai API"""
    success: bool
    data: Optional[Dict] = None
    images: Optional[List[str]] = None
    error: Optional[str] = None


class XAIClient:
    """Client cho x.ai Official API"""

    BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_key: Optional[str] = None, config_file: str = "config/xai_config.json"):
        self.api_key = api_key
        self.config_file = Path(config_file)

        if not self.api_key:
            self._load_api_key()

        self.session = requests.Session()
        self._setup_session()

    def _load_api_key(self):
        """Load API key từ config file"""
        if self.config_file.exists():
            with open(self.config_file, "r") as f:
                config = json.load(f)
                self.api_key = config.get("api_key")

        if not self.api_key:
            console.print("[yellow]⚠️ Chưa có API key. Chạy: python -m src.main setup-xai[/]")

    def _setup_session(self):
        """Setup session với headers"""
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            })

    def test_connection(self) -> bool:
        """Test kết nối API"""
        if not self.api_key:
            console.print("[red]❌ Chưa có API key![/]")
            return False

        try:
            # Test với endpoint models
            response = self.session.get(f"{self.BASE_URL}/models", timeout=10)

            if response.status_code == 200:
                console.print("[green]✅ Kết nối x.ai API thành công![/]")
                data = response.json()
                models = data.get("data", [])
                if models:
                    console.print(f"[dim]Các models có sẵn: {', '.join(m.get('id', '') for m in models[:5])}[/]")
                return True
            elif response.status_code == 401:
                console.print("[red]❌ API key không hợp lệ![/]")
                return False
            else:
                console.print(f"[yellow]⚠️ HTTP {response.status_code}: {response.text[:100]}[/]")
                return False

        except Exception as e:
            console.print(f"[red]❌ Lỗi kết nối: {e}[/]")
            return False

    def chat(self, prompt: str, model: str = "grok-beta") -> XAIResponse:
        """Chat với Grok"""
        if not self.api_key:
            return XAIResponse(success=False, error="Chưa có API key")

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }

        try:
            response = self.session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return XAIResponse(success=True, data=data)
            else:
                return XAIResponse(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )

        except Exception as e:
            return XAIResponse(success=False, error=str(e))

    def generate_image(
        self,
        prompt: str,
        model: str = "aurora",  # Grok's image model
        n: int = 1,
        size: str = "1024x1024"
    ) -> XAIResponse:
        """Tạo ảnh với Grok Aurora"""
        if not self.api_key:
            return XAIResponse(success=False, error="Chưa có API key")

        payload = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size
        }

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Đang tạo ảnh với Grok...", total=None)

                response = self.session.post(
                    f"{self.BASE_URL}/images/generations",
                    json=payload,
                    timeout=120
                )

                progress.update(task, completed=True)

            if response.status_code == 200:
                data = response.json()
                images = [img.get("url") for img in data.get("data", [])]
                return XAIResponse(success=True, data=data, images=images)
            else:
                return XAIResponse(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )

        except Exception as e:
            return XAIResponse(success=False, error=str(e))

    def download_image(self, url: str, output_path: str) -> bool:
        """Tải ảnh về"""
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.content)
                console.print(f"[green]✅ Đã tải: {output_path}[/]")
                return True
        except Exception as e:
            console.print(f"[red]❌ Lỗi tải ảnh: {e}[/]")
        return False


def setup_xai_api():
    """Hướng dẫn và setup x.ai API"""
    console.print("\n[bold cyan]🔧 Setup x.ai API[/]\n")

    console.print("""
[bold]Bước 1: Đăng ký tài khoản x.ai[/]
  • Truy cập: https://console.x.ai/
  • Đăng nhập bằng tài khoản X (Twitter)

[bold]Bước 2: Tạo API Key[/]
  • Vào mục API Keys
  • Click "Create new key"
  • Copy API key

[bold]Bước 3: Nhập API key bên dưới[/]
""")

    api_key = console.input("[bold]Nhập API Key:[/] ").strip()

    if not api_key:
        console.print("[red]❌ API key không được để trống![/]")
        return

    # Lưu config
    config = {"api_key": api_key}
    config_path = Path("config/xai_config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print(f"[green]✅ Đã lưu API key vào {config_path}[/]")

    # Test connection
    client = XAIClient(api_key)
    client.test_connection()


if __name__ == "__main__":
    setup_xai_api()
