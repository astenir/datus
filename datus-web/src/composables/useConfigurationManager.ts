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
  ProviderConfigMap,
  SavedModelProbeInput,
  TargetModelConfig,
} from "@/types";

const DEFAULT_PROBE_FAILURE = "连接测试失败，请检查配置";
const REDACTED_SECRET_PATTERN = /^\*{6,}$/;

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isSecretLikeProbeField(key: string): boolean {
  const normalized = key.trim().toLowerCase();
  return normalized === "password"
    || normalized.endsWith("_password")
    || normalized === "private_key_file_pwd"
    || normalized === "api_key"
    || normalized === "token"
    || normalized.endsWith("_token")
    || normalized.includes("secret");
}

function isRedactedSecretValue(value: unknown): value is string {
  return typeof value === "string" && REDACTED_SECRET_PATTERN.test(value.trim());
}

function normalizeProbeFieldValue(key: string, value: unknown): unknown {
  if (isSecretLikeProbeField(key) && isRedactedSecretValue(value)) return "";
  return value;
}

function redactedDatasourceProbeFieldsFromConfig(config: Record<string, unknown>): string[] {
  const fields: string[] = [];
  for (const [key, value] of Object.entries(config)) {
    if (key === "extra") continue;
    if (isSecretLikeProbeField(key) && isRedactedSecretValue(value)) {
      fields.push(key);
    }
  }

  if (isRecord(config.extra)) {
    for (const [key, value] of Object.entries(config.extra)) {
      if (fields.includes(key)) continue;
      if (isSecretLikeProbeField(key) && isRedactedSecretValue(value)) {
        fields.push(key);
      }
    }
  }
  return fields;
}

function maskedProbeSecretFields(source: Record<string, unknown>, prefix = ""): string[] {
  const fields: string[] = [];
  for (const [key, value] of Object.entries(source)) {
    const fieldPath = prefix ? `${prefix}.${key}` : key;
    if (isSecretLikeProbeField(key) && isRedactedSecretValue(value)) {
      fields.push(fieldPath);
      continue;
    }
    if (isRecord(value)) {
      fields.push(...maskedProbeSecretFields(value, fieldPath));
    }
  }
  return fields;
}

function parseRecordText(text: string, label: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) return {};

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error(`${label} 必须是合法的 JSON 对象`);
  }
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
  if (!ok) return { ok: false, message: DEFAULT_PROBE_FAILURE };

  const message = typeof result?.message === "string" && result.message.trim()
    ? result.message.trim()
    : typeof result?.errorMessage === "string" && result.errorMessage.trim()
      ? result.errorMessage.trim()
      : typeof result?.error === "string" && result.error.trim()
        ? result.error.trim()
        : "连接正常";

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

function targetModelRef(target: ConfigSummary["target"], fallback = ""): string {
  if (typeof target === "string") return target ? `custom/${target}` : fallback;
  if (target?.custom) return `custom/${target.custom}`;
  if (target?.provider && target.model) return `${target.provider}/${target.model}`;
  return fallback;
}

function targetModelConfig(reference: string): TargetModelConfig | null {
  const [provider = "", ...modelParts] = reference.trim().split("/");
  const model = modelParts.join("/").trim();
  if (!provider || !model) return null;
  return provider === "custom" ? { custom: model } : { provider, model };
}

function modelReference(model: ModelInfo): string {
  return `${model.provider}/${model.id}`;
}

function isChatModel(model: ModelInfo): boolean {
  return !model.capabilities?.includes("embedding");
}

function firstAvailableTargetRef(models: ModelsData | null, customModels: ModelConfigMap): string {
  const providerModel = models?.models.find((model) => model.provider !== "custom" && isChatModel(model));
  if (providerModel) return modelReference(providerModel);
  const embeddingNames = new Set(
    models?.models
      .filter(model => model.provider === "custom" && !isChatModel(model))
      .map(model => model.id) ?? [],
  );
  const customName = Object.keys(customModels).find(name => !embeddingNames.has(name));
  return customName ? `custom/${customName}` : "";
}

function isTargetReferenceAvailable(reference: string, models: ModelsData | null, customModels: ModelConfigMap): boolean {
  if (reference.startsWith("custom/")) {
    const customName = reference.slice("custom/".length);
    const catalogModel = models?.models.find(model => model.provider === "custom" && model.id === customName);
    return Boolean(customModels[customName]) && (!catalogModel || isChatModel(catalogModel));
  }
  return Boolean(models?.models.some((model) => model.provider !== "custom" && isChatModel(model) && modelReference(model) === reference));
}

function shouldIncludeProbeField(key: string, value: unknown): boolean {
  if (key === "display_name" || key === "extra") return false;
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
    probe[key] = normalizeProbeFieldValue(key, value);
  }

  if (isRecord(config.extra)) {
    for (const [key, value] of Object.entries(config.extra)) {
      if (key in probe || !shouldIncludeProbeField(key, value)) continue;
      probe[key] = normalizeProbeFieldValue(key, value);
    }
  }

  return probe;
}

