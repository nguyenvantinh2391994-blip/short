"""
Test Shopee Image Downloader - Mở Chrome tự động

Chạy: python test_shopee.py
"""

import sys
import time
from pathlib import Path

print("\n" + "="*60)
print("TEST SHOPEE - TỰ ĐỘNG MỞ CHROME")
print("="*60)

# Import selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    print("✅ Selenium OK")
except ImportError:
    print("❌ Cần cài Selenium: pip install selenium")
    sys.exit(1)

# Cấu hình Chrome
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_PATH = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Default"

print(f"\n📁 Chrome: {CHROME_PATH}")
print(f"📁 Profile: {PROFILE_PATH}")

# Nhập link Shopee
print("\n" + "-"*60)
url = input("🔗 Nhập link Shopee: ").strip()

if not url:
    print("❌ Chưa nhập link!")
    sys.exit(1)

if "shopee" not in url.lower():
    print("⚠️ Có vẻ không phải link Shopee, tiếp tục...")

# Mở Chrome
print("\n🌐 Đang mở Chrome...")

options = Options()
options.binary_location = CHROME_PATH

# Sử dụng profile đã đăng nhập
profile = Path(PROFILE_PATH)
if profile.exists():
    options.add_argument(f"--user-data-dir={profile.parent}")
    options.add_argument(f"--profile-directory={profile.name}")
    print(f"✅ Dùng profile: {profile.name}")

# Window settings
options.add_argument("--window-size=1200,800")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")

# Preferences
prefs = {
    "download.prompt_for_download": False,
    "profile.default_content_setting_values.notifications": 2,
}
options.add_experimental_option("prefs", prefs)
options.add_experimental_option("excludeSwitches", ["enable-automation"])

try:
    driver = webdriver.Chrome(options=options)
    print("✅ Đã mở Chrome!")
except Exception as e:
    print(f"❌ Không mở được Chrome: {e}")
    print("\n💡 Thử đóng tất cả Chrome rồi chạy lại")
    sys.exit(1)

# Vào trang Shopee
print(f"\n📄 Đang vào: {url[:60]}...")
driver.get(url)

# Chờ trang load
print("⏳ Chờ trang load (10s)...")
try:
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "picture.UkIsx8 img"))
    )
    print("✅ Đã tìm thấy ảnh sản phẩm!")
except:
    print("⚠️ Chờ thêm...")
    time.sleep(5)

time.sleep(3)

# Lấy ảnh bằng JavaScript
print("\n" + "="*60)
print("LẤY ẢNH TỪ TRANG")
print("="*60)

js_script = """
var hashes = new Set();
var urls = [];

document.querySelectorAll('picture.UkIsx8 img').forEach(img => {
    let src = img.src;
    if (!src) return;

    src = src.split('@')[0];

    if (src.includes('susercontent.com/file/')) {
        let match = src.match(/\\/file\\/([a-zA-Z0-9_-]+)/);
        if (match && match[1] && !hashes.has(match[1])) {
            hashes.add(match[1]);
            urls.push(src);
        }
    }
});

return {
    urls: urls,
    count: urls.length,
    total_imgs: document.querySelectorAll('img').length,
    picture_imgs: document.querySelectorAll('picture.UkIsx8 img').length
};
"""

result = driver.execute_script(js_script)
print(f"\n📊 Kết quả:")
print(f"   - Tổng img tags: {result['total_imgs']}")
print(f"   - picture.UkIsx8 img: {result['picture_imgs']}")
print(f"   - Ảnh sản phẩm unique: {result['count']}")

image_urls = result['urls']

if image_urls:
    print(f"\n📷 Danh sách {len(image_urls)} URLs:")
    for i, u in enumerate(image_urls, 1):
        short = u.split('/')[-1][:40]
        print(f"   {i}. .../{short}")

    # Hỏi download
    print("\n" + "-"*60)
    folder = input("📁 Nhập tên thư mục lưu (hoặc Enter để bỏ qua): ").strip()

    if folder:
        import requests

        output_dir = Path("input") / folder
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n⬇️ Đang tải vào {output_dir}...")

        downloaded = 0
        for i, img_url in enumerate(image_urls, 1):
            filename = f"{i:02d}.jpg"
            filepath = output_dir / filename

            try:
                response = requests.get(img_url, timeout=30)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    size_kb = len(response.content) // 1024
                    print(f"   ✅ {filename} ({size_kb}KB)")
                    downloaded += 1
                else:
                    print(f"   ❌ {filename} - HTTP {response.status_code}")
            except Exception as e:
                print(f"   ❌ {filename} - {e}")

        print(f"\n✅ Đã tải {downloaded}/{len(image_urls)} ảnh")
        print(f"📁 Thư mục: {output_dir.absolute()}")
else:
    print("\n⚠️ Không tìm thấy ảnh sản phẩm!")
    print("   Có thể do:")
    print("   1. Trang chưa load xong")
    print("   2. Shopee đã thay đổi giao diện")
    print("   3. Không phải trang sản phẩm")

# Đóng browser
print("\n" + "="*60)
input("Nhấn Enter để đóng Chrome...")
driver.quit()
print("✅ Xong!")
