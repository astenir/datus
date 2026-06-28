import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { configApi, modelsApi } from "@/lib/api";
import type {
  ConfigSummary,
  ConfigurationTextForms,
  DatasourceConfigMap,
  DatasourceProbeInput,
  ModelConfigMap,
  ModelInfo,
  ModelProbeInput,
  ModelsData,
  NormalizedProbeResult,
  ProbeResult,
} from "@/types";

const DEFAULT_PROBE_FAILURE = "连接测试失败，请检查配置";

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseRecordText(text: string, label: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) return {};

  const parsed: unknown = JSON.parse(trimmed);
  if (!isRecord(parsed)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return parsed;
}

function parseConfigMap(text: string, label: string): Record<string, Record<string, unknown>> {
  const parsed = parseRecordText(text, label);
  const result: Record<string, Record<string, unknown>> = {};

  for (const [key, value] of Object.entries(parsed)) {
    if (!isRecord(value)) {
      throw new Error(`${label}.${key} 必须是 JSON 对象`);
    }
    result[key] = value;
  }

  return result;
}

function normalizeProbeResult(result: ProbeResult | null): NormalizedProbeResult {
  const ok = typeof result?.ok === "boolean"
    ? result.ok
    : typeof result?.success === "boolean"
      ? result.success
      : Boolean(result);
  const message = typeof result?.message === "string" && result.message.trim()
    ? result.message.trim()
    : typeof result?.errorMessage === "string" && result.errorMessage.trim()
      ? result.errorMessage.trim()
      : typeof result?.error === "string" && result.error.trim()
        ? result.error.trim()
        : ok
          ? "连接正常"
          : DEFAULT_PROBE_FAILURE;

  return { ok, message };
}

function modelProbeFromTarget(target: string): ModelProbeInput {
  const [type = "", ...rest] = target.split("/");
  return {
    type: type.trim(),
    model: rest.join("/").trim(),
    api_key: null,
    base_url: null,
  };
}

function shouldIncludeProbeField(key: string, value: unknown): boolean {
  if (key === "extra") return false;
  if (value == null) return false;
  if (typeof value !== "string") return true;
  return value.trim() !== "" || key === "password";
}

function datasourceProbeFromConfig(config: Record<string, unknown>): DatasourceProbeInput | null {
  const type = typeof config.type === "string" ? config.type.trim() : "";
  if (!type) return null;

  const probe: DatasourceProbeInput = { type };
  for (const [key, value] of Object.entries(config)) {
    if (key === "type" || !shouldIncludeProbeField(key, value)) continue;
    probe[key] = value;
  }

  if (isRecord(config.extra)) {
    for (const [key, value] of Object.entries(config.extra)) {
      if (key in probe || !shouldIncludeProbeField(key, value)) continue;
      probe[key] = value;
    }
  }

  return probe;
}

