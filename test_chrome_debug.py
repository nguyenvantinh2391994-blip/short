"""
Test Chrome với Remote Debugging Port
Cách này mở Chrome bằng subprocess, sau đó Selenium connect vào
QUAN TRỌNG: Đóng TẤT CẢ Chrome trước khi chạy!
"""
import os
import subprocess
import time

print("=" * 50)
print("TEST CHROME VỚI REMOTE DEBUGGING")
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

# Config
chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
user_data = r"C:\Users\trant\AppData\Local\Google\Chrome\User Data"
profile = "Profile 5"
debug_port = 9222

print(f"\n2. Config:")
print(f"   Chrome: {chrome_exe}")
print(f"   User Data: {user_data}")
print(f"   Profile: {profile}")
print(f"   Debug Port: {debug_port}")

# Bước 1: Mở Chrome bằng subprocess với remote debugging
print("\n3. Mở Chrome bằng subprocess...")
try:
    chrome_cmd = [
        chrome_exe,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data}",
        f"--profile-directory={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    # Mở Chrome trong background
    process = subprocess.Popen(chrome_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"   ✓ Chrome đã mở (PID: {process.pid})")

    # Đợi Chrome khởi động
    print("   Đợi 3 giây cho Chrome khởi động...")
    time.sleep(3)

except Exception as e:
    print(f"   ✗ LỖI mở Chrome: {e}")
    exit(1)

# Bước 2: Connect Selenium vào Chrome đang chạy
print("\n4. Connect Selenium vào Chrome...")
try:
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")

    driver_path = ChromeDriverManager().install()
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)

    print(f"   ✓ CONNECT THÀNH CÔNG!")
    print(f"   URL hiện tại: {driver.current_url}")

except Exception as e:
    print(f"   ✗ LỖI connect: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Bước 3: Test điều hướng
print("\n5. Test điều hướng tới grok.com...")
try:
    driver.get("https://grok.com")
    time.sleep(2)
    print(f"   ✓ Đã mở grok.com")
    print(f"   URL: {driver.current_url}")
    print(f"   Title: {driver.title}")

except Exception as e:
    print(f"   ✗ LỖI: {e}")

print("\n   Hãy đăng nhập Grok nếu cần.")
input("\n   Nhấn Enter để đóng browser...")

# Đóng
driver.quit()
print("   ✓ Đã đóng Selenium")

# Kill Chrome process nếu còn chạy
try:
    process.terminate()
    print("   ✓ Đã terminate Chrome process")
except:
    pass

print("\n" + "=" * 50)
print("TEST HOÀN TẤT")
print("=" * 50)
