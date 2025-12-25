"""
Flow Generator - Wrapper để tạo ảnh/video từ extracted images
Sử dụng Google Flow API (GemPix2/Veo3)
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Callable
from datetime import datetime
from rich.console import Console

from .google_flow_api import get_flow_api, GoogleFlowAPI

console = Console()


class FlowGenerator:
    """Tạo ảnh/video biến thể từ ảnh extracted sử dụng Google Flow API"""

    def __init__(self, base_dir: str = "products"):
        """
        Khởi tạo Flow Generator

        Args:
            base_dir: Thư mục gốc chứa các sản phẩm
        """
        self.base_dir = Path(base_dir)
        self.api = get_flow_api()
        self.log_callback: Optional[Callable[[str], None]] = None

    def set_token(self, token: str) -> None:
        """Set Bearer token cho API"""
        self.api.set_token(token)

    def set_log_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback để log ra UI"""
        self.log_callback = callback

    def _log(self, message: str) -> None:
        """Log message"""
        if self.log_callback:
            self.log_callback(message)
        else:
            console.print(message)

    def get_extracted_images(self, product_code: str) -> List[Path]:
        """
        Lấy danh sách ảnh đã extracted của sản phẩm

        Args:
            product_code: Mã sản phẩm

        Returns:
            List đường dẫn file ảnh
        """
        extracted_folder = self.base_dir / product_code / "extracted"
        if not extracted_folder.exists():
            return []

        images = []
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
            images.extend(extracted_folder.glob(ext))

        return sorted(images)

    def get_flow_folder(self, product_code: str) -> Path:
        """
        Lấy/tạo thư mục flow cho sản phẩm

        Args:
            product_code: Mã sản phẩm

        Returns:
            Đường dẫn thư mục flow
        """
        flow_folder = self.base_dir / product_code / "flow"
        flow_folder.mkdir(parents=True, exist_ok=True)
        return flow_folder

    def generate_variations(
        self,
        product_code: str,
        prompt: str = "",
        num_variations: int = 4,
        style: Optional[str] = None,
        aspect_ratio: str = "1:1"
    ) -> List[str]:
        """
        Tạo biến thể từ ảnh extracted

        Args:
            product_code: Mã sản phẩm
            prompt: Prompt mô tả (để trống sẽ dùng default)
            num_variations: Số biến thể mỗi ảnh gốc
            style: Style preset
            aspect_ratio: Tỷ lệ ảnh

        Returns:
            List đường dẫn ảnh đã tạo
        """
        extracted_images = self.get_extracted_images(product_code)
        if not extracted_images:
            self._log(f"[yellow]⚠️ {product_code}: Không có ảnh extracted[/]")
            return []

        flow_folder = self.get_flow_folder(product_code)
        generated_files = []

        self._log(f"[cyan]🔄 {product_code}: Đang tạo biến thể từ {len(extracted_images)} ảnh...[/]")

        for i, image_path in enumerate(extracted_images, 1):
            self._log(f"[dim]   Ảnh {i}/{len(extracted_images)}: {image_path.name}[/]")

            # Tạo prompt nếu chưa có
            if not prompt:
                prompt = "product photo, clean background, professional lighting, high quality"

            # Gọi API tạo ảnh
            image_urls = self.api.generate_images(
                prompt=prompt,
                reference_image=str(image_path),
                num_images=num_variations,
                aspect_ratio=aspect_ratio,
                style=style
            )

            # Download và lưu ảnh
            timestamp = datetime.now().strftime("%H%M%S")
            for j, url in enumerate(image_urls, 1):
                output_name = f"{image_path.stem}_flow_{timestamp}_{j}.png"
                output_path = flow_folder / output_name

                if self.api.download_image(url, str(output_path)):
                    generated_files.append(str(output_path))
                    self._log(f"[green]   ✅ Saved: {output_name}[/]")

            # Rate limiting
            if i < len(extracted_images):
                time.sleep(2)

        self._log(f"[green]✅ {product_code}: Đã tạo {len(generated_files)} ảnh flow[/]")
        return generated_files

    def generate_video_from_image(
        self,
        product_code: str,
        image_index: int = 0,
        prompt: str = "",
        duration: int = 5
    ) -> Optional[str]:
        """
        Tạo video từ ảnh extracted

        Args:
            product_code: Mã sản phẩm
            image_index: Index của ảnh trong extracted
            prompt: Prompt mô tả video
            duration: Độ dài video (giây)

        Returns:
            Đường dẫn video đã tạo
        """
        extracted_images = self.get_extracted_images(product_code)
        if not extracted_images:
            self._log(f"[yellow]⚠️ {product_code}: Không có ảnh extracted[/]")
            return None

        if image_index >= len(extracted_images):
            image_index = 0

        image_path = extracted_images[image_index]
        flow_folder = self.get_flow_folder(product_code)

        self._log(f"[cyan]🎬 {product_code}: Đang tạo video từ {image_path.name}...[/]")

        if not prompt:
            prompt = "product showcase video, smooth camera movement, professional lighting"

        video_url = self.api.generate_video(
            prompt=prompt,
            reference_image=str(image_path),
            duration=duration
        )

        if video_url:
            timestamp = datetime.now().strftime("%H%M%S")
            output_name = f"{image_path.stem}_video_{timestamp}.mp4"
            output_path = flow_folder / output_name

            if self.api.download_video(video_url, str(output_path)):
                self._log(f"[green]✅ {product_code}: Video saved: {output_name}[/]")
                return str(output_path)

        return None

    def process_products(
        self,
        product_codes: List[str],
        prompt: str = "",
        num_variations: int = 4,
        style: Optional[str] = None,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, List[str]]:
        """
        Xử lý nhiều sản phẩm

        Args:
            product_codes: List mã sản phẩm
            prompt: Prompt mô tả
            num_variations: Số biến thể
            style: Style preset
            skip_existing: Bỏ qua sản phẩm đã có flow
            progress_callback: Callback cập nhật progress (current, total)

        Returns:
            Dict mapping product_code -> list generated files
        """
        results = {}
        total = len(product_codes)

        for i, code in enumerate(product_codes, 1):
            if progress_callback:
                progress_callback(i, total)

            # Kiểm tra đã có flow chưa
            if skip_existing:
                flow_folder = self.get_flow_folder(code)
                existing = list(flow_folder.glob("*.png")) + list(flow_folder.glob("*.jpg"))
                if existing:
                    self._log(f"[dim]⏭️ {code}: Đã có {len(existing)} ảnh flow - bỏ qua[/]")
                    results[code] = [str(f) for f in existing]
                    continue

            # Tạo variations
            generated = self.generate_variations(
                product_code=code,
                prompt=prompt,
                num_variations=num_variations,
                style=style
            )
            results[code] = generated

            # Rate limiting giữa các sản phẩm
            if i < total:
                time.sleep(3)

        return results


# Singleton instance
_generator_instance: Optional[FlowGenerator] = None


def get_flow_generator(base_dir: str = "products") -> FlowGenerator:
    """Get singleton instance của FlowGenerator"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = FlowGenerator(base_dir)
    return _generator_instance
