"""
Image Processor - Xử lý ảnh cho video TikTok/Shopee

Chức năng:
1. Crop ảnh về tỷ lệ 9:16 (lấy tâm)
2. Lọc ảnh tự động (xóa logo, giữ ảnh sản phẩm/người)
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass

from PIL import Image
import requests
import base64
from rich.console import Console

console = Console()


@dataclass
class ImageAnalysis:
    """Kết quả phân tích ảnh"""
    has_product: bool = False
    has_person: bool = False
    is_logo_only: bool = False
    description: str = ""
    should_keep: bool = True
    confidence: float = 0.0


def crop_to_9_16(image_path: str, output_path: str = None) -> str:
    """
    Crop ảnh về tỷ lệ 9:16, lấy tâm

    Args:
        image_path: Đường dẫn ảnh gốc
        output_path: Đường dẫn output (mặc định ghi đè file gốc)

    Returns:
        Đường dẫn file đã crop
    """
    if output_path is None:
        output_path = image_path

    try:
        with Image.open(image_path) as img:
            width, height = img.size

            # Target ratio 9:16
            target_ratio = 9 / 16

            current_ratio = width / height

            if abs(current_ratio - target_ratio) < 0.01:
                # Đã đúng tỷ lệ
                if output_path != image_path:
                    img.save(output_path, quality=95)
                return output_path

            if current_ratio > target_ratio:
                # Ảnh quá rộng -> crop chiều ngang
                new_width = int(height * target_ratio)
                new_height = height
                left = (width - new_width) // 2
                top = 0
            else:
                # Ảnh quá cao -> crop chiều dọc
                new_width = width
                new_height = int(width / target_ratio)
                left = 0
                top = (height - new_height) // 2

            # Crop từ tâm
            right = left + new_width
            bottom = top + new_height

            cropped = img.crop((left, top, right, bottom))
            cropped.save(output_path, quality=95)

            console.print(f"[dim]Crop {Path(image_path).name}: {width}x{height} → {new_width}x{new_height}[/]")
            return output_path

    except Exception as e:
        console.print(f"[yellow]⚠️ Lỗi crop {image_path}: {e}[/]")
        return image_path


def crop_folder_to_9_16(folder_path: str, skip_if_ratio_ok: bool = True) -> int:
    """
    Crop tất cả ảnh trong folder về 9:16

    Args:
        folder_path: Đường dẫn folder
        skip_if_ratio_ok: Bỏ qua nếu ảnh đã đúng tỷ lệ

    Returns:
        Số ảnh đã crop
    """
    folder = Path(folder_path)
    if not folder.exists():
        return 0

    count = 0
    extensions = {'.jpg', '.jpeg', '.png', '.webp'}

    for file in folder.iterdir():
        if file.suffix.lower() in extensions:
            crop_to_9_16(str(file))
            count += 1

    return count


class ImageFilter:
    """Lọc ảnh sử dụng Gemini Vision API"""

    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    FILTER_PROMPT = """Phân tích ảnh này và trả về JSON với format:
{
    "has_product": true/false,  // Có sản phẩm thực sự không (quần áo, đồ vật, thiết bị...)
    "has_person": true/false,   // Có người hoặc model không
    "is_logo_only": true/false, // Ảnh chỉ là logo/banner/text không có sản phẩm
    "description": "mô tả ngắn",
    "should_keep": true/false   // Có nên giữ ảnh này cho video bán hàng không
}

Quy tắc:
- should_keep = true nếu: có sản phẩm thật hoặc có người mặc/cầm sản phẩm
- should_keep = false nếu: chỉ là logo, banner quảng cáo, text, ảnh mờ, ảnh kém chất lượng

