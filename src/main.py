"""
Short Video Creator - CLI chính
Tạo video short tự động cho Facebook và TikTok
"""

import sys
import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .config_manager import get_config, ConfigManager
from .token_extractor import TokenExtractor, interactive_add_token
from .grok_client import GrokClient
from .sheets_reader import SheetsReader, LocalProductReader, Product
from .video_generator import VideoGenerator, VideoConfig
from .watcher import AutoVideoWatcher, SheetsWatcher

console = Console()


@click.group()
@click.option("--config", "-c", default="config/config.json", help="Đường dẫn file config")
@click.pass_context
def cli(ctx, config):
    """Short Video Creator - Tạo video bán hàng cho Facebook & TikTok"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.pass_context
def init(ctx):
    """Khởi tạo project và tạo file config mẫu"""
    config_path = Path(ctx.obj["config_path"])

    # Tạo các thư mục cần thiết
    dirs = ["config", "products", "outputs", "music", "templates"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        console.print(f"[green]✓[/] Tạo thư mục: {d}/")

    # Copy config mẫu nếu chưa có
    if not config_path.exists():
        example_path = config_path.parent / "config.example.json"
        if example_path.exists():
            import shutil
            shutil.copy(example_path, config_path)
            console.print(f"[green]✓[/] Tạo file config: {config_path}")
        else:
            # Tạo config mặc định
            config = ConfigManager(str(config_path))
            config.save()

    console.print("\n[bold green]Khởi tạo thành công![/]")
    console.print("\n[bold]Bước tiếp theo:[/]")
    console.print("1. Chỉnh sửa file [cyan]config/config.json[/]")
    console.print("2. Thêm file [cyan]config/credentials.json[/] (Google Sheets API)")
    console.print("3. Chạy [cyan]python -m src.main add-token[/] để thêm Grok token")
    console.print("4. Thêm ảnh sản phẩm vào thư mục [cyan]products/{ma_sp}/[/]")


@cli.command("add-token")
def add_token():
    """Thêm token Grok mới"""
    interactive_add_token()


@cli.command("list-tokens")
def list_tokens():
    """Hiển thị danh sách tokens"""
    extractor = TokenExtractor()
    extractor.list_tokens()


@cli.command("test-token")
@click.option("--token-id", "-t", type=int, help="ID của token cần test")
def test_token(token_id):
    """Test token Grok"""
    client = GrokClient()
    if token_id:
        tokens = client.token_extractor.tokens
        token = next((t for t in tokens if t["id"] == token_id), None)
        if not token:
            console.print(f"[red]❌ Không tìm thấy token #{token_id}[/]")
            return
        client.test_token(token)
    else:
        client.test_token()


@cli.command("list-products")
@click.option("--source", "-s", type=click.Choice(["sheets", "local"]), default="sheets")
@click.pass_context
def list_products(ctx, source):
    """Hiển thị danh sách sản phẩm"""
    config = get_config(ctx.obj["config_path"])

    if source == "sheets":
        reader = SheetsReader(
            credentials_file=config.get("google_sheets.credentials_file"),
            spreadsheet_id=config.get("google_sheets.spreadsheet_id"),
            sheet_name=config.get("google_sheets.sheet_name")
        )
    else:
        reader = LocalProductReader()

    reader.display_products()


@cli.command("generate")
@click.argument("product_id", required=False)
@click.option("--all", "-a", "generate_all", is_flag=True, help="Tạo video cho tất cả sản phẩm")
@click.option("--use-grok", "-g", is_flag=True, help="Sử dụng Grok AI để tạo video")
@click.option("--source", "-s", type=click.Choice(["sheets", "local"]), default="sheets")
@click.pass_context
def generate(ctx, product_id, generate_all, use_grok, source):
    """Tạo video cho sản phẩm"""
    config = get_config(ctx.obj["config_path"])

    # Khởi tạo video generator
    video_config = VideoConfig(
        width=config.get("video.resolution.width", 1080),
        height=config.get("video.resolution.height", 1920),
        fps=config.get("video.fps", 30),
        duration_per_image=config.get("video.duration_per_image", 3),
        transition_duration=config.get("video.transition_duration", 0.5),
    )

    generator = VideoGenerator(
        products_dir=config.get("products.images_dir", "products"),
        output_dir=config.get("video.output_dir", "outputs"),
        music_dir="music",
        config=video_config
    )

    # Khởi tạo Grok nếu cần
    if use_grok:
        generator.init_grok(config.get("grok.tokens_file"))

    # Lấy danh sách sản phẩm
    if source == "sheets":
        reader = SheetsReader(
            credentials_file=config.get("google_sheets.credentials_file"),
            spreadsheet_id=config.get("google_sheets.spreadsheet_id"),
            sheet_name=config.get("google_sheets.sheet_name")
        )
    else:
        reader = LocalProductReader()

    products = reader.get_products()

    if not products:
        console.print("[yellow]Không có sản phẩm nào[/]")
        return

    # Tạo video
    if generate_all:
        generator.generate_batch(products, use_grok)
    elif product_id:
        product = next((p for p in products if p.id == product_id), None)
        if product:
            generator.generate_video(product, use_grok)
        else:
            console.print(f"[red]❌ Không tìm thấy sản phẩm: {product_id}[/]")
    else:
        console.print("[yellow]Chỉ định --all hoặc product_id[/]")
        console.print("Ví dụ: python -m src.main generate SP001")
        console.print("       python -m src.main generate --all")


@cli.command("watch")
@click.option("--interval", "-i", default=60, help="Thời gian kiểm tra Sheets (giây)")
@click.pass_context
def watch(ctx, interval):
    """Theo dõi thay đổi và tự động tạo video"""
    config = get_config(ctx.obj["config_path"])

    # Video generator
    video_config = VideoConfig(
        width=config.get("video.resolution.width", 1080),
        height=config.get("video.resolution.height", 1920),
    )

    generator = VideoGenerator(
        products_dir=config.get("products.images_dir", "products"),
        output_dir=config.get("video.output_dir", "outputs"),
        config=video_config
    )

    # Sheets reader
    sheets_reader = SheetsReader(
        credentials_file=config.get("google_sheets.credentials_file"),
        spreadsheet_id=config.get("google_sheets.spreadsheet_id"),
        sheet_name=config.get("google_sheets.sheet_name")
    )

    def on_product_change(product_id: str):
        """Callback khi có sản phẩm thay đổi"""
        products = sheets_reader.get_products()
        product = next((p for p in products if p.id == product_id), None)
        if product:
            generator.generate_video(product)

    def on_sheets_change(changed_ids: list):
        """Callback khi Sheets thay đổi"""
        for product_id in changed_ids:
            on_product_change(product_id)

    console.print(Panel(
        "[bold]Auto Video Generator[/]\n\n"
        "Theo dõi:\n"
        f"  • Thư mục ảnh: {config.get('products.images_dir')}/\n"
        f"  • Google Sheets: mỗi {interval}s\n\n"
        "[dim]Nhấn Ctrl+C để dừng[/]",
        title="Watch Mode"
    ))

    # Chạy file watcher
    file_watcher = AutoVideoWatcher(
        products_dir=config.get("products.images_dir", "products"),
        on_change_callback=on_product_change
    )
    file_watcher.start()

    # Chạy sheets watcher (nếu có config)
    if config.get("google_sheets.spreadsheet_id"):
        sheets_watcher = SheetsWatcher(
            sheets_reader=sheets_reader,
            check_interval=interval,
            on_change_callback=on_sheets_change
        )
        sheets_watcher.run_forever()
    else:
        file_watcher.run_forever()


@cli.command("guide")
def guide():
    """Hiển thị hướng dẫn sử dụng"""
    guide_text = """
