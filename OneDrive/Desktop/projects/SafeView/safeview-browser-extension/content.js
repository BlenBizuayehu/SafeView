// Content script responsibilities:
// - Discover images on the page.
// - Ask background service worker to analyze each image URL.
// - Receive analysis results and blur matching images.
// - Keep scanning dynamic pages using MutationObserver.

const FILTER_STORAGE_KEY = "filterEnabled";
const PROCESSED_ATTR = "data-safeview-processed";
const explicitByUrl = new Map();
let filterEnabled = true;

function getImageKey(img) {
  return img.currentSrc || img.src || "";
}

function markProcessed(img) {
  img.setAttribute(PROCESSED_ATTR, "1");
}

function isProcessed(img) {
  return img.getAttribute(PROCESSED_ATTR) === "1";
}

function applyBlurStateForImage(img) {
  const key = getImageKey(img);
  const isExplicit = explicitByUrl.get(key) === true;
  if (filterEnabled && isExplicit) {
    img.classList.add("safeview-blur");
  } else {
    img.classList.remove("safeview-blur");
  }
}

function refreshAllImageBlurStates() {
  const images = document.querySelectorAll("img");
  images.forEach((img) => applyBlurStateForImage(img));
}

function scanForImages() {
  const images = document.querySelectorAll("img");

  images.forEach((img) => {
    if (isProcessed(img)) return;
    const imageUrl = getImageKey(img);
    if (!imageUrl) {
      markProcessed(img);
      return;
    }

    markProcessed(img);

    // Send request to background service worker for backend analysis.
    chrome.runtime.sendMessage({
      type: "SAFEVIEW_ANALYZE_IMAGE",
      imageUrl
    });
  });
}

// Receive backend analysis result forwarded by background.js.
chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "SAFEVIEW_ANALYSIS_RESULT") return;

  const { imageUrl, isExplicit } = message;
  if (!imageUrl) return;

  explicitByUrl.set(imageUrl, Boolean(isExplicit));

  // Apply to all matching image elements (same URL can appear multiple times).
  const images = document.querySelectorAll("img");
  images.forEach((img) => {
    if (getImageKey(img) === imageUrl) {
      applyBlurStateForImage(img);
    }
  });
});

// Listen for setting updates from background (optional, but keeps page in sync).
chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== "SAFEVIEW_FILTER_STATE_CHANGED") return;
  filterEnabled = Boolean(message.enabled);
  refreshAllImageBlurStates();
});

// Load current filter setting when script starts.
chrome.storage.sync.get({ [FILTER_STORAGE_KEY]: true }, (items) => {
  filterEnabled = Boolean(items[FILTER_STORAGE_KEY]);
  scanForImages();
});

// React to local storage changes (e.g., popup toggled while page is open).
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "sync" || !changes[FILTER_STORAGE_KEY]) return;
  filterEnabled = Boolean(changes[FILTER_STORAGE_KEY].newValue);
  refreshAllImageBlurStates();
});

// Observe DOM updates for infinite-scroll/dynamic pages.
const observer = new MutationObserver((mutations) => {
  const hasPotentialImageChange = mutations.some((mutation) => {
    if (mutation.type !== "childList") return false;
    return Array.from(mutation.addedNodes).some((node) => {
      if (!(node instanceof Element)) return false;
      return node.tagName === "IMG" || node.querySelector("img") !== null;
    });
  });

  if (hasPotentialImageChange) {
    scanForImages();
  }
});

observer.observe(document.documentElement || document.body, {
  childList: true,
  subtree: true
});

