/**
 * SORA Inject Script - Chay trong page context
 * Expose SORA_HELPER ra window de Python tool su dung
 * KHONG check visibility - hoat dong ca khi browser an/thu nho
 */

(function() {
  if (window.SORA_HELPER) {
    console.log('[SORA] Already loaded');
    return;
  }

  console.log('[SORA Inject] Loading...');

  // ========== STATE ==========
  const state = {
    videoUrl: null,
    videoReady: false,
  };

  // ========== UTILITIES ==========
  function log(msg, type = 'info') {
    const prefix = '[SORA]';
    const color = type === 'success' ? '#2ecc71' :
                  type === 'error' ? '#e74c3c' :
                  type === 'warning' ? '#f39c12' : '#3498db';
    console.log(`%c${prefix} ${msg}`, `color: ${color}; font-weight: bold`);
  }

  // ========== ELEMENT HELPERS ==========
  function findTextarea() {
    // Tim tat ca textarea, khong check visibility
    const selectors = [
      'textarea[placeholder*="Describe"]',
      'textarea[placeholder*="describe"]',
      'textarea[placeholder*="prompt"]',
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
      log('Focused textarea', 'success');
      return true;
    }
    log('Textarea not found', 'warning');
    return false;
  }

  // React-friendly way to set input value
  function setNativeValue(element, value) {
    const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set;
    const prototype = Object.getPrototypeOf(element);
    const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;

    if (valueSetter && valueSetter !== prototypeValueSetter) {
      prototypeValueSetter.call(element, value);
    } else if (valueSetter) {
      valueSetter.call(element, value);
    } else {
      element.value = value;
    }
  }

  function inputPrompt(text) {
    const ta = findTextarea();
    if (ta) {
      ta.focus();

      // Use native setter for React compatibility
      setNativeValue(ta, text);

      // Trigger React events
      ta.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
      ta.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));

      // Also try React's onChange handler
      const tracker = ta._valueTracker;
      if (tracker) {
        tracker.setValue('');
      }
      ta.dispatchEvent(new Event('input', { bubbles: true }));

      log(`Prompt set: ${text.substring(0, 40)}...`, 'success');
      return true;
    }
    log('Cannot input prompt - textarea not found', 'error');
    return false;
  }

  function clickUploadButton() {
    // Tim tat ca button, khong check visibility
    const btns = document.querySelectorAll('button');

    // Tim theo SVG path (plus icon) - M12 6a1 1 0 0 1 1 1v
    for (const b of btns) {
      const svg = b.querySelector('svg');
      if (svg) {
        const paths = svg.querySelectorAll('path');
        for (const p of paths) {
          const d = p.getAttribute('d') || '';
          // Plus icon patterns - SORA dùng "M12 6a1"
          if (d.startsWith('M12 6') || d.startsWith('M12 5') || d.startsWith('M12 4')) {
            b.click();
            log('Upload button clicked (SVG)!', 'success');
            return true;
          }
        }
      }
    }

    // Tim theo text "Attach media"
    for (const b of btns) {
      const text = b.textContent || '';
      if (text.toLowerCase().includes('attach')) {
        b.click();
        log('Upload button clicked (Attach)!', 'success');
        return true;
      }
    }

    // Tim theo aria-label
    const labels = ['upload', 'attach', 'add', 'plus', 'image'];
    for (const label of labels) {
      const btn = document.querySelector(`button[aria-label*="${label}" i]`);
      if (btn) {
        btn.click();
        log(`Upload button clicked (${label})!`, 'success');
        return true;
      }
    }

    log('Upload button not found', 'warning');
    return false;
  }

  function triggerFileInput() {
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      fileInput.click();
      log('File input triggered', 'success');
      return true;
    }
    log('File input not found', 'warning');
    return false;
  }

  function pressEnter() {
    const ta = findTextarea();
    if (ta) {
      ta.focus();

      // Method 1: KeyboardEvent
      const events = ['keydown', 'keypress', 'keyup'];
      for (const eventType of events) {
        ta.dispatchEvent(new KeyboardEvent(eventType, {
          key: 'Enter',
          code: 'Enter',
          keyCode: 13,
          which: 13,
          bubbles: true,
          cancelable: true,
        }));
      }

      log('Enter pressed', 'success');
      return true;
    }
    log('Cannot press Enter', 'error');
    return false;
  }

  function clickSubmitButton() {
    // Tim button submit
    const selectors = [
      'button[type="submit"]',
      'button[aria-label*="submit" i]',
      'button[aria-label*="generate" i]',
      'button[aria-label*="create" i]',
      'button[aria-label*="send" i]',
    ];

    for (const sel of selectors) {
      const btn = document.querySelector(sel);
      if (btn) {
        btn.click();
        log('Submit clicked', 'success');
        return true;
      }
    }

    // Tim theo SVG arrow/send icon
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const svg = b.querySelector('svg');
      if (svg) {
        const paths = svg.querySelectorAll('path');
        for (const p of paths) {
          const d = p.getAttribute('d') || '';
          if (d.includes('M5 12h14') || d.includes('M22 2') || d.includes('l7 7')) {
            b.click();
            log('Submit clicked (arrow)', 'success');
            return true;
          }
        }
      }
    }

    log('Submit button not found', 'warning');
    return false;
  }

  function getVideoUrl() {
    const videos = document.querySelectorAll('video');
    for (const v of videos) {
      const src = v.src || v.currentSrc || '';
      if (src.includes('videos.openai.com')) {
        state.videoUrl = src;
        state.videoReady = true;
        return src;
      }
    }
    return state.videoUrl || null;
  }

  function checkStatus() {
    const videoUrl = getVideoUrl();
    if (videoUrl) {
      return { status: 'done', videoUrl };
    }

    // Check loading - khong check offsetParent
    const loadingIndicators = document.querySelectorAll(
      '[class*="animate-spin"], [class*="loading"], [class*="spinner"], [role="progressbar"]'
    );
    if (loadingIndicators.length > 0) {
      return { status: 'loading' };
    }

    return { status: 'waiting' };
  }

  function waitForVideo(timeout = 300) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const check = () => {
        const status = checkStatus();
        if (status.status === 'done') {
          log(`Video ready!`, 'success');
          resolve(status);
          return;
        }

        if (Date.now() - startTime > timeout * 1000) {
          log('Timeout', 'error');
          resolve({ status: 'timeout' });
          return;
        }

        setTimeout(check, 2000);
      };
      check();
    });
  }

  // ========== EXPOSE TO WINDOW ==========
  window.SORA_HELPER = {
    clickTextarea,
    inputPrompt,
    clickUploadButton,
    triggerFileInput,
    pressEnter,
    clickSubmitButton,
    getVideoUrl,
    checkStatus,
    waitForVideo,
    getState: () => state,

    // Upload flow
    async startUpload() {
      log('Starting upload...');
      clickUploadButton();
      await new Promise(r => setTimeout(r, 500));
      return triggerFileInput();
    },

    // Tao video (khong co anh)
    async createVideo(prompt) {
      log(`Creating: ${prompt.substring(0, 30)}...`);

      clickTextarea();
      await new Promise(r => setTimeout(r, 300));

      inputPrompt(prompt);
      await new Promise(r => setTimeout(r, 500));

      pressEnter();

      return waitForVideo();
    },

    // Tao video voi anh
    async createVideoWithImage(prompt) {
      log(`With image: ${prompt.substring(0, 30)}...`);

      clickTextarea();
      await new Promise(r => setTimeout(r, 200));

      inputPrompt(prompt);
      await new Promise(r => setTimeout(r, 200));

      clickUploadButton();

      return { status: 'waiting_for_file' };
    },

    // Debug: list all buttons
    debugButtons() {
      const btns = document.querySelectorAll('button');
      btns.forEach((b, i) => {
        const label = b.getAttribute('aria-label') || '';
        const title = b.getAttribute('title') || '';
        const svg = b.querySelector('svg');
        const path = svg?.querySelector('path')?.getAttribute('d')?.substring(0, 20) || '';
        console.log(i, { label, title, path, text: b.textContent?.substring(0, 20) });
      });
    },

    // Debug: list all inputs
    debugInputs() {
      document.querySelectorAll('textarea, input').forEach((el, i) => {
        console.log(i, el.tagName, el.type, el.placeholder || el.className);
      });
    }
  };

  // ========== MESSAGE HANDLER ==========
  // Nhan message tu content script
  window.addEventListener('message', (event) => {
    if (event.data?.type !== 'SORA_CONTENT_TO_INJECT') return;

    const { id, action, data } = event.data;
    let result = { success: false };

    switch (action) {
      case 'CLICK_TEXTAREA':
        result = { success: clickTextarea() };
        break;
      case 'INPUT_PROMPT':
        result = { success: inputPrompt(data.text) };
        break;
      case 'CLICK_UPLOAD':
        result = { success: clickUploadButton() };
        break;
      case 'TRIGGER_FILE_INPUT':
        result = { success: triggerFileInput() };
        break;
      case 'PRESS_ENTER':
        result = { success: pressEnter() };
        break;
      case 'CLICK_SUBMIT':
        result = { success: clickSubmitButton() };
        break;
      case 'GET_STATUS':
        result = checkStatus();
        break;
      case 'GET_VIDEO_URL':
        result = { url: getVideoUrl(), ready: state.videoReady };
        break;
      default:
        result = { error: 'Unknown action' };
    }

    // Send response back
    window.postMessage({
      type: 'SORA_INJECT_TO_CONTENT',
      id,
      result
    }, '*');
  });

  log('SORA_HELPER ready!', 'success');
  window.dispatchEvent(new CustomEvent('SORA_HELPER_READY'));

})();
