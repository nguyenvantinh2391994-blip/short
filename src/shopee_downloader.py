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

    def __init__(
        self,
        output_dir: str = "INPUT",
        chrome_path: str = None,
        profile_path: str = None,
        headless: bool = True,
    ):
        """
        Args:
            output_dir: Thư mục gốc để lưu ảnh
            chrome_path: Đường dẫn Chrome executable (để dùng browser có sẵn)
            profile_path: Đường dẫn Chrome profile (để dùng profile đã đăng nhập)
            headless: Chạy ẩn browser (mặc định True)
        """
        self.output_dir = Path(output_dir)
        self.chrome_path = chrome_path
        self.profile_path = profile_path
        self.headless = headless
        self.driver = None  # Lưu driver để có thể show/hide
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def _hide_chrome_window(self):
        """Ẩn Chrome window khỏi taskbar (Windows) hoặc đẩy ra ngoài màn hình"""
        if not self.driver:
            return
        try:
            import platform
            if platform.system() == 'Windows':
                import ctypes
                from ctypes import wintypes

                GWL_EXSTYLE = -20
                WS_EX_TOOLWINDOW = 0x00000080
                WS_EX_APPWINDOW = 0x00040000
                SWP_NOSIZE = 0x0001

                user32 = ctypes.windll.user32
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

                chrome_windows = []

                def enum_callback(hwnd, lparam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.lower()
                            if 'shopee' in title or 'chrome' in title:
                                chrome_windows.append(hwnd)
                    return True

                user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

                for hwnd in chrome_windows:
                    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    new_style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    user32.SetWindowPos(hwnd, 0, -2000, -2000, 0, 0, SWP_NOSIZE)

                if chrome_windows:
                    self._chrome_hwnds = chrome_windows
                    self._is_hidden = True
            else:
                self.driver.set_window_position(-2000, -2000)
                self._is_hidden = True
        except Exception:
            pass

    def show_chrome_window(self):
        """Hiện Chrome window trên taskbar và đưa vào màn hình"""
        if not self.driver:
            return
        try:
            import platform
            if platform.system() == 'Windows':
                import ctypes
                from ctypes import wintypes

                GWL_EXSTYLE = -20
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_TOOLWINDOW = 0x00000080
                SW_RESTORE = 9
                HWND_TOP = 0
                SWP_SHOWWINDOW = 0x0040

                user32 = ctypes.windll.user32

                screen_w = user32.GetSystemMetrics(0)
                screen_h = user32.GetSystemMetrics(1)
                win_w, win_h = 1200, 800
                x = (screen_w - win_w) // 2
                y = (screen_h - win_h) // 2

                if hasattr(self, '_chrome_hwnds') and self._chrome_hwnds:
                    for hwnd in self._chrome_hwnds:
                        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                        new_style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
                        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                        user32.ShowWindow(hwnd, SW_RESTORE)
                        user32.SetWindowPos(hwnd, HWND_TOP, x, y, win_w, win_h, SWP_SHOWWINDOW)
                        user32.SetForegroundWindow(hwnd)
                    self._is_hidden = False
                else:
                    self.driver.set_window_position(x, y)
                    self.driver.set_window_size(win_w, win_h)
                    self._is_hidden = False
            else:
                self.driver.set_window_position(100, 100)
                self._is_hidden = False
        except Exception:
            pass

    def toggle_browser_visibility(self):
        """Toggle ẩn/hiện browser"""
        if hasattr(self, '_is_hidden') and self._is_hidden:
            self.show_chrome_window()
        else:
            self._hide_chrome_window()

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

    def get_product_info(self, shop_id: int, item_id: int, original_url: str = None) -> Optional[ShopeeProduct]:
        """
        Lấy thông tin sản phẩm từ Shopee API

        Args:
            shop_id: Shop ID
            item_id: Item ID
            original_url: Link Shopee gốc (để dùng khi fallback sang Selenium)

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
                return self._get_product_fallback(shop_id, item_id, original_url)

            data = response.json()

            # Check error
            if data.get("error"):
                error_msg = data.get("error_msg", "Unknown error")
                console.print(f"[yellow]⚠️ API error: {error_msg}[/]")
                return self._get_product_fallback(shop_id, item_id, original_url)

            item_data = data.get("data", {})
            if not item_data:
                console.print("[yellow]⚠️ Không có dữ liệu sản phẩm[/]")
                return self._get_product_fallback(shop_id, item_id, original_url)

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
            return self._get_product_fallback(shop_id, item_id, original_url)
        except json.JSONDecodeError as e:
            console.print(f"[red]❌ Lỗi parse JSON: {e}[/]")
            return self._get_product_fallback(shop_id, item_id, original_url)

    def _get_product_fallback(self, shop_id: int, item_id: int, original_url: str = None) -> Optional[ShopeeProduct]:
        """
        Fallback: Lấy thông tin bằng cách parse HTML trang sản phẩm
        """
        # Dùng link gốc nếu có, nếu không thì build từ shop_id/item_id
        url = original_url if original_url else f"https://shopee.vn/-i.{shop_id}.{item_id}"

        try:
            console.print(f"[dim]Thử fallback method (HTML parsing)...[/]")

            # Dùng mobile user-agent có thể dễ hơn
            headers = self.DEFAULT_HEADERS.copy()
            headers["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

            response = self.session.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                # Thử dùng Selenium nếu HTML cũng bị block
                return self._get_product_selenium(
                    shop_id, item_id,
                    original_url=url,
                    chrome_path=self.chrome_path,
                    profile_path=self.profile_path
                )

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
            return self._get_product_selenium(
                shop_id, item_id,
                original_url=url,
                chrome_path=self.chrome_path,
                profile_path=self.profile_path
            )

        except Exception as e:
            console.print(f"[red]❌ Fallback failed: {e}[/]")
            return self._get_product_selenium(
                shop_id, item_id,
                original_url=url,
                chrome_path=self.chrome_path,
                profile_path=self.profile_path
            )

    def _load_cookies_from_file(self, driver, cookie_file: str = "config/shopee_cookies.txt"):
        """Load cookies từ file Netscape format vào browser"""
        from pathlib import Path
        cookie_path = Path(cookie_file)

        if not cookie_path.exists():
            console.print(f"[dim]Cookie file không tồn tại: {cookie_file}[/]")
            return False

        try:
            with open(cookie_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain, _, path, secure, expiry, name, value = parts[:7]

                        cookie = {
                            'name': name,
                            'value': value,
                            'domain': domain,
                            'path': path,
                            'secure': secure.upper() == 'TRUE',
                        }

                        # Chỉ set expiry nếu không phải 0 (session cookie)
                        if expiry and expiry != '0':
                            try:
                                cookie['expiry'] = int(expiry)
                            except ValueError:
                                pass

                        try:
                            driver.add_cookie(cookie)
                        except Exception:
                            pass  # Bỏ qua cookies không thêm được

            console.print(f"[dim]Đã load cookies từ {cookie_file}[/]")
            return True

        except Exception as e:
            console.print(f"[yellow]⚠️ Không load được cookies: {e}[/]")
            return False

    def _get_product_selenium(
        self,
        shop_id: int,
        item_id: int,
        headless: bool = None,
        chrome_path: str = None,
        profile_path: str = None,
        original_url: str = None,
    ) -> Optional[ShopeeProduct]:
        """
        Fallback cuối: Sử dụng Selenium để crawl trang sản phẩm
        Sử dụng selector 'picture.UkIsx8 img' và bỏ resize param để tránh 403

        Args:
            shop_id: Shopee shop ID
            item_id: Shopee item ID
            headless: Chạy ở chế độ ẩn browser (None = dùng self.headless)
            chrome_path: Đường dẫn đến Chrome executable (tùy chọn)
            profile_path: Đường dẫn đến Chrome profile (tùy chọn, dùng profile có sẵn)
            original_url: Link Shopee gốc (ưu tiên dùng thay vì build từ shop_id/item_id)
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
        except ImportError:
            console.print("[yellow]⚠️ Selenium không được cài đặt. Chạy: pip install selenium[/]")
            return None

        # Dùng self.headless nếu không truyền param
        is_headless = headless if headless is not None else self.headless

        # Ưu tiên dùng link gốc, nếu không có thì build từ shop_id/item_id
        url = original_url if original_url else f"https://shopee.vn/-i.{shop_id}.{item_id}"

        try:
            console.print(f"[cyan]🌐 Mở browser để lấy ảnh từ Shopee...[/]")

            # Setup Chrome options
            options = Options()

            # Sử dụng browser profile có sẵn (đã đăng nhập Shopee)
            if profile_path:
                profile = Path(profile_path)
                if profile.exists():
                    console.print(f"[dim]Sử dụng profile: {profile.name}[/]")
                    options.add_argument(f"--user-data-dir={profile.parent}")
                    options.add_argument(f"--profile-directory={profile.name}")

            # Đường dẫn Chrome
            if chrome_path and Path(chrome_path).exists():
                options.binary_location = chrome_path

            # Nếu chạy ẩn: đẩy window ra ngoài màn hình (không dùng headless vì hay lỗi)
            if is_headless:
                options.add_argument("--window-size=1200,800")
                options.add_argument("--window-position=-2000,-2000")  # Ngoài màn hình
            else:
                options.add_argument("--window-size=1920,1080")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-blink-features=AutomationControlled")

            # Chrome preferences - tự động cho phép download, không hỏi lại
            prefs = {
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "profile.default_content_setting_values.automatic_downloads": 1,  # Allow multiple downloads
                "profile.default_content_setting_values.notifications": 2,  # Block notifications
            }
            options.add_experimental_option("prefs", prefs)
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            # Thử dùng undetected-chromedriver nếu KHÔNG có profile
            # (undetected_chromedriver không hoạt động tốt với existing profile)
            if not profile_path:
                try:
                    import undetected_chromedriver as uc
                    console.print(f"[dim]Sử dụng undetected-chromedriver...[/]")
                    self.driver = uc.Chrome(headless=False)  # Không dùng headless, dùng window position
                except ImportError:
                    self.driver = webdriver.Chrome(options=options)
            else:
                # Dùng selenium thường với profile có sẵn
                console.print(f"[dim]Sử dụng Selenium với profile đã đăng nhập...[/]")
                self.driver = webdriver.Chrome(options=options)

            # Ẩn khỏi taskbar nếu headless (Windows)
            if is_headless:
                self._is_hidden = True
                self._hide_chrome_window()
            else:
                self._is_hidden = False

            driver = self.driver  # Alias cho code cũ

            # Nếu không có profile, load cookies từ file
            if not profile_path:
                driver.get("https://shopee.vn")
                time.sleep(2)
                self._load_cookies_from_file(driver)
                driver.refresh()
                time.sleep(2)

            # Giờ vào trang sản phẩm
            console.print(f"[dim]Đang mở: {url}[/]")
            driver.get(url)

            # Chờ trang load - dùng explicit wait
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "picture.UkIsx8 img"))
                )
                console.print(f"[dim]Đã tìm thấy ảnh sản phẩm[/]")
            except Exception:
                console.print(f"[dim]Chờ thêm để ảnh load...[/]")
                time.sleep(8)

            # Chờ thêm để ảnh load hoàn toàn
            time.sleep(3)

            # LẤY ẢNH TỪ SELECTOR picture.UkIsx8 img (đã test hoạt động)
            js_script = """
            var hashes = new Set();
            var urls = [];

            // Dùng selector picture.UkIsx8 img - đã được xác nhận hoạt động
            document.querySelectorAll('picture.UkIsx8 img').forEach(img => {
                let src = img.src;
                if (!src) return;

                // Bỏ resize param (@...)
                src = src.split('@')[0];

                if (src.includes('susercontent.com/file/')) {
                    // Extract hash từ URL để loại bỏ trùng lặp
                    let match = src.match(/\\/file\\/([a-zA-Z0-9_-]+)/);
                    if (match && match[1] && !hashes.has(match[1])) {
                        hashes.add(match[1]);
                        urls.push(src);
                    }
                }
            });

            return urls;
            """

            image_urls = driver.execute_script(js_script)
            console.print(f"[cyan]📷 Tìm thấy {len(image_urls)} ảnh (unique)[/]")

            # Nếu không tìm thấy, thử selector backup
            if not image_urls:
                console.print(f"[dim]Thử selector backup...[/]")

                backup_js = """
                var hashes = new Set();
                var urls = [];
                document.querySelectorAll('img[src*="susercontent.com/file/"]').forEach(img => {
                    let src = img.src.split('@')[0];
                    if (src) {
                        let match = src.match(/\\/file\\/([a-zA-Z0-9_-]+)/);
                        if (match && !hashes.has(match[1])) {
                            hashes.add(match[1]);
                            urls.push(src);
                        }
                    }
                });
                return urls;
                """
                image_urls = driver.execute_script(backup_js)
                console.print(f"[dim]Backup: Tìm thấy {len(image_urls)} ảnh[/]")

            # Lấy tên sản phẩm
            name = ""
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, "div.HLQqkk span")
                name = title_elem.text
            except Exception:
                try:
                    name = driver.title.replace(" | Shopee Việt Nam", "")
                except Exception:
                    pass

            driver.quit()
            driver = None
            self.driver = None

            if image_urls:
                # Extract hash từ URLs
                images = []
                for url in image_urls:
                    hash_match = re.search(r'/file/([a-zA-Z0-9_-]+)', url)
                    if hash_match:
                        images.append(hash_match.group(1))

                product = ShopeeProduct(
                    shop_id=shop_id,
                    item_id=item_id,
                    name=name,
                    images=images,
                )
                # Lưu direct URLs để download (đã bỏ resize param)
                product.description = json.dumps(image_urls)

                return product

            return None

        except Exception as e:
            console.print(f"[red]❌ Selenium failed: {e}[/]")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            self.driver = None

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

        # Lấy thông tin sản phẩm - truyền link gốc để dùng khi fallback
        product = self.get_product_info(shop_id, item_id, original_url=url)

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
