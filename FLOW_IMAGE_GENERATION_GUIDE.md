# Google Flow Image Generation - Implementation Guide

## Overview
Hướng dẫn implement tính năng tạo ảnh với Google Flow API, từ mở Chrome lấy token cho đến download ảnh về.

---

## 1. Architecture

```
[Chrome Profile] --> [Navigate to Flow] --> [Inject Capture Script]
                                                    |
[Click "Dự án mới"] --> [Click "Tạo hình ảnh"] --> [Focus textarea]
                                                    |
[Enter test prompt] --> [Wait for API call] --> [Capture Bearer Token]
                                                    |
[Use Token for API] --> [Generate Images] --> [Download to local]
```

---

## 2. Chrome Profile Setup

### 2.1 Profile Structure
```
chrome_profiles/
└── main/                # Profile đã login Google
    ├── Default/
    ├── Cookies
    └── ...
```

### 2.2 Mở Chrome với Profile
```python
import subprocess
from pathlib import Path

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
profile_path = Path("chrome_profiles/main")

cmd = [
    chrome_path,
    f"--user-data-dir={profile_path.parent}",
    f"--profile-directory={profile_path.name}",
    "https://labs.google/fx/vi/tools/flow"
]
subprocess.Popen(cmd)
```

---

## 3. Token Extraction

### 3.1 Inject Capture Script
Inject vào DevTools Console để hook `fetch()` và capture token:

```javascript
// Capture script - hook fetch to get Bearer token
window._tk = null;  // Token
window._pj = null;  // Project ID

(function() {
    var originalFetch = window.fetch;
    window.fetch = function(url, options) {
        var urlStr = url ? url.toString() : '';

        // Capture from Flow API calls
        if (urlStr.includes('flowMedia') || urlStr.includes('aisandbox')) {
            var headers = options && options.headers ? options.headers : {};
            var auth = headers.Authorization || headers.authorization || '';

            if (auth.startsWith('Bearer ')) {
                window._tk = auth.substring(7);  // Remove "Bearer " prefix

                // Extract project_id from URL
                var match = urlStr.match(/\/projects\/([^\/]+)\//);
                if (match) window._pj = match[1];

                console.log('TOKEN CAPTURED!');
            }
        }
        return originalFetch.apply(this, arguments);
    };
    console.log('Capture ready');
})();
```

### 3.2 Trigger API Call
Để capture token, cần trigger một API call bằng cách:

1. **Click "Dự án mới"** - Tạo project mới
2. **Click dropdown** - Chọn loại tạo
3. **Click "Tạo hình ảnh"** - Chọn mode tạo ảnh
4. **Focus textarea** - Click vào ô nhập
5. **Enter prompt** - Gõ prompt bất kỳ và Enter

```javascript
// Click "Dự án mới"
document.querySelectorAll('button').forEach(btn => {
    if (btn.textContent.includes('Dự án mới')) btn.click();
});

// Wait 5s for project to load...

// Click dropdown và chọn "Tạo hình ảnh"
var dropdown = document.querySelector('button[role="combobox"]');
if (dropdown) {
    dropdown.click();
    setTimeout(() => {
        document.querySelectorAll('*').forEach(el => {
            if (el.textContent === 'Tạo hình ảnh') {
                var rect = el.getBoundingClientRect();
                if (rect.height > 10 && rect.height < 80) el.click();
            }
        });
    }, 500);
}

// Wait 3s...

// Focus textarea
var textarea = document.querySelector('textarea');
if (textarea) {
    textarea.focus();
    textarea.click();
}
```

### 3.3 Get Token
Sau khi API call được thực hiện, lấy token từ DevTools:

```javascript
// Get captured token
JSON.stringify({
    token: window._tk,
    project_id: window._pj
})
```

**Token format**: `ya29.xxx...` (bắt đầu bằng "ya29.")

---

## 4. API Endpoints

### 4.1 Direct API (có thể bị captcha)
```
Base URL: https://aisandbox-pa.googleapis.com
Endpoint: /v1/projects/{project_id}/flowMedia:batchGenerateImages
```

