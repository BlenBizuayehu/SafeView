const IS_YOUTUBE_MAIN_WINDOW =
  window.location.hostname === "www.youtube.com" && window.self === window.top;

if (!IS_YOUTUBE_MAIN_WINDOW) {
  // Ignore about:blank/sandboxed/iframe contexts.
} else {
  const FILTER_STORAGE_KEY = "filterEnabled";
  const SETTINGS_STORAGE_KEY = "safeviewSettings";
  const VIDEO_BLOCK_ATTR = "data-aegis-status";
  const BLOCK_CLASS = "safeview-blocked";
  const OVERLAY_ID = "safeview-status-overlay";
  const AUDIO_TOAST_ID = "safeview-audio-toast";
  const STYLE_ID = "safeview-block-style";

  const DEFAULT_SETTINGS = {
    categories: {
      nudity_explicit: true,
      violence_weapons: true,
      lgbtq_symbols: false,
      kissing_affection: true
    },
    sensitivity_level: 7
  };

  let filterEnabled = true;
  let localSettings = DEFAULT_SETTINGS;
  let activeVideoElement = null;
  let lastDecision = "ALLOW";
  let videoCaptureIntervalId = null;
  let latestFrameIdSent = 0;
  let activeBlockedVideoId = null;
  let videoIdCounter = 0;
  const videoCaptureCanvas = document.createElement("canvas");
  videoCaptureCanvas.style.display = "none";

  function ensureGlobalStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      .safeview-blocked {
        filter: blur(80px) !important;
        opacity: 0.2 !important;
        pointer-events: none !important;
      }
      #${OVERLAY_ID} {
        position: absolute;
        top: 12px;
        left: 12px;
        z-index: 2147483647;
        padding: 8px 12px;
        border-radius: 8px;
        background: rgba(0, 0, 0, 0.75);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
        pointer-events: none;
      }
      #${AUDIO_TOAST_ID} {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 2147483647;
        padding: 10px 14px;
        border-radius: 10px;
        background: rgba(0, 0, 0, 0.85);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        pointer-events: none;
      }
    `;
    document.head.appendChild(style);
  }

  function getActiveVideoElement() {
    const videos = Array.from(document.querySelectorAll("video"));
    const candidates = videos.filter((video) => {
      if (!(video instanceof HTMLVideoElement)) return false;
      if (video.readyState < 2 || video.videoWidth <= 0 || video.videoHeight <= 0) return false;
      const rect = video.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
    if (candidates.length === 0) return null;
    candidates.sort((a, b) => {
      const rectA = a.getBoundingClientRect();
      const rectB = b.getBoundingClientRect();
      return rectB.width * rectB.height - rectA.width * rectA.height;
    });
    return candidates[0];
  }

  function getPlayerContainer(videoEl) {
    if (!videoEl) return null;
    return videoEl.closest("div.html5-video-player, div.ytd-player") || videoEl.parentElement;
  }

  function ensureVideoElementId(videoEl) {
    if (!videoEl) return null;
    if (!videoEl.dataset.safeviewVideoId) {
      videoIdCounter += 1;
      videoEl.dataset.safeviewVideoId = `safeview-video-${videoIdCounter}`;
    }
    return videoEl.dataset.safeviewVideoId;
  }

  function ensureStatusOverlay(container) {
    if (!container) return null;
    let overlay = document.getElementById(OVERLAY_ID);
    if (overlay && overlay.parentElement !== container) {
      overlay.remove();
      overlay = null;
    }
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = OVERLAY_ID;
      overlay.textContent = "🛡️ SafeView: Content Masked";
      if (window.getComputedStyle(container).position === "static") {
        container.style.position = "relative";
      }
      container.appendChild(overlay);
    }
    return overlay;
  }

  function clearStatusOverlay() {
    const overlay = document.getElementById(OVERLAY_ID);
    if (overlay) overlay.remove();
  }

  function showAudioToast(message) {
    let toast = document.getElementById(AUDIO_TOAST_ID);
    if (!toast) {
      toast = document.createElement("div");
      toast.id = AUDIO_TOAST_ID;
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    window.setTimeout(() => {
      const currentToast = document.getElementById(AUDIO_TOAST_ID);
      if (currentToast) currentToast.remove();
    }, 2200);
  }

  function applyVideoDecision(decision, targetVideoId = null, triggerLabel = null) {
    const videoEl = getActiveVideoElement();
    activeVideoElement = videoEl;
    const container = getPlayerContainer(videoEl);
    if (!videoEl) return;
    const currentVideoId = ensureVideoElementId(videoEl);
    const isSameTarget = !targetVideoId || targetVideoId === currentVideoId;

    if (decision === "BLOCK" && filterEnabled) {
      requestAnimationFrame(() => {
        console.log("[SafeView] Applying BLUR to element...", triggerLabel ? `label=${triggerLabel}` : "");
        videoEl.classList.add(BLOCK_CLASS);
        videoEl.setAttribute(VIDEO_BLOCK_ATTR, "blocked");
        if (container) container.classList.add(BLOCK_CLASS);
        ensureStatusOverlay(container);
      });
      activeBlockedVideoId = currentVideoId;
    } else {
      // Do not clear blur unless ALLOW is explicit for the same element.
      if (!isSameTarget || (activeBlockedVideoId && activeBlockedVideoId !== currentVideoId)) return;
      videoEl.classList.remove(BLOCK_CLASS);
      videoEl.removeAttribute(VIDEO_BLOCK_ATTR);
      videoEl.style.filter = "none";
      if (container) container.classList.remove(BLOCK_CLASS);
      clearStatusOverlay();
      activeBlockedVideoId = null;
    }
  }

  function captureVideoFrameAndSend() {
    if (!filterEnabled) {
      applyVideoDecision("ALLOW");
      return;
    }
    const video = getActiveVideoElement();
    if (!video) {
      applyVideoDecision("ALLOW");
      return;
    }

    activeVideoElement = video;
    const videoElementId = ensureVideoElementId(video);
    videoCaptureCanvas.width = video.videoWidth;
    videoCaptureCanvas.height = video.videoHeight;
    const ctx = videoCaptureCanvas.getContext("2d");
    if (!ctx) return;

    try {
      ctx.drawImage(video, 0, 0, videoCaptureCanvas.width, videoCaptureCanvas.height);
    } catch (error) {
      console.warn("[SafeView-CS] drawImage failed:", error);
      return;
    }

    const frameDataUrl = videoCaptureCanvas.toDataURL("image/jpeg", 0.8);
    console.log("[SafeView-CS] Sending Frame...");
    latestFrameIdSent += 1;
    chrome.runtime.sendMessage({
      type: "SAFEVIEW_ANALYZE_FRAME_DATA_URL",
      frameDataUrl,
      videoElementId,
      frameId: latestFrameIdSent
    });
  }

  function startVideoCaptureLoop() {
    if (videoCaptureIntervalId != null) return;
    videoCaptureIntervalId = window.setInterval(captureVideoFrameAndSend, 500);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (!message || message.type !== "SAFEVIEW_VIDEO_DECISION") return;
    const responseFrameId = Number(message.frameId || 0);
    if (responseFrameId > 0 && responseFrameId < latestFrameIdSent) {
      return;
    }
    if (message.settings) {
      localSettings = {
        ...DEFAULT_SETTINGS,
        ...message.settings,
        categories: {
          ...DEFAULT_SETTINGS.categories,
          ...(message.settings.categories || {})
        }
      };
    }

    lastDecision = message.decision === "BLOCK" ? "BLOCK" : "ALLOW";
    console.log("[SafeView] Final Decision for this frame: " + lastDecision);
    applyVideoDecision(lastDecision, message.videoElementId || null, message.triggerLabel || null);
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (!message || message.type !== "SAFEVIEW_AUDIO_ACTION") return;
    if (message.action !== "muteAudio") return;
    const videoEl = getActiveVideoElement();
    if (!videoEl) return;
    const duration = Math.max(0, Number(message.duration || 2000));
    videoEl.muted = true;
    showAudioToast("🔇 SafeView: Profanity Muted");
    window.setTimeout(() => {
      videoEl.muted = false;
    }, duration);
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (!message || message.type !== "SAFEVIEW_FILTER_STATE_CHANGED") return;
    filterEnabled = Boolean(message.enabled);
    applyVideoDecision(filterEnabled ? lastDecision : "ALLOW");
  });

  chrome.storage.sync.get({ [FILTER_STORAGE_KEY]: true }, (items) => {
    filterEnabled = Boolean(items[FILTER_STORAGE_KEY]);
    chrome.storage.sync.get({ [SETTINGS_STORAGE_KEY]: DEFAULT_SETTINGS }, (settingsItems) => {
      localSettings = {
        ...DEFAULT_SETTINGS,
        ...(settingsItems[SETTINGS_STORAGE_KEY] || {}),
        categories: {
          ...DEFAULT_SETTINGS.categories,
          ...((settingsItems[SETTINGS_STORAGE_KEY] || {}).categories || {})
        }
      };
    });
    ensureGlobalStyles();
    startVideoCaptureLoop();
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName !== "sync") return;
    if (changes[FILTER_STORAGE_KEY]) {
      filterEnabled = Boolean(changes[FILTER_STORAGE_KEY].newValue);
    }
    if (changes[SETTINGS_STORAGE_KEY]) {
      localSettings = {
        ...DEFAULT_SETTINGS,
        ...(changes[SETTINGS_STORAGE_KEY].newValue || {}),
        categories: {
          ...DEFAULT_SETTINGS.categories,
          ...((changes[SETTINGS_STORAGE_KEY].newValue || {}).categories || {})
        }
      };
    }
    applyVideoDecision(filterEnabled ? lastDecision : "ALLOW");
  });
}

