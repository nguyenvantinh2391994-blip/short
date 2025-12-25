"""
Google Flow API - Tạo ảnh và video với GemPix2/Veo3 qua nanoai.pics proxy
"""

import requests
import base64
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console

console = Console()


class GoogleFlowAPI:
    """API client cho Google Flow (GemPix2 + Veo3) qua nanoai.pics proxy"""

    BASE_URL = "https://nanoai.pics/api"

    def __init__(self, bearer_token: Optional[str] = None):
        """
        Khởi tạo Google Flow API

        Args:
            bearer_token: Bearer token từ Google (ya29.xxx format)
        """
        self.bearer_token = bearer_token
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def set_token(self, token: str) -> None:
        """Set Bearer token"""
        if token.startswith("Bearer "):
            token = token[7:]
        self.bearer_token = token

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers với Bearer token"""
        headers = dict(self.session.headers)
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def upload_image(self, image_path: str) -> Optional[str]:
        """
        Upload ảnh reference lên server

        Args:
            image_path: Đường dẫn file ảnh

        Returns:
            Image ID hoặc URL để dùng làm reference
        """
        try:
            path = Path(image_path)
            if not path.exists():
                console.print(f"[red]❌ File không tồn tại: {image_path}[/]")
                return None

            # Đọc và encode ảnh thành base64
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Xác định mime type
            suffix = path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".gif": "image/gif"
            }
            mime_type = mime_types.get(suffix, "image/jpeg")

            payload = {
                "image": f"data:{mime_type};base64,{image_data}",
                "filename": path.name
            }

            response = self.session.post(
                f"{self.BASE_URL}/upload",
                json=payload,
                headers=self._get_headers(),
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("image_id") or result.get("url")
            else:
                console.print(f"[red]❌ Upload failed: {response.status_code}[/]")
                return None

        except Exception as e:
            console.print(f"[red]❌ Upload error: {e}[/]")
            return None

    def generate_images(
        self,
        prompt: str,
        reference_image: Optional[str] = None,
        num_images: int = 4,
        aspect_ratio: str = "1:1",
        style: Optional[str] = None,
        model: str = "gempix2"
    ) -> List[str]:
        """
        Tạo ảnh với GemPix2

        Args:
            prompt: Mô tả ảnh cần tạo
            reference_image: Đường dẫn ảnh reference (Image-to-Image)
            num_images: Số lượng ảnh tạo (1-4)
            aspect_ratio: Tỷ lệ ảnh (1:1, 16:9, 9:16, 4:3, 3:4)
            style: Style preset (realistic, anime, digital-art, etc.)
            model: Model sử dụng (gempix2)

        Returns:
            List URL ảnh đã tạo
        """
        try:
            payload = {
                "prompt": prompt,
                "model": model,
                "num_images": min(num_images, 4),
                "aspect_ratio": aspect_ratio
            }

            if style:
                payload["style"] = style

            # Upload reference image nếu có
            if reference_image:
                image_id = self.upload_image(reference_image)
                if image_id:
                    payload["reference_image"] = image_id
                    payload["mode"] = "image-to-image"

            console.print(f"[cyan]🎨 Đang tạo {num_images} ảnh với GemPix2...[/]")

            response = self.session.post(
                f"{self.BASE_URL}/generate/image",
                json=payload,
                headers=self._get_headers(),
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                images = result.get("images", [])
                console.print(f"[green]✅ Tạo thành công {len(images)} ảnh[/]")
                return images
            elif response.status_code == 202:
                # Task đang xử lý, cần poll
                task_id = response.json().get("task_id")
                return self._poll_task(task_id, "image")
            else:
                console.print(f"[red]❌ Generate failed: {response.status_code} - {response.text}[/]")
                return []

        except Exception as e:
            console.print(f"[red]❌ Generate error: {e}[/]")
            return []

    def generate_video(
        self,
        prompt: str,
        reference_image: Optional[str] = None,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        model: str = "veo3"
    ) -> Optional[str]:
        """
        Tạo video với Veo3

        Args:
            prompt: Mô tả video cần tạo
            reference_image: Ảnh đầu tiên của video
            duration: Độ dài video (giây)
            aspect_ratio: Tỷ lệ video
            model: Model sử dụng (veo3)

        Returns:
            URL video đã tạo
        """
        try:
            payload = {
                "prompt": prompt,
                "model": model,
                "duration": duration,
                "aspect_ratio": aspect_ratio
            }

            # Upload reference image nếu có
            if reference_image:
                image_id = self.upload_image(reference_image)
                if image_id:
                    payload["reference_image"] = image_id
                    payload["mode"] = "image-to-video"

            console.print(f"[cyan]🎬 Đang tạo video {duration}s với Veo3...[/]")

            response = self.session.post(
                f"{self.BASE_URL}/generate/video",
                json=payload,
                headers=self._get_headers(),
                timeout=300
            )

            if response.status_code == 200:
                result = response.json()
                video_url = result.get("video_url")
                console.print(f"[green]✅ Tạo video thành công[/]")
                return video_url
            elif response.status_code == 202:
                # Task đang xử lý, cần poll
                task_id = response.json().get("task_id")
                results = self._poll_task(task_id, "video")
                return results[0] if results else None
            else:
                console.print(f"[red]❌ Generate video failed: {response.status_code}[/]")
                return None

        except Exception as e:
            console.print(f"[red]❌ Generate video error: {e}[/]")
            return None

    def _poll_task(self, task_id: str, task_type: str, max_wait: int = 300) -> List[str]:
        """
        Poll trạng thái task cho đến khi hoàn thành

        Args:
            task_id: ID của task
            task_type: Loại task (image/video)
            max_wait: Thời gian chờ tối đa (giây)

        Returns:
            List URL kết quả
        """
        start_time = time.time()
        poll_interval = 3

        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(
                    f"{self.BASE_URL}/task/{task_id}",
                    headers=self._get_headers(),
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status")

                    if status == "completed":
                        if task_type == "image":
                            return result.get("images", [])
                        else:
                            video_url = result.get("video_url")
                            return [video_url] if video_url else []
                    elif status == "failed":
                        error = result.get("error", "Unknown error")
                        console.print(f"[red]❌ Task failed: {error}[/]")
                        return []
                    else:
                        # Still processing
                        progress = result.get("progress", 0)
                        console.print(f"[dim]⏳ Processing... {progress}%[/]")

            except Exception as e:
                console.print(f"[yellow]⚠️ Poll error: {e}[/]")

            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 10)

        console.print(f"[red]❌ Task timeout sau {max_wait}s[/]")
        return []

    def download_image(self, url: str, output_path: str) -> bool:
        """
        Tải ảnh về local

        Args:
            url: URL ảnh
            output_path: Đường dẫn lưu file

        Returns:
            True nếu thành công
        """
        try:
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            console.print(f"[red]❌ Download error: {e}[/]")
            return False

    def download_video(self, url: str, output_path: str) -> bool:
        """
        Tải video về local

        Args:
            url: URL video
            output_path: Đường dẫn lưu file

        Returns:
            True nếu thành công
        """
        return self.download_image(url, output_path)  # Same logic


# Singleton instance
_api_instance: Optional[GoogleFlowAPI] = None


def get_flow_api() -> GoogleFlowAPI:
    """Get singleton instance của GoogleFlowAPI"""
    global _api_instance
    if _api_instance is None:
        _api_instance = GoogleFlowAPI()
    return _api_instance
