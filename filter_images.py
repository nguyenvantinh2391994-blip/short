#!/usr/bin/env python3
"""
Filter Images - Lọc ảnh sản phẩm tự động

Sử dụng Gemini Vision API để:
- Giữ ảnh có sản phẩm thật hoặc người mặc sản phẩm
- Xóa ảnh chỉ có logo, banner, text

Cách dùng:
    python filter_images.py INPUT --api-key YOUR_API_KEY
    python filter_images.py INPUT/SP001 --api-key YOUR_API_KEY --dry-run
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.image_processor import ImageFilter, crop_folder_to_9_16, process_shopee_images
from rich.console import Console
from rich.table import Table

console = Console()


def filter_single_folder(folder: Path, api_key: str, dry_run: bool = False):
    """Lọc 1 folder"""
    console.print(f"\n[bold cyan]📁 {folder.name}[/]")

    filter = ImageFilter(api_key)
    kept, deleted = filter.filter_folder(str(folder), delete_unwanted=not dry_run)

    return len(kept), len(deleted)


def main():
    parser = argparse.ArgumentParser(
        description="Lọc ảnh sản phẩm - xóa logo/banner, giữ ảnh sản phẩm thật",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python filter_images.py INPUT --api-key YOUR_KEY
  python filter_images.py INPUT/SP001 --api-key YOUR_KEY
  python filter_images.py INPUT --api-key YOUR_KEY --dry-run
  python filter_images.py INPUT --crop-only
        """
    )

    parser.add_argument(
        "path",
        help="Đường dẫn folder chứa ảnh hoặc folder cha chứa nhiều folder sản phẩm"
    )
    parser.add_argument(
        "--api-key",
        help="Gemini API key (hoặc set GEMINI_API_KEY env)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ phân tích, không xóa file"
    )
    parser.add_argument(
        "--crop-only",
        action="store_true",
        help="Chỉ crop 9:16, không lọc"
    )
    parser.add_argument(
        "--no-crop",
        action="store_true",
        help="Không crop, chỉ lọc"
    )

    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        console.print(f"[red]❌ Không tìm thấy: {path}[/]")
        return

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY", "")

    if not args.crop_only and not api_key:
        console.print("[red]❌ Cần API key để lọc ảnh![/]")
        console.print("[dim]Dùng: --api-key YOUR_KEY hoặc set GEMINI_API_KEY[/]")
        console.print("[dim]Hoặc dùng --crop-only để chỉ crop 9:16[/]")
        return

    # Xác định là folder đơn hay folder cha
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    has_images = any(f.suffix.lower() in image_extensions for f in path.iterdir() if f.is_file())

    if has_images:
        # Folder đơn chứa ảnh
        folders = [path]
    else:
        # Folder cha chứa nhiều subfolder
        folders = [f for f in path.iterdir() if f.is_dir()]

    if not folders:
        console.print("[yellow]Không tìm thấy folder nào để xử lý[/]")
        return

    console.print(f"[bold]🔍 Tìm thấy {len(folders)} folder[/]\n")

    total_kept = 0
    total_deleted = 0
    total_cropped = 0

    for folder in folders:
        # Crop trước
        if not args.no_crop:
            cropped = crop_folder_to_9_16(str(folder))
            total_cropped += cropped
            if cropped > 0:
                console.print(f"[dim]✂️ Crop {cropped} ảnh[/]")

        # Lọc
        if not args.crop_only and api_key:
            kept, deleted = filter_single_folder(folder, api_key, args.dry_run)
            total_kept += kept
            total_deleted += deleted

    # Tổng kết
    console.print("\n" + "="*50)
    table = Table(title="📊 Kết quả")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    if not args.no_crop:
        table.add_row("Ảnh đã crop", str(total_cropped))

    if not args.crop_only:
        table.add_row("Ảnh giữ lại", str(total_kept))
        table.add_row("Ảnh đã xóa" if not args.dry_run else "Ảnh sẽ xóa", str(total_deleted))

    console.print(table)

    if args.dry_run:
        console.print("\n[yellow]⚠️ Đây là dry-run, không có file nào bị xóa[/]")


if __name__ == "__main__":
    main()
