/**
 * Grok Video Debug Helper - Background Service Worker
 * Quản lý communication giữa content script và Python tool
 */

console.log('[Video Debug] Background service worker started');

// ========== STATE MANAGEMENT ==========
const globalState = {
  isConnected: false,
  lastVideoUrl: null,
  lastError: null,
  activeTabId: null,
  activeSource: null, // 'grok' or 'sora'
  logs: [],
  grokTabId: null,
  soraTabId: null,
};

function addLog(message, type = 'info') {
  const timestamp = new Date().toLocaleTimeString();
  globalState.logs.push({ timestamp, message, type });
  // Keep only last 100 logs
  if (globalState.logs.length > 100) {
    globalState.logs.shift();
  }
  console.log(`[${timestamp}] [${type}] ${message}`);
}

// ========== MESSAGE HANDLING FROM CONTENT SCRIPT ==========
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const tabId = sender.tab?.id;
  const source = message.source || 'grok'; // 'grok' or 'sora'

  switch (message.action) {
    case 'CONTENT_SCRIPT_READY':
      addLog(`[${source.toUpperCase()}] Content script ready: ${message.url}`, 'success');
      globalState.activeTabId = tabId;
      globalState.activeSource = source;
      globalState.isConnected = true;
      // Track tab by source
      if (source === 'sora') {
        globalState.soraTabId = tabId;
      } else {
        globalState.grokTabId = tabId;
      }
      break;

    case 'VIDEO_URL_FOUND':
      addLog(`[${source.toUpperCase()}] Video URL: ${message.url.substring(0, 50)}...`, 'success');
      globalState.lastVideoUrl = message.url;
      // Notify popup
      chrome.runtime.sendMessage({ action: 'VIDEO_READY', url: message.url, source });
      // Show notification
      showNotification(`${source.toUpperCase()} Video Ready!`, 'Video URL has been captured');
      break;

    case 'ERROR_DETECTED':
      addLog(`Error: ${message.error}`, 'error');
      globalState.lastError = message.error;
      showNotification('Error Detected', message.error);
      break;

    case 'CAPTCHA_DETECTED':
      addLog('CAPTCHA detected - manual intervention required', 'error');
      showNotification('CAPTCHA Alert!', 'Please solve the captcha manually');
      break;

    case 'STATUS_UPDATE':
      // Just update state, don't log every update
      if (message.status === 'ready' && !globalState.lastVideoUrl) {
        addLog('Video is ready for download', 'success');
      }
      break;

    default:
      // Forward to popup if open
      chrome.runtime.sendMessage(message);
  }

  sendResponse({ received: true });
  return true;
});

// ========== EXTERNAL COMMUNICATION ==========
// Cho phép Python tool giao tiếp qua Native Messaging hoặc WebSocket
// Hiện tại dùng chrome.storage để share state

chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local' && changes.toolCommand) {
    const command = changes.toolCommand.newValue;
    if (command) {
      handleToolCommand(command);
    }
  }
});

async function handleToolCommand(command) {
  addLog(`Tool command: ${command.action}`, 'info');

  if (!globalState.activeTabId) {
    addLog('No active Grok tab', 'error');
    return;
  }

  try {
    const response = await chrome.tabs.sendMessage(globalState.activeTabId, command);
    chrome.storage.local.set({
      toolResponse: {
        command: command.action,
        response,
        timestamp: Date.now(),
      },
    });
  } catch (error) {
    addLog(`Command error: ${error.message}`, 'error');
  }
}

// ========== NOTIFICATIONS ==========
function showNotification(title, message) {
  // Note: Requires notifications permission
  chrome.notifications?.create({
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title: `Grok Debug: ${title}`,
    message,
  });
}

// ========== TAB MONITORING ==========
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete') {
    if (tab.url?.includes('grok.com')) {
      addLog(`Grok tab updated: ${tab.url}`, 'info');
      globalState.grokTabId = tabId;
      globalState.activeTabId = tabId;
      globalState.activeSource = 'grok';
    } else if (tab.url?.includes('sora.chatgpt.com')) {
      addLog(`SORA tab updated: ${tab.url}`, 'info');
      globalState.soraTabId = tabId;
      globalState.activeTabId = tabId;
      globalState.activeSource = 'sora';
    }
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === globalState.grokTabId) {
    addLog('Grok tab closed', 'warning');
    globalState.grokTabId = null;
  }
  if (tabId === globalState.soraTabId) {
    addLog('SORA tab closed', 'warning');
    globalState.soraTabId = null;
  }
  if (tabId === globalState.activeTabId) {
    globalState.activeTabId = globalState.soraTabId || globalState.grokTabId || null;
    globalState.isConnected = globalState.activeTabId !== null;
  }
});

// ========== CONTEXT MENU ==========
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus?.create({
    id: 'grok-debug-menu',
    title: 'Grok Debug Helper',
    contexts: ['page'],
    documentUrlPatterns: ['https://grok.com/*'],
  });

  chrome.contextMenus?.create({
    id: 'grok-copy-video-url',
    parentId: 'grok-debug-menu',
    title: 'Copy Video URL',
    contexts: ['page'],
  });

  chrome.contextMenus?.create({
    id: 'grok-click-download',
    parentId: 'grok-debug-menu',
    title: 'Click Download Button',
    contexts: ['page'],
  });
});

chrome.contextMenus?.onClicked.addListener((info, tab) => {
  if (!tab?.id) return;

  switch (info.menuItemId) {
    case 'grok-copy-video-url':
      if (globalState.lastVideoUrl) {
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          func: (url) => navigator.clipboard.writeText(url),
          args: [globalState.lastVideoUrl],
        });
        addLog('Video URL copied to clipboard', 'success');
      }
      break;

    case 'grok-click-download':
      chrome.tabs.sendMessage(tab.id, { action: 'CLICK_DOWNLOAD' });
      break;
  }
});

// ========== EXPOSE STATE TO POPUP ==========
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'GET_GLOBAL_STATE') {
    sendResponse(globalState);
    return true;
  }

  if (message.action === 'GET_LOGS') {
    sendResponse({ logs: globalState.logs });
    return true;
  }

  if (message.action === 'SEND_TO_TAB') {
    if (globalState.activeTabId) {
      chrome.tabs.sendMessage(globalState.activeTabId, message.command)
        .then(sendResponse)
        .catch((error) => sendResponse({ error: error.message }));
      return true;
    }
    sendResponse({ error: 'No active tab' });
  }
});