Chỉ trả về JSON, không có text khác."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model

    def analyze_image(self, image_path: str) -> ImageAnalysis:
        """
        Phân tích 1 ảnh

        Args:
            image_path: Đường dẫn ảnh

        Returns:
            ImageAnalysis với kết quả phân tích
        """
        if not self.api_key:
            return ImageAnalysis(should_keep=True, description="No API key")

        try:
            # Đọc và encode ảnh
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Detect mime type
            ext = Path(image_path).suffix.lower()
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
            }
            mime_type = mime_map.get(ext, 'image/jpeg')

            # Gọi Gemini API
            url = f"{self.GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

            payload = {
                "contents": [{
                    "parts": [
                        {"text": self.FILTER_PROMPT},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 500,
                }
            }

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                error_msg = response.json().get("error", {}).get("message", response.text)
                console.print(f"[yellow]API error: {error_msg}[/]")
                return ImageAnalysis(should_keep=True, description=f"API error: {error_msg}")

            data = response.json()

            # Parse response
            candidates = data.get("candidates", [])
            if not candidates:
                return ImageAnalysis(should_keep=True, description="No response")

            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            # Extract JSON từ response
            try:
                # Tìm JSON trong response
                json_start = text.find('{')
                json_end = text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = text[json_start:json_end]
                    result = json.loads(json_str)

                    return ImageAnalysis(
                        has_product=result.get("has_product", False),
                        has_person=result.get("has_person", False),
                        is_logo_only=result.get("is_logo_only", False),
                        description=result.get("description", ""),
                        should_keep=result.get("should_keep", True),
                        confidence=0.8
                    )
            except json.JSONDecodeError:
                pass

            return ImageAnalysis(should_keep=True, description="Parse error")

        except Exception as e:
            console.print(f"[yellow]Lỗi phân tích {image_path}: {e}[/]")
            return ImageAnalysis(should_keep=True, description=str(e))

    def filter_folder(
        self,
        folder_path: str,
        delete_unwanted: bool = True,
        dry_run: bool = False
    ) -> Tuple[List[str], List[str]]:
        """
        Lọc ảnh trong folder

        Args:
            folder_path: Đường dẫn folder
            delete_unwanted: Xóa ảnh không cần thiết
            dry_run: Chỉ phân tích, không xóa

        Returns:
            Tuple (kept_files, deleted_files)
        """
        folder = Path(folder_path)
        if not folder.exists():
            return [], []

        kept = []
        deleted = []
        extensions = {'.jpg', '.jpeg', '.png', '.webp'}

        images = [f for f in folder.iterdir() if f.suffix.lower() in extensions]
        console.print(f"[cyan]🔍 Phân tích {len(images)} ảnh trong {folder.name}...[/]")

        for img_path in images:
            analysis = self.analyze_image(str(img_path))

            if analysis.should_keep:
                kept.append(str(img_path))
                console.print(f"[green]✓ {img_path.name}: {analysis.description}[/]")
            else:
                deleted.append(str(img_path))
                console.print(f"[red]✗ {img_path.name}: {analysis.description}[/]")

                if delete_unwanted and not dry_run:
                    try:
                        img_path.unlink()
                        console.print(f"[dim]  → Đã xóa[/]")
                    except Exception as e:
                        console.print(f"[yellow]  → Lỗi xóa: {e}[/]")

        return kept, deleted


def process_shopee_images(
    folder_path: str,
    api_key: str = None,
    crop_9_16: bool = True,
    filter_images: bool = False,
    delete_unwanted: bool = True
) -> dict:
    """
    Xử lý ảnh Shopee: crop 9:16 và lọc ảnh

    Args:
        folder_path: Đường dẫn folder ảnh
        api_key: Gemini API key (cần cho filter)
        crop_9_16: Crop ảnh về 9:16
        filter_images: Lọc ảnh bằng AI
        delete_unwanted: Xóa ảnh không cần thiết

    Returns:
        Dict với kết quả xử lý
    """
    result = {
        "cropped": 0,
        "kept": [],
        "deleted": []
    }

    folder = Path(folder_path)
    if not folder.exists():
        console.print(f"[yellow]Folder không tồn tại: {folder_path}[/]")
        return result

    # Bước 1: Crop 9:16
    if crop_9_16:
        console.print(f"[cyan]✂️ Crop ảnh 9:16...[/]")
        result["cropped"] = crop_folder_to_9_16(folder_path)

    # Bước 2: Lọc ảnh
    if filter_images and api_key:
        console.print(f"[cyan]🔍 Lọc ảnh...[/]")
        filter = ImageFilter(api_key)
        kept, deleted = filter.filter_folder(folder_path, delete_unwanted=delete_unwanted)
        result["kept"] = kept
        result["deleted"] = deleted

    return result


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Xử lý ảnh cho video TikTok")
    parser.add_argument("folder", help="Đường dẫn folder ảnh")
    parser.add_argument("--crop", action="store_true", help="Crop ảnh về 9:16")
    parser.add_argument("--filter", action="store_true", help="Lọc ảnh bằng AI")
    parser.add_argument("--api-key", help="Gemini API key")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ phân tích, không xóa")

    args = parser.parse_args()

    if args.filter and not args.api_key:
        print("❌ Cần API key để lọc ảnh. Dùng --api-key <key>")
        exit(1)

    result = process_shopee_images(
        folder_path=args.folder,
        api_key=args.api_key,
        crop_9_16=args.crop,
        filter_images=args.filter,
        delete_unwanted=not args.dry_run
    )

    print(f"\n📊 Kết quả:")
    print(f"  - Đã crop: {result['cropped']} ảnh")
    if args.filter:
        print(f"  - Giữ lại: {len(result['kept'])} ảnh")
        print(f"  - Đã xóa: {len(result['deleted'])} ảnh")