# Hướng dẫn sử dụng Short Video Creator

## 1. Chuẩn bị

### Google Sheets
1. Tạo Google Cloud Project
2. Enable Google Sheets API
3. Tạo Service Account và download JSON key
4. Lưu vào `config/credentials.json`
5. Share spreadsheet với email của Service Account

### Grok Token
1. Mở https://grok.com/imagine
2. Mở DevTools (F12) → Network
3. Tạo 1 ảnh thử
4. Copy Bearer token từ request headers
5. Chạy: `python -m src.main add-token`

## 2. Cấu trúc thư mục

```
products/
├── SP001/          # Mã sản phẩm
│   ├── 1.jpg
│   ├── 2.jpg
│   └── 3.png
├── SP002/
│   └── ...
```

## 3. Google Sheets format

| Mã SP | Tên sản phẩm    | Giá      | Khuyến mãi |
|-------|-----------------|----------|------------|
| SP001 | Áo thun nam     | 299.000đ | -20%       |
| SP002 | Quần jean       | 499.000đ |            |

## 4. Các lệnh

```bash
# Khởi tạo project
python -m src.main init

# Thêm Grok token
python -m src.main add-token

# Xem danh sách sản phẩm
python -m src.main list-products

# Tạo video cho 1 sản phẩm
python -m src.main generate SP001

# Tạo video tất cả sản phẩm
python -m src.main generate --all

# Tạo video với Grok AI
python -m src.main generate --all --use-grok

# Auto watch và tạo video
python -m src.main watch
```

## 5. Tips

- Đặt ảnh theo thứ tự: 1.jpg, 2.jpg, 3.jpg
- Sử dụng ảnh có tỷ lệ 9:16 để tránh bị crop
- Thêm nhạc vào thư mục `music/` (MP3 format)
- Token Grok có thể hết hạn, cần refresh định kỳ
"""
    console.print(Markdown(guide_text))


@cli.command("quick-start")
@click.argument("product_name")
@click.argument("price")
@click.argument("image_folder")
@click.option("--promotion", "-p", default="", help="Thông tin khuyến mãi")
def quick_start(product_name, price, image_folder, promotion):
    """Tạo nhanh 1 video từ thư mục ảnh"""
    # Tạo product tạm
    folder = Path(image_folder)
    product = Product(
        id=folder.name,
        name=product_name,
        price=price,
        promotion=promotion or None,
        images_folder=str(folder)
    )

    generator = VideoGenerator()
    result = generator.generate_video(product)

    if result:
        console.print(f"\n[bold green]Thành công![/]")
        console.print(f"Video: {result}")


def main():
    """Entry point"""
    cli(obj={})


if __name__ == "__main__":
    main()
