"""
File Watcher - Tự động tạo video khi có thay đổi
"""

import time
from pathlib import Path
from typing import Set, Dict, Optional, Callable
from datetime import datetime
from rich.console import Console
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

console = Console()


class ProductFolderHandler(FileSystemEventHandler):
    """Handler cho sự kiện thay đổi trong thư mục products"""

    def __init__(
        self,
        callback: Callable[[str], None],
        debounce_seconds: float = 2.0
    ):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._pending: Dict[str, float] = {}  # product_id -> timestamp
        self._processed: Set[str] = set()
        self._image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    def _get_product_id(self, path: str) -> Optional[str]:
        """Lấy product_id từ đường dẫn"""
        p = Path(path)
        # Giả sử cấu trúc: products/{product_id}/image.jpg
        parts = p.parts
        try:
            products_idx = parts.index("products")
            if len(parts) > products_idx + 1:
                return parts[products_idx + 1]
        except ValueError:
            pass
        return None

    def _is_image(self, path: str) -> bool:
        """Kiểm tra có phải file ảnh không"""
        return Path(path).suffix.lower() in self._image_extensions

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_change(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._handle_change(event.src_path)

    def _handle_change(self, path: str):
        """Xử lý thay đổi file"""
        if not self._is_image(path):
            return

        product_id = self._get_product_id(path)
        if not product_id:
            return

        # Debounce: chờ một chút trước khi xử lý
        self._pending[product_id] = time.time()

    def process_pending(self):
        """Xử lý các thay đổi đang chờ"""
        current_time = time.time()
        to_process = []

        for product_id, timestamp in list(self._pending.items()):
            if current_time - timestamp >= self.debounce_seconds:
                to_process.append(product_id)
                del self._pending[product_id]

        for product_id in to_process:
            console.print(f"[cyan]Phát hiện thay đổi: {product_id}[/]")
            self.callback(product_id)


class AutoVideoWatcher:
    """Tự động tạo video khi có thay đổi"""

    def __init__(
        self,
        products_dir: str = "products",
        on_change_callback: Optional[Callable[[str], None]] = None
    ):
        self.products_dir = Path(products_dir)
        self.callback = on_change_callback or self._default_callback
        self.observer: Optional[Observer] = None
        self._running = False

    def _default_callback(self, product_id: str):
        """Callback mặc định khi có thay đổi"""
        console.print(f"[yellow]Cần tạo video mới cho: {product_id}[/]")

    def start(self):
        """Bắt đầu watch"""
        if self._running:
            console.print("[yellow]Watcher đang chạy[/]")
            return

        if not self.products_dir.exists():
            self.products_dir.mkdir(parents=True)
            console.print(f"[green]Đã tạo thư mục: {self.products_dir}[/]")

        self.handler = ProductFolderHandler(self.callback)
        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.products_dir), recursive=True)
        self.observer.start()
        self._running = True

        console.print(f"[green]Đang theo dõi: {self.products_dir}[/]")
        console.print("[dim]Nhấn Ctrl+C để dừng[/]")

    def run_forever(self):
        """Chạy watcher liên tục"""
        self.start()
        try:
            while self._running:
                time.sleep(1)
                self.handler.process_pending()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Dừng watch"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self._running = False
        console.print("[yellow]Đã dừng watcher[/]")


class SheetsWatcher:
    """Theo dõi thay đổi từ Google Sheets (polling)"""

    def __init__(
        self,
        sheets_reader,
        check_interval: int = 60,  # Kiểm tra mỗi 60 giây
        on_change_callback: Optional[Callable[[list], None]] = None
    ):
        self.sheets_reader = sheets_reader
        self.check_interval = check_interval
        self.callback = on_change_callback
        self._last_data: Dict = {}
        self._running = False

    def _get_data_hash(self, products) -> Dict:
        """Tạo hash từ dữ liệu để so sánh"""
        return {p.id: f"{p.name}|{p.price}|{p.promotion}" for p in products}

    def check_changes(self) -> list:
        """Kiểm tra thay đổi"""
        products = self.sheets_reader.get_products()
        current_hash = self._get_data_hash(products)

        changed_ids = []

        # Tìm sản phẩm mới hoặc thay đổi
        for product_id, hash_val in current_hash.items():
            if product_id not in self._last_data:
                changed_ids.append(product_id)
                console.print(f"[green]Sản phẩm mới: {product_id}[/]")
            elif self._last_data[product_id] != hash_val:
                changed_ids.append(product_id)
                console.print(f"[yellow]Sản phẩm thay đổi: {product_id}[/]")

        self._last_data = current_hash
        return changed_ids

    def run_forever(self):
        """Chạy polling liên tục"""
        self._running = True
        console.print(f"[green]Đang theo dõi Google Sheets (mỗi {self.check_interval}s)...[/]")

        # Lần đầu load data
        products = self.sheets_reader.get_products()
        self._last_data = self._get_data_hash(products)

        try:
            while self._running:
                time.sleep(self.check_interval)
                changed = self.check_changes()
                if changed and self.callback:
                    self.callback(changed)
        except KeyboardInterrupt:
            self._running = False
            console.print("[yellow]Đã dừng theo dõi Sheets[/]")

    def stop(self):
        self._running = False
