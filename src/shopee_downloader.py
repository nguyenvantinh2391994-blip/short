"""
Shopee Image Downloader - Tải ảnh sản phẩm từ link Shopee
"""

import re
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


@dataclass
class ShopeeProduct:
    """Thông tin sản phẩm Shopee"""
    shop_id: int
    item_id: int
    name: str = ""
    price: float = 0
    images: List[str] = None  # List of image hashes
    description: str = ""

    def __post_init__(self):
        if self.images is None:
            self.images = []


class ShopeeDownloader:
    """Download ảnh sản phẩm từ Shopee"""

    # Shopee API endpoint
    API_URL = "https://shopee.vn/api/v4/item/get"

    # Shopee image CDN
    IMAGE_CDN = "https://down-vn.img.susercontent.com/file/"

    # Headers để tránh bị block
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://shopee.vn/",
        "Origin": "https://shopee.vn",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-requested-with": "XMLHttpRequest",
        "x-shopee-language": "vi",
        "x-api-source": "pc",
        "af-ac-enc-dat": "null",
    }

    def __init__(self, output_dir: str = "INPUT"):
        """
        Args:
            output_dir: Thư mục gốc để lưu ảnh
        """
        self.output_dir = Path(output_dir)
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def parse_shopee_url(self, url: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse link Shopee để lấy shop_id và item_id

        Formats được hỗ trợ:
        - https://shopee.vn/product-name-i.123456.789012
        - https://shopee.vn/-i.123456.789012
        - https://shopee.vn/product?shopid=123456&itemid=789012
        - https://vn.xiapibuy.com/... (redirect từ app)

        Returns:
            Tuple[shop_id, item_id] hoặc (None, None) nếu không parse được
        """
        if not url:
            return None, None

        url = url.strip()

        # Pattern 1: .../product-name-i.{shop_id}.{item_id}
        pattern1 = r'-i\.(\d+)\.(\d+)'
        match = re.search(pattern1, url)
        if match:
            return int(match.group(1)), int(match.group(2))

        # Pattern 2: URL params ?shopid=xxx&itemid=xxx
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'shopid' in params and 'itemid' in params:
            try:
                return int(params['shopid'][0]), int(params['itemid'][0])
            except (ValueError, IndexError):
                pass

        # Pattern 3: shopee.vn/shop/{shop_id}/product/{item_id}
        pattern3 = r'/shop/(\d+)/product/(\d+)'
        match = re.search(pattern3, url)
        if match:
            return int(match.group(1)), int(match.group(2))

        return None, None

    def get_product_info(self, shop_id: int, item_id: int) -> Optional[ShopeeProduct]:
        """
        Lấy thông tin sản phẩm từ Shopee API

        Args:
            shop_id: Shop ID
            item_id: Item ID

        Returns:
            ShopeeProduct hoặc None nếu lỗi
        """
        params = {
            "itemid": item_id,
            "shopid": shop_id,
        }

        try:
            # Thử gọi API v4
            response = self.session.get(
                self.API_URL,
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                console.print(f"[yellow]⚠️ API trả về status {response.status_code}[/]")
                return self._get_product_fallback(shop_id, item_id)

            data = response.json()

            # Check error
            if data.get("error"):
                error_msg = data.get("error_msg", "Unknown error")
                console.print(f"[yellow]⚠️ API error: {error_msg}[/]")
                return self._get_product_fallback(shop_id, item_id)

            item_data = data.get("data", {})
            if not item_data:
                console.print("[yellow]⚠️ Không có dữ liệu sản phẩm[/]")
                return self._get_product_fallback(shop_id, item_id)

            # Parse images
            images = item_data.get("images", [])

            # Lấy thêm ảnh từ tier_variations (các biến thể màu sắc, size)
            tier_variations = item_data.get("tier_variations", [])
            for variation in tier_variations:
                var_images = variation.get("images", [])
                for img in var_images:
                    if img and img not in images:
                        images.append(img)

            return ShopeeProduct(
                shop_id=shop_id,
                item_id=item_id,
                name=item_data.get("name", ""),
                price=item_data.get("price", 0) / 100000,  # Shopee lưu giá * 100000
                images=images,
                description=item_data.get("description", ""),
            )

        except requests.RequestException as e:
            console.print(f"[red]❌ Lỗi kết nối: {e}[/]")
            return self._get_product_fallback(shop_id, item_id)
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ Lỗi parse JSON: {e}[/]")
            return self._get_product_fallback(shop_id, item_id)

    def _get_product_fallback(self, shop_id: int, item_id: int) -> Optional[ShopeeProduct]:
        """
        Fallback: Lấy thông tin bằng cách parse HTML trang sản phẩm
        """
        url = f"https://shopee.vn/-i.{shop_id}.{item_id}"

        try:
            console.print(f"[dim]Thử fallback method (HTML parsing)...[/]")

            # Dùng mobile user-agent có thể dễ hơn
            headers = self.DEFAULT_HEADERS.copy()
            headers["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

            response = self.session.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                # Thử dùng Selenium nếu HTML cũng bị block
                return self._get_product_selenium(shop_id, item_id)

            html = response.text

            # Tìm JSON data trong HTML
            # Shopee embed data trong script tag
            pattern = r'<script[^>]*>window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>'
            match = re.search(pattern, html, re.DOTALL)

            if match:
                try:
                    state = json.loads(match.group(1))
                    item_data = state.get("item", {}).get("item", {})
                    if item_data:
                        images = item_data.get("images", [])
                        return ShopeeProduct(
                            shop_id=shop_id,
                            item_id=item_id,
                            name=item_data.get("name", ""),
                            images=images,
                        )
                except json.JSONDecodeError:
                    pass

            # Tìm pattern ảnh trực tiếp trong HTML
            image_pattern = r'"images"\s*:\s*\[(.*?)\]'
            match = re.search(image_pattern, html)
            if match:
                try:
                    images_str = "[" + match.group(1) + "]"
                    images = json.loads(images_str)
                    if images:
                        return ShopeeProduct(
                            shop_id=shop_id,
                            item_id=item_id,
                            images=images,
                        )
                except json.JSONDecodeError:
                    pass

            # Nếu không parse được, thử Selenium
            return self._get_product_selenium(shop_id, item_id)

        except Exception as e:
            console.print(f"[red]❌ Fallback failed: {e}[/]")
            return self._get_product_selenium(shop_id, item_id)

    def _get_product_selenium(self, shop_id: int, item_id: int) -> Optional[ShopeeProduct]:
        """
        Fallback cuối: Sử dụng Selenium để crawl trang sản phẩm
        Sử dụng selector 'picture.UkIsx8 img' và bỏ resize param để tránh 403
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
        except ImportError:
            console.print("[yellow]⚠️ Selenium không được cài đặt. Chạy: pip install selenium[/]")
            return None

        url = f"https://shopee.vn/-i.{shop_id}.{item_id}"

        try:
            console.print(f"[dim]Thử Selenium method...[/]")

            # Setup Chrome options
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

            # Thử dùng undetected-chromedriver nếu có
            try:
                import undetected_chromedriver as uc
                driver = uc.Chrome(options=options, headless=True)
            except ImportError:
                driver = webdriver.Chrome(options=options)

            driver.get(url)

            # Chờ trang load và ảnh render
            time.sleep(5)

            # Lấy page source và parse
            html = driver.page_source
            images = []
            image_urls = []  # Lưu full URLs để download trực tiếp

            # Phương pháp 1: Tìm ảnh qua selector chính xác của Shopee
            # Selector: picture.UkIsx8 img (ảnh sản phẩm chính)
            selectors = [
                "picture.UkIsx8 img",  # Ảnh sản phẩm chính
                "div[class*='product-image'] img",
                "div[class*='image-carousel'] img",
                "img[src*='img.susercontent.com/file/']",
            ]

            for selector in selectors:
                try:
                    img_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for img in img_elements:
                        src = img.get_attribute("src")
                        if src and 'img.susercontent.com/file/' in src:
                            # Bỏ phần resize (@...) để lấy ảnh gốc và tránh 403
                            clean_url = src.split("@")[0]
                            if clean_url not in image_urls:
                                image_urls.append(clean_url)
                                # Extract hash để backup
                                hash_match = re.search(r'/file/([a-f0-9_]+)', clean_url)
                                if hash_match:
                                    images.append(hash_match.group(1))
                except Exception:
                    continue

            # Phương pháp 2: Tìm trong JSON data của page
            patterns = [
                r'"images"\s*:\s*\[([^\]]+)\]',
                r'"image"\s*:\s*"([^"]+)"',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if isinstance(match, str):
                        # Có thể là list string hoặc single string
                        if '","' in match:
                            # List of images
                            for img_hash in re.findall(r'"([a-f0-9_]+)"', match):
                                if img_hash not in images and len(img_hash) > 20:
                                    images.append(img_hash)
                        elif len(match) > 20 and not match.startswith('http'):
                            if match not in images:
                                images.append(match)

            driver.quit()

            # Lọc unique images
            images = list(dict.fromkeys(images))

            if images or image_urls:
                # Lấy tên sản phẩm từ title
                title_match = re.search(r'<title>([^<]+)</title>', html)
                name = title_match.group(1).replace(" | Shopee Việt Nam", "") if title_match else ""

                product = ShopeeProduct(
                    shop_id=shop_id,
                    item_id=item_id,
                    name=name,
                    images=images if images else [],
                )
                # Lưu URLs vào extra field để download trực tiếp
                if image_urls:
                    product.description = json.dumps(image_urls)  # Tạm lưu URLs

                return product

            return None

        except Exception as e:
            console.print(f"[red]❌ Selenium failed: {e}[/]")
            return None

    def download_images(
        self,
        product: ShopeeProduct,
        folder_name: str,
        skip_existing: bool = True
    ) -> List[str]:
        """
        Download tất cả ảnh của sản phẩm

        Args:
            product: ShopeeProduct object
            folder_name: Tên thư mục lưu (thường là mã sản phẩm)
            skip_existing: Bỏ qua nếu thư mục đã có ảnh

        Returns:
            List các đường dẫn ảnh đã download
        """
        # Kiểm tra xem có direct URLs không (từ Selenium method)
        direct_urls = []
        if product.description:
            try:
                direct_urls = json.loads(product.description)
                if not isinstance(direct_urls, list):
                    direct_urls = []
            except json.JSONDecodeError:
                direct_urls = []

        if not product.images and not direct_urls:
            console.print(f"[yellow]⚠️ Sản phẩm không có ảnh[/]")
            return []

        # Tạo thư mục
        folder = self.output_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        # Check nếu đã có ảnh
        if skip_existing:
            existing_images = list(folder.glob("*.jpg")) + list(folder.glob("*.png")) + list(folder.glob("*.webp"))
            if existing_images:
                console.print(f"[dim]⏭️ Bỏ qua {folder_name} (đã có {len(existing_images)} ảnh)[/]")
                return [str(p) for p in existing_images]

        downloaded = []

        # Ưu tiên direct URLs (đã bỏ resize, tránh 403)
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
                    f"[cyan]Đang tải {folder_name} (direct URLs)...",
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
                            except requests.RequestException:
                                if attempt < 2:
                                    time.sleep(1)
                                continue
                    except Exception as e:
                        console.print(f"[yellow]⚠️ Lỗi tải ảnh {idx}: {e}[/]")

                    progress.update(task, advance=1)

        # Nếu không có direct URLs hoặc download thất bại, dùng image hashes
        if not downloaded and product.images:
            total = len(product.images)
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

                for idx, image_hash in enumerate(product.images, 1):
                    # Build image URL - bỏ resize param
                    image_url = f"{self.IMAGE_CDN}{image_hash}"

                    filename = f"{idx:02d}.jpg"
                    filepath = folder / filename

                    try:
                        # Download với retry và thử nhiều CDN
                        success = False
                        cdns = [
                            self.IMAGE_CDN,
                            "https://cf.shopee.vn/file/",
                            "https://down-vn.img.susercontent.com/file/vn-11134207-7r98o-",
                        ]

                        for cdn in cdns:
                            if success:
                                break
                            url = f"{cdn}{image_hash}"

                            for attempt in range(3):
                                try:
                                    response = self.session.get(url, timeout=30)
                                    if response.status_code == 200:
                                        with open(filepath, 'wb') as f:
                                            f.write(response.content)
                                        downloaded.append(str(filepath))
                                        success = True
                                        break
                                except requests.RequestException:
                                    if attempt < 2:
                                        time.sleep(1)
                                    continue

                    except Exception as e:
                        console.print(f"[yellow]⚠️ Lỗi tải ảnh {idx}: {e}[/]")

                    progress.update(task, advance=1)

        if downloaded:
            console.print(f"[green]✅ Đã tải {len(downloaded)} ảnh vào {folder}[/]")

        return downloaded

    def download_from_url(
        self,
        url: str,
        folder_name: str,
        skip_existing: bool = True
    ) -> List[str]:
        """
        Download ảnh từ link Shopee

        Args:
            url: Link sản phẩm Shopee
            folder_name: Tên thư mục lưu
            skip_existing: Bỏ qua nếu đã có ảnh

        Returns:
            List các đường dẫn ảnh đã download
        """
        # Parse URL
        shop_id, item_id = self.parse_shopee_url(url)

        if not shop_id or not item_id:
            console.print(f"[red]❌ Không thể parse link: {url}[/]")
            return []

        console.print(f"[dim]Shop ID: {shop_id}, Item ID: {item_id}[/]")

        # Lấy thông tin sản phẩm
        product = self.get_product_info(shop_id, item_id)

        if not product:
            console.print(f"[red]❌ Không lấy được thông tin sản phẩm[/]")
            return []

        if product.name:
            console.print(f"[cyan]📦 {product.name}[/]")

        # Download ảnh
        return self.download_images(product, folder_name, skip_existing)


class ShopeeSheetProcessor:
    """Xử lý Google Sheet để tải ảnh Shopee"""

    def __init__(
        self,
        downloader: ShopeeDownloader,
        code_column: str = "A",
        link_column: str = "B",
    ):
        """
        Args:
            downloader: ShopeeDownloader instance
            code_column: Cột chứa mã sản phẩm (default: A)
            link_column: Cột chứa link Shopee (default: B)
        """
        self.downloader = downloader
        self.code_column = code_column
        self.link_column = link_column

    def process_sheet(
        self,
        sheet,  # gspread.Worksheet
        skip_existing: bool = True,
        delay_between: float = 1.0,
    ) -> Dict[str, List[str]]:
        """
        Xử lý toàn bộ sheet, tải ảnh cho từng dòng

        Args:
            sheet: gspread Worksheet object
            skip_existing: Bỏ qua thư mục đã có ảnh
            delay_between: Delay giữa các request (giây)

        Returns:
            Dict mapping mã -> list ảnh đã tải
        """
        results = {}

        try:
            # Lấy tất cả dữ liệu
            all_values = sheet.get_all_values()

            if not all_values:
                console.print("[yellow]⚠️ Sheet trống[/]")
                return results

            # Tìm index cột
            code_col_idx = ord(self.code_column.upper()) - ord('A')
            link_col_idx = ord(self.link_column.upper()) - ord('A')

            # Bỏ qua header row
            data_rows = all_values[1:] if len(all_values) > 1 else []

            console.print(f"[cyan]📋 Tìm thấy {len(data_rows)} dòng dữ liệu[/]")

            for row_idx, row in enumerate(data_rows, start=2):
                # Lấy mã và link
                code = row[code_col_idx] if len(row) > code_col_idx else ""
                link = row[link_col_idx] if len(row) > link_col_idx else ""

                if not code or not link:
                    continue

                code = code.strip()
                link = link.strip()

                # Kiểm tra link có phải Shopee không
                if "shopee" not in link.lower():
                    console.print(f"[dim]⏭️ Bỏ qua {code} (không phải link Shopee)[/]")
                    continue

                console.print(f"\n[bold]📦 [{row_idx}] {code}[/]")
                console.print(f"[dim]{link}[/]")

                # Download ảnh
                images = self.downloader.download_from_url(
                    url=link,
                    folder_name=code,
                    skip_existing=skip_existing
                )

                results[code] = images

                # Delay để tránh bị rate limit
                if delay_between > 0:
                    time.sleep(delay_between)

            return results

        except Exception as e:
            console.print(f"[red]❌ Lỗi xử lý sheet: {e}[/]")
            return results

    def process_from_reader(
        self,
        sheets_reader,  # SheetsReader instance
        skip_existing: bool = True,
        delay_between: float = 1.0,
    ) -> Dict[str, List[str]]:
        """
        Xử lý từ SheetsReader đã kết nối

        Args:
            sheets_reader: SheetsReader instance đã connect
            skip_existing: Bỏ qua thư mục đã có ảnh
            delay_between: Delay giữa các request

        Returns:
            Dict mapping mã -> list ảnh
        """
        if not sheets_reader.sheet:
            if not sheets_reader.open_spreadsheet():
                console.print("[red]❌ Không thể mở spreadsheet[/]")
                return {}

        return self.process_sheet(
            sheet=sheets_reader.sheet,
            skip_existing=skip_existing,
            delay_between=delay_between
        )


def download_shopee_images(
    url: str,
    folder_name: str,
    output_dir: str = "INPUT",
    skip_existing: bool = True,
) -> List[str]:
    """
    Utility function để tải ảnh từ 1 link Shopee

    Args:
        url: Link sản phẩm Shopee
        folder_name: Tên thư mục lưu
        output_dir: Thư mục gốc
        skip_existing: Bỏ qua nếu đã có ảnh

    Returns:
        List đường dẫn ảnh đã tải
    """
    downloader = ShopeeDownloader(output_dir=output_dir)
    return downloader.download_from_url(url, folder_name, skip_existing)


def batch_download_from_sheet(
    spreadsheet_id: str,
    credentials_file: str = "config/credentials.json",
    sheet_name: str = "Sheet1",
    output_dir: str = "INPUT",
    code_column: str = "A",
    link_column: str = "B",
    skip_existing: bool = True,
    delay_between: float = 1.0,
) -> Dict[str, List[str]]:
    """
    Utility function để tải ảnh từ Google Sheet

    Args:
        spreadsheet_id: ID của Google Sheet
        credentials_file: File credentials
        sheet_name: Tên sheet
        output_dir: Thư mục output
        code_column: Cột mã (A, B, C...)
        link_column: Cột link
        skip_existing: Bỏ qua thư mục đã có ảnh
        delay_between: Delay giữa các request

    Returns:
        Dict mapping mã -> list ảnh
    """
    from .sheets_reader import SheetsReader

    reader = SheetsReader(
        credentials_file=credentials_file,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
    )

    if not reader.connect():
        return {}

    downloader = ShopeeDownloader(output_dir=output_dir)
    processor = ShopeeSheetProcessor(
        downloader=downloader,
        code_column=code_column,
        link_column=link_column,
    )

    return processor.process_from_reader(
        sheets_reader=reader,
        skip_existing=skip_existing,
        delay_between=delay_between,
    )
