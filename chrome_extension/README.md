# Grok Video Debug Helper - Chrome Extension

Extension ho tro debug va automation cho Video Creator Tool.

## Tinh nang

1. **Tu dong bat Video URL** - Hook vao fetch API de bat URL video khi Grok tra ve
2. **Theo doi trang thai** - Check progress (0-100%), trang thai video
3. **Phat hien loi** - Detect error messages, CAPTCHA
4. **Quick Actions** - Click download, copy URL tu popup
5. **Logs** - Xem log realtime

## Cai dat

### Cach 1: Load Unpacked (Development)

1. Mo Chrome, vao `chrome://extensions/`
2. Bat **Developer mode** (goc tren phai)
3. Click **Load unpacked**
4. Chon thu muc `chrome_extension`
5. Extension se xuat hien trong danh sach

### Cach 2: Cai vao Profile cua Tool

Khi chay tool, Chrome se tu dong load extension neu ban:

1. Copy thu muc `chrome_extension` vao `C:\Users\{user}\AppData\Local\Google\Chrome\User Data\Default\Extensions\grok-debug`
2. Hoac su dung flag `--load-extension` khi khoi dong Chrome

## Su dung

### Trong Tool (Tu dong)

- Extension tu dong inject vao trang grok.com
- Bat moi video URL
- Gui thong bao khi co loi hoac CAPTCHA

### Thu cong (Popup)

1. Click icon extension
2. Xem trang thai: Connected, Video Status, Progress
3. Su dung Quick Actions:
   - **Download**: Click nut download tren trang
   - **Copy URL**: Copy video URL da bat duoc
   - **Refresh**: Lam moi trang thai
   - **Reset**: Reset state

## API cho Python Tool

Extension luu state vao `chrome.storage.local`:

```javascript
// Gui lenh tu Python (qua Selenium)
chrome.storage.local.set({
  toolCommand: {
    action: 'CLICK_DOWNLOAD',
    // hoac: 'GET_STATUS', 'CLICK_ATTACH', 'INPUT_PROMPT', ...
  }
});

// Doc ket qua
chrome.storage.local.get('toolResponse', (data) => {
  console.log(data.toolResponse);
});
```

## Cac Action ho tro

| Action | Mo ta |
|--------|-------|
| GET_STATUS | Lay trang thai hien tai |
| CHECK_ERRORS | Kiem tra loi tren trang |
| CLICK_DOWNLOAD | Click nut download |
| CLICK_ATTACH | Click nut dinh kem |
| CLICK_UPLOAD | Click menu tai len |
| INPUT_PROMPT | Nhap prompt vao o text |
| GET_VIDEO_URL | Lay URL video da bat |
| RESET_STATE | Reset state |

## Luu y

- Extension chi hoat dong tren `grok.com`
- Can login Grok truoc khi su dung
- Neu thay CAPTCHA, can giai thu cong
