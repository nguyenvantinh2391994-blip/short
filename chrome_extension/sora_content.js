/**
 * SORA Video Debug Helper - Content Script
 * Chay tren trang sora.chatgpt.com de ho tro automation
 */

console.log('[SORA Debug] Content script loaded');

// ========== STATE ==========
const state = {
  videoUrl: null,
  videoReady: false,
  isProcessing: false,
  progress: 0,
  lastError: null,
  pageType: 'sora',
};

// ========== UTILITIES ==========
function log(msg, type = 'info') {
  const prefix = '[SORA Debug]';
  const styles = {
    info: 'color: #3498db',
    success: 'color: #2ecc71',
    error: 'color: #e74c3c',
    warning: 'color: #f39c12',
  };
  console.log(`%c${prefix} ${msg}`, styles[type] || styles.info);
}

function sendToBackground(action, data = {}) {
  chrome.runtime.sendMessage({ action, source: 'sora', ...data });
}

function saveState() {
  chrome.storage.local.set({ soraState: state });
}

// ========== VIDEO URL CAPTURE ==========
function installFetchHook() {
  if (window._soraDebugHookInstalled) return;
  window._soraDebugHookInstalled = true;

  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const response = await originalFetch.apply(this, args);

    try {
      const clonedResponse = response.clone();
      const text = await clonedResponse.text();

      // Tim video URL trong response (SORA dung videos.openai.com)
      const patterns = [
        /https:\/\/videos\.openai\.com\/[^"'\s]+/gi,
        /"url":\s*"([^"]+videos\.openai\.com[^"]*)"/gi,
        /"videoUrl":\s*"([^"]+)"/gi,
      ];

      for (const pattern of patterns) {
        const matches = [...text.matchAll(pattern)];
        for (const match of matches) {
          const videoUrl = (match[1] || match[0]).replace(/["\s]/g, '');
          if (videoUrl && videoUrl.includes('videos.openai.com')) {
            log(`Video URL captured: ${videoUrl.substring(0, 60)}...`, 'success');
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
  // Check video element
  const videos = document.querySelectorAll('video');
  for (const v of videos) {
    const src = v.src || v.currentSrc || '';
    if (src.includes('videos.openai.com')) {
      state.videoUrl = src;
      state.videoReady = true;
      log(`Video src found: ${src.substring(0, 60)}...`, 'success');
      return { status: 'done', url: src };
    }
  }

  // Check loading spinner
  const spinners = document.querySelectorAll('[class*="animate-spin"]');
  for (const s of spinners) {
    if (s.offsetParent !== null) {
      state.isProcessing = true;
      return { status: 'loading' };
    }
  }

  return { status: 'waiting' };
}

function checkForErrors() {
  // Check for error messages
  const errorSelectors = [
    '.error-message',
    '[class*="error"]',
    '[role="alert"]',
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

  return null;
}

// ========== ELEMENT HELPERS ==========
function findTextarea() {
  // Tim textarea prompt cua SORA
  const selectors = [
    'textarea[placeholder*="Describe"]',
    'textarea[placeholder*="describe"]',
    'textarea',
  ];

  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el) return el;
  }
  return null;
}

function clickTextarea() {
  const ta = findTextarea();
  if (ta) {
    ta.focus();
    ta.click();
    log('Clicked textarea', 'success');
    return true;
  }
  log('Textarea not found', 'warning');
  return false;
}

function inputPrompt(text) {
  const ta = findTextarea();
  if (ta) {
    ta.focus();
    ta.value = text;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
    log(`Prompt entered: ${text.substring(0, 30)}...`, 'success');
    return true;
  }
  return false;
}

function clickUploadButton() {
  // Tim nut upload (+) bang SVG path
  const btns = document.querySelectorAll('button');
  for (const b of btns) {
    const svg = b.querySelector('svg');
    if (svg) {
      const paths = svg.querySelectorAll('path');
      for (const p of paths) {
        const d = p.getAttribute('d') || '';
        // Plus icon path
        if (d.includes('M12 6') || d.includes('M12 5')) {
          b.click();
          log('Upload button clicked!', 'success');
          return true;
        }
      }
    }
  }

  // Fallback: tim theo aria-label
  const uploadBtn = document.querySelector('button[aria-label*="upload" i], button[aria-label*="attach" i]');
  if (uploadBtn) {
    uploadBtn.click();
    log('Upload button clicked (aria-label)!', 'success');
    return true;
  }

  log('Upload button not found', 'warning');
  return false;
}

function pressEnter() {
  // Gui Enter de submit
  const ta = findTextarea();
  if (ta) {
    ta.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter',
      code: 'Enter',
      keyCode: 13,
      which: 13,
      bubbles: true,
    }));
    log('Enter pressed', 'success');
    return true;
  }
  return false;
}

function getVideoUrl() {
  const videos = document.querySelectorAll('video');
  for (const v of videos) {
    const src = v.src || v.currentSrc || '';
    if (src.includes('videos.openai.com')) {
      return src;
    }
  }
  return state.videoUrl || null;
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
        source: 'sora',
      });
      break;

    case 'CHECK_ERRORS':
      const error = checkForErrors();
      sendResponse({ error });
      break;

    case 'CLICK_TEXTAREA':
      sendResponse({ success: clickTextarea() });
      break;

    case 'INPUT_PROMPT':
      sendResponse({ success: inputPrompt(request.text) });
      break;

    case 'CLICK_UPLOAD':
      sendResponse({ success: clickUploadButton() });
      break;

    case 'PRESS_ENTER':
      sendResponse({ success: pressEnter() });
      break;

    case 'GET_VIDEO_URL':
      sendResponse({ url: getVideoUrl(), ready: state.videoReady });
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

  return true;
});

// ========== AUTO MONITORING ==========
let monitorInterval = null;

function startMonitoring() {
  if (monitorInterval) return;

  monitorInterval = setInterval(() => {
    const status = checkProgress();
    checkForErrors();

    sendToBackground('STATUS_UPDATE', {
      ...state,
      ...status,
      url: window.location.href,
      source: 'sora',
    });
  }, 2000);

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
  installFetchHook();
  startMonitoring();

  sendToBackground('CONTENT_SCRIPT_READY', {
    pageType: 'sora',
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

// ========== EXPOSE TO WINDOW FOR PYTHON TOOL ==========
// Python co the chay JS: window.SORA_HELPER.clickUpload()
window.SORA_HELPER = {
  clickTextarea,
  inputPrompt,
  clickUploadButton,
  pressEnter,
  getVideoUrl,
  getStatus: checkProgress,
  getState: () => state,
};

log('SORA_HELPER exposed to window', 'success');
