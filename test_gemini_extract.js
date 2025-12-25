// ========== GEMINI PRODUCT EXTRACTION - CONSOLE TEST ==========
// Chạy code này trong Console của trang https://gemini.google.com/app

const EXTRACT_PROMPT = `IMAGE EDITING TASK — OBJECT EXTRACTION

This is an IMAGE EDITING task.
You must PROCESS the input image and RETURN a NEW IMAGE as output.

Task description:
Extract (cut out) the MAIN PRODUCT from the image.

Definition of the product:
- The product is the CLOTHING ONLY.
- Any human, child, model, body part, face, skin, hair, or watermark
  is NOT part of the product and must be completely removed.

Editing instructions:
- Remove the entire background
- Remove all people and body parts
- Remove all text, logos, and watermarks
- Keep ONLY the clothing item itself
- Preserve realistic fabric shape and folds
- Do NOT flatten the clothing
- Do NOT stylize or redesign

Output requirements:
- Output must be an IMAGE
- ONE clothing item only
- Pure white background (#FFFFFF)
- No shadows, no reflections
- No text in the output

Final rule:
You must return ONLY the edited image.
Do NOT return any text, explanation, or description.`;

// 1. Nhập prompt vào textarea
function typePrompt(text) {
    const editor = document.querySelector('.ql-editor');
    if (!editor) {
        console.error('Không tìm thấy textarea');
        return false;
    }

    // Focus và nhập text
    editor.focus();
    editor.innerHTML = `<p>${text}</p>`;

    // Trigger input event
    editor.dispatchEvent(new Event('input', { bubbles: true }));

    console.log('✓ Đã nhập prompt');
    return true;
}

// 2. Click nút upload
function clickUploadButton() {
    const uploadBtn = document.querySelector('button.upload-card-button');
    if (!uploadBtn) {
        console.error('Không tìm thấy nút upload');
        return false;
    }

    uploadBtn.click();
    console.log('✓ Đã click nút upload');
    return true;
}

// 3. Kiểm tra đang chạy (có icon stop)
function isGenerating() {
    const stopIcon = document.querySelector('mat-icon[fonticon="stop"]');
    return !!stopIcon;
}

// 4. Kiểm tra đã xong (có icon mic)
function isComplete() {
    const micIcon = document.querySelector('.text-input-field mat-icon[fonticon="mic"]');
    return !!micIcon && !isGenerating();
}

// 5. Lấy URL ảnh đã tạo
function getGeneratedImages() {
    const images = document.querySelectorAll('generated-image img.image');
    const urls = [];

    images.forEach(img => {
        if (img.src && img.src.includes('googleusercontent.com')) {
            urls.push(img.src);
        }
    });

    console.log(`📷 Tìm thấy ${urls.length} ảnh được tạo`);
    return urls;
}

// 6. Click nút gửi (Enter)
function clickSendButton() {
    const sendBtn = document.querySelector('button.send-button');
    if (sendBtn) {
        sendBtn.click();
        console.log('✓ Đã click nút gửi');
        return true;
    }

    // Hoặc nhấn Enter
    const editor = document.querySelector('.ql-editor');
    if (editor) {
        editor.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            keyCode: 13,
            which: 13,
            bubbles: true
        }));
        console.log('✓ Đã nhấn Enter');
        return true;
    }

    return false;
}

// 7. Đợi ảnh tạo xong
async function waitForGeneration(timeout = 120000) {
    console.log('⏳ Đang chờ ảnh được tạo...');
    const start = Date.now();

    while (Date.now() - start < timeout) {
        if (isGenerating()) {
            console.log('   🔄 Đang tạo ảnh...');
        }

        if (isComplete()) {
            console.log('✓ Đã hoàn thành!');
            return true;
        }

        await new Promise(r => setTimeout(r, 2000));
    }

    console.error('⏰ Timeout!');
    return false;
}

// 8. Download ảnh
function downloadImage(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    console.log(`✓ Download: ${filename}`);
}

// ========== CHẠY TEST ==========

// Test 1: Nhập prompt
// typePrompt(EXTRACT_PROMPT);

// Test 2: Click upload (sau đó chọn file thủ công)
// clickUploadButton();

// Test 3: Gửi prompt
// clickSendButton();

// Test 4: Đợi và lấy ảnh
// await waitForGeneration();
// const images = getGeneratedImages();
// images.forEach((url, i) => console.log(`Ảnh ${i+1}: ${url}`));

// ========== FULL FLOW (chạy sau khi đã upload ảnh) ==========
async function runExtraction() {
    // Bước 1: Nhập prompt
    if (!typePrompt(EXTRACT_PROMPT)) return;
    await new Promise(r => setTimeout(r, 500));

    // Bước 2: Click upload
    clickUploadButton();
    console.log('📁 Vui lòng chọn ảnh để upload...');
    console.log('   Sau khi chọn xong, chạy: continueAfterUpload()');
}

async function continueAfterUpload() {
    // Đợi 1s sau khi upload
    await new Promise(r => setTimeout(r, 1000));

    // Bước 3: Gửi prompt
    clickSendButton();

    // Bước 4: Đợi tạo ảnh
    const success = await waitForGeneration();

    if (success) {
        // Bước 5: Lấy ảnh
        const images = getGeneratedImages();
        console.log('\n📷 Ảnh đã tạo:');
        images.forEach((url, i) => {
            console.log(`${i+1}. ${url}`);
        });

        return images;
    }

    return [];
}

// ========== HƯỚNG DẪN ==========
console.log(`
========== GEMINI PRODUCT EXTRACTION TEST ==========

Cách test:

1. Chạy: runExtraction()
   → Sẽ nhập prompt và mở dialog upload

2. Chọn ảnh cần tách sản phẩm (có thể chọn nhiều ảnh)

3. Chạy: continueAfterUpload()
   → Sẽ gửi prompt và đợi ảnh được tạo

4. Xem kết quả trong console

Các hàm riêng lẻ:
- typePrompt(text)      : Nhập prompt
- clickUploadButton()   : Mở dialog upload
- clickSendButton()     : Gửi prompt
- isGenerating()        : Check đang tạo ảnh
- isComplete()          : Check đã xong
- getGeneratedImages()  : Lấy URL ảnh đã tạo
- waitForGeneration()   : Đợi tạo xong

====================================================
`);
