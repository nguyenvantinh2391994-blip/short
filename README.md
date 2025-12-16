# Short Video Creator

Tool tạo video short tự động cho bán hàng trên Facebook và TikTok.

## Tính năng

- Tạo video từ ảnh sản phẩm với hiệu ứng chuyển cảnh
- Tự động thêm text overlay (tên SP, giá, khuyến mãi)
- Hỗ trợ nhạc nền
- Đọc thông tin sản phẩm từ Google Sheets
- Hỗ trợ Grok AI để tạo video chất lượng cao
- Auto-watch: tự động tạo video khi có thay đổi
- Output format phù hợp TikTok/Reels (9:16)

## Cài đặt

```bash
# Clone repo
git clone <repo-url>
cd short

# Cài đặt dependencies
pip install -r requirements.txt

# Cài đặt FFmpeg (Windows)
# Download từ: https://ffmpeg.org/download.html
# Thêm vào PATH

# Khởi tạo project
python -m src.main init
```

## Cấu hình

### 1. Google Sheets API

1. Vào [Google Cloud Console](https://console.cloud.google.com/)
2. Tạo project mới
3. Enable **Google Sheets API** và **Google Drive API**
4. Tạo **Service Account**
5. Download JSON key → lưu vào `config/credentials.json`
6. Share spreadsheet với email của Service Account

### 2. Grok Token

```bash
python -m src.main add-token
```

Làm theo hướng dẫn để lấy token từ https://grok.com/imagine

### 3. File config

Chỉnh sửa `config/config.json`:

```json
{
  "google_sheets": {
    "spreadsheet_id": "YOUR_SPREADSHEET_ID",
    "sheet_name": "Products"
  }
}
```

## Cấu trúc thư mục

```
short/
├── config/
│   ├── config.json           # Cấu hình chính
│   ├── credentials.json      # Google Sheets API key
│   └── grok_tokens.json      # Grok tokens
├── products/                  # Ảnh sản phẩm
│   ├── SP001/
│   │   ├── 1.jpg
│   │   └── 2.jpg
│   └── SP002/
│       └── ...
├── music/                     # Nhạc nền (*.mp3)
├── outputs/                   # Video đầu ra
└── src/                       # Source code
```

## Sử dụng

```bash
# Xem hướng dẫn
python -m src.main guide

# Xem danh sách sản phẩm
python -m src.main list-products

# Tạo video cho 1 sản phẩm
python -m src.main generate SP001

# Tạo video tất cả sản phẩm
python -m src.main generate --all

# Tạo với Grok AI
python -m src.main generate --all --use-grok

# Auto watch mode
python -m src.main watch

# Quick start (không cần Google Sheets)
python -m src.main quick-start "Áo thun nam" "299.000đ" ./my_images --promotion "-20%"
```

## Google Sheets Format

| Mã SP | Tên sản phẩm | Giá | Khuyến mãi | Trạng thái |
|-------|-------------|-----|-----------|------------|
| SP001 | Áo thun nam | 299.000đ | -20% | active |
| SP002 | Quần jean | 499.000đ | | active |

Các tên cột hỗ trợ (tiếng Việt có dấu hoặc không):
- Mã SP: `ma`, `mã`, `ma_sp`, `product_id`, `sku`
- Tên: `ten`, `tên`, `product_name`, `name`
- Giá: `gia`, `giá`, `price`
- Khuyến mãi: `khuyen_mai`, `khuyến mãi`, `promotion`, `sale`

## Yêu cầu hệ thống

- Python 3.8+
- FFmpeg (cho video processing)
- Windows 10+ / macOS / Linux

## License

MIT
