/**
 * Grok Debug Helper - Popup Script
 */

// DOM Elements
const elements = {
  connectionStatus: document.getElementById('connectionStatus'),
  pageType: document.getElementById('pageType'),
  videoStatus: document.getElementById('videoStatus'),
  progressText: document.getElementById('progressText'),
  progressFill: document.getElementById('progressFill'),
  videoUrl: document.getElementById('videoUrl'),
  logsContainer: document.getElementById('logsContainer'),
  btnDownload: document.getElementById('btnDownload'),
  btnCopyUrl: document.getElementById('btnCopyUrl'),
  btnRefresh: document.getElementById('btnRefresh'),
  btnReset: document.getElementById('btnReset'),
};

// State
let currentVideoUrl = null;

// ========== UTILITIES ==========
function updateConnectionStatus(connected) {
  if (connected) {
    elements.connectionStatus.textContent = 'Connected';
    elements.connectionStatus.className = 'status-badge status-connected';
  } else {
    elements.connectionStatus.textContent = 'Disconnected';
    elements.connectionStatus.className = 'status-badge status-disconnected';
  }
}

function updateVideoStatus(status, progress = 0) {
  const statusMap = {
    waiting: { text: 'Waiting...', class: 'warning' },
    processing: { text: `Processing ${progress}%`, class: 'warning' },
    ready: { text: 'Ready!', class: 'success' },
    error: { text: 'Error', class: 'error' },
  };

  const info = statusMap[status] || statusMap.waiting;
  elements.videoStatus.textContent = info.text;
  elements.videoStatus.className = `info-value ${info.class}`;
  elements.progressText.textContent = `${progress}%`;
  elements.progressFill.style.width = `${progress}%`;
}

function updateVideoUrl(url) {
  currentVideoUrl = url;
  if (url) {
    elements.videoUrl.textContent = url;
    elements.videoUrl.style.color = '#2ecc71';
    elements.btnCopyUrl.disabled = false;
    elements.btnDownload.disabled = false;
  } else {
    elements.videoUrl.textContent = 'No video URL captured yet';
    elements.videoUrl.style.color = '#888';
    elements.btnCopyUrl.disabled = true;
  }
}

function addLog(message, type = 'info') {
  const entry = document.createElement('div');
  entry.className = 'log-entry';

  const time = new Date().toLocaleTimeString();
  entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-${type}">${message}</span>`;

  elements.logsContainer.insertBefore(entry, elements.logsContainer.firstChild);

  // Keep only last 20 logs
  while (elements.logsContainer.children.length > 20) {
    elements.logsContainer.removeChild(elements.logsContainer.lastChild);
  }
}

// ========== TAB COMMUNICATION ==========
async function sendToActiveTab(command) {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url?.includes('grok.com')) {
      return await chrome.tabs.sendMessage(tab.id, command);
    }
    return null;
  } catch (error) {
    addLog(`Error: ${error.message}`, 'error');
    return null;
  }
}

async function refreshStatus() {
  const response = await sendToActiveTab({ action: 'GET_STATUS' });

  if (response) {
    updateConnectionStatus(true);
    elements.pageType.textContent = response.pageType || 'Unknown';

    if (response.videoReady || response.status === 'ready') {
      updateVideoStatus('ready', 100);
    } else if (response.isProcessing || response.status === 'processing') {
      updateVideoStatus('processing', response.progress || 0);
    } else {
      updateVideoStatus('waiting', 0);
    }

    if (response.videoUrl || response.url) {
      updateVideoUrl(response.videoUrl || response.url);
    }
  } else {
    updateConnectionStatus(false);
  }
}

// ========== BUTTON HANDLERS ==========
elements.btnDownload.addEventListener('click', async () => {
  addLog('Clicking download button...', 'info');
  const response = await sendToActiveTab({ action: 'CLICK_DOWNLOAD' });
  if (response?.success) {
    addLog('Download initiated!', 'success');
  } else {
    addLog('Download button not found', 'error');
  }
});

elements.btnCopyUrl.addEventListener('click', async () => {
  if (currentVideoUrl) {
    await navigator.clipboard.writeText(currentVideoUrl);
    addLog('URL copied to clipboard!', 'success');
    elements.btnCopyUrl.textContent = 'Copied!';
    setTimeout(() => {
      elements.btnCopyUrl.textContent = 'Copy URL';
    }, 1500);
  }
});

elements.btnRefresh.addEventListener('click', () => {
  addLog('Refreshing status...', 'info');
  refreshStatus();
});

elements.btnReset.addEventListener('click', async () => {
  addLog('Resetting state...', 'info');
  await sendToActiveTab({ action: 'RESET_STATE' });
  updateVideoUrl(null);
  updateVideoStatus('waiting', 0);
  addLog('State reset complete', 'success');
});

// ========== LOAD LOGS FROM BACKGROUND ==========
async function loadLogs() {
  chrome.runtime.sendMessage({ action: 'GET_LOGS' }, (response) => {
    if (response?.logs) {
      elements.logsContainer.innerHTML = '';
      response.logs.slice(-10).reverse().forEach((log) => {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `<span class="log-time">[${log.timestamp}]</span> <span class="log-${log.type}">${log.message}</span>`;
        elements.logsContainer.appendChild(entry);
      });
    }
  });
}

// ========== MESSAGE LISTENER ==========
chrome.runtime.onMessage.addListener((message) => {
  switch (message.action) {
    case 'VIDEO_READY':
      updateVideoUrl(message.url);
      updateVideoStatus('ready', 100);
      addLog('Video URL captured!', 'success');
      break;

    case 'STATUS_UPDATE':
      if (message.status === 'processing') {
        updateVideoStatus('processing', message.progress);
      } else if (message.status === 'ready') {
        updateVideoStatus('ready', 100);
      }
      break;

    case 'ERROR_DETECTED':
      addLog(`Error: ${message.error}`, 'error');
      break;
  }
});

// ========== INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', () => {
  loadLogs();
  refreshStatus();

  // Auto refresh every 2 seconds
  setInterval(refreshStatus, 2000);
});
