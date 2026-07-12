import { readonly, shallowRef, watch } from "vue";
import { readLocalStorage, writeLocalStorage } from "@/lib/local-storage";

const STORAGE_KEY = "datus-chat-settings";

type StoredSettings = {
  language: string;
  permissionMode: string;
  planMode: boolean;
};

const DEFAULT_SETTINGS: StoredSettings = {
  language: "zh",
  permissionMode: "normal",
  planMode: false,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeSettings(value: unknown): StoredSettings {
  if (!isRecord(value)) return { ...DEFAULT_SETTINGS };

  return {
    language: typeof value.language === "string" ? value.language : DEFAULT_SETTINGS.language,
    permissionMode: typeof value.permissionMode === "string" ? value.permissionMode : DEFAULT_SETTINGS.permissionMode,
    planMode: typeof value.planMode === "boolean" ? value.planMode : DEFAULT_SETTINGS.planMode,
  };
}

function loadSettings(): StoredSettings {
  const raw = readLocalStorage(STORAGE_KEY);
  if (!raw) return { ...DEFAULT_SETTINGS };

  try {
    const parsed: unknown = JSON.parse(raw);
    return normalizeSettings(parsed);
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

const saved = loadSettings();

const language = shallowRef(saved.language);
const permissionMode = shallowRef(saved.permissionMode);
const planMode = shallowRef(saved.planMode);

watch([language, permissionMode, planMode], ([lang, perm, plan]) => {
  writeLocalStorage(STORAGE_KEY, JSON.stringify({ language: lang, permissionMode: perm, planMode: plan }));
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
