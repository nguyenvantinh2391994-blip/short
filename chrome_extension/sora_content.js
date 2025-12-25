/**
 * SORA Video Debug Helper - Content Script
 * CHI lam: Inject script + Monitoring
 * Cac function thao tac DOM nam trong sora_inject.js
 */

console.log('[SORA Debug] Content script loaded');

// ========== INJECT HELPER INTO PAGE CONTEXT ==========
function injectScript() {
  if (window._soraInjectLoaded) return;
  window._soraInjectLoaded = true;

  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('sora_inject.js');
  script.onload = () => {
    script.remove();
    console.log('[SORA Debug] Inject script loaded');
  };
  (document.head || document.documentElement).appendChild(script);
}

// Inject ngay khi load
injectScript();

// ========== STATE ==========
const state = {
  videoUrl: null,
  videoReady: false,
  lastError: null,
};

// ========== UTILITIES ==========
function log(msg, type = 'info') {
  const prefix = '[SORA Debug]';
  console.log(`%c${prefix} ${msg}`, type === 'success' ? 'color: #2ecc71' :
    type === 'error' ? 'color: #e74c3c' : 'color: #3498db');
}

function sendToBackground(action, data = {}) {
  chrome.runtime.sendMessage({ action, source: 'sora', ...data });
}

// ========== VIDEO URL MONITORING ==========
function checkForVideo() {
  const videos = document.querySelectorAll('video');
  for (const v of videos) {
    const src = v.src || v.currentSrc || '';
    if (src.includes('videos.openai.com') && src !== state.videoUrl) {
      state.videoUrl = src;
      state.videoReady = true;
      log(`Video found: ${src.substring(0, 60)}...`, 'success');
      sendToBackground('VIDEO_URL_FOUND', { url: src });
      return src;
    }
  }
  return null;
}

// ========== MESSAGE HANDLER ==========
// Chuyen tat ca requests den page context qua postMessage
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  log(`Message: ${request.action}`);

  // Cac action don gian xu ly trong content script
  if (request.action === 'GET_VIDEO_URL') {
    const url = checkForVideo();
    sendResponse({ url: url || state.videoUrl, ready: state.videoReady });
    return true;
  }

  if (request.action === 'RESET_STATE') {
    state.videoUrl = null;
    state.videoReady = false;
    state.lastError = null;
    sendResponse({ success: true });
    return true;
  }

  // Cac action khac: forward den SORA_HELPER trong page context
  // Su dung window.postMessage de giao tiep voi inject script
  const messageId = Date.now();

  window.postMessage({
    type: 'SORA_CONTENT_TO_INJECT',
    id: messageId,
    action: request.action,
    data: request
  }, '*');

  // Listen for response
  const handler = (event) => {
    if (event.data?.type === 'SORA_INJECT_TO_CONTENT' && event.data?.id === messageId) {
      window.removeEventListener('message', handler);
      sendResponse(event.data.result);
    }
  };
  window.addEventListener('message', handler);

  // Timeout after 5s
  setTimeout(() => {
    window.removeEventListener('message', handler);
  }, 5000);

  return true; // Keep channel open
});

// ========== AUTO MONITORING ==========
let monitorInterval = null;

function startMonitoring() {
  if (monitorInterval) return;

  monitorInterval = setInterval(() => {
    checkForVideo();
  }, 3000); // Check every 3s

  log('Monitoring started', 'success');
}

// ========== INITIALIZATION ==========
function init() {
  injectScript();
  startMonitoring();

  sendToBackground('CONTENT_SCRIPT_READY', {
    pageType: 'sora',
    url: window.location.href,
  });

  log('Ready', 'success');
}

// Run
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Re-init on URL change
let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    log('URL changed');
    setTimeout(init, 1000);
  }
}).observe(document, { subtree: true, childList: true });