### 4.2 Proxy API (bypass captcha) - KHUYÊN DÙNG
```
Image API: https://flow-api.nanoai.pics/api/fix/create-image-veo3
Task Status: https://flow-api.nanoai.pics/api/fix/task-status
```

---

## 5. Image Generation API

### 5.1 Request Payload
```python
import requests
import json
import uuid
import random

# Config
PROXY_API_URL = "https://flow-api.nanoai.pics/api/fix/create-image-veo3"
proxy_api_token = "YOUR_PROXY_TOKEN"  # Get from nanoai.pics
bearer_token = "ya29.xxx..."  # From Chrome capture
project_id = "your-project-id"

# Build payload
def generate_seed():
    return random.randint(1, 999999)

def generate_session_id():
    return str(uuid.uuid4())

body_json = {
    "requests": [
        {
            "clientContext": {
                "sessionId": generate_session_id(),
                "projectId": project_id,
                "tool": "PINHOLE"
            },
            "seed": generate_seed(),
            "imageModelName": "GEM_PIX_2",
            "imageAspectRatio": "IMAGE_ASPECT_RATIO_LANDSCAPE",  # 16:9
            "prompt": "a beautiful sunset over the ocean",
            "imageInputs": []  # Reference images go here
        },
        # Add more requests for multiple images
    ]
}

# Proxy request
proxy_payload = {
    "body_json": body_json,
    "flow_auth_token": bearer_token,
    "flow_url": f"https://aisandbox-pa.googleapis.com/v1/projects/{project_id}/flowMedia:batchGenerateImages"
}

headers = {
    "Authorization": f"Bearer {proxy_api_token}",
    "Content-Type": "application/json"
}

response = requests.post(PROXY_API_URL, headers=headers, json=proxy_payload)
result = response.json()
task_id = result.get("taskId")
```

### 5.2 Poll for Result
```python
TASK_STATUS_URL = "https://flow-api.nanoai.pics/api/fix/task-status"

def poll_task(task_id, headers, max_attempts=60, interval=2):
    for attempt in range(max_attempts):
        response = requests.get(
            f"{TASK_STATUS_URL}?taskId={task_id}",
            headers=headers
        )
        result = response.json()

        if result.get("success"):
            task_result = result.get("result", {})

            # Check for media/images
            if "media" in task_result:
                return task_result["media"]

            if task_result.get("success") == True:
                return task_result

        time.sleep(interval)

    return None
```

### 5.3 Parse Response & Download
```python
def parse_and_download(media_list, output_dir):
    """Parse media response and download images."""
    for i, media_item in enumerate(media_list):
        # Get image data
        image_wrapper = media_item.get("image", {})
        generated_image = image_wrapper.get("generatedImage", {})

        # Important fields
        fife_url = generated_image.get("fifeUrl")  # Direct image URL
        media_name = media_item.get("name")  # For reference in future prompts
        seed = generated_image.get("seed")

        if fife_url:
            # Download image
            img_response = requests.get(fife_url)
            filename = f"image_{i+1}.png"
            filepath = Path(output_dir) / filename

            with open(filepath, 'wb') as f:
                f.write(img_response.content)

            print(f"Downloaded: {filename}")
            print(f"  media_name: {media_name}")  # Save this for reference!
            print(f"  seed: {seed}")
```

---

## 6. Reference Images (Advanced)

### 6.1 Using media_name as Reference
Khi đã tạo ảnh, bạn có thể dùng `media_name` để tham chiếu trong prompt tiếp theo:

```python
# Previous image's media_name
ref_media_name = "projects/xxx/media/yyy"

body_json = {
    "requests": [{
        # ... other fields ...
        "imageInputs": [
            {
                "name": ref_media_name,
                "imageInputType": "IMAGE_INPUT_TYPE_REFERENCE"
            }
        ]
    }]
}
```

### 6.2 Upload Local Image as Reference
```python
import base64

def upload_reference(image_path):
    """Convert local image to base64 for upload."""
    with open(image_path, 'rb') as f:
        base64_data = base64.b64encode(f.read()).decode('utf-8')
    return base64_data
```

---

## 7. Complete Flow Example

