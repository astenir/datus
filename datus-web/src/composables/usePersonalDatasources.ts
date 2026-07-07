import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { meApi } from "@/lib/api";
import type {
  ApiResponse,
  PersonalDatasourceProbeResult,
  PersonalDatasourceProviderOptions,
  PersonalDatasourceSummary,
  UpsertPersonalDatasourceInput,
} from "@/types/profile";

export interface PersonalDatasourceForm {
  type: string;
  host: string;
  port: string;
  username: string;
  password: string;
  database: string;
  schema_name: string;
  catalog_name: string;
  display_name: string;
  enabled: boolean;
}

function resultData<T>(response: ApiResponse<T>, fallback: T): T {
  if (!response.success) {
    throw new Error(response.errorMessage || response.errorCode || "请求失败");
  }
  return response.data ?? fallback;
}

function defaultOptions(): PersonalDatasourceProviderOptions {
  return {
    enabled: false,
    allowed_types: [],
    allowed_hosts: [],
    default_ports: {},
  };
}

function defaultForm(type = "", port = ""): PersonalDatasourceForm {
  return {
    type,
    host: "",
    port,
    username: "",
    password: "",
    database: "",
    schema_name: "",
    catalog_name: "",
    display_name: "",
    enabled: true,
  };
}

export function usePersonalDatasources() {
  const loading = shallowRef(false);
  const saving = shallowRef(false);
  const testingId = shallowRef<string | null>(null);
  const error = shallowRef<string | null>(null);
  const options = ref<PersonalDatasourceProviderOptions>(defaultOptions());
  const datasources = ref<PersonalDatasourceSummary[]>([]);
  const form = ref<PersonalDatasourceForm>(defaultForm());

  const enabledDatasources = computed(() => datasources.value.filter(item => item.enabled));
  const typeOptions = computed(() => options.value.allowed_types);
  const hasDatasources = computed(() => datasources.value.length > 0);
  const isEnabled = computed(() => options.value.enabled);

  async function load() {
    loading.value = true;
    error.value = null;
    try {
      const [optionResult, datasourceResult] = await Promise.all([
        meApi.datasourceProviders(),
        meApi.personalDatasources(),
      ]);
      options.value = resultData(optionResult, defaultOptions());
      datasources.value = resultData(datasourceResult, []);
      ensureFormDefaults();
    } catch (err) {
      console.error("加载个人数据源失败:", err);
      error.value = err instanceof Error ? err.message : "加载个人数据源失败";
      toast.error("加载个人数据源失败");
    } finally {
      loading.value = false;
    }
  }

  function startCreate() {
    const type = typeOptions.value[0] ?? "";
    form.value = defaultForm(type, options.value.default_ports[type] ?? "");
  }

  function startEdit(datasource: PersonalDatasourceSummary) {
    form.value = {
      type: datasource.type,
      host: datasource.host,
      port: datasource.port,
      username: datasource.username,
      password: "",
      database: datasource.database,
      schema_name: datasource.schema_name ?? "",
      catalog_name: datasource.catalog_name ?? "",
      display_name: datasource.display_name ?? "",
      enabled: datasource.enabled,
    };
  }

  async function saveDatasource(id?: string) {
    saving.value = true;
    error.value = null;
    try {
      const payload = datasourcePayload();
      const result = id
        ? await meApi.updatePersonalDatasource(id, payload)
        : await meApi.createPersonalDatasource(payload);
      resultData(result, null);
      toast.success(id ? "个人数据源已更新" : "个人数据源已添加");
      await load();
    } catch (err) {
      console.error("保存个人数据源失败:", err);
      error.value = err instanceof Error ? err.message : "保存个人数据源失败";
      toast.error("保存个人数据源失败");
      throw err;
    } finally {
      saving.value = false;
    }
  }

  async function deleteDatasource(id: string) {
    saving.value = true;
    error.value = null;
    try {
      await meApi.deletePersonalDatasource(id);
      toast.success("个人数据源已删除");
      await load();
    } catch (err) {
      console.error("删除个人数据源失败:", err);
      error.value = err instanceof Error ? err.message : "删除个人数据源失败";
      toast.error("删除个人数据源失败");
    } finally {
      saving.value = false;
    }
  }

  async function testDatasource(id: string): Promise<PersonalDatasourceProbeResult | null> {
    testingId.value = id;
    try {
      const result = resultData(await meApi.testPersonalDatasource(id), { ok: false, message: "测试失败" });
      if (result.ok) {
        toast.success("数据源连接可用");
      } else {
        toast.error(result.message || "数据源连接不可用");
      }
      return result;
    } catch (err) {
      console.error("测试个人数据源失败:", err);
      toast.error("测试个人数据源失败");
      return null;
    } finally {
      testingId.value = null;
    }
  }

  function ensureFormDefaults() {
    if (form.value.type && form.value.port) return;
    const type = typeOptions.value[0];
    if (!type) return;
    form.value = defaultForm(type, options.value.default_ports[type] ?? "");
  }

  function setType(type: string) {
    form.value.type = type;
    form.value.port = options.value.default_ports[type] ?? form.value.port;
  }

  function datasourcePayload(): UpsertPersonalDatasourceInput {
    return {
      type: form.value.type,
      host: form.value.host,
      port: form.value.port,
      username: form.value.username,
      password: form.value.password,
      database: form.value.database,
      schema_name: form.value.schema_name || null,
      catalog_name: form.value.catalog_name || null,
      display_name: form.value.display_name || null,
      enabled: form.value.enabled,
    };
  }

  return {
    loading,
    saving,
    testingId,
    error,
    options,
    datasources,
    form,
    enabledDatasources,
    typeOptions,
    hasDatasources,
    isEnabled,
    load,
    startCreate,
    startEdit,
    saveDatasource,
    deleteDatasource,
    testDatasource,
    setType,
  };
}
