// Background service worker responsibilities:
// - Receive image analysis requests from content scripts.
// - Download image bytes.
// - Send bytes to backend /analyze-image endpoint.
// - Return explicit/non-explicit decision to the tab's content script.

const BACKEND_ANALYZE_URL = "http://localhost:8000/analyze-image";
const FILTER_STORAGE_KEY = "filterEnabled";

// Test class labels to blur for now. Replace with your explicit categories later.
const EXPLICIT_LABELS = new Set(["person"]);

async function analyzeImageUrl(imageUrl) {
  // 1) Fetch original image from the page URL.
  const imageResponse = await fetch(imageUrl);
  if (!imageResponse.ok) {
    throw new Error(`Image fetch failed: ${imageResponse.status}`);
  }

  const imageBlob = await imageResponse.blob();

  // 2) Post image blob to backend as multipart/form-data.
  const formData = new FormData();
  formData.append("image", imageBlob, "safeview-image");

  const backendResponse = await fetch(BACKEND_ANALYZE_URL, {
    method: "POST",
    body: formData
  });

  if (!backendResponse.ok) {
    throw new Error(`Backend analyze failed: ${backendResponse.status}`);
  }

  return backendResponse.json();
}

function isExplicitFromAnalysis(analysisPayload) {
  const detections = Array.isArray(analysisPayload?.analysis)
    ? analysisPayload.analysis
    : [];

  return detections.some((item) => EXPLICIT_LABELS.has(String(item?.label || "")));
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "SAFEVIEW_ANALYZE_IMAGE") return;

  const imageUrl = message.imageUrl;
  const tabId = sender.tab && sender.tab.id;
  if (!imageUrl || tabId == null) return;

  (async () => {
    try {
      const payload = await analyzeImageUrl(imageUrl);
      const isExplicit = isExplicitFromAnalysis(payload);

      // Send result back only to the originating tab's content script.
      chrome.tabs.sendMessage(tabId, {
        type: "SAFEVIEW_ANALYSIS_RESULT",
        imageUrl,
        isExplicit
      });

      sendResponse({ ok: true });
    } catch (error) {
      // Fail closed as non-explicit for safety of UX; can be changed later.
      chrome.tabs.sendMessage(tabId, {
        type: "SAFEVIEW_ANALYSIS_RESULT",
        imageUrl,
        isExplicit: false
      });

      sendResponse({ ok: false, error: String(error && error.message ? error.message : error) });
    }
  })();

  // Keep message channel alive for async sendResponse.
  return true;
});

// Relay filter toggle updates to active tab(s) so content script updates immediately.
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "sync" || !changes[FILTER_STORAGE_KEY]) return;
  const enabled = Boolean(changes[FILTER_STORAGE_KEY].newValue);

  chrome.tabs.query({}, (tabs) => {
    tabs.forEach((tab) => {
      if (typeof tab.id === "number") {
        chrome.tabs.sendMessage(tab.id, {
          type: "SAFEVIEW_FILTER_STATE_CHANGED",
          enabled
        });
      }
    });
  });
});

