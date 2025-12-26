"""
Flow Generator - Wrapper để tạo ảnh/video từ extracted images
Sử dụng Google Flow API (GemPix2/Veo3)
"""

import time
from pathlib import Path
from typing import Optional, List, Dict, Callable
from datetime import datetime

from .google_flow_api import (
    GoogleFlowAPI, get_flow_api,
    ImageInput, ImageInputType, AspectRatio,
    GeneratedImage
)


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
        # Strip rich markup for plain text logging
        clean_msg = message.replace("[cyan]", "").replace("[/cyan]", "")
        clean_msg = clean_msg.replace("[dim]", "").replace("[/dim]", "")
        clean_msg = clean_msg.replace("[green]", "").replace("[/green]", "")
        clean_msg = clean_msg.replace("[yellow]", "").replace("[/yellow]", "")
        clean_msg = clean_msg.replace("[red]", "").replace("[/red]", "")
        clean_msg = clean_msg.replace("[/]", "")

        if self.log_callback:
            self.log_callback(clean_msg)
        else:
            print(clean_msg)

    def get_extracted_images(self, product_code: str) -> List[Path]:
        """Lấy danh sách ảnh đã extracted của sản phẩm"""
        extracted_folder = self.base_dir / product_code / "extracted"
        if not extracted_folder.exists():
            return []

        images = []
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
            images.extend(extracted_folder.glob(ext))

        return sorted(images)

    def get_flow_folder(self, product_code: str) -> Path:
        """Lấy/tạo thư mục flow cho sản phẩm"""
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
            self._log(f"⚠️ {product_code}: Không có ảnh extracted")
            return []

        flow_folder = self.get_flow_folder(product_code)
        generated_files = []

        self._log(f"🔄 {product_code}: Đang tạo biến thể từ {len(extracted_images)} ảnh...")

        # Map aspect ratio string to enum
        ar_map = {
            "1:1": AspectRatio.SQUARE,
            "16:9": AspectRatio.LANDSCAPE,
            "9:16": AspectRatio.PORTRAIT,
            "landscape": AspectRatio.LANDSCAPE,
            "portrait": AspectRatio.PORTRAIT,
            "square": AspectRatio.SQUARE
        }
        ar_enum = ar_map.get(aspect_ratio.lower(), AspectRatio.SQUARE)

        for i, image_path in enumerate(extracted_images, 1):
            self._log(f"   Ảnh {i}/{len(extracted_images)}: {image_path.name}")

            # Tạo prompt nếu chưa có
            actual_prompt = prompt or "product photo, clean background, professional lighting, high quality"

            # Gọi API tạo ảnh KHÔNG dùng reference image (API không hỗ trợ base64 trực tiếp)
            # TODO: Dùng nanoai.pics proxy để hỗ trợ reference image
            success, images, error = self.api.generate_images(
                prompt=actual_prompt,
                count=num_variations,
                aspect_ratio=ar_enum,
                image_inputs=[]  # Không dùng reference - API không hỗ trợ base64
            )

            if not success:
                self._log(f"   ❌ Lỗi API: {error}")
                continue

            # Download và lưu ảnh
            timestamp = datetime.now().strftime("%H%M%S")
            for j, gen_image in enumerate(images, 1):
                output_name = f"{image_path.stem}_flow_{timestamp}_{j}.png"
                output_path = flow_folder / output_name

                downloaded = self.api.download_image(gen_image, flow_folder, f"{image_path.stem}_flow_{timestamp}_{j}")
                if downloaded:
                    generated_files.append(str(downloaded))
                    self._log(f"   ✅ Saved: {output_name}")

            # Rate limiting
            if i < len(extracted_images):
                time.sleep(2)

        self._log(f"✅ {product_code}: Đã tạo {len(generated_files)} ảnh flow")
        return generated_files

    def process_products(
        self,
        product_codes: List[str],
        prompt: str = "",
        num_variations: int = 4,
        style: Optional[str] = None,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, List[str]]:
        """Xử lý nhiều sản phẩm"""
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
                    self._log(f"⏭️ {code}: Đã có {len(existing)} ảnh flow - bỏ qua")
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
    if _generator_instance is None or str(_generator_instance.base_dir) != base_dir:
        _generator_instance = FlowGenerator(base_dir)
    return _generator_instance