```python
"""
Complete example: Open Chrome -> Get Token -> Generate Image -> Download
"""

import time
import json
import requests
import subprocess
from pathlib import Path

class FlowImageGenerator:
    FLOW_URL = "https://labs.google/fx/vi/tools/flow"
    PROXY_API_URL = "https://flow-api.nanoai.pics/api/fix/create-image-veo3"
    TASK_STATUS_URL = "https://flow-api.nanoai.pics/api/fix/task-status"

    def __init__(self, chrome_path, profile_path, proxy_token):
        self.chrome_path = chrome_path
        self.profile_path = Path(profile_path)
        self.proxy_token = proxy_token
        self.bearer_token = None
        self.project_id = None

    def open_chrome(self):
        """Open Chrome with profile."""
        cmd = [
            self.chrome_path,
            f"--user-data-dir={self.profile_path.parent}",
            f"--profile-directory={self.profile_path.name}",
            self.FLOW_URL
        ]
        subprocess.Popen(cmd)
        print("Chrome opened. Wait for page to load...")
        time.sleep(12)

    def extract_token_manual(self):
        """
        Manual token extraction steps:
        1. Open DevTools (Ctrl+Shift+J)
        2. Paste capture script
        3. Close DevTools
        4. Click "Dự án mới"
        5. Wait 5s
        6. Click dropdown -> "Tạo hình ảnh"
        7. Wait 3s
        8. Focus textarea and enter any prompt
        9. Wait 20s for image generation
        10. Open DevTools
        11. Run: JSON.stringify({t:window._tk,p:window._pj})
        12. Copy result
        """
        print("Follow manual steps to extract token...")
        token_json = input("Paste token JSON: ")
        data = json.loads(token_json)
        self.bearer_token = data.get("t")
        self.project_id = data.get("p")
        print(f"Token: {self.bearer_token[:30]}...")
        print(f"Project: {self.project_id}")

    def generate_image(self, prompt, count=2):
        """Generate images via proxy API."""
        import uuid
        import random

        body_json = {
            "requests": [
                {
                    "clientContext": {
                        "sessionId": str(uuid.uuid4()),
                        "projectId": self.project_id,
                        "tool": "PINHOLE"
                    },
                    "seed": random.randint(1, 999999),
                    "imageModelName": "GEM_PIX_2",
                    "imageAspectRatio": "IMAGE_ASPECT_RATIO_LANDSCAPE",
                    "prompt": prompt,
                    "imageInputs": []
                }
                for _ in range(count)
            ]
        }

        proxy_payload = {
            "body_json": body_json,
            "flow_auth_token": self.bearer_token,
            "flow_url": f"https://aisandbox-pa.googleapis.com/v1/projects/{self.project_id}/flowMedia:batchGenerateImages"
        }

        headers = {
            "Authorization": f"Bearer {self.proxy_token}",
            "Content-Type": "application/json"
        }

        # Create task
        response = requests.post(self.PROXY_API_URL, headers=headers, json=proxy_payload)
        result = response.json()

        if not result.get("success"):
            return None, result.get("error")

        task_id = result.get("taskId")
        print(f"Task created: {task_id}")

        # Poll for result
        for attempt in range(60):
            time.sleep(2)
            response = requests.get(f"{self.TASK_STATUS_URL}?taskId={task_id}", headers=headers)
            result = response.json()

            if result.get("success"):
                task_result = result.get("result", {})
                if "media" in task_result:
                    return task_result["media"], None

            print(f"Polling... {attempt+1}/60")

        return None, "Timeout"

    def download_images(self, media_list, output_dir):
        """Download images from media list."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        downloaded = []
        for i, media in enumerate(media_list):
            image = media.get("image", {}).get("generatedImage", {})
            url = image.get("fifeUrl")

            if url:
                response = requests.get(url)
                filename = f"generated_{i+1}.png"
                filepath = output_path / filename

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                downloaded.append({
                    "file": str(filepath),
                    "media_name": media.get("name"),
                    "seed": image.get("seed")
                })
                print(f"Downloaded: {filename}")

        return downloaded


# Usage
if __name__ == "__main__":
    generator = FlowImageGenerator(
        chrome_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        profile_path="chrome_profiles/main",
        proxy_token="YOUR_PROXY_TOKEN"
    )

    # Step 1: Open Chrome
    generator.open_chrome()

    # Step 2: Extract token (manual)
    generator.extract_token_manual()

    # Step 3: Generate images
    prompt = "a majestic lion in the savanna at golden hour, cinematic lighting"
    media, error = generator.generate_image(prompt, count=2)

    if error:
        print(f"Error: {error}")
    else:
        # Step 4: Download
        results = generator.download_images(media, "output/images")
        print(f"Downloaded {len(results)} images")
```

