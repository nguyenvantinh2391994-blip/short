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
    description: str = ""  # Mô tả sản phẩm
    image_urls_json: str = ""  # JSON của direct image URLs (để download)

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
        self._is_first_product = True  # Flag để biết có phải sản phẩm đầu tiên không
        self._main_window = None  # Lưu handle của window chính
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def _hide_chrome_window(self):
        """Ẩn Chrome window của tool bằng cách đẩy ra ngoài màn hình"""
        if not self.driver:
            console.print("[dim]Không có browser để ẩn[/]")
            return False
        try:
            # Chỉ dùng Selenium - chỉ ảnh hưởng Chrome của tool
            self.driver.set_window_position(-2000, -2000)
            self._is_hidden = True
            console.print("[dim]Đã ẩn browser[/]")
            return True
        except Exception as e:
            console.print(f"[yellow]Lỗi ẩn browser: {e}[/]")
            return False

    def show_chrome_window(self):
        """Hiện Chrome window của tool"""
        if not self.driver:
            console.print("[dim]Không có browser để hiện[/]")
            return False
        try:
            # Đưa vào giữa màn hình
            self.driver.set_window_position(100, 100)
            self.driver.set_window_size(1200, 800)
            self._is_hidden = False
            console.print("[dim]Đã hiện browser[/]")
            return True
        except Exception as e:
            console.print(f"[yellow]Lỗi hiện browser: {e}[/]")
            return False

    def close_browser(self):
        """Đóng Chrome hoàn toàn - gọi sau khi xử lý xong tất cả sản phẩm"""
        if self.driver:
            try:
                self.driver.quit()
                console.print("[dim]Đã đóng browser[/]")
            except Exception as e:
                console.print(f"[yellow]Lỗi đóng browser: {e}[/]")
            finally:
                self.driver = None
                self._is_first_product = True
                self._main_window = None

    def toggle_browser_visibility(self):
        """Toggle ẩn/hiện browser"""
        if not self.driver:
            console.print("[yellow]Không có browser đang chạy[/]")
            return False

        is_hidden = getattr(self, '_is_hidden', False)
        console.print(f"[dim]Toggle: _is_hidden = {is_hidden}[/]")

        if is_hidden:
            return self.show_chrome_window()
        else:
            return self._hide_chrome_window()

    def resolve_short_url(self, url: str) -> str:
        """
        Resolve link rút gọn Shopee (s.shopee.vn) thành link đầy đủ

        Args:
            url: Link có thể là rút gọn hoặc đầy đủ

        Returns:
            Link đầy đủ sau khi follow redirect (đã clean params)
        """
        if not url:
            return url

        url = url.strip()

        # Chỉ xử lý link rút gọn s.shopee.vn
        if 's.shopee.vn' not in url and 'shp.ee' not in url:
            return url

        try:
            import requests
            console.print(f"[dim]Resolving short URL: {url}[/]")

            # Follow redirect để lấy URL thật
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=10,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )

            final_url = response.url

            # Clean URL: bỏ __mobile__ và các tracking params
            final_url = self._clean_shopee_url(final_url)

            console.print(f"[green]Resolved: {final_url[:80]}...[/]")
            return final_url

        except Exception as e:
            console.print(f"[yellow]Không resolve được short URL: {e}[/]")
            return url

    def _clean_shopee_url(self, url: str) -> str:
        """
        Clean URL Shopee - convert về format product-i.xxx.xxx
        Format này load page đầy đủ với gallery ảnh
        """
        try:
            import re

            # Tìm shop_id và item_id
            shop_id = None
            item_id = None

            # Pattern 1: -i.{shop_id}.{item_id}
            match = re.search(r'-i\.(\d+)\.(\d+)', url)
            if match:
                shop_id, item_id = match.group(1), match.group(2)

            # Pattern 2: /{anything}/{shop_id}/{item_id}
            if not shop_id:
                match = re.search(r'shopee\.vn/[^/]+/(\d+)/(\d+)', url)
                if match:
                    shop_id, item_id = match.group(1), match.group(2)

            # Nếu tìm được, dùng format product-i.xxx.xxx
            if shop_id and item_id:
                # Format này load gallery ảnh đúng
                clean_url = f"https://shopee.vn/product-i.{shop_id}.{item_id}"
                console.print(f"[dim]Converted to: {clean_url}[/]")
                return clean_url

            # Giữ nguyên nếu không parse được
            return url
        except:
            return url

    def parse_shopee_url(self, url: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse link Shopee để lấy shop_id và item_id

        Formats được hỗ trợ:
        - https://shopee.vn/product-name-i.123456.789012
        - https://shopee.vn/-i.123456.789012
        - https://shopee.vn/product/123456/789012 (từ link rút gọn)
        - https://shopee.vn/product?shopid=123456&itemid=789012
        - https://shopee.vn/shop/123456/product/789012
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

        # Pattern 2: /{anything}/{shop_id}/{item_id} (từ link rút gọn s.shopee.vn)
        # Ví dụ: /product/123/456 hoặc /opaanlp/123/456
        pattern2 = r'shopee\.vn/[^/]+/(\d+)/(\d+)'
        match = re.search(pattern2, url)
        if match:
            return int(match.group(1)), int(match.group(2))

        # Pattern 3: URL params ?shopid=xxx&itemid=xxx
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'shopid' in params and 'itemid' in params:
            try:
                return int(params['shopid'][0]), int(params['itemid'][0])
            except (ValueError, IndexError):
                pass

        # Pattern 4: shopee.vn/shop/{shop_id}/product/{item_id}
        pattern4 = r'/shop/(\d+)/product/(\d+)'
        match = re.search(pattern4, url)
        if match:
            return int(match.group(1)), int(match.group(2))

        return None, None

    def get_product_info(self, shop_id: int, item_id: int, original_url: str = None, force_selenium: bool = True, min_images: int = 3) -> Optional[ShopeeProduct]:
        """
        Lấy thông tin sản phẩm từ Shopee API

        Args:
            shop_id: Shop ID
            item_id: Item ID
            original_url: Link Shopee gốc (để dùng khi fallback sang Selenium)
            force_selenium: Luôn dùng Selenium (default: False - thử API trước)
            min_images: Số ảnh tối thiểu, nếu API trả về ít hơn sẽ dùng Selenium

        Returns:
            ShopeeProduct hoặc None nếu lỗi
        """
        # Nếu force_selenium=True, bỏ qua API và dùng Selenium luôn
        if force_selenium:
            console.print(f"[dim]Dùng Selenium để lấy đầy đủ ảnh...[/]")
            return self._get_product_selenium(
                shop_id, item_id,
                original_url=original_url,
                chrome_path=self.chrome_path,
                profile_path=self.profile_path
            )

        params = {
            "itemid": item_id,
            "shopid": shop_id,
        }

        try:
            # Thử gọi API v4
            console.print(f"[dim]Thử API trước...[/]")
            response = self.session.get(
                self.API_URL,
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if not data.get("error"):
                    item_data = data.get("data", {})
                    if item_data:
                        images = item_data.get("images", [])
                        # Lấy thêm ảnh từ tier_variations
                        tier_variations = item_data.get("tier_variations", [])
                        for variation in tier_variations:
                            var_images = variation.get("images", [])
                            for img in var_images:
                                if img and img not in images:
                                    images.append(img)

                        # Nếu đủ ảnh, trả về luôn
                        if len(images) >= min_images:
                            console.print(f"[green]✓ API trả về {len(images)} ảnh[/]")
                            return ShopeeProduct(
                                shop_id=shop_id,
                                item_id=item_id,
                                name=item_data.get("name", ""),
                                price=item_data.get("price", 0) / 100000,
                                images=images,
                                description=item_data.get("description", ""),
                            )
                        else:
                            console.print(f"[yellow]API chỉ trả về {len(images)} ảnh, thử Selenium...[/]")

            # API không đủ ảnh hoặc lỗi -> dùng Selenium
            console.print(f"[yellow]API không đủ ảnh, thử Selenium...[/]")
            return self._get_product_selenium(
                shop_id, item_id,
                original_url=original_url,
                chrome_path=self.chrome_path,
                profile_path=self.profile_path
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

    def _save_cookies_to_file(self, driver, cookie_file: str = "config/shopee_cookies.txt"):
        """Lưu cookies từ browser ra file Netscape format"""
        try:
            cookie_path = Path(cookie_file)
            cookie_path.parent.mkdir(parents=True, exist_ok=True)

            cookies = driver.get_cookies()
            with open(cookie_path, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Saved by ShopeeDownloader\n\n")
                for cookie in cookies:
                    domain = cookie.get('domain', '')
                    # Chỉ lưu cookies của Shopee
                    if 'shopee' not in domain:
                        continue
                    flag = "TRUE" if domain.startswith('.') else "FALSE"
                    path = cookie.get('path', '/')
                    secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                    expiry = str(int(cookie.get('expiry', 0)))
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

            console.print(f"[green]✓ Đã lưu cookies vào {cookie_file}[/]")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠️ Không lưu được cookies: {e}[/]")
            return False

    def _check_and_handle_captcha(self, driver, timeout: int = 60):
        """
        Kiểm tra và xử lý captcha của Shopee
        Nếu gặp captcha, hiện browser để user giải quyết

        Returns:
            True nếu không có captcha hoặc đã giải quyết xong
        """
        import time
        from selenium.webdriver.common.by import By

        # Các dấu hiệu của captcha
        captcha_indicators = [
            "verify",
            "captcha",
            "robot",
            "security",
            "xác minh",
            "bảo mật"
        ]

        try:
            page_source = driver.page_source.lower()
            current_url = driver.current_url.lower()

            # Kiểm tra có captcha không
            has_captcha = any(indicator in page_source or indicator in current_url
                            for indicator in captcha_indicators)

            if has_captcha:
                console.print("[yellow]⚠️ Phát hiện CAPTCHA! Đang hiện browser để bạn giải quyết...[/]")

                # Hiện browser
                self.show_chrome_window()

                # Đợi user giải quyết captcha
                console.print(f"[cyan]⏳ Vui lòng giải captcha trong browser. Đợi tối đa {timeout}s...[/]")

                start_time = time.time()
                while time.time() - start_time < timeout:
                    time.sleep(2)

                    # Kiểm tra lại xem còn captcha không
                    try:
                        page_source = driver.page_source.lower()
                        current_url = driver.current_url.lower()

                        still_has_captcha = any(indicator in page_source or indicator in current_url
                                               for indicator in captcha_indicators)

                        if not still_has_captcha:
                            console.print("[green]✓ Captcha đã được giải quyết![/]")
                            # Lưu cookies sau khi vượt captcha thành công
                            self._save_cookies_to_file(driver)
                            # Ẩn browser lại
                            if self.headless:
                                self._hide_chrome_window()
                            return True
                    except:
                        pass

                console.print("[red]❌ Hết thời gian chờ captcha[/]")
                return False

            return True  # Không có captcha

        except Exception as e:
            console.print(f"[yellow]⚠️ Lỗi kiểm tra captcha: {e}[/]")
            return True  # Tiếp tục nếu không kiểm tra được

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

        # Flag để biết có mở tab mới không (để sau đó đóng tab thay vì quit)
        opened_new_tab = False

        try:
            # Kiểm tra xem đã có driver chưa
            if self.driver is not None:
                # Đã có Chrome, mở tab mới thay vì mở Chrome mới
                console.print(f"[cyan]📑 Mở tab mới trong Chrome hiện có...[/]")
                driver = self.driver

                # Lưu handle hiện tại
                current_handles = driver.window_handles

                # Mở tab mới
                driver.execute_script("window.open('');")
                time.sleep(0.5)

                # Chuyển sang tab mới
                new_handles = driver.window_handles
                new_tab = [h for h in new_handles if h not in current_handles][0]
                driver.switch_to.window(new_tab)
                opened_new_tab = True

                console.print(f"[dim]Đang mở: {url}[/]")
                driver.get(url)
            else:
                # Chưa có Chrome, tạo mới
                console.print(f"[cyan]🌐 Mở Chrome mới...[/]")
                console.print(f"[dim]DEBUG: chrome_path={chrome_path}[/]")
                console.print(f"[dim]DEBUG: profile_path={profile_path}[/]")

                # Thử dùng selenium thường trước (nhanh hơn, ổn định hơn)
                # Nếu bị CAPTCHA thì mới cần undetected-chromedriver
                try:
                    from selenium import webdriver
                    from selenium.webdriver.chrome.options import Options
                    from selenium.webdriver.chrome.service import Service

                    console.print(f"[dim]Sử dụng Selenium...[/]")

                    options = Options()
                    options.add_argument("--no-first-run")
                    options.add_argument("--no-default-browser-check")
                    options.add_argument("--disable-extensions")
                    options.add_argument("--disable-popup-blocking")
                    options.add_argument("--disable-infobars")
                    options.add_argument("--window-size=1920,1080")

                    # KHÔNG dùng profile để tránh conflict với Chrome khác
                    # Shopee không cần login để xem ảnh sản phẩm

                    prefs = {
                        "download.prompt_for_download": False,
                        "download.directory_upgrade": True,
                        "profile.default_content_setting_values.notifications": 2,
                    }
                    options.add_experimental_option("prefs", prefs)
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])

                    console.print(f"[dim]Khởi tạo Chrome...[/]")
                    self.driver = webdriver.Chrome(options=options)
                    console.print(f"[green]Chrome đã mở![/]")

                except Exception as selenium_err:
                    console.print(f"[yellow]Selenium lỗi: {selenium_err}[/]")
                    console.print(f"[dim]Thử undetected-chromedriver...[/]")

                    # Fallback: undetected-chromedriver (không dùng profile)
                    try:
                        import undetected_chromedriver as uc

                        options = uc.ChromeOptions()
                        options.add_argument("--no-first-run")
                        options.add_argument("--no-default-browser-check")
                        options.add_argument("--window-size=1920,1080")

                        self.driver = uc.Chrome(
                            options=options,
                            headless=is_headless,
                            use_subprocess=True,
                        )
                        console.print(f"[green]Chrome đã mở (uc)![/]")
                    except Exception as uc_err:
                        console.print(f"[red]Không mở được Chrome: {uc_err}[/]")
                        console.print(f"[yellow]Thử: taskkill /F /IM chrome.exe[/]")
                        raise uc_err

                if is_headless:
                    self._is_hidden = True
                    self._hide_chrome_window()
                else:
                    self._is_hidden = False

                driver = self.driver

                # Lưu handle của window chính
                self._main_window = driver.current_window_handle

                # Nếu không có profile, load cookies từ file
                if not profile_path:
                    driver.get("https://shopee.vn")
                    time.sleep(2)
                    self._load_cookies_from_file(driver)
                    driver.refresh()
                    time.sleep(2)

                console.print(f"[dim]Đang mở: {url}[/]")
                driver.get(url)

            # Chờ trang load
            console.print(f"[dim]Chờ trang load...[/]")
            time.sleep(8)

            # Debug: Đếm số img
            debug_count = driver.execute_script("return document.querySelectorAll('picture.UkIsx8 img').length;")
            console.print(f"[dim]Số img trong picture.UkIsx8: {debug_count}[/]")

            # Lấy tất cả URLs - chạy script giống hệt như thủ công
            image_urls = driver.execute_script("""
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
                return urls;
            """)

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

            # Lấy tên sản phẩm - thử nhiều selector
            name = ""
            try:
                # Selector mới: h1.vR6K3w trong div.WBVL_7
                title_elem = driver.find_element(By.CSS_SELECTOR, "div.WBVL_7 h1.vR6K3w")
                name = title_elem.text.strip()
                console.print(f"[dim]Tên SP (h1.vR6K3w): {name[:50]}...[/]" if len(name) > 50 else f"[dim]Tên SP: {name}[/]")
            except Exception:
                try:
                    # Selector cũ
                    title_elem = driver.find_element(By.CSS_SELECTOR, "div.HLQqkk span")
                    name = title_elem.text.strip()
                except Exception:
                    try:
                        name = driver.title.replace(" | Shopee Việt Nam", "").strip()
                    except Exception:
                        pass

            # Lấy mô tả sản phẩm - dùng JavaScript để lấy chính xác
            description = ""
            try:
                description = driver.execute_script("""
                    var descParts = [];
                    document.querySelectorAll('div.e8lZp3 p.QN2lPu').forEach(function(p) {
                        var text = p.innerText.trim();
                        if (text) descParts.push(text);
                    });
                    return descParts.join('\\n');
                """)
                if description:
                    console.print(f"[dim]Mô tả: {len(description)} ký tự[/]")
                else:
                    console.print(f"[dim]Không tìm thấy mô tả[/]")
            except Exception as e:
                console.print(f"[dim]Không lấy được mô tả: {e}[/]")

            # Lưu cookies sau khi load thành công (để lần sau không bị captcha)
            if image_urls:
                self._save_cookies_to_file(driver)

            # Đóng tab thay vì quit Chrome (nếu mở tab mới)
            if opened_new_tab:
                # Đóng tab hiện tại
                driver.close()
                # Chuyển về tab chính
                if self._main_window:
                    driver.switch_to.window(self._main_window)
                console.print(f"[dim]Đã đóng tab, giữ Chrome[/]")
            # Không quit driver nữa - giữ Chrome mở

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
                    description=description,
                    images=images,
                    image_urls_json=json.dumps(image_urls),  # Lưu direct URLs để download
                )

                return product

            return None

        except Exception as e:
            console.print(f"[red]❌ Selenium failed: {e}[/]")
            import traceback
            traceback.print_exc()

            # Nếu lỗi và đã mở tab mới, đóng tab đó
            if opened_new_tab and self.driver:
                try:
                    self.driver.close()
                    if self._main_window:
                        self.driver.switch_to.window(self._main_window)
                except Exception:
                    pass

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
        if product.image_urls_json:
            try:
                direct_urls = json.loads(product.image_urls_json)
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
            console.print(f"[green]Đã tải {len(downloaded)} ảnh vào {folder}[/]")

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

    def get_product_and_download(
        self,
        url: str,
        folder_name: str,
        skip_existing: bool = True
    ) -> Tuple[Optional[ShopeeProduct], List[str]]:
        """
        Lấy thông tin sản phẩm và download ảnh từ link Shopee

        Args:
            url: Link sản phẩm Shopee (hỗ trợ cả link rút gọn s.shopee.vn)
            folder_name: Tên thư mục lưu
            skip_existing: Bỏ qua nếu đã có ảnh

        Returns:
            Tuple (ShopeeProduct, List đường dẫn ảnh)
        """
        # Resolve link rút gọn trước (nếu có)
        url = self.resolve_short_url(url)

        # Clean URL về format chuẩn -i.{shop_id}.{item_id}
        url = self._clean_shopee_url(url)

        # Parse URL
        shop_id, item_id = self.parse_shopee_url(url)

        if not shop_id or not item_id:
            console.print(f"[red]❌ Không thể parse link: {url}[/]")
            return None, []

        console.print(f"[dim]Shop ID: {shop_id}, Item ID: {item_id}[/]")

        # Lấy thông tin sản phẩm - truyền link gốc để dùng khi fallback
        product = self.get_product_info(shop_id, item_id, original_url=url)

        if not product:
            console.print(f"[red]❌ Không lấy được thông tin sản phẩm[/]")
            return None, []

        if product.name:
            console.print(f"[cyan]📦 {product.name}[/]")

        # Download ảnh
        images = self.download_images(product, folder_name, skip_existing)
        return product, images


class ShopeeSheetProcessor:
    """Xử lý Google Sheet để tải ảnh Shopee"""

    def __init__(
        self,
        downloader: ShopeeDownloader,
        code_column: str = "A",
        link_column: str = "B",
        name_column: str = "C",
        description_column: str = "D",
    ):
        """
        Args:
            downloader: ShopeeDownloader instance
            code_column: Cột chứa mã sản phẩm (default: A)
            link_column: Cột chứa link Shopee (default: B)
            name_column: Cột để ghi tên sản phẩm (default: C)
            description_column: Cột để ghi mô tả (default: D)
        """
        self.downloader = downloader
        self.code_column = code_column
        self.link_column = link_column
        self.name_column = name_column
        self.description_column = description_column

    def process_sheet(
        self,
        sheet,  # gspread.Worksheet
        skip_existing: bool = True,
        delay_between: float = 1.0,
        update_sheet: bool = True,  # Có cập nhật tên/mô tả vào sheet không
    ) -> Dict[str, List[str]]:
        """
        Xử lý toàn bộ sheet, tải ảnh cho từng dòng

        Args:
            sheet: gspread Worksheet object
            skip_existing: Bỏ qua thư mục đã có ảnh
            delay_between: Delay giữa các request (giây)
            update_sheet: Cập nhật tên và mô tả vào cột C, D

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
            name_col_idx = ord(self.name_column.upper()) - ord('A')
            desc_col_idx = ord(self.description_column.upper()) - ord('A')

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

                # Kiểm tra xem đã có tên chưa (skip nếu đã có)
                existing_name = row[name_col_idx] if len(row) > name_col_idx else ""
                if skip_existing and existing_name.strip():
                    console.print(f"[dim]⏭️ Bỏ qua {code} (đã có tên: {existing_name[:30]}...)[/]")
                    continue

                console.print(f"\n[bold]📦 [{row_idx}] {code}[/]")
                console.print(f"[dim]{link}[/]")

                # Lấy thông tin sản phẩm và download ảnh
                product, images = self.downloader.get_product_and_download(
                    url=link,
                    folder_name=code,
                    skip_existing=skip_existing
                )

                # Cập nhật tên và mô tả vào sheet
                if update_sheet and product:
                    try:
                        # Ghi tên vào cột C
                        if product.name:
                            cell_name = f"{self.name_column}{row_idx}"
                            sheet.update_acell(cell_name, product.name)
                            console.print(f"[green]✓ Đã ghi tên vào {cell_name}[/]")

                        # Ghi mô tả vào cột D
                        if product.description:
                            cell_desc = f"{self.description_column}{row_idx}"
                            sheet.update_acell(cell_desc, product.description)
                            console.print(f"[green]✓ Đã ghi mô tả vào {cell_desc}[/]")
                    except Exception as e:
                        console.print(f"[yellow]⚠️ Lỗi ghi sheet: {e}[/]")

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
        update_sheet: bool = True,
    ) -> Dict[str, List[str]]:
        """
        Xử lý từ SheetsReader đã kết nối

        Args:
            sheets_reader: SheetsReader instance đã connect
            skip_existing: Bỏ qua thư mục đã có ảnh
            delay_between: Delay giữa các request
            update_sheet: Cập nhật tên/mô tả vào sheet

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
            delay_between=delay_between,
            update_sheet=update_sheet,
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
    name_column: str = "C",
    description_column: str = "D",
    skip_existing: bool = True,
    delay_between: float = 1.0,
    update_sheet: bool = True,
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
        name_column: Cột ghi tên sản phẩm (default: C)
        description_column: Cột ghi mô tả (default: D)
        skip_existing: Bỏ qua thư mục đã có ảnh
        delay_between: Delay giữa các request
        update_sheet: Cập nhật tên/mô tả vào sheet

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
        name_column=name_column,
        description_column=description_column,
    )

    return processor.process_from_reader(
        sheets_reader=reader,
        skip_existing=skip_existing,
        delay_between=delay_between,
        update_sheet=update_sheet,
    )
