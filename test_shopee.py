"""
Test Shopee Image Downloader - Dùng Chrome đang mở sẵn

BƯỚC 1: Mở Chrome với debug mode (chạy trong CMD):
    "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222

BƯỚC 2: Vào trang Shopee cần tải ảnh trong Chrome đó

BƯỚC 3: Chạy script này:
    python test_shopee.py
"""

import sys
import json
import time

sys.path.insert(0, "/home/user/short")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

print(f"\n{'='*60}")
print(f"TEST SHOPEE - DÙNG CHROME ĐANG MỞ")
print(f"{'='*60}")

# Kết nối Chrome đang chạy với debug port
options = Options()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

try:
    driver = webdriver.Chrome(options=options)
    print(f"✅ Đã kết nối Chrome!")
    print(f"URL hiện tại: {driver.current_url}")
except Exception as e:
    print(f"❌ Không kết nối được Chrome!")
    print(f"Lỗi: {e}")
    print(f"\n👉 Hãy mở Chrome với debug mode trước:")
    print(f'   "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222')
    sys.exit(1)

# Chờ user xác nhận đã vào đúng trang Shopee
input("\n⏳ Hãy vào trang sản phẩm Shopee rồi nhấn ENTER để tiếp tục...")

print(f"\n{'='*60}")
print(f"LẤY ẢNH TỪ TRANG HIỆN TẠI")
print(f"{'='*60}")

# Chờ trang load
time.sleep(2)

# JavaScript lấy ảnh
js_script = """
var hashes = new Set();
var urls = [];

document.querySelectorAll('picture.UkIsx8 img').forEach(img => {
    let src = img.src;
    if (!src) return;

    // Bỏ resize param
    src = src.split('@')[0];

    if (src.includes('susercontent.com/file/')) {
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

print(f"\n📷 Tìm thấy: {len(image_urls)} ảnh unique")
print(f"\nDanh sách URLs:")
for i, url in enumerate(image_urls, 1):
    print(f"  {i}. {url}")

# Hỏi có muốn download không
if image_urls:
    print(f"\n{'='*60}")
    folder = input("Nhập tên thư mục để lưu (VD: TEST001): ").strip()

    if folder:
        import requests
        from pathlib import Path

        output_dir = Path("input") / folder
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n⬇️ Đang tải {len(image_urls)} ảnh vào {output_dir}...")

        downloaded = []
        for i, url in enumerate(image_urls, 1):
            filename = f"{i:02d}.jpg"
            filepath = output_dir / filename

            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    downloaded.append(str(filepath))
                    print(f"  ✅ {filename}")
                else:
                    print(f"  ❌ {filename} - HTTP {response.status_code}")
            except Exception as e:
                print(f"  ❌ {filename} - {e}")

        print(f"\n✅ Đã tải {len(downloaded)}/{len(image_urls)} ảnh")
        print(f"📁 Thư mục: {output_dir}")
    else:
        print("Bỏ qua download.")
else:
    print("\n⚠️ Không tìm thấy ảnh! Kiểm tra lại selector hoặc đợi trang load xong.")

print(f"\n{'='*60}")
print("XONG!")
