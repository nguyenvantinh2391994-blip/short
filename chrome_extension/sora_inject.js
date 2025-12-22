/**
 * SORA Inject Script - Chay trong page context
 * Expose SORA_HELPER ra window de Python tool su dung
 */

(function() {
  console.log('[SORA Inject] Loading...');

  // ========== STATE ==========
  const state = {
    videoUrl: null,
    videoReady: false,
    isProcessing: false,
  };

  // ========== UTILITIES ==========
  function log(msg, type = 'info') {
    const prefix = '[SORA]';
    const styles = {
      info: 'color: #3498db',
      success: 'color: #2ecc71; font-weight: bold',
      error: 'color: #e74c3c',
      warning: 'color: #f39c12',
    };
    console.log(`%c${prefix} ${msg}`, styles[type] || styles.info);
  }

  // ========== ELEMENT HELPERS ==========
  function findTextarea() {
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
      log(`Prompt: ${text.substring(0, 40)}...`, 'success');
      return true;
    }
    log('Cannot input prompt - textarea not found', 'error');
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
          if (d.includes('M12 6') || d.includes('M12 5')) {
            b.click();
            log('Upload button clicked!', 'success');
            return true;
          }
        }
      }
    }

    // Fallback: tim theo aria-label
    const uploadBtn = document.querySelector('button[aria-label*="upload" i], button[aria-label*="attach" i], button[aria-label*="Add" i]');
    if (uploadBtn) {
      uploadBtn.click();
      log('Upload button clicked (aria-label)!', 'success');
      return true;
    }

    log('Upload button not found', 'warning');
    return false;
  }

  function pressEnter() {
    const ta = findTextarea();
    if (ta) {
      ta.focus();
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true,
        cancelable: true,
      });
      ta.dispatchEvent(event);
      log('Enter pressed', 'success');
      return true;
    }
    log('Cannot press Enter - textarea not found', 'error');
    return false;
  }

  function clickSubmitButton() {
    // Tim nut submit/generate
    const selectors = [
      'button[type="submit"]',
      'button[aria-label*="submit" i]',
      'button[aria-label*="generate" i]',
      'button[aria-label*="create" i]',
    ];

    for (const sel of selectors) {
      const btn = document.querySelector(sel);
      if (btn) {
        btn.click();
        log('Submit button clicked!', 'success');
        return true;
      }
    }

    // Fallback: tim button co icon arrow/send
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const svg = b.querySelector('svg');
      if (svg) {
        const paths = svg.querySelectorAll('path');
        for (const p of paths) {
          const d = p.getAttribute('d') || '';
          // Arrow right hoac send icon
          if (d.includes('M5 12h14') || d.includes('M22 2L11 13') || d.includes('m12.586')) {
            b.click();
            log('Submit button clicked (arrow)!', 'success');
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
    // Check video
    const videoUrl = getVideoUrl();
    if (videoUrl) {
      return { status: 'done', videoUrl };
    }

    // Check loading
    const spinners = document.querySelectorAll('[class*="animate-spin"], [class*="loading"]');
    for (const s of spinners) {
      if (s.offsetParent !== null) {
        return { status: 'loading' };
      }
    }

    return { status: 'waiting' };
  }

  function waitForVideo(timeout = 300) {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const check = () => {
        const status = checkStatus();
        if (status.status === 'done') {
          log(`Video ready! ${status.videoUrl.substring(0, 50)}...`, 'success');
          resolve(status);
          return;
        }

        if (Date.now() - startTime > timeout * 1000) {
          log('Timeout waiting for video', 'error');
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
    pressEnter,
    clickSubmitButton,
    getVideoUrl,
    checkStatus,
    waitForVideo,
    getState: () => state,

    // Shortcut: tao video tu prompt
    async createVideo(prompt) {
      log(`Creating video: ${prompt.substring(0, 30)}...`);

      clickTextarea();
      await new Promise(r => setTimeout(r, 500));

      inputPrompt(prompt);
      await new Promise(r => setTimeout(r, 500));

      pressEnter();

      return waitForVideo();
    }
  };

  log('SORA_HELPER ready!', 'success');

  // Notify qua custom event
  window.dispatchEvent(new CustomEvent('SORA_HELPER_READY'));

})();
