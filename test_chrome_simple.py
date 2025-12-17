"""
Test mở Chrome ĐÚNG CÁCH - đơn giản như Windows Run
QUAN TRỌNG: Đóng TẤT CẢ Chrome trước khi chạy!
"""
import os
import subprocess
import time

print("=" * 50)
print("TEST MỞ CHROME ĐƠN GIẢN (như Windows Run)")
print("=" * 50)
print("\n⚠️  QUAN TRỌNG: Đóng TẤT CẢ cửa sổ Chrome trước!")
input("Nhấn Enter khi đã đóng Chrome...")

# Config
chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
profile = "Profile 5"
debug_port = 9222

print(f"\n1. Config:")
print(f"   Chrome: {chrome_exe}")
print(f"   Profile: {profile}")

# ========================================
# CÁCH 1: Mở Chrome đơn giản bằng subprocess (như Windows Run)
# ========================================
print("\n" + "=" * 50)
print("CÁCH 1: Mở Chrome đơn giản (subprocess)")
print("=" * 50)

try:
    # Mở giống hệt Windows Run: chrome.exe --profile-directory="Profile 5" --remote-debugging-port=9222
    cmd = f'"{chrome_exe}" --profile-directory="{profile}" --remote-debugging-port={debug_port}'
    print(f"\n   Lệnh: {cmd}")

    # Dùng os.system giống Run
    print("\n   Đang mở Chrome...")
    process = subprocess.Popen(cmd, shell=True)
    print(f"   ✓ Chrome đã mở (PID: {process.pid})")

    # Đợi Chrome khởi động
    print("   Đợi 3 giây...")
    time.sleep(3)

except Exception as e:
    print(f"   ✗ LỖI: {e}")
    exit(1)

# ========================================
# CÁCH 2: Selenium connect vào Chrome đang chạy
# ========================================
print("\n" + "=" * 50)
print("CÁCH 2: Selenium connect vào Chrome")
print("=" * 50)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    print("\n   Đang connect...")

    options = Options()
    # CHỈ CẦN 1 DÒNG NÀY - connect vào Chrome đang chạy
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    print(f"   ✓ CONNECT THÀNH CÔNG!")
    print(f"   URL: {driver.current_url}")

except Exception as e:
    print(f"   ✗ LỖI connect: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# ========================================
# TEST: Mở grok.com
# ========================================
print("\n" + "=" * 50)
print("TEST: Mở grok.com")
print("=" * 50)

try:
    driver.get("https://grok.com")
    time.sleep(2)
    print(f"\n   ✓ Đã mở grok.com")
    print(f"   Title: {driver.title}")

except Exception as e:
    print(f"   ✗ LỖI: {e}")

print("\n   Hãy đăng nhập Grok nếu cần.")
input("\n   Nhấn Enter để đóng...")

driver.quit()
print("   ✓ Đã đóng")

print("\n" + "=" * 50)
print("TEST HOÀN TẤT - CÁCH NÀY HOẠT ĐỘNG!")
print("=" * 50)
