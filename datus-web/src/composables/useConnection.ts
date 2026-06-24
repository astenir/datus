import { computed, readonly, ref, shallowRef } from "vue";
import { configApi } from "@/lib/api";
import { normalizeBaseUrl } from "@/lib/chat";
import { getInjectedApiOrigin } from "@/lib/injected-config";
import { setApiBaseResolver } from "@/lib/request";
import { handleError } from "@/lib/utils";
import type { ConnectionState, ConfigSummary, NormalizedProbeResult, ProbeResult, SelectOption } from "@/types";

const STORAGE_KEY = "datus-api-base";
const DEFAULT_BASE = "";
const DEFAULT_DATASOURCE_TEST_FAILURE = "连接测试失败，请检查数据源配置";

const apiBase = shallowRef(loadApiBase());
const connection = shallowRef<ConnectionState>("idle");
const config = ref<ConfigSummary | null>(null);
const isTestingDatasource = shallowRef(false);

const datasourceOptions = computed<SelectOption[]>(() => {
  const datasources = config.value?.datasources ?? {};
  const options = Object.keys(datasources).map((name) => ({ value: name, label: name }));
  const current = config.value?.current_datasource?.trim();

  if (current && !options.some((option) => option.value === current)) {
    return [{ value: current, label: current }, ...options];
  }

  return options;
});

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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function shouldIncludeDatasourceField(key: string, value: unknown): boolean {
  if (value == null) return false;
  if (typeof value !== "string") return true;
  return value.trim() !== "" || key === "password";
}

function datasourceProbe(name?: string): { type: string; [key: string]: unknown } | null {
  const datasourceName = name?.trim() || config.value?.current_datasource?.trim();
  if (!datasourceName) return null;

  const datasource = config.value?.datasources?.[datasourceName];
  const type = datasource?.type;
  if (!datasource || typeof type !== "string" || !type.trim()) return null;

  const probe: { type: string; [key: string]: unknown } = { type };
  for (const [key, value] of Object.entries(datasource)) {
    if (key === "type" || key === "extra" || !shouldIncludeDatasourceField(key, value)) continue;
    probe[key] = value;
  }

  if (isRecord(datasource.extra)) {
    for (const [key, value] of Object.entries(datasource.extra)) {
      if (key in probe || !shouldIncludeDatasourceField(key, value)) continue;
      probe[key] = value;
    }
  }

  return probe;
}

function stringField(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function isInternalErrorMessage(value: string): boolean {
  return value.includes("dictionary update sequence element")
    || value.includes("Traceback")
    || /\b(TypeError|ValueError|KeyError|AttributeError):/.test(value);
}

function datasourceTestMessage(ok: boolean, message: string): string {
  if (!message) return ok ? "连接正常" : DEFAULT_DATASOURCE_TEST_FAILURE;
  if (!ok && isInternalErrorMessage(message)) return DEFAULT_DATASOURCE_TEST_FAILURE;
  return message;
}

function normalizeProbeResult(result: ProbeResult | null): NormalizedProbeResult {
  const ok = typeof result?.ok === "boolean"
    ? result.ok
    : typeof result?.success === "boolean"
      ? result.success
      : Boolean(result);
  const rawMessage = stringField(result?.message)
    || stringField(result?.errorMessage)
    || stringField(result?.error);
  const message = datasourceTestMessage(ok, rawMessage);

  return { ok, message };
}

async function testDatasource(name?: string): Promise<NormalizedProbeResult> {
  const probe = datasourceProbe(name);
  if (!probe) {
    const error = new Error("当前数据源缺少可测试配置");
    handleError("测试数据源连接失败", error);
    return { ok: false, message: error.message };
  }

  isTestingDatasource.value = true;
  try {
    const result = await configApi.testDatasource(effectiveBase(), probe);
    return normalizeProbeResult(result);
  } catch (error) {
    handleError("测试数据源连接失败", error);
    const rawMessage = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      message: datasourceTestMessage(false, rawMessage),
    };
  } finally {
    isTestingDatasource.value = false;
  }
}

async function switchDatasource(name: string): Promise<boolean> {
  const datasourceName = name.trim();
  if (!datasourceName || datasourceName === config.value?.current_datasource) return false;

  try {
    const result = await configApi.switchDatasource(effectiveBase(), datasourceName);
    if (!result?.current_datasource) return false;
    await checkConnection();
    return true;
  } catch (error) {
    handleError("切换数据源失败", error);
    return false;
  }
}

export function useConnection() {
  return {
    apiBase: readonly(apiBase),
    connection: readonly(connection),
    config: readonly(config),
    datasourceOptions,
    isTestingDatasource: readonly(isTestingDatasource),
    effectiveBase,
    checkConnection,
    setApiBase,
    testDatasource,
    switchDatasource,
  };
}