export function useConfigurationManager() {
  const connection = useConnection();

  const loading = shallowRef(false);
  const savingModels = shallowRef(false);
  const savingDatasources = shallowRef(false);
  const testingModel = shallowRef(false);
  const testingDatasource = shallowRef(false);

  const config = ref<ConfigSummary | null>(null);
  const modelsData = ref<ModelsData | null>(null);
  const modelProbe = ref<ModelProbeInput>({
    type: "",
    model: "",
    api_key: null,
    base_url: null,
  });
  const forms = ref<ConfigurationTextForms>({
    target: "",
    modelsText: "{}",
    datasourcesText: "{}",
    datasourceProbeText: "{}",
  });
  const selectedDatasourceName = shallowRef("");
  const modelProbeResult = shallowRef<NormalizedProbeResult | null>(null);
  const datasourceProbeResult = shallowRef<NormalizedProbeResult | null>(null);

  const configuredModelEntries = computed(() => Object.entries(config.value?.models ?? {}));
  const configuredDatasourceEntries = computed(() => Object.entries(config.value?.datasources ?? {}));
  const availableModels = computed<ModelInfo[]>(() => modelsData.value?.models ?? []);
  const providerCount = computed(() => modelsData.value?.providers?.length ?? 0);
  const currentTarget = computed(() => forms.value.target.trim() || config.value?.target || modelsData.value?.current_model || "");

  function hydrateForms(nextConfig: ConfigSummary | null, nextModels: ModelsData | null) {
    const target = typeof nextConfig?.target === "string"
      ? nextConfig.target
      : nextModels?.current_model ?? "";
    forms.value = {
      target,
      modelsText: prettyJson(nextConfig?.models ?? {}),
      datasourcesText: prettyJson(nextConfig?.datasources ?? {}),
      datasourceProbeText: "{}",
    };
    modelProbe.value = modelProbeFromTarget(target);

    const datasourceName = nextConfig?.current_datasource
      || Object.keys(nextConfig?.datasources ?? {})[0]
      || "";
    selectDatasourceForProbe(datasourceName, nextConfig);
  }

  async function loadConfiguration() {
    loading.value = true;
    try {
      const base = connection.effectiveBase();
      const [nextConfig, nextModels] = await Promise.all([
        configApi.getAgent(base),
        modelsApi.list(base),
      ]);
      config.value = nextConfig;
      modelsData.value = nextModels;
      hydrateForms(nextConfig, nextModels);
    } catch (err) {
      console.error("加载配置失败:", err);
      toast.error("加载配置失败");
    } finally {
      loading.value = false;
    }
  }

  function selectDatasourceForProbe(name: string, sourceConfig: ConfigSummary | null = config.value) {
    selectedDatasourceName.value = name;
    const datasource = sourceConfig?.datasources?.[name];
    const probe = datasource ? datasourceProbeFromConfig(datasource) : null;
    forms.value.datasourceProbeText = prettyJson(probe ?? {});
    datasourceProbeResult.value = null;
  }

  async function saveModels() {
    let models: ModelConfigMap;
    try {
      models = parseConfigMap(forms.value.modelsText, "models");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "模型配置 JSON 无效");
      return;
    }

    savingModels.value = true;
    try {
      const target = forms.value.target.trim() || null;
      await configApi.updateModels(connection.effectiveBase(), models, target);
      await loadConfiguration();
      await connection.checkConnection();
      toast.success("模型配置已保存");
    } catch (err) {
      console.error("保存模型配置失败:", err);
      toast.error("保存模型配置失败");
    } finally {
      savingModels.value = false;
    }
  }

  async function saveDatasources() {
    let datasources: DatasourceConfigMap;
    try {
      datasources = parseConfigMap(forms.value.datasourcesText, "datasources");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "数据源配置 JSON 无效");
      return;
    }

    savingDatasources.value = true;
    try {
      await configApi.updateDatasources(connection.effectiveBase(), datasources);
      await loadConfiguration();
      await connection.checkConnection();
      toast.success("数据源配置已保存");
    } catch (err) {
      console.error("保存数据源配置失败:", err);
      toast.error("保存数据源配置失败");
    } finally {
      savingDatasources.value = false;
    }
  }

  async function testModelProbe() {
    const type = modelProbe.value.type.trim();
    const model = modelProbe.value.model.trim();
    if (!type || !model) {
      toast.error("请填写模型 Provider 和模型名");
      return;
    }

    testingModel.value = true;
    try {
      const result = await configApi.testModel(connection.effectiveBase(), {
        ...modelProbe.value,
        type,
        model,
        api_key: modelProbe.value.api_key?.trim() || null,
        base_url: modelProbe.value.base_url?.trim() || null,
      });
      modelProbeResult.value = normalizeProbeResult(result);
    } catch (err) {
      console.error("测试模型连接失败:", err);
      modelProbeResult.value = { ok: false, message: DEFAULT_PROBE_FAILURE };
      toast.error("测试模型连接失败");
    } finally {
      testingModel.value = false;
    }
  }

  async function testDatasourceProbe() {
    let probe: Record<string, unknown>;
    try {
      probe = parseRecordText(forms.value.datasourceProbeText, "datasource probe");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "数据源测试 JSON 无效");
      return;
    }

    if (typeof probe.type !== "string" || !probe.type.trim()) {
      toast.error("数据源测试配置必须包含 type");
      return;
    }

    testingDatasource.value = true;
    try {
      const result = await configApi.testDatasource(connection.effectiveBase(), probe as DatasourceProbeInput);
      datasourceProbeResult.value = normalizeProbeResult(result);
    } catch (err) {
      console.error("测试数据源连接失败:", err);
      datasourceProbeResult.value = { ok: false, message: DEFAULT_PROBE_FAILURE };
      toast.error("测试数据源连接失败");
    } finally {
      testingDatasource.value = false;
    }
  }

  return {
    loading,
    savingModels,
    savingDatasources,
    testingModel,
    testingDatasource,
    config,
    modelsData,
    modelProbe,
    forms,
    selectedDatasourceName,
    modelProbeResult,
    datasourceProbeResult,
    configuredModelEntries,
    configuredDatasourceEntries,
    availableModels,
    providerCount,
    currentTarget,
    loadConfiguration,
    selectDatasourceForProbe,
    saveModels,
    saveDatasources,
    testModelProbe,
    testDatasourceProbe,
  };
}

export const configurationManagerInternals = {
  parseConfigMap,
  normalizeProbeResult,
  modelProbeFromTarget,
  datasourceProbeFromConfig,
};
