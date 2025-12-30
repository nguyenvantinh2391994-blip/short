"""
Shopee DrissionPage - Tải ảnh sản phẩm từ Shopee
Sử dụng DrissionPage thay cho PyAutoGUI + subprocess Chrome

Đây là module độc lập, có thể dùng riêng hoặc kết hợp với shopee_downloader.py
"""

import re
import json
import time
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

try:
    from .drission_manager import DrissionManager
except ImportError:
    from drission_manager import DrissionManager

console = Console()


@dataclass
class ShopeeProduct:
    """Thông tin sản phẩm Shopee"""
    shop_id: int
    item_id: int
    name: str = ""
    price: float = 0
    images: List[str] = None
    description: str = ""
    image_urls_json: str = ""

    def __post_init__(self):
        if self.images is None:
            self.images = []


class ShopeeDrission:
    """Download ảnh sản phẩm từ Shopee bằng DrissionPage"""

    IMAGE_CDN = "https://down-vn.img.susercontent.com/file/"

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi-VN,vi;q=0.9",
    }

    def __init__(
        self,
        output_dir: str = "INPUT",
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.headless = headless

        # DrissionManager instance
        self.manager: Optional[DrissionManager] = None

        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def setup(self) -> bool:
        """Khởi tạo browser"""
        try:
            self.manager = DrissionManager(
                chrome_path=self.chrome_path,
                profile_path=self.profile_path,
                headless=self.headless,
            )

            if not self.manager.is_available():
                console.print("[red]DrissionPage chưa được cài đặt![/]")
                return False

            return self.manager.setup()

        except Exception as e:
            console.print(f"[red]Lỗi setup: {e}[/]")
            return False

    def close(self):
        """Đóng browser"""
        if self.manager:
            self.manager.close()
            self.manager = None

    def show_window(self):
        """Hiện browser window"""
        if self.manager:
            self.manager.show_window()

    def hide_window(self):
        """Ẩn browser window"""
        if self.manager:
            self.manager._hide_window()

    def toggle_visibility(self):
        """Toggle ẩn/hiện browser"""
        if self.manager:
            self.manager.toggle_visibility()

    def resolve_short_url(self, url: str) -> str:
        """Resolve link rút gọn Shopee (s.shopee.vn) thành link đầy đủ"""
        if not url:
            return url

        url = url.strip()

        if 's.shopee.vn' not in url and 'shp.ee' not in url:
            return url

        try:
            console.print(f"[dim]Resolving short URL: {url}[/]")

            response = requests.head(
                url,
                allow_redirects=True,
                timeout=10,
                headers={'User-Agent': self.DEFAULT_HEADERS['User-Agent']}
            )

            final_url = response.url
            final_url = self._clean_shopee_url(final_url)

            console.print(f"[green]Resolved: {final_url[:80]}...[/]")
            return final_url

        except Exception as e:
            console.print(f"[yellow]Không resolve được short URL: {e}[/]")
            return url

    def _clean_shopee_url(self, url: str) -> str:
        """Clean URL Shopee - convert về format product-i.xxx.xxx"""
        try:
            shop_id = None
            item_id = None

            match = re.search(r'-i\.(\d+)\.(\d+)', url)
            if match:
                shop_id, item_id = match.group(1), match.group(2)

            if not shop_id:
                match = re.search(r'shopee\.vn/[^/]+/(\d+)/(\d+)', url)
                if match:
                    shop_id, item_id = match.group(1), match.group(2)

            if shop_id and item_id:
                clean_url = f"https://shopee.vn/product-i.{shop_id}.{item_id}"
                console.print(f"[dim]Converted to: {clean_url}[/]")
                return clean_url

            return url
        except:
            return url

    def parse_shopee_url(self, url: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse link Shopee để lấy shop_id và item_id"""
        if not url:
            return None, None

        url = url.strip()

        # Pattern 1: -i.{shop_id}.{item_id}
        match = re.search(r'-i\.(\d+)\.(\d+)', url)
        if match:
            return int(match.group(1)), int(match.group(2))

        # Pattern 2: /{anything}/{shop_id}/{item_id}
        match = re.search(r'shopee\.vn/[^/]+/(\d+)/(\d+)', url)
        if match:
            return int(match.group(1)), int(match.group(2))

        return None, None

    def get_product_with_browser(
        self,
        shop_id: int,
        item_id: int,
        original_url: str = None,
    ) -> Optional[ShopeeProduct]:
        """Lấy thông tin sản phẩm bằng DrissionPage browser"""
        url = original_url if original_url else f"https://shopee.vn/-i.{shop_id}.{item_id}"

        try:
            # Setup browser nếu chưa có
            if not self.manager or not self.manager.is_running():
                if not self.setup():
                    return None

            console.print(f"[dim]Đang mở: {url}[/]")
            self.manager.navigate(url, wait=5)

            # Scroll để load ảnh
            console.print(f"[dim]Chờ trang load...[/]")
            for _ in range(3):
                self.manager.scroll("down", 500)
                time.sleep(0.5)
            self.manager.scroll("up", 1500)
            time.sleep(2)

            console.print(f"[dim]Đang lấy ảnh...[/]")

            # Lấy URLs bằng JavaScript
            js_get_urls = '''
            (function() {
                var hashes = new Set();
                var urls = [];
                document.querySelectorAll('picture.UkIsx8 img').forEach(function(img) {
                    var src = img.src;
                    if (!src) return;
                    src = src.split('@')[0];
                    if (src.includes('susercontent.com/file/')) {
                        var match = src.match(/\\/file\\/([a-zA-Z0-9_-]+)/);
                        if (match && match[1] && !hashes.has(match[1])) {
                            hashes.add(match[1]);
                            urls.push(src);
                        }
                    }
                });
                if (urls.length === 0) {
                    document.querySelectorAll('img[src*="susercontent.com/file/"]').forEach(function(img) {
                        var src = img.src.split('@')[0];
                        if (src) {
                            var match = src.match(/\\/file\\/([a-zA-Z0-9_-]+)/);
                            if (match && !hashes.has(match[1])) {
                                hashes.add(match[1]);
                                urls.push(src);
                            }
                        }
                    });
                }
                return JSON.stringify(urls);
            })();
            '''
            result = self.manager.run_js_return(js_get_urls)

            image_urls = []
            try:
                image_urls = json.loads(result)
            except:
                pass

            console.print(f"[cyan]Tìm thấy {len(image_urls)} ảnh[/]")

            # Lấy tên sản phẩm
            js_get_name = '''
            (function() {
                var name = '';
                var el = document.querySelector('div.WBVL_7 h1.vR6K3w') ||
                         document.querySelector('div.HLQqkk span') ||
                         document.querySelector('h1');
                if (el) name = el.textContent.trim();
                return name;
            })();
            '''
            name = self.manager.run_js_return(js_get_name) or ""
            if name:
                console.print(f"[dim]Tên SP: {name[:50]}{'...' if len(name) > 50 else ''}[/]")

            # Lấy mô tả sản phẩm
            js_get_desc = '''
            (function() {
                var descParts = [];
                document.querySelectorAll('div.e8lZp3 p.QN2lPu').forEach(function(p) {
                    var text = p.innerText.trim();
                    if (text) descParts.push(text);
                });
                return descParts.join('\\n');
            })();
            '''
            description = self.manager.run_js_return(js_get_desc) or ""
            if description:
                console.print(f"[dim]Mô tả: {len(description)} ký tự[/]")

            # Trả về product nếu có
            if name or image_urls:
                images = []
                for img_url in image_urls:
                    hash_match = re.search(r'/file/([a-zA-Z0-9_-]+)', img_url)
                    if hash_match:
                        images.append(hash_match.group(1))

                return ShopeeProduct(
                    shop_id=shop_id,
                    item_id=item_id,
                    name=name,
                    description=description,
                    images=images,
                    image_urls_json=json.dumps(image_urls),
                )

            return None

        except Exception as e:
            console.print(f"[red]Lỗi: {e}[/]")
            return None

    def download_images(
        self,
        product: ShopeeProduct,
        folder_name: str,
        skip_existing: bool = True
    ) -> List[str]:
        """Download tất cả ảnh của sản phẩm"""
        # Kiểm tra direct URLs
        direct_urls = []
        if product.image_urls_json:
            try:
                direct_urls = json.loads(product.image_urls_json)
                if not isinstance(direct_urls, list):
                    direct_urls = []
            except:
                direct_urls = []

        if not product.images and not direct_urls:
            console.print(f"[yellow]Sản phẩm không có ảnh[/]")
            return []

        # Tạo thư mục
        folder = self.output_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        # Check nếu đã có ảnh
        if skip_existing:
            existing_images = list(folder.glob("*.jpg")) + list(folder.glob("*.png"))
            if existing_images:
                console.print(f"[dim]Bỏ qua {folder_name} (đã có {len(existing_images)} ảnh)[/]")
                return [str(p) for p in existing_images]

        downloaded = []

        # Download từ direct URLs
        if direct_urls:
            total = len(direct_urls)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"[cyan]Đang tải {folder_name}...",
                    total=total
                )

                for idx, image_url in enumerate(direct_urls, 1):
                    filename = f"{idx:02d}.jpg"
                    filepath = folder / filename

                    try:
                        for attempt in range(3):
                            try:
                                response = self.session.get(image_url, timeout=30)
                                if response.status_code == 200:
                                    with open(filepath, 'wb') as f:
                                        f.write(response.content)
                                    downloaded.append(str(filepath))
                                    break
                            except:
                                if attempt < 2:
                                    time.sleep(1)
                                continue
                    except Exception as e:
                        console.print(f"[yellow]Lỗi tải ảnh {idx}: {e}[/]")

                    progress.update(task, advance=1)

        if downloaded:
            console.print(f"[green]Đã tải {len(downloaded)} ảnh vào {folder}[/]")

        return downloaded

    def download_from_url(
        self,
        url: str,
        folder_name: str,
        skip_existing: bool = True
    ) -> Tuple[Optional[ShopeeProduct], List[str]]:
        """
        Download ảnh từ link Shopee

        Returns:
            Tuple (ShopeeProduct, List đường dẫn ảnh)
        """
        # Resolve link rút gọn
        url = self.resolve_short_url(url)
        url = self._clean_shopee_url(url)

        # Parse URL
        shop_id, item_id = self.parse_shopee_url(url)

        if not shop_id or not item_id:
            console.print(f"[red]Không thể parse link: {url}[/]")
            return None, []

        console.print(f"[dim]Shop ID: {shop_id}, Item ID: {item_id}[/]")

        # Lấy thông tin sản phẩm
        product = self.get_product_with_browser(shop_id, item_id, original_url=url)

        if not product:
            console.print(f"[red]Không lấy được thông tin sản phẩm[/]")
            return None, []

        if product.name:
            console.print(f"[cyan]{product.name}[/]")

        # Download ảnh
        images = self.download_images(product, folder_name, skip_existing)
        return product, images

    # Alias để tương thích với ShopeeDownloader
    def get_product_and_download(
        self,
        url: str,
        folder_name: str,
        skip_existing: bool = True
    ) -> Tuple[Optional[ShopeeProduct], List[str]]:
        """Alias cho download_from_url để tương thích với ShopeeDownloader"""
        return self.download_from_url(url, folder_name, skip_existing)

    def close_browser(self):
        """Alias cho close() để tương thích với ShopeeDownloader"""
        self.close()

    def toggle_browser_visibility(self):
        """Toggle ẩn/hiện browser - tương thích với ShopeeDownloader"""
        self.toggle_visibility()


def download_shopee_with_drission(
    url: str,
    folder_name: str,
    output_dir: str = "INPUT",
    chrome_path: str = None,
    profile_path: str = None,
    skip_existing: bool = True,
) -> Tuple[Optional[ShopeeProduct], List[str]]:
    """
    Utility function để tải ảnh từ 1 link Shopee bằng DrissionPage

    Returns:
        Tuple (ShopeeProduct, List đường dẫn ảnh)
    """
    downloader = ShopeeDrission(
        output_dir=output_dir,
        chrome_path=chrome_path,
        profile_path=profile_path,
    )

    try:
        return downloader.download_from_url(url, folder_name, skip_existing)
    finally:
        downloader.close()
