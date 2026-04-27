// Background service worker responsibilities:
// - Receive image analysis requests from content scripts.
// - Receive video frame data URLs from content scripts.
// - Download image bytes.
// - Send bytes to backend /analyze-image endpoint.
// - Return explicit/non-explicit decision to the tab's content script.

const BACKEND_ANALYZE_URL = "http://localhost:8000/analyze-image";
const FILTER_STORAGE_KEY = "filterEnabled";
const SETTINGS_STORAGE_KEY = "safeviewSettings";
const RISKY_LABELS = new Set(["nudity", "violence", "kiss"]);
const CONFIDENCE_THRESHOLD = 0.5;
const frameRequestControllers = new Map();
const DEFAULT_SETTINGS = {
  categories: {
    nudity_explicit: true,
    violence_weapons: true,
    lgbtq_symbols: false,
    kissing_affection: true
  },
  sensitivity_level: 7
};

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

function getUserSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ [SETTINGS_STORAGE_KEY]: DEFAULT_SETTINGS }, (items) => {
      resolve(items[SETTINGS_STORAGE_KEY] || DEFAULT_SETTINGS);
    });
  });
}

function mapSensitivityToThreshold(level) {
  const numeric = Number(level || DEFAULT_SETTINGS.sensitivity_level);
  const clamped = Math.max(1, Math.min(10, numeric));
  // Higher slider value => stricter filtering (lower confidence threshold).
  return Math.max(0.2, 0.65 - clamped * 0.04);
}

async function analyzeFrameBlob(frameBlob, signal) {
  // Read the latest user settings immediately before backend fetch.
  const settings = await getUserSettings();
  const userPreferences = {
    nudity: Boolean(settings?.categories?.nudity_explicit),
    violence: Boolean(settings?.categories?.violence_weapons),
    kissing: Boolean(settings?.categories?.kissing_affection),
    thematic: Boolean(settings?.categories?.lgbtq_symbols),
    sensitivity: Number(settings?.sensitivity_level || DEFAULT_SETTINGS.sensitivity_level)
  };

  const formData = new FormData();
  // Keep both keys for compatibility while backend/form field naming stabilizes.
  formData.append("file", frameBlob, "safeview-frame.jpg");
  formData.append("image", frameBlob, "safeview-frame.jpg");
  formData.append("user_preferences", JSON.stringify(userPreferences));
  formData.append("settings", JSON.stringify(settings || DEFAULT_SETTINGS));
  formData.append("sensitivity", String(mapSensitivityToThreshold(settings?.sensitivity_level)));
  formData.append("filter_nudity", String(Boolean(settings?.categories?.nudity_explicit)));
  formData.append("filter_violence", String(Boolean(settings?.categories?.violence_weapons)));

  const backendResponse = await fetch(BACKEND_ANALYZE_URL, {
    method: "POST",
    mode: "cors",
    headers: {
      Accept: "application/json"
    },
    signal,
    body: formData
  });

  if (!backendResponse.ok) {
    throw new Error(`Backend frame analyze failed: ${backendResponse.status}`);
  }

  const payload = await backendResponse.json();
  return { payload, settings };
}

