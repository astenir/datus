import { readonly, ref, shallowRef } from "vue";
import { configApi } from "@/lib/api";
import { normalizeBaseUrl } from "@/lib/chat";
import { getInjectedApiOrigin } from "@/lib/injected-config";
import { setApiBaseResolver } from "@/lib/request";
import type { ConnectionState, ConfigSummary } from "@/types";

const STORAGE_KEY = "datus-api-base";
const DEFAULT_BASE = "";

const apiBase = shallowRef(loadApiBase());
const connection = shallowRef<ConnectionState>("idle");
const config = ref<ConfigSummary | null>(null);

function loadApiBase(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_BASE;
  } catch {
    return DEFAULT_BASE;
  }
}

function saveApiBase(value: string) {
  localStorage.setItem(STORAGE_KEY, value);
}

function effectiveBase(): string {
  const stored = apiBase.value.trim();
  if (stored) return stored;

  const injected = normalizeBaseUrl(getInjectedApiOrigin());
  if (injected) return injected;

  const env = import.meta.env.VITE_DATUS_API_TARGET as string | undefined;
  return env?.trim() ?? "";
}

setApiBaseResolver(effectiveBase);

async function checkConnection(): Promise<void> {
  connection.value = "checking";
  const base = effectiveBase();
  try {
    const result = await configApi.getAgent(base);
    if (result) {
      config.value = result;
      connection.value = "online";
    } else {
      connection.value = "offline";
    }
  } catch {
    connection.value = "offline";
  }
}

function setApiBase(value: string) {
  const normalized = normalizeBaseUrl(value);
  apiBase.value = normalized;
  saveApiBase(normalized);
}

export function useConnection() {
  return {
    apiBase: readonly(apiBase),
    connection: readonly(connection),
    config: readonly(config),
    effectiveBase,
    checkConnection,
    setApiBase,
  };
}
