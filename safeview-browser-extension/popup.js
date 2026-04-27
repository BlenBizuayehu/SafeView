const FILTER_STORAGE_KEY = "filterEnabled";
const SETTINGS_STORAGE_KEY = "safeviewSettings";

const DEFAULT_SETTINGS = {
  categories: {
    nudity_explicit: true,
    violence_weapons: true,
    lgbtq_symbols: false,
    kissing_affection: true
  },
  sensitivity_level: 7
};

function getSettingsFromUI(elements) {
  return {
    categories: {
      nudity_explicit: Boolean(elements.nudityToggle.checked),
      violence_weapons: Boolean(elements.violenceToggle.checked),
      lgbtq_symbols: Boolean(elements.lgbtqToggle.checked),
      kissing_affection: Boolean(elements.kissToggle.checked)
    },
    sensitivity_level: Number(elements.sensitivitySlider.value || DEFAULT_SETTINGS.sensitivity_level)
  };
}

function applySettingsToUI(settings, elements) {
  elements.nudityToggle.checked = Boolean(settings.categories?.nudity_explicit);
  elements.violenceToggle.checked = Boolean(settings.categories?.violence_weapons);
  elements.lgbtqToggle.checked = Boolean(settings.categories?.lgbtq_symbols);
  elements.kissToggle.checked = Boolean(settings.categories?.kissing_affection);
  elements.sensitivitySlider.value = String(settings.sensitivity_level || DEFAULT_SETTINGS.sensitivity_level);
  elements.sensitivityValue.textContent = String(settings.sensitivity_level || DEFAULT_SETTINGS.sensitivity_level);
}

document.addEventListener("DOMContentLoaded", () => {
  const elements = {
    nudityToggle: document.getElementById("category-nudity"),
    violenceToggle: document.getElementById("category-violence"),
    lgbtqToggle: document.getElementById("category-lgbtq"),
    kissToggle: document.getElementById("category-kiss"),
    sensitivitySlider: document.getElementById("sensitivity-level"),
    sensitivityValue: document.getElementById("sensitivity-value")
  };

  const hasAllElements = Object.values(elements).every(Boolean);
  if (!hasAllElements) return;

  chrome.storage.sync.get(
    {
      [FILTER_STORAGE_KEY]: true,
      [SETTINGS_STORAGE_KEY]: DEFAULT_SETTINGS
    },
    (items) => {
      const settings = items[SETTINGS_STORAGE_KEY] || DEFAULT_SETTINGS;
      applySettingsToUI(settings, elements);
    }
  );

  const saveSettings = () => {
    const settings = getSettingsFromUI(elements);
    chrome.storage.sync.set({
      [SETTINGS_STORAGE_KEY]: settings,
      [FILTER_STORAGE_KEY]: Object.values(settings.categories).some(Boolean)
    });
  };

  elements.sensitivitySlider.addEventListener("input", () => {
    elements.sensitivityValue.textContent = elements.sensitivitySlider.value;
  });

  elements.sensitivitySlider.addEventListener("change", saveSettings);
  elements.nudityToggle.addEventListener("change", saveSettings);
  elements.violenceToggle.addEventListener("change", saveSettings);
  elements.lgbtqToggle.addEventListener("change", saveSettings);
  elements.kissToggle.addEventListener("change", saveSettings);
});