function dataUrlToBlob(dataUrl) {
  const parts = String(dataUrl || "").split(",");
  if (parts.length !== 2) {
    throw new Error("Invalid DataURL payload");
  }
  const meta = parts[0] || "";
  const base64 = parts[1] || "";
  const mimeMatch = meta.match(/data:(.*?);base64/);
  const mimeType = mimeMatch ? mimeMatch[1] : "image/jpeg";
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

function decisionFromAnalysis(payload) {
  const detections = Array.isArray(payload?.analysis) ? payload.analysis : [];

  if (detections.length === 0) {
    return { decision: "ALLOW", triggerLabel: null };
  }

  const explicitBlurHit = detections.find((item) => String(item?.action_required || "").toLowerCase() === "blur");
  if (explicitBlurHit) {
    return {
      decision: "BLOCK",
      triggerLabel: String(explicitBlurHit?.label || "unknown")
    };
  }

  const shouldBlock = detections.some((item) => {
    const label = String(item?.label || "").toLowerCase();
    const score = Number(item?.score || 0);
    return RISKY_LABELS.has(label) && score > CONFIDENCE_THRESHOLD;
  });
  if (!shouldBlock) return { decision: "ALLOW", triggerLabel: null };

  const matched = detections.find((item) => {
    const label = String(item?.label || "").toLowerCase();
    const score = Number(item?.score || 0);
    return RISKY_LABELS.has(label) && score > CONFIDENCE_THRESHOLD;
  });
  return {
    decision: "BLOCK",
    triggerLabel: String(matched?.label || "unknown")
  };
}

function isExplicitFromAnalysis(analysisPayload) {
  const detections = Array.isArray(analysisPayload?.analysis)
    ? analysisPayload.analysis
    : [];

  return detections.some((item) => EXPLICIT_LABELS.has(String(item?.label || "")));
}

function categoriesFromAnalysis(payload) {
  const detections = Array.isArray(payload?.analysis) ? payload.analysis : [];
  const categories = new Set();
  detections.forEach((item) => {
    const label = String(item?.label || "").toLowerCase();
    if (["nudity", "skin", "underwear", "bikini", "porn", "erotica"].includes(label)) {
      categories.add("nudity_explicit");
    }
    if (["violence", "weapon", "gun", "knife", "pistol", "blood"].includes(label)) {
      categories.add("violence_weapons");
    }
    if (["lgbtq", "lgbt", "rainbow_flag", "pride_flag", "gay", "lesbian"].includes(label)) {
      categories.add("lgbtq_symbols");
    }
    if (["kiss", "kissing", "intimate", "affection"].includes(label)) {
      categories.add("kissing_affection");
    }
  });
  return Array.from(categories);
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "SAFEVIEW_ANALYZE_FRAME_DATA_URL") {
    const tabId = sender.tab && sender.tab.id;
    if (tabId == null || !message.frameDataUrl) return;
    const frameId = Number(message.frameId || 0);

    (async () => {
      try {
        const previousController = frameRequestControllers.get(tabId);
        if (previousController) previousController.abort();
        const controller = new AbortController();
        frameRequestControllers.set(tabId, controller);

        const frameBlob = dataUrlToBlob(message.frameDataUrl);
        const { payload, settings } = await analyzeFrameBlob(frameBlob, controller.signal);
        if (frameRequestControllers.get(tabId) !== controller) return;

        const decisionResult = decisionFromAnalysis(payload);
        const detectedCategories = categoriesFromAnalysis(payload);
        console.log("[SafeView-BG] Received AI Result:", JSON.stringify(payload));

        if (String(payload?.audio_decision || "").toUpperCase() === "MUTE") {
          chrome.tabs.sendMessage(tabId, {
            type: "SAFEVIEW_AUDIO_ACTION",
            action: "muteAudio",
            duration: 2000
          });
        }

        chrome.tabs.sendMessage(tabId, {
          type: "SAFEVIEW_VIDEO_DECISION",
          decision: decisionResult.decision,
          triggerLabel: decisionResult.triggerLabel,
          detectedCategories,
          settings,
          videoElementId: message.videoElementId || null,
          frameId
        });

        frameRequestControllers.delete(tabId);
        sendResponse({ ok: true });
      } catch (error) {
        if (error && error.name === "AbortError") {
          sendResponse({ ok: true, aborted: true });
          return;
        }
        chrome.tabs.sendMessage(tabId, {
          type: "SAFEVIEW_VIDEO_DECISION",
          decision: "ALLOW",
          frameId
        });
        frameRequestControllers.delete(tabId);
        sendResponse({ ok: false, error: String(error && error.message ? error.message : error) });
      }
    })();

    return true;
  }

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

