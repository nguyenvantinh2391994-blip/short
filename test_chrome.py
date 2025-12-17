"""
Test mở Chrome với Profile 5 mới tạo
QUAN TRỌNG: Đóng TẤT CẢ Chrome trước khi chạy!
"""
import os

print("=" * 50)
print("TEST CHROME VỚI PROFILE 5")
print("=" * 50)
print("\n⚠️  QUAN TRỌNG: Đóng TẤT CẢ cửa sổ Chrome trước!")
input("Nhấn Enter khi đã đóng Chrome...")

# Import
print("\n1. Import thư viện...")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
print("   ✓ OK")

# ChromeDriver
print("\n2. Tải ChromeDriver...")
driver_path = ChromeDriverManager().install()
print(f"   ✓ {driver_path}")

# Config
chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
user_data = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data"
profile = "Profile 5"

print(f"\n3. Config:")
print(f"   Chrome: {chrome_exe}")
print(f"   User Data: {user_data}")
print(f"   Profile: {profile}")

# Mở Chrome
print("\n4. Mở Chrome với Profile 5...")
try:
    options = Options()
    options.add_argument("--window-size=1200,800")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Chrome path
    if os.path.exists(chrome_exe):
        options.binary_location = chrome_exe

    # Profile
    options.add_argument(f"--user-data-dir={user_data}")
    options.add_argument(f"--profile-directory={profile}")

    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://grok.com")

    print(f"   ✓ MỞ THÀNH CÔNG!")
    print(f"   URL: {driver.current_url}")
    print("\n   Hãy đăng nhập Grok nếu cần.")

    input("\n   Nhấn Enter để đóng browser...")
    driver.quit()
    print("   ✓ Đã đóng browser")

except Exception as e:
    print(f"   ✗ LỖI: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("TEST HOÀN TẤT")
print("=" * 50)