export function useConfigurationManager() {
  const connection = useConnection();

  const loading = shallowRef(false);
  const savingProviders = shallowRef(false);
  const savingModels = shallowRef(false);
  const savingDatasources = shallowRef(false);
  const testingModel = shallowRef(false);
  const testingDatasource = shallowRef(false);

  const config = ref<ConfigSummary | null>(null);
  const modelsData = ref<ModelsData | null>(null);
  const providerConfigs = ref<ProviderConfigMap>({});
  const modelConfigs = ref<ModelConfigMap>({});
  const datasourceConfigs = ref<DatasourceConfigMap>({});
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
  const savedModelProbeResults = ref<Record<string, NormalizedProbeResult>>({});
  const testingSavedModels = ref<string[]>([]);
  const datasourceProbeResult = shallowRef<NormalizedProbeResult | null>(null);
  const savedDatasourceProbeResults = ref<Record<string, NormalizedProbeResult>>({});
  const testingSavedDatasources = ref<string[]>([]);
  const datasourceProbeSecretFields = shallowRef<string[]>([]);

  const configuredModelEntries = computed(() => Object.entries(modelConfigs.value));
  const configuredDatasourceEntries = computed(() => Object.entries(datasourceConfigs.value));
  const availableModels = computed<ModelInfo[]>(() => modelsData.value?.models ?? []);
  const embeddingModelNames = computed(() => new Set(
    availableModels.value
      .filter(model => model.provider === "custom" && model.capabilities?.includes("embedding"))
      .map(model => model.id),
  ));
  const providerCount = computed(() => modelsData.value?.providers?.length ?? 0);
  const currentTarget = computed(() => forms.value.target.trim() || modelsData.value?.current_model || "");

  function hydrateForms(nextConfig: ConfigSummary | null, nextModels: ModelsData | null) {
    providerConfigs.value = structuredClone(nextConfig?.providers ?? {});
    modelConfigs.value = structuredClone(nextConfig?.models ?? {});
    datasourceConfigs.value = structuredClone(nextConfig?.datasources ?? {});
    const configuredTarget = targetModelRef(nextConfig?.target, nextModels?.current_model ?? "");
    const target = isTargetReferenceAvailable(configuredTarget, nextModels, modelConfigs.value)
      ? configuredTarget
      : firstAvailableTargetRef(nextModels, modelConfigs.value);
    forms.value = {
      target,
      modelsText: prettyJson(modelConfigs.value),
      datasourcesText: prettyJson(datasourceConfigs.value),
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
    const datasource = sourceConfig === config.value
      ? datasourceConfigs.value[name]
      : sourceConfig?.datasources?.[name];
    const probe = datasource ? datasourceProbeFromConfig(datasource) : null;
    datasourceProbeSecretFields.value = datasource ? redactedDatasourceProbeFieldsFromConfig(datasource) : [];
    forms.value.datasourceProbeText = prettyJson(probe ?? {});
    datasourceProbeResult.value = null;
  }

  async function saveModels() {
    savingModels.value = true;
    try {
      const target = targetModelConfig(forms.value.target);
      if (!target) {
        toast.error("请选择默认模型");
        return;
      }
      await configApi.updateModels(connection.effectiveBase(), {
        models: modelConfigs.value,
        target,
      });
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

  async function saveTargetModel() {
    savingModels.value = true;
    try {
      const target = targetModelConfig(forms.value.target);
      if (!target) {
        toast.error("请选择默认模型");
        return;
      }
      await configApi.updateModels(connection.effectiveBase(), { target });
      await loadConfiguration();
      await connection.checkConnection();
      toast.success("默认模型已保存");
    } catch (err) {
      console.error("保存默认模型失败:", err);
      toast.error("保存默认模型失败");
    } finally {
      savingModels.value = false;
    }
  }

  async function saveProviders() {
    savingProviders.value = true;
    try {
      await configApi.updateModels(connection.effectiveBase(), {
        providers: providerConfigs.value,
      });
      await loadConfiguration();
      await connection.checkConnection();
      toast.success("Provider 凭据已保存");
    } catch (err) {
      console.error("保存 Provider 凭据失败:", err);
      toast.error("保存 Provider 凭据失败");
    } finally {
      savingProviders.value = false;
    }
  }

  async function saveDatasources() {
    savingDatasources.value = true;
    try {
      await configApi.updateDatasources(connection.effectiveBase(), datasourceConfigs.value);
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

  function replaceModelConfigs(models: ModelConfigMap) {
    modelConfigs.value = structuredClone(models);
    forms.value.modelsText = prettyJson(modelConfigs.value);
    if (forms.value.target.startsWith("custom/")) {
      const selectedCustom = forms.value.target.slice("custom/".length);
      if (!modelConfigs.value[selectedCustom]) {
        forms.value.target = firstAvailableTargetRef(modelsData.value, modelConfigs.value);
      }
    }
  }

  function replaceProviderConfigs(providers: ProviderConfigMap) {
    providerConfigs.value = structuredClone(providers);
  }

  function replaceDatasourceConfigs(datasources: DatasourceConfigMap) {
    datasourceConfigs.value = structuredClone(datasources);
    forms.value.datasourcesText = prettyJson(datasourceConfigs.value);
    if (!datasourceConfigs.value[selectedDatasourceName.value]) {
      selectDatasourceForProbe(Object.keys(datasourceConfigs.value)[0] ?? "");
    }
  }

  function applyModelsJson() {
    try {
      replaceModelConfigs(parseConfigMap(forms.value.modelsText, "models"));
      toast.success("模型 JSON 已应用");
      return true;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "模型配置 JSON 无效");
      return false;
    }
  }

  function applyDatasourcesJson() {
    try {
      replaceDatasourceConfigs(parseConfigMap(forms.value.datasourcesText, "datasources"));
      toast.success("数据源 JSON 已应用");
      return true;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "数据源配置 JSON 无效");
      return false;
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

  async function testSavedModel(key: string, probe: SavedModelProbeInput) {
    if (testingSavedModels.value.includes(key)) return;
    testingSavedModels.value = [...testingSavedModels.value, key];
    try {
      const result = await configApi.testSavedModel(connection.effectiveBase(), probe);
      savedModelProbeResults.value = {
        ...savedModelProbeResults.value,
        [key]: normalizeProbeResult(result),
      };
    } catch (err) {
      console.error("检测已保存模型配置失败:", err);
      savedModelProbeResults.value = {
        ...savedModelProbeResults.value,
        [key]: { ok: false, message: DEFAULT_PROBE_FAILURE },
      };
      toast.error("模型连接检测失败");
    } finally {
      testingSavedModels.value = testingSavedModels.value.filter((item) => item !== key);
    }
  }

  function testProviderConfig(provider: string, model: string) {
    return testSavedModel(`provider:${provider}`, { provider, model });
  }

  function testCustomModel(name: string) {
    return testSavedModel(`custom:${name}`, { custom: name });
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

    const maskedFields = maskedProbeSecretFields(probe);
    if (maskedFields.length > 0) {
      const message = `请先填写真实密钥字段，不能使用脱敏值：${maskedFields.join(", ")}`;
      datasourceProbeResult.value = { ok: false, message };
      toast.error(message);
      return;
    }

    const missingSecretFields = datasourceProbeSecretFields.value.filter((field) => {
      const value = probe[field];
      return value == null || (typeof value === "string" && !value.trim());
    });
    if (missingSecretFields.length > 0) {
      const message = `请先填写真实密钥字段：${missingSecretFields.join(", ")}`;
      datasourceProbeResult.value = { ok: false, message };
      toast.error(message);
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

  async function testSavedDatasource(name: string) {
    if (testingSavedDatasources.value.includes(name)) return;
    testingSavedDatasources.value = [...testingSavedDatasources.value, name];
    try {
      const result = await configApi.testSavedDatasource(connection.effectiveBase(), name);
      savedDatasourceProbeResults.value = {
        ...savedDatasourceProbeResults.value,
        [name]: normalizeProbeResult(result),
      };
    } catch (err) {
      console.error("检测已保存数据源失败:", err);
      savedDatasourceProbeResults.value = {
        ...savedDatasourceProbeResults.value,
        [name]: { ok: false, message: DEFAULT_PROBE_FAILURE },
      };
      toast.error("数据源连接检测失败");
    } finally {
      testingSavedDatasources.value = testingSavedDatasources.value.filter(item => item !== name);
    }
  }

  return {
    loading,
    savingProviders,
    savingModels,
    savingDatasources,
    testingModel,
    testingDatasource,
    config,
    modelsData,
    providerConfigs,
    modelConfigs,
    datasourceConfigs,
    modelProbe,
    forms,
    selectedDatasourceName,
    modelProbeResult,
    savedModelProbeResults,
    testingSavedModels,
    datasourceProbeResult,
    savedDatasourceProbeResults,
    testingSavedDatasources,
    datasourceProbeSecretFields,
    configuredModelEntries,
    configuredDatasourceEntries,
    availableModels,
    embeddingModelNames,
    providerCount,
    currentTarget,
    loadConfiguration,
    selectDatasourceForProbe,
    replaceProviderConfigs,
    replaceModelConfigs,
    replaceDatasourceConfigs,
    applyModelsJson,
    applyDatasourcesJson,
    saveProviders,
    saveTargetModel,
    saveModels,
    saveDatasources,
    testModelProbe,
    testProviderConfig,
    testCustomModel,
    testDatasourceProbe,
    testSavedDatasource,
  };
}

export const configurationManagerInternals = {
  parseConfigMap,
  normalizeProbeResult,
  modelProbeFromTarget,
  datasourceProbeFromConfig,
  maskedProbeSecretFields,
  redactedDatasourceProbeFieldsFromConfig,
  targetModelRef,
  targetModelConfig,
};