---

## 8. Automation với Selenium (Optional)

### 8.1 Setup
```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.add_argument(f"--user-data-dir={profile_dir}")
options.add_argument("--remote-debugging-port=9222")

driver = webdriver.Chrome(options=options)
driver.get("https://labs.google/fx/vi/tools/flow")
```

### 8.2 Inject Script
```python
capture_script = """
window._tk=null;window._pj=null;
(function(){
    var f=window.fetch;
    window.fetch=function(u,o){
        var s=u?u.toString():'';
        if(s.includes('flowMedia')||s.includes('aisandbox')){
            var h=o&&o.headers?o.headers:{};
            var a=h.Authorization||h.authorization||'';
            if(a.startsWith('Bearer ')){
                window._tk=a.substring(7);
                var m=s.match(/\\/projects\\/([^\\/]+)\\//);
                if(m)window._pj=m[1];
            }
        }
        return f.apply(this,arguments);
    };
})();
"""
driver.execute_script(capture_script)
```

### 8.3 Get Token
```python
result = driver.execute_script("return {token: window._tk, project: window._pj};")
bearer_token = result.get("token")
project_id = result.get("project")
```

---

## 9. Tips & Troubleshooting

### 9.1 Token hết hạn
- Token có hiệu lực khoảng 1 giờ
- Cache token và check trước khi dùng
- Nếu API trả về 401, cần lấy token mới

### 9.2 Rate Limit
- Không gọi API quá nhanh
- Delay 2-3 giây giữa các request
- Dùng proxy API để bypass một số limit

### 9.3 Captcha
- Direct API có thể yêu cầu captcha
- Proxy API (`nanoai.pics`) giúp bypass
- Cần có `proxy_api_token` riêng

### 9.4 Reference Images
- `media_name` chỉ valid trong cùng project
- Lưu `media_name` khi tạo ảnh để dùng sau
- Format: `projects/{project_id}/media/{media_id}`

---

## 10. Constants Reference

```python
# Aspect Ratios
IMAGE_ASPECT_RATIO_LANDSCAPE = "IMAGE_ASPECT_RATIO_LANDSCAPE"  # 16:9
IMAGE_ASPECT_RATIO_PORTRAIT = "IMAGE_ASPECT_RATIO_PORTRAIT"    # 9:16
IMAGE_ASPECT_RATIO_SQUARE = "IMAGE_ASPECT_RATIO_SQUARE"        # 1:1

# Image Models
IMAGE_MODEL_GEM_PIX = "GEM_PIX"
IMAGE_MODEL_GEM_PIX_2 = "GEM_PIX_2"  # Recommended

# Tool name
TOOL_NAME = "PINHOLE"  # Internal name for Flow

# API URLs
DIRECT_API = "https://aisandbox-pa.googleapis.com/v1/projects/{project_id}/flowMedia:batchGenerateImages"
PROXY_IMAGE_API = "https://flow-api.nanoai.pics/api/fix/create-image-veo3"
PROXY_TASK_STATUS = "https://flow-api.nanoai.pics/api/fix/task-status"
```

---

## Summary

1. **Mở Chrome** với profile đã login Google
2. **Navigate** đến `https://labs.google/fx/vi/tools/flow`
3. **Inject capture script** để hook `fetch()`
4. **Click "Dự án mới"** -> **"Tạo hình ảnh"** -> **Enter prompt**
5. **Capture token** từ `window._tk`
6. **Gọi Proxy API** với token để tạo ảnh
7. **Poll task status** cho đến khi complete
8. **Download ảnh** từ `fifeUrl` trong response
