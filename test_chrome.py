"""
Test mở Chrome với Selenium
Chạy: python test_chrome.py
"""

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

# Test 4: Mở Chrome với Profile
print("\n4. Mở Chrome với Profile...")
profile_path = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data\Profile 4"
user_data = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data"
profile_dir = "Profile 4"

print(f"   User Data: {user_data}")
print(f"   Profile: {profile_dir}")

try:
    options = Options()
    options.add_argument("--window-size=800,600")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument(f"--user-data-dir={user_data}")
    options.add_argument(f"--profile-directory={profile_dir}")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Đặt Chrome path
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    import os
    if os.path.exists(chrome_path):
        options.binary_location = chrome_path
        print(f"   Chrome: {chrome_path}")

    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.get("https://grok.com")
    print(f"   ✓ Mở OK! URL: {driver.current_url}")

    input("   Nhấn Enter để đóng browser...")
    driver.quit()
except Exception as e:
    print(f"   ✗ Lỗi: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("TEST HOÀN TẤT")
print("=" * 50)
