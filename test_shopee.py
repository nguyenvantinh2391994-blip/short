"""
Test Shopee Image Downloader
Chạy: python test_shopee.py "LINK_SHOPEE"
"""

import sys
import json

# Thêm path
sys.path.insert(0, "/home/user/short")

from src.shopee_downloader import ShopeeDownloader

# Lấy URL từ argument hoặc dùng URL mặc định
if len(sys.argv) > 1:
    url = sys.argv[1]
else:
    url = input("Nhập link Shopee: ").strip()

print(f"\n{'='*60}")
print(f"TEST SHOPEE DOWNLOADER")
print(f"{'='*60}")
print(f"URL: {url}")

# Khởi tạo downloader
downloader = ShopeeDownloader(output_dir="input", headless=False)

# Parse URL
shop_id, item_id = downloader.parse_shopee_url(url)
print(f"\nShop ID: {shop_id}")
print(f"Item ID: {item_id}")

if not shop_id or not item_id:
    print("❌ Không parse được URL!")
    sys.exit(1)

# Test Selenium trực tiếp (bỏ qua API)
print(f"\n{'='*60}")
print("TEST SELENIUM TRỰC TIẾP (bỏ qua API)")
print(f"{'='*60}")

product = downloader._get_product_selenium(
    shop_id=shop_id,
    item_id=item_id,
    headless=False,  # Hiện browser để xem
    original_url=url
)

if product:
    print(f"\n✅ Lấy product thành công!")
    print(f"Tên: {product.name[:80] if product.name else 'N/A'}...")
    print(f"Số ảnh (images list): {len(product.images)}")
    print(f"Images: {product.images}")

    # Check direct URLs (lưu trong description)
    try:
        direct_urls = json.loads(product.description) if product.description else []
        print(f"\nDirect URLs: {len(direct_urls)}")
        for i, u in enumerate(direct_urls, 1):
            print(f"  {i}. {u}")
    except Exception as e:
        print(f"Không có direct URLs: {e}")
else:
    print("❌ Không lấy được product!")

print(f"\n{'='*60}")
print("TEST DOWNLOAD ẢNH")
print(f"{'='*60}")

if product:
    # Thử download
    images = downloader.download_images(product, "TEST_SHOPEE", skip_existing=False)
    print(f"\n✅ Downloaded: {len(images)} ảnh")
    for img in images:
        print(f"  - {img}")
