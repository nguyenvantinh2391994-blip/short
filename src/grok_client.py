"""
Grok API Client - Gọi API Grok để tạo ảnh/video
"""

import json
import time
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .token_extractor import TokenExtractor

console = Console()


class GrokModel(Enum):
    """Các model của Grok"""
    GROK_2 = "grok-2"
    GROK_2_VISION = "grok-2-vision"
    FLUX = "flux"  # Image generation


@dataclass
class GrokResponse:
    """Response từ Grok API"""
    success: bool
    data: Optional[Dict] = None
    images: Optional[List[str]] = None  # URLs hoặc base64
    video_url: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[Dict] = None


class GrokClient:
    """Client để tương tác với Grok API"""

    # Các endpoint có thể của Grok (cần điều chỉnh theo thực tế)
    ENDPOINTS = {
        "imagine": "/api/imagine",
        "generate": "/api/generate",
        "grok_api": "/api/2/grok/add_response.json",
        "upload": "/api/upload",
    }

    def __init__(self, tokens_file: str = "config/grok_tokens.json"):
        self.token_extractor = TokenExtractor(tokens_file)
        self.base_url = "https://grok.com"
        self.session = requests.Session()
        self._setup_session()

    def _setup_session(self) -> None:
        """Setup session với headers mặc định"""
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://grok.com",
            "Referer": "https://grok.com/imagine",
        })

    def _get_headers_with_token(self, token: Dict) -> Dict[str, str]:
        """Tạo headers với token"""
        headers = dict(self.session.headers)

        # Bearer token
        if token.get("bearer_token"):
            headers["Authorization"] = f"Bearer {token['bearer_token']}"

        # CSRF token
        if token.get("csrf_token"):
            headers["x-csrf-token"] = token["csrf_token"]
            headers["x-twitter-auth-type"] = "OAuth2Session"  # Nếu dùng Twitter/X auth

        # Cookies
        if token.get("cookies"):
            headers["Cookie"] = token["cookies"]

        return headers

    def test_token(self, token: Optional[Dict] = None) -> bool:
        """Test xem token có hoạt động không"""
        if token is None:
            token = self.token_extractor.get_active_token()

        if not token:
            console.print("[red]❌ Không có token nào![/]")
            return False

        headers = self._get_headers_with_token(token)

        try:
            # Thử gọi một endpoint đơn giản
            response = self.session.get(
                f"{self.base_url}/api/user",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                console.print(f"[green]✅ Token #{token['id']} hoạt động![/]")
                return True
            elif response.status_code in [401, 403]:
                console.print(f"[red]❌ Token #{token['id']} đã hết hạn hoặc không hợp lệ[/]")
                self.token_extractor.mark_token_expired(token["id"])
                return False
            else:
                console.print(f"[yellow]⚠️ Status code: {response.status_code}[/]")
                return False

        except Exception as e:
            console.print(f"[red]❌ Lỗi kết nối: {e}[/]")
            return False

    def generate_image(
        self,
        prompt: str,
        num_images: int = 1,
        model: str = "flux",
        token: Optional[Dict] = None
    ) -> GrokResponse:
        """Tạo ảnh từ prompt"""
        if token is None:
            token = self.token_extractor.rotate_token()

        if not token:
            return GrokResponse(success=False, error="Không có token khả dụng")

        headers = self._get_headers_with_token(token)

        # Payload cho image generation (cần điều chỉnh theo API thực tế)
        payload = {
            "prompt": prompt,
            "model": model,
            "num_images": num_images,
            "size": "1024x1024",
        }

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Đang tạo ảnh...", total=None)

                response = self.session.post(
                    f"{self.base_url}/api/imagine",
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                progress.update(task, completed=True)

            self.token_extractor.mark_token_used(token["id"])

            if response.status_code == 200:
                data = response.json()
                images = data.get("images", []) or data.get("urls", [])
                return GrokResponse(
                    success=True,
                    data=data,
                    images=images,
                    raw_response=data
                )
            elif response.status_code in [401, 403]:
                self.token_extractor.mark_token_expired(token["id"])
                return GrokResponse(
                    success=False,
                    error=f"Token hết hạn (HTTP {response.status_code})"
                )
            else:
                return GrokResponse(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )

        except requests.Timeout:
            return GrokResponse(success=False, error="Timeout - quá thời gian chờ")
        except Exception as e:
            return GrokResponse(success=False, error=str(e))

    def generate_video_from_images(
        self,
        image_paths: List[str],
        prompt: str,
        duration: int = 5,
        token: Optional[Dict] = None
    ) -> GrokResponse:
        """Tạo video từ các ảnh (nếu Grok hỗ trợ)"""
        if token is None:
            token = self.token_extractor.rotate_token()

        if not token:
            return GrokResponse(success=False, error="Không có token khả dụng")

        headers = self._get_headers_with_token(token)

        # Upload ảnh trước (nếu cần)
        uploaded_ids = []
        for img_path in image_paths:
            upload_result = self._upload_image(img_path, headers)
            if upload_result:
                uploaded_ids.append(upload_result)

        # Payload cho video generation
        payload = {
            "prompt": prompt,
            "images": uploaded_ids if uploaded_ids else image_paths,
            "duration": duration,
            "type": "video",
        }

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Đang tạo video...", total=None)

                response = self.session.post(
                    f"{self.base_url}/api/video/generate",
                    headers=headers,
                    json=payload,
                    timeout=300  # Video cần nhiều thời gian hơn
                )

                progress.update(task, completed=True)

            self.token_extractor.mark_token_used(token["id"])

            if response.status_code == 200:
                data = response.json()
                return GrokResponse(
                    success=True,
                    data=data,
                    video_url=data.get("video_url") or data.get("url"),
                    raw_response=data
                )
            else:
                return GrokResponse(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}"
                )

        except Exception as e:
            return GrokResponse(success=False, error=str(e))

    def _upload_image(self, image_path: str, headers: Dict) -> Optional[str]:
        """Upload ảnh lên Grok"""
        path = Path(image_path)
        if not path.exists():
            console.print(f"[red]❌ Không tìm thấy ảnh: {image_path}[/]")
            return None

        try:
            with open(path, "rb") as f:
                files = {"file": (path.name, f, "image/jpeg")}
                response = self.session.post(
                    f"{self.base_url}/api/upload",
                    headers={k: v for k, v in headers.items() if k != "Content-Type"},
                    files=files,
                    timeout=60
                )

            if response.status_code == 200:
                data = response.json()
                return data.get("id") or data.get("media_id")

        except Exception as e:
            console.print(f"[red]❌ Lỗi upload: {e}[/]")

        return None

    def download_media(self, url: str, output_path: str) -> bool:
        """Tải ảnh/video về"""
        try:
            response = self.session.get(url, timeout=120, stream=True)
            if response.status_code == 200:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                console.print(f"[green]✅ Đã tải: {output_path}[/]")
                return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi tải file: {e}[/]")

        return False

    def chat_with_image(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        token: Optional[Dict] = None
    ) -> GrokResponse:
        """Chat với Grok (có thể kèm ảnh)"""
        if token is None:
            token = self.token_extractor.rotate_token()

        if not token:
            return GrokResponse(success=False, error="Không có token khả dụng")

        headers = self._get_headers_with_token(token)

        # Upload ảnh nếu có
        image_id = None
        if image_path:
            image_id = self._upload_image(image_path, headers)

        payload = {
            "prompt": prompt,
            "model": "grok-2-vision" if image_id else "grok-2",
        }

        if image_id:
            payload["image_id"] = image_id

        try:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                headers=headers,
                json=payload,
                timeout=60
            )

            self.token_extractor.mark_token_used(token["id"])

            if response.status_code == 200:
                return GrokResponse(
                    success=True,
                    data=response.json(),
                    raw_response=response.json()
                )
            else:
                return GrokResponse(
                    success=False,
                    error=f"HTTP {response.status_code}"
                )

        except Exception as e:
            return GrokResponse(success=False, error=str(e))


# Tiện ích tạo prompt cho sản phẩm
def create_product_video_prompt(
    product_name: str,
    price: str,
    description: str = "",
    promotion: str = "",
    style: str = "modern, professional, e-commerce"
) -> str:
    """Tạo prompt cho video sản phẩm"""
    prompt_parts = [
        f"Create a professional product showcase video for: {product_name}",
        f"Style: {style}",
        f"Price: {price}",
    ]

    if description:
        prompt_parts.append(f"Description: {description}")

    if promotion:
        prompt_parts.append(f"Promotion: {promotion}")

    prompt_parts.extend([
        "The video should be:",
        "- Eye-catching and professional",
        "- Suitable for TikTok and Facebook",
        "- 9:16 vertical format",
        "- Show product from multiple angles",
        "- Include smooth transitions",
    ])

    return "\n".join(prompt_parts)
