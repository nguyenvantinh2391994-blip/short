"""
Test mở Chrome với Selenium
Chạy: python test_chrome.py
"""
import os
import shutil

print("=" * 50)
print("TEST MỞ CHROME VỚI SELENIUM")
print("=" * 50)

# Test 1: Import
print("\n1. Import thư viện...")
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    print("   ✓ Import OK")
except Exception as e:
    print(f"   ✗ Lỗi import: {e}")
    print("   Chạy: pip install selenium webdriver-manager")
    exit(1)

# Test 2: ChromeDriver
print("\n2. Tải ChromeDriver...")
try:
    driver_path = ChromeDriverManager().install()
    print(f"   ✓ ChromeDriver: {driver_path}")
except Exception as e:
    print(f"   ✗ Lỗi tải ChromeDriver: {e}")
    exit(1)

# Test 3: Mở Chrome đơn giản
print("\n3. Mở Chrome (không profile)...")
try:
    options = Options()
    options.add_argument("--window-size=800,600")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://google.com")
    print(f"   ✓ Mở OK! Title: {driver.title}")

    input("   Nhấn Enter để đóng browser và tiếp tục...")
    driver.quit()
except Exception as e:
    print(f"   ✗ Lỗi: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: Mở Chrome với Profile RIÊNG (không dùng profile Chrome đang mở)
print("\n4. Mở Chrome với Profile RIÊNG cho automation...")

# Tạo thư mục profile riêng
automation_profile = os.path.join(os.path.expanduser("~"), ".grok_automation_profile")
print(f"   Profile automation: {automation_profile}")

# Xóa profile cũ nếu có (để test fresh)
if os.path.exists(automation_profile):
    print("   Xóa profile cũ...")
    try:
        shutil.rmtree(automation_profile)
    except:
        pass

os.makedirs(automation_profile, exist_ok=True)

try:
    options = Options()
    options.add_argument("--window-size=1200,800")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument(f"--user-data-dir={automation_profile}")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Đặt Chrome path
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.path.exists(chrome_path):
        options.binary_location = chrome_path
        print(f"   Chrome: {chrome_path}")

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://grok.com")
    print(f"   ✓ Mở OK! URL: {driver.current_url}")
    print("\n   ⚠️  ĐÂY LÀ PROFILE MỚI - BẠN CẦN ĐĂNG NHẬP GROK!")
    print("   Sau khi login, profile sẽ được lưu cho lần sau.")

    input("\n   Nhấn Enter để đóng browser...")
    driver.quit()
    print("   ✓ Profile đã được lưu!")
except Exception as e:
    print(f"   ✗ Lỗi: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Copy cookies từ profile Chrome sang profile automation
print("\n5. CÁCH KHÁC: Copy profile từ Chrome sang automation...")
print("   Nếu bạn muốn dùng tài khoản đã login trong Chrome:")
print("")
print("   Bước 1: Đóng TẤT CẢ cửa sổ Chrome")
print("   Bước 2: Chạy lệnh sau trong CMD:")
print("")
print(f'   xcopy "C:\\Users\\trant\\AppData\\Local\\Google\\Chrome\\User Data\\Profile 4" "{automation_profile}" /E /I /Y')
print("")
print("   Bước 3: Chạy lại test_chrome.py")

print("\n" + "=" * 50)
print("TEST HOÀN TẤT")
print("=" * 50)
