// Popup UI logic:
// 1) Load current toggle value from chrome.storage.sync when popup opens.
// 2) Persist toggle value whenever user changes it.

const STORAGE_KEY = "filterEnabled";

document.addEventListener("DOMContentLoaded", () => {
  const filterToggle = document.getElementById("filter-toggle");
  if (!filterToggle) return;

  // Load saved preference; default to enabled.
  chrome.storage.sync.get({ [STORAGE_KEY]: true }, (items) => {
    filterToggle.checked = Boolean(items[STORAGE_KEY]);
  });

  filterToggle.addEventListener("change", (event) => {
    const target = event.target;
    const isEnabled = Boolean(target && target.checked);
    chrome.storage.sync.set({ [STORAGE_KEY]: isEnabled });
  });
});
