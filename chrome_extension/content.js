/**
 * Grok Video Debug Helper - Content Script
 * Chạy trên trang grok.com để hỗ trợ automation
 */

console.log('[Grok Debug] Content script loaded');

// ========== STATE ==========
const state = {
  videoUrl: null,
  videoReady: false,
  isProcessing: false,
  progress: 0,
  lastError: null,
  pageType: 'unknown', // 'imagine', 'post', 'other'
};

// ========== UTILITIES ==========
function log(msg, type = 'info') {
  const prefix = '[Grok Debug]';
  const styles = {
    info: 'color: #3498db',
    success: 'color: #2ecc71',
    error: 'color: #e74c3c',
    warning: 'color: #f39c12',
  };
  console.log(`%c${prefix} ${msg}`, styles[type] || styles.info);
}

function sendToBackground(action, data = {}) {
  chrome.runtime.sendMessage({ action, ...data });
}

function saveState() {
  chrome.storage.local.set({ grokState: state });
}

// ========== PAGE DETECTION ==========
function detectPageType() {
  const url = window.location.href;
  if (url.includes('/imagine/post/')) {
    state.pageType = 'post';
  } else if (url.includes('/imagine')) {
    state.pageType = 'imagine';
  } else {
    state.pageType = 'other';
  }
  log(`Page type: ${state.pageType}`);
  return state.pageType;
}

// ========== VIDEO URL CAPTURE ==========
function installFetchHook() {
  if (window._grokDebugHookInstalled) return;
  window._grokDebugHookInstalled = true;

  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const response = await originalFetch.apply(this, args);

    try {
      const clonedResponse = response.clone();
      const text = await clonedResponse.text();

      // Tìm video URL trong response
      const patterns = [
        /https:\/\/assets\.grok\.com\/[^"'\s]+\.mp4[^"'\s]*/gi,
        /"url":\s*"([^"]+\.mp4[^"]*)"/gi,
        /"videoUrl":\s*"([^"]+)"/gi,
      ];

      for (const pattern of patterns) {
        const matches = [...text.matchAll(pattern)];
        for (const match of matches) {
          const videoUrl = (match[1] || match[0]).replace(/["\s]/g, '');
          if (videoUrl && videoUrl.includes('.mp4')) {
            log(`Video URL captured: ${videoUrl.substring(0, 50)}...`, 'success');
            state.videoUrl = videoUrl;
            state.videoReady = true;
            saveState();
            sendToBackground('VIDEO_URL_FOUND', { url: videoUrl });
          }
        }
      }
    } catch (e) {
      // Ignore errors
    }

    return response;
  };

  log('Fetch hook installed', 'success');
}

// ========== UI MONITORING ==========
function checkProgress() {
  // Check progress percentage (0% - 100%)
  const progressDiv = document.querySelector('div.tabular-nums');
  if (progressDiv) {
    const text = progressDiv.textContent || '';
    if (text.includes('%')) {
      const match = text.match(/(\d+)%/);
      if (match) {
        state.progress = parseInt(match[1]);
        state.isProcessing = true;
        log(`Progress: ${state.progress}%`);
        return { status: 'processing', progress: state.progress };
      }
    }
  }

  // Check film icon (video done)
  const filmIcon = document.querySelector('svg.lucide-film');
  if (filmIcon) {
    state.videoReady = true;
    state.isProcessing = false;
    log('Film icon found - Video ready!', 'success');
    return { status: 'ready' };
  }

  // Check download button
  const downloadBtn = document.querySelector('button[aria-label="Tải xuống"], button[aria-label="Download"]');
  if (downloadBtn) {
    state.videoReady = true;
    return { status: 'ready' };
  }

  // Check video element
  const video = document.querySelector('#sd-video, video');
  if (video && video.src && video.src.includes('.mp4')) {
    state.videoUrl = video.src;
    state.videoReady = true;
    log(`Video src found: ${video.src.substring(0, 50)}...`, 'success');
    return { status: 'ready', url: video.src };
  }

  return { status: 'waiting' };
}

function checkForErrors() {
  // Check for error messages
  const errorSelectors = [
    '.error-message',
    '[class*="error"]',
    '.toast-error',
  ];

  for (const selector of errorSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent) {
      const errorText = el.textContent.trim();
      if (errorText.length > 0 && errorText.length < 200) {
        state.lastError = errorText;
        log(`Error detected: ${errorText}`, 'error');
        sendToBackground('ERROR_DETECTED', { error: errorText });
        return errorText;
      }
    }
  }

  // Check for captcha
  const captchaSelectors = [
    'iframe[src*="captcha"]',
    'iframe[src*="challenge"]',
    '[class*="captcha"]',
  ];

  for (const selector of captchaSelectors) {
    if (document.querySelector(selector)) {
      log('CAPTCHA detected!', 'error');
      sendToBackground('CAPTCHA_DETECTED', {});
      return 'CAPTCHA';
    }
  }

  return null;
}

