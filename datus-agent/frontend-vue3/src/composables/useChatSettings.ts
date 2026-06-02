import { ref, watch } from "vue";

const STORAGE_KEY = "datus-chat-settings";

type StoredSettings = {
  language: string;
  permissionMode: string;
  planMode: boolean;
};

function loadSettings(): StoredSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        language: parsed.language ?? "zh",
        permissionMode: parsed.permissionMode ?? "normal",
        planMode: parsed.planMode ?? false,
      };
    }
  } catch {
    /* ignore */
  }
  return { language: "zh", permissionMode: "normal", planMode: false };
}

const saved = loadSettings();

const language = ref(saved.language);
const permissionMode = ref(saved.permissionMode);
const planMode = ref(saved.planMode);

watch([language, permissionMode, planMode], ([lang, perm, plan]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ language: lang, permissionMode: perm, planMode: plan }));
});

export function useChatSettings() {
  return { language, permissionMode, planMode };
}
