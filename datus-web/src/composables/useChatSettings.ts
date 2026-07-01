import { readonly, shallowRef, watch } from "vue";

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

const language = shallowRef(saved.language);
const permissionMode = shallowRef(saved.permissionMode);
const planMode = shallowRef(saved.planMode);

watch([language, permissionMode, planMode], ([lang, perm, plan]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ language: lang, permissionMode: perm, planMode: plan }));
});

function setLanguage(value: string) {
  language.value = value;
}

function setPermissionMode(value: string) {
  permissionMode.value = value;
}

function setPlanMode(value: boolean) {
  planMode.value = value;
}

export function useChatSettings() {
  return {
    language: readonly(language),
    permissionMode: readonly(permissionMode),
    planMode: readonly(planMode),
    setLanguage,
    setPermissionMode,
    setPlanMode,
  };
}