// ========== ELEMENT HELPERS ==========
function findElement(selector) {
  const el = document.querySelector(selector);
  return el ? { found: true, rect: el.getBoundingClientRect() } : { found: false };
}

function clickElement(selector) {
  const el = document.querySelector(selector);
  if (el) {
    el.click();
    log(`Clicked: ${selector}`, 'success');
    return true;
  }
  log(`Not found: ${selector}`, 'warning');
  return false;
}

function clickDownloadButton() {
  // Try multiple selectors
  const selectors = [
    'button[aria-label="Tải xuống"]',
    'button[aria-label="Download"]',
    'svg.lucide-download',
  ];

  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el) {
      const btn = el.closest('button') || el;
      btn.click();
      log('Download button clicked!', 'success');
      return true;
    }
  }

  log('Download button not found', 'warning');
  return false;
}

function clickAttachButton() {
  const buttons = document.querySelectorAll('button');
  for (const btn of buttons) {
    const label = btn.getAttribute('aria-label') || '';
    if (label.includes('Đính kèm') || label.includes('Attach')) {
      btn.click();
      log('Attach button clicked!', 'success');
      return true;
    }
  }
  return false;
}

function clickUploadMenu() {
  const items = document.querySelectorAll('div[role="menuitem"]');
  for (const item of items) {
    const text = item.textContent || '';
    if (text.includes('Tải lên') || text.includes('Upload')) {
      item.click();
      log('Upload menu clicked!', 'success');
      return true;
    }
  }
  return false;
}

function inputPrompt(text) {
  const selectors = [
    '.ProseMirror',
    'div[contenteditable="true"]',
    'p[data-placeholder]',
  ];

  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (el) {
      el.focus();
      el.innerHTML = `<p>${text}</p>`;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      log(`Prompt entered: ${text.substring(0, 30)}...`, 'success');
      return true;
    }
  }
  return false;
}

// ========== MESSAGE HANDLER ==========
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  log(`Received message: ${request.action}`);

  switch (request.action) {
    case 'GET_STATUS':
      const status = checkProgress();
      sendResponse({
        ...state,
        ...status,
        url: window.location.href,
      });
      break;

    case 'CHECK_ERRORS':
      const error = checkForErrors();
      sendResponse({ error });
      break;

    case 'CLICK_DOWNLOAD':
      const downloadResult = clickDownloadButton();
      sendResponse({ success: downloadResult });
      break;

    case 'CLICK_ATTACH':
      sendResponse({ success: clickAttachButton() });
      break;

    case 'CLICK_UPLOAD':
      sendResponse({ success: clickUploadMenu() });
      break;

    case 'INPUT_PROMPT':
      sendResponse({ success: inputPrompt(request.text) });
      break;

    case 'GET_VIDEO_URL':
      sendResponse({ url: state.videoUrl, ready: state.videoReady });
      break;

    case 'FIND_ELEMENT':
      sendResponse(findElement(request.selector));
      break;

    case 'CLICK_ELEMENT':
      sendResponse({ success: clickElement(request.selector) });
      break;

    case 'RESET_STATE':
      state.videoUrl = null;
      state.videoReady = false;
      state.isProcessing = false;
      state.progress = 0;
      state.lastError = null;
      saveState();
      sendResponse({ success: true });
      break;

    default:
      sendResponse({ error: 'Unknown action' });
  }

  return true; // Keep channel open for async response
});

// ========== AUTO MONITORING ==========
let monitorInterval = null;

function startMonitoring() {
  if (monitorInterval) return;

  monitorInterval = setInterval(() => {
    const status = checkProgress();
    checkForErrors();

    // Send status to background
    sendToBackground('STATUS_UPDATE', {
      ...state,
      ...status,
      url: window.location.href,
    });
  }, 2000); // Check every 2 seconds

  log('Monitoring started', 'success');
}

function stopMonitoring() {
  if (monitorInterval) {
    clearInterval(monitorInterval);
    monitorInterval = null;
    log('Monitoring stopped');
  }
}

// ========== INITIALIZATION ==========
function init() {
  detectPageType();
  installFetchHook();

  // Start monitoring on imagine/post pages
  if (state.pageType === 'post' || state.pageType === 'imagine') {
    startMonitoring();
  }

  // Notify background that content script is ready
  sendToBackground('CONTENT_SCRIPT_READY', {
    pageType: state.pageType,
    url: window.location.href,
  });

  log('Initialization complete', 'success');
}

// Run on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Re-init on URL change (SPA navigation)
let lastUrl = location.href;
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    log('URL changed, re-initializing...');
    stopMonitoring();
    setTimeout(init, 1000);
  }
}).observe(document, { subtree: true, childList: true });
