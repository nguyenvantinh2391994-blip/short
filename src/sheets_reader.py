"""
Google Sheets Reader - Đọc thông tin sản phẩm từ Google Sheets
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from rich.console import Console
from rich.table import Table

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

console = Console()


@dataclass
class Product:
    """Thông tin sản phẩm"""
    id: str  # Mã sản phẩm
    name: str  # Tên sản phẩm
    price: str  # Giá
    original_price: Optional[str] = None  # Giá gốc (nếu có khuyến mãi)
    promotion: Optional[str] = None  # Thông tin khuyến mãi
    description: Optional[str] = None  # Mô tả
    category: Optional[str] = None  # Danh mục
    images_folder: Optional[str] = None  # Thư mục chứa ảnh
    status: str = "active"  # Trạng thái
    tags: List[str] = field(default_factory=list)  # Tags
    extra: Dict[str, Any] = field(default_factory=dict)  # Thông tin thêm

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "original_price": self.original_price,
            "promotion": self.promotion,
            "description": self.description,
            "category": self.category,
            "images_folder": self.images_folder,
            "status": self.status,
            "tags": self.tags,
            "extra": self.extra,
        }


class SheetsReader:
    """Đọc dữ liệu từ Google Sheets"""

    # Mapping tên cột tiếng Việt -> field
    COLUMN_MAPPING = {
        # ID
        "ma": "id", "mã": "id", "ma_sp": "id", "mã_sp": "id",
        "product_id": "id", "sku": "id", "code": "id",

        # Name
        "ten": "name", "tên": "name", "ten_sp": "name", "tên_sp": "name",
        "product_name": "name", "name": "name",
        "tên_sản_phẩm": "name", "ten_san_pham": "name",

        # Price
        "gia": "price", "giá": "price", "gia_ban": "price", "giá_bán": "price",
        "price": "price", "giá_bán": "price",

        # Original price
        "gia_goc": "original_price", "giá_gốc": "original_price",
        "original_price": "original_price",

        # Promotion
        "khuyen_mai": "promotion", "khuyến_mãi": "promotion",
        "promotion": "promotion", "sale": "promotion",

        # Description
        "mo_ta": "description", "mô_tả": "description",
        "description": "description",

        # Category
        "danh_muc": "category", "danh_mục": "category",
        "category": "category", "loai": "category", "loại": "category",

        # Images folder
        "thu_muc_anh": "images_folder", "thư_mục_ảnh": "images_folder",
        "images": "images_folder", "folder": "images_folder",

        # Status
        "trang_thai": "status", "trạng_thái": "status",
        "status": "status",

        # Tags
        "tags": "tags", "nhan": "tags", "nhãn": "tags",

        # Extra fields (sẽ lưu vào product.extra)
        "prompt": "prompt",
        "link": "link",
    }

    def __init__(
        self,
        credentials_file: str = "config/credentials.json",
        spreadsheet_id: Optional[str] = None,
        sheet_name: str = "Products"
    ):
        self.credentials_file = Path(credentials_file)
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.client: Optional[gspread.Client] = None
        self.sheet: Optional[gspread.Worksheet] = None

    def connect(self) -> bool:
        """Kết nối đến Google Sheets"""
        if not GSPREAD_AVAILABLE:
            console.print("[red]❌ Chưa cài đặt gspread. Chạy: pip install gspread google-auth[/]")
            return False

        if not self.credentials_file.exists():
            console.print(f"[red]❌ Không tìm thấy file credentials: {self.credentials_file}[/]")
            console.print("[yellow]Hướng dẫn:[/]")
            console.print("1. Vào Google Cloud Console")
            console.print("2. Tạo Service Account")
            console.print("3. Tải JSON key và lưu vào config/credentials.json")
            console.print("4. Share spreadsheet với email của Service Account")
            return False

        try:
            # Cho phép đọc VÀ ghi
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]

            credentials = Credentials.from_service_account_file(
                str(self.credentials_file),
                scopes=scopes
            )

            self.client = gspread.authorize(credentials)
            console.print("[green]✅ Đã kết nối Google Sheets API[/]")
            return True

        except Exception as e:
            console.print(f"[red]❌ Lỗi kết nối: {e}[/]")
            return False

    def open_spreadsheet(self, spreadsheet_id: Optional[str] = None) -> bool:
        """Mở spreadsheet"""
        if not self.client:
            if not self.connect():
                return False

        sheet_id = spreadsheet_id or self.spreadsheet_id
        if not sheet_id:
            console.print("[red]❌ Chưa cung cấp spreadsheet_id[/]")
            return False

        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            self.sheet = spreadsheet.worksheet(self.sheet_name)
            console.print(f"[green]✅ Đã mở sheet: {self.sheet_name}[/]")
            return True

        except gspread.SpreadsheetNotFound:
            console.print(f"[red]❌ Không tìm thấy spreadsheet: {sheet_id}[/]")
            return False
        except gspread.WorksheetNotFound:
            console.print(f"[red]❌ Không tìm thấy worksheet: {self.sheet_name}[/]")
            # Liệt kê các sheet có sẵn
            try:
                spreadsheet = self.client.open_by_key(sheet_id)
                sheets = [ws.title for ws in spreadsheet.worksheets()]
                console.print(f"[yellow]Các sheet có sẵn: {', '.join(sheets)}[/]")
            except:
                pass
            return False
        except Exception as e:
            console.print(f"[red]❌ Lỗi mở spreadsheet: {e}[/]")
            return False

    def _normalize_column_name(self, name: str) -> str:
        """Chuẩn hóa tên cột"""
        normalized = name.lower().strip()
        normalized = normalized.replace(" ", "_")
        return self.COLUMN_MAPPING.get(normalized, normalized)

    def get_products(
        self,
        filter_status: Optional[str] = "active",
        filter_category: Optional[str] = None
    ) -> List[Product]:
        """Lấy danh sách sản phẩm"""
        if not self.sheet:
            if not self.open_spreadsheet():
                return []

        try:
            # Lấy tất cả dữ liệu
            records = self.sheet.get_all_records()

            if not records:
                console.print("[yellow]⚠️ Sheet trống hoặc không có dữ liệu[/]")
                return []

            products = []

            for row in records:
                # Map column names
                mapped_row = {}
                for key, value in row.items():
                    normalized_key = self._normalize_column_name(key)
                    mapped_row[normalized_key] = value

                # Bỏ qua nếu không có ID hoặc tên
                if not mapped_row.get("id") or not mapped_row.get("name"):
                    continue

                # Tạo Product object
                product = Product(
                    id=str(mapped_row.get("id", "")),
                    name=str(mapped_row.get("name", "")),
                    price=str(mapped_row.get("price", "")),
                    original_price=str(mapped_row.get("original_price", "")) or None,
                    promotion=str(mapped_row.get("promotion", "")) or None,
                    description=str(mapped_row.get("description", "")) or None,
                    category=str(mapped_row.get("category", "")) or None,
                    images_folder=str(mapped_row.get("images_folder", "")) or None,
                    status=str(mapped_row.get("status", "active")),
                    tags=self._parse_tags(mapped_row.get("tags", "")),
                )

                # Lưu các field khác vào extra
                known_fields = {"id", "name", "price", "original_price", "promotion",
                              "description", "category", "images_folder", "status", "tags"}
                for key, value in mapped_row.items():
                    if key not in known_fields and value:
                        product.extra[key] = value

                # Apply filters
                if filter_status and product.status.lower() != filter_status.lower():
                    continue
                if filter_category and product.category != filter_category:
                    continue

                products.append(product)

            console.print(f"[green]✅ Đã load {len(products)} sản phẩm[/]")
            return products

        except Exception as e:
            console.print(f"[red]❌ Lỗi đọc dữ liệu: {e}[/]")
            return []

    def _parse_tags(self, tags_str: Any) -> List[str]:
        """Parse tags từ string"""
        if not tags_str:
            return []
        if isinstance(tags_str, list):
            return tags_str
        return [t.strip() for t in str(tags_str).split(",") if t.strip()]

    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """Lấy sản phẩm theo ID"""
        products = self.get_products(filter_status=None)
        for product in products:
            if product.id == product_id:
                return product
        return None

    def get_pending_products(
        self,
        status_column: str = "E",
        prompt_column: str = "F",
        sora_prompt_column: str = "F",
        flow_prompt_column: str = "I",
        flow_prompt_column_2: str = "K"
    ) -> List[Dict]:
        """Lấy các sản phẩm có cột trạng thái trống (chưa làm video)

        Args:
            status_column: Cột trạng thái (mặc định E)
            prompt_column: Cột chứa prompt video (mặc định F)
            sora_prompt_column: Cột chứa prompt SORA (mặc định F - dùng chung)
            flow_prompt_column: Cột chứa prompt Flow 1 (mặc định I)
            flow_prompt_column_2: Cột chứa prompt Flow 2 (mặc định K)

        Returns:
            List[Dict]: Danh sách {row, code, prompt, sora_prompt, flow_prompt, flow_prompt_2, data}
        """
        if not self.sheet:
            if not self.open_spreadsheet():
                return []

        try:
            # Lấy tất cả dữ liệu
            all_values = self.sheet.get_all_values()
            if not all_values:
                return []

            headers = all_values[0]
            pending = []

            # Tìm index của các cột
            status_col_idx = ord(status_column.upper()) - ord('A')
            prompt_col_idx = ord(prompt_column.upper()) - ord('A')
            sora_prompt_col_idx = ord(sora_prompt_column.upper()) - ord('A')
            flow_prompt_col_idx = ord(flow_prompt_column.upper()) - ord('A')
            flow_prompt_2_col_idx = ord(flow_prompt_column_2.upper()) - ord('A')

            for row_idx, row in enumerate(all_values[1:], start=2):  # Bắt đầu từ row 2
                # Kiểm tra cột trạng thái có trống không
                status_value = row[status_col_idx] if len(row) > status_col_idx else ""

                if not status_value.strip():  # Trống
                    # Lấy mã sản phẩm từ cột A
                    code = row[0] if row else ""
                    # Lấy prompt Grok từ cột F
                    prompt = row[prompt_col_idx] if len(row) > prompt_col_idx else ""
                    # Lấy prompt SORA từ cột E
                    sora_prompt = row[sora_prompt_col_idx] if len(row) > sora_prompt_col_idx else ""
                    # Lấy prompt Flow 1 từ cột I
                    flow_prompt = row[flow_prompt_col_idx] if len(row) > flow_prompt_col_idx else ""
                    # Lấy prompt Flow 2 từ cột K
                    flow_prompt_2 = row[flow_prompt_2_col_idx] if len(row) > flow_prompt_2_col_idx else ""

                    if code:
                        pending.append({
                            "row": row_idx,
                            "code": code,
                            "prompt": prompt.strip(),
                            "sora_prompt": sora_prompt.strip(),
                            "flow_prompt": flow_prompt.strip(),
                            "flow_prompt_2": flow_prompt_2.strip(),
                            "data": row
                        })

            console.print(f"[green]✅ Tìm thấy {len(pending)} sản phẩm chưa làm video[/]")
            return pending

        except Exception as e:
            console.print(f"[red]❌ Lỗi đọc dữ liệu: {e}[/]")
            return []

    def update_status(self, row: int, status: str = "VIDEO", status_column: str = "E") -> bool:
        """Cập nhật trạng thái cho sản phẩm"""
        if not self.sheet:
            if not self.open_spreadsheet():
                return False

        try:
            cell = f"{status_column}{row}"
            self.sheet.update_acell(cell, status)
            console.print(f"[green]✅ Đã cập nhật {cell} = {status}[/]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Lỗi cập nhật trạng thái: {e}[/]")
            return False

    def display_products(self, products: Optional[List[Product]] = None) -> None:
        """Hiển thị bảng sản phẩm"""
        if products is None:
            products = self.get_products()

        if not products:
            console.print("[yellow]Không có sản phẩm nào[/]")
            return

        table = Table(title="Danh sách sản phẩm")
        table.add_column("Mã SP", style="cyan")
        table.add_column("Tên sản phẩm", style="white")
        table.add_column("Giá", style="green")
        table.add_column("Khuyến mãi", style="yellow")
        table.add_column("Trạng thái", style="blue")

        for product in products:
            table.add_row(
                product.id,
                product.name[:40] + "..." if len(product.name) > 40 else product.name,
                product.price,
                product.promotion or "-",
                product.status
            )

        console.print(table)


class LocalProductReader:
    """Đọc sản phẩm từ file JSON local (backup khi không có Sheets)"""

    def __init__(self, products_file: str = "config/products.json"):
        self.products_file = Path(products_file)

    def get_products(self) -> List[Product]:
        """Lấy danh sách sản phẩm từ file JSON"""
        if not self.products_file.exists():
            console.print(f"[yellow]⚠️ Không tìm thấy file: {self.products_file}[/]")
            return []

        try:
            with open(self.products_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            products = []
            for item in data.get("products", []):
                products.append(Product(**item))

            return products

        except Exception as e:
            console.print(f"[red]❌ Lỗi đọc file: {e}[/]")
            return []

    def save_products(self, products: List[Product]) -> None:
        """Lưu sản phẩm ra file JSON"""
        self.products_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "products": [p.to_dict() for p in products]
        }

        with open(self.products_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✅ Đã lưu {len(products)} sản phẩm vào {self.products_file}[/]")
