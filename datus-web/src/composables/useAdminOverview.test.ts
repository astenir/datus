import { beforeEach, describe, expect, it, vi } from "vitest";

const listDatasources = vi.fn();
const listAdminCatalog = vi.fn();
const listGrants = vi.fn();
const getGrant = vi.fn();
const upsertGrant = vi.fn();
const deleteGrant = vi.fn();
const listQuotas = vi.fn();
const upsertQuota = vi.fn();
const deleteQuota = vi.fn();
const listUsage = vi.fn();
const listSecrets = vi.fn();
const getSecret = vi.fn();
const upsertSecret = vi.fn();
const deleteSecret = vi.fn();
const listSessions = vi.fn();
const getSession = vi.fn();
const stopSession = vi.fn();
const deleteSession = vi.fn();
const listArtifacts = vi.fn();
const getAcl = vi.fn();
const putAcl = vi.fn();
const toastError = vi.fn();
const fetchPermissions = vi.fn();
const grantedPermissions = new Set<string>();

function permissionMatches(required: string, granted: string): boolean {
  if (granted === "*" || granted === required) return true;
  const pattern = granted
    .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*");
  return new RegExp(`^${pattern}$`).test(required);
}

vi.mock("@/lib/api", () => ({
  adminDatasourceApi: {
    listDatasources,
    listCatalog: listAdminCatalog,
    listGrants,
    getGrant,
    upsertGrant,
    deleteGrant,
  },
  adminQuotaApi: {
    listQuotas,
    upsertQuota,
    deleteQuota,
    listUsage,
  },
  adminSecretApi: {
    listSecrets,
    getSecret,
    upsertSecret,
    deleteSecret,
  },
  adminSessionApi: {
    listSessions,
    getSession,
    stopSession,
    deleteSession,
  },
  adminArtifactApi: {
    listArtifacts,
    getAcl,
    putAcl,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

vi.mock("@/composables/usePermission", () => ({
  usePermission: () => ({
    isLoaded: { value: true },
    fetchPermissions,
    hasPermission: (permissionCode: string) =>
      [...grantedPermissions].some((permission) => permissionMatches(permissionCode, permission)),
  }),
}));

const grant = {
  subject_type: "role",
  subject_id: "analyst",
  datasource_key: "fund",
  effect: "allow",
  scope: { schemas: ["public"] },
  created_at: null,
  updated_at: null,
};

const artifact = {
  artifact_type: "dashboard",
  manifest: {
    slug: "fund-overview",
    name: "基金概览",
    datasources: ["fund"],
    created_at: null,
    updated_at: null,
  },
};

const artifactAcl = {
  owner_user_id: "alice",
  visibility: "role",
  allowed_roles: ["analyst"],
  allowed_user_ids: ["bob"],
  datasources: ["fund"],
};

const secret = {
  name: "openai.default",
  provider: "env",
  ref_hint: "***KEY",
  description: "默认 OpenAI 密钥引用",
  enabled: true,
  created_at: null,
  updated_at: null,
};

describe("useAdminOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    grantedPermissions.clear();
    grantedPermissions.add("module.admin.datasources");
    grantedPermissions.add("module.admin.quotas");
    grantedPermissions.add("module.admin.secrets");
    grantedPermissions.add("module.admin.sessions");
    grantedPermissions.add("module.admin.artifacts");
    listDatasources.mockResolvedValue({ data: [{ name: "fund", type: "postgres", is_default: true }] });
    listGrants.mockResolvedValue({ data: [grant] });
    getGrant.mockResolvedValue({ data: grant });
    listQuotas.mockResolvedValue({ data: [] });
    deleteQuota.mockResolvedValue({ data: { deleted: true } });
    listUsage.mockResolvedValue({ data: [] });
    listSecrets.mockResolvedValue({ data: [secret] });
    getSecret.mockResolvedValue({ data: secret });
    upsertSecret.mockResolvedValue({ data: secret });
    deleteSecret.mockResolvedValue({ data: {} });
    listSessions.mockResolvedValue({ data: [] });
    getSession.mockResolvedValue({
      data: {
        session_id: "session-1",
        owner_user_id: "alice",
        status: "running",
        is_running: true,
        runtime_snapshot_available: true,
        created_at: null,
        updated_at: null,
        event_count: 3,
        exists_on_disk: true,
        consumer_offset: 2,
        error: null,
      },
    });
    listArtifacts.mockResolvedValue({ data: [artifact] });
    getAcl.mockResolvedValue({ data: artifactAcl });
    putAcl.mockResolvedValue({ data: artifactAcl });
    listAdminCatalog.mockResolvedValue({
      success: true,
      data: {
        databases: [
          {
            name: "analytics",
            type: "postgres",
            schema_name: "public",
            tables: ["orders", "accounts"],
          },
        ],
      },
    });
  });

  it("loads the enterprise admin overview resources together", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.loadOverview();

    expect(listDatasources).toHaveBeenCalled();
    expect(listGrants).toHaveBeenCalled();
    expect(listQuotas).toHaveBeenCalled();
    expect(listUsage).toHaveBeenCalled();
    expect(listSecrets).toHaveBeenCalled();
    expect(listSessions).toHaveBeenCalled();
    expect(listArtifacts).toHaveBeenCalled();
    expect(overview.defaultDatasourceName.value).toBe("fund");
    expect(overview.data.value.datasourceGrants).toEqual([grant]);
    expect(overview.data.value.secrets).toEqual([secret]);
  });

  it("skips optional admin overview APIs without matching permissions", async () => {
    grantedPermissions.clear();
    grantedPermissions.add("module.admin.users");
    grantedPermissions.add("module.admin.roles");
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.loadOverview();

    expect(listDatasources).not.toHaveBeenCalled();
    expect(listGrants).not.toHaveBeenCalled();
    expect(listQuotas).not.toHaveBeenCalled();
    expect(listUsage).not.toHaveBeenCalled();
    expect(listSecrets).not.toHaveBeenCalled();
    expect(listSessions).not.toHaveBeenCalled();
    expect(listArtifacts).not.toHaveBeenCalled();
    expect(overview.data.value).toEqual({
      datasources: [],
      datasourceGrants: [],
      quotas: [],
      usage: [],
      secrets: [],
      sessions: [],
      artifacts: [],
    });

    await overview.loadDatasourceGrants();
    await overview.loadQuotasAndUsage();
    await overview.loadSessions();
    await overview.loadSecrets();
    await overview.loadArtifacts();

    expect(listDatasources).not.toHaveBeenCalled();
    expect(listGrants).not.toHaveBeenCalled();
    expect(listQuotas).not.toHaveBeenCalled();
    expect(listUsage).not.toHaveBeenCalled();
    expect(listSecrets).not.toHaveBeenCalled();
    expect(listSessions).not.toHaveBeenCalled();
    expect(listArtifacts).not.toHaveBeenCalled();
  });

  it("refreshes focused overview slices without overfetching unrelated tab data", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    await overview.loadOverview();

    const nextGrant = { ...grant, subject_id: "operator" };
    const nextQuota = {
      subject_type: "user",
      subject_id: "alice",
      resource: "chat.stream",
      limit: 10,
      window_seconds: 60,
      enabled: true,
      created_at: null,
      updated_at: null,
    };
    const nextUsage = {
      subject_type: "user",
      subject_id: "alice",
      resource: "chat.stream",
      used: 3,
      window_seconds: 60,
      reset_at: null,
    };
    const nextSession = {
      session_id: "session-2",
      owner_user_id: "bob",
      status: "idle",
      is_running: false,
      runtime_snapshot_available: true,
      created_at: null,
      updated_at: null,
      event_count: 1,
    };
    const nextArtifact = {
      ...artifact,
      manifest: {
        ...artifact.manifest,
        slug: "risk-report",
      },
    };
    const nextSecret = {
      ...secret,
      name: "deepseek.default",
    };

    vi.clearAllMocks();
    listDatasources.mockResolvedValue({ data: [{ name: "risk", type: "postgres", is_default: false }] });
    listGrants.mockResolvedValue({ data: [nextGrant] });
    listQuotas.mockResolvedValue({ data: [nextQuota] });
    listUsage.mockResolvedValue({ data: [nextUsage] });
    listSecrets.mockResolvedValue({ data: [nextSecret] });
    listSessions.mockResolvedValue({ data: [nextSession] });
    listArtifacts.mockResolvedValue({ data: [nextArtifact] });

    await overview.loadDatasourceGrants();

    expect(listDatasources).toHaveBeenCalledTimes(1);
    expect(listGrants).toHaveBeenCalledTimes(1);
    expect(listQuotas).not.toHaveBeenCalled();
    expect(listSecrets).not.toHaveBeenCalled();
    expect(listSessions).not.toHaveBeenCalled();
    expect(listArtifacts).not.toHaveBeenCalled();
    expect(overview.data.value.datasourceGrants).toEqual([nextGrant]);
    expect(overview.data.value.artifacts).toEqual([artifact]);

    vi.clearAllMocks();

    await overview.loadQuotasAndUsage();

    expect(listQuotas).toHaveBeenCalledTimes(1);
    expect(listUsage).toHaveBeenCalledTimes(1);
    expect(listDatasources).not.toHaveBeenCalled();
    expect(listGrants).not.toHaveBeenCalled();
    expect(listSecrets).not.toHaveBeenCalled();
    expect(overview.data.value.quotas).toEqual([nextQuota]);
    expect(overview.data.value.usage).toEqual([nextUsage]);
    expect(overview.data.value.datasourceGrants).toEqual([nextGrant]);

    vi.clearAllMocks();

    await overview.loadSessions();

    expect(listSessions).toHaveBeenCalledTimes(1);
    expect(listQuotas).not.toHaveBeenCalled();
    expect(listSecrets).not.toHaveBeenCalled();
    expect(listArtifacts).not.toHaveBeenCalled();
    expect(overview.data.value.sessions).toEqual([nextSession]);
    expect(overview.data.value.quotas).toEqual([nextQuota]);

    vi.clearAllMocks();

    await overview.loadSecrets();

    expect(listSecrets).toHaveBeenCalledTimes(1);
    expect(listSessions).not.toHaveBeenCalled();
    expect(listGrants).not.toHaveBeenCalled();
    expect(overview.data.value.secrets).toEqual([nextSecret]);
    expect(overview.data.value.sessions).toEqual([nextSession]);

    vi.clearAllMocks();

    await overview.loadArtifacts();

    expect(listArtifacts).toHaveBeenCalledTimes(1);
    expect(listSessions).not.toHaveBeenCalled();
    expect(listGrants).not.toHaveBeenCalled();
    expect(overview.data.value.artifacts).toEqual([nextArtifact]);
    expect(overview.data.value.sessions).toEqual([nextSession]);
  });

  it("saves datasource grants with parsed scope JSON", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.grantForm.value = {
      subject_type: "role",
      subject_id: "analyst",
      datasource_key: "fund",
      effect: "allow",
      scope_text: "{\"schemas\":[\"public\"]}",
    };
    overview.setGrantScopeMode("json");

    await overview.saveGrant();

    expect(upsertGrant).toHaveBeenCalledWith("role", "analyst", "fund", {
      effect: "allow",
      scope: { schemas: ["public"] },
    });
    expect(listDatasources).toHaveBeenCalled();
  });

  it("saves datasource grants from selected catalog nodes", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.grantForm.value = {
      subject_type: "role",
      subject_id: "analyst",
      datasource_key: "fund",
      effect: "allow",
      scope_text: "{}",
    };
    overview.setGrantScopeMode("picker");
    overview.toggleGrantNode("table:fund:analytics:public:orders");

    await overview.saveGrant();

    expect(upsertGrant).toHaveBeenCalledWith("role", "analyst", "fund", {
      effect: "allow",
      scope: {
        tables: ["analytics.public.orders"],
      },
    });
  });

  it("loads grant picker catalog through the admin datasource API", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.loadGrantCatalog("fund");

    expect(listAdminCatalog).toHaveBeenCalledWith("fund");
    expect(overview.grantCatalogDatabases.value).toEqual([
      {
        datasourceName: "fund",
        name: "analytics",
        type: "postgres",
        catalogName: undefined,
        schemaName: "public",
        tables: ["orders", "accounts"],
      },
    ]);
  });

  it("surfaces catalog timeout responses both inline and as a toast", async () => {
    listAdminCatalog.mockResolvedValueOnce({
      success: false,
      errorCode: "REQUEST_TIMEOUT",
      errorMessage: "Datasource query timed out.",
    });
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.loadGrantCatalog("fund");

    expect(overview.grantCatalogError.value).toBe("数据源目录加载超时，请稍后重试");
    expect(overview.grantCatalogDatabases.value).toEqual([]);
    expect(toastError).toHaveBeenCalledWith("数据源目录加载超时，请稍后重试");
    expect(overview.loadingGrantCatalog.value).toBe(false);
  });

  it("does not expose unknown catalog backend errors", async () => {
    listAdminCatalog.mockResolvedValueOnce({
      success: false,
      errorCode: "INTERNAL_ERROR",
      errorMessage: "RuntimeError: https://db.private failed at /srv/catalog.py",
    });
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.loadGrantCatalog("fund");

    expect(overview.grantCatalogError.value).toBe("加载数据源目录失败");
    expect(toastError).toHaveBeenCalledWith("加载数据源目录失败");
    expect(JSON.stringify(toastError.mock.calls)).not.toContain("db.private");
  });

  it("surfaces rejected catalog requests both inline and as a toast", async () => {
    listAdminCatalog.mockRejectedValueOnce(new Error("upstream timeout"));
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.loadGrantCatalog("fund");

    expect(overview.grantCatalogError.value).toBe("数据源目录加载超时，请稍后重试");
    expect(toastError).toHaveBeenCalledWith("数据源目录加载超时，请稍后重试");
    expect(overview.loadingGrantCatalog.value).toBe(false);
  });

  it("narrows an inherited parent selection when a child node is selected", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.grantForm.value = {
      subject_type: "role",
      subject_id: "analyst",
      datasource_key: "fund",
      effect: "allow",
      scope_text: "{}",
    };
    overview.setGrantScopeMode("picker");
    await overview.loadGrantCatalog("fund");

    overview.toggleGrantNode("schema:fund:analytics:public");
    overview.toggleGrantNode("table:fund:analytics:public:orders");

    expect(overview.selectedGrantNodes.value).toEqual(["table:fund:analytics:public:orders"]);

    await overview.saveGrant();

    expect(upsertGrant).toHaveBeenCalledWith("role", "analyst", "fund", {
      effect: "allow",
      scope: {
        tables: ["analytics.public.orders"],
      },
    });
  });

  it("promotes child selections into the selected parent node", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.grantForm.value = {
      subject_type: "role",
      subject_id: "analyst",
      datasource_key: "fund",
      effect: "allow",
      scope_text: "{}",
    };
    overview.setGrantScopeMode("picker");
    await overview.loadGrantCatalog("fund");

    overview.toggleGrantNode("table:fund:analytics:public:orders");
    overview.toggleGrantNode("schema:fund:analytics:public");

    expect(overview.selectedGrantNodes.value).toEqual(["schema:fund:analytics:public"]);

    await overview.saveGrant();

    expect(upsertGrant).toHaveBeenCalledWith("role", "analyst", "fund", {
      effect: "allow",
      scope: {
        schemas: ["analytics.public"],
      },
    });
  });

  it("loads datasource grant detail into the edit form", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    const detailPromise = overview.openGrantDetail(" role ", " analyst ", " fund ");

    expect(overview.showGrantDialog.value).toBe(true);
    expect(overview.selectedGrantRouteKey.value).toBe("role:analyst:fund");
    expect(overview.loadingGrantDetail.value).toBe(true);

    await detailPromise;

    expect(getGrant).toHaveBeenCalledWith("role", "analyst", "fund");
    expect(overview.editingGrant.value).toEqual(grant);
    expect(overview.grantForm.value).toEqual({
      subject_type: "role",
      subject_id: "analyst",
      datasource_key: "fund",
      effect: "allow",
      scope_text: "{\n  \"schemas\": [\n    \"public\"\n  ]\n}",
    });
    expect(overview.grantScopeMode.value).toBe("picker");
    expect(overview.grantDetailError.value).toBeNull();

    overview.closeGrantDialog();

    expect(overview.showGrantDialog.value).toBe(false);
    expect(overview.selectedGrantRouteKey.value).toBeNull();
    expect(overview.editingGrant.value).toBeNull();
  });

  it("does not request the runtime catalog for wildcard datasource grants", async () => {
    const wildcardGrant = {
      ...grant,
      datasource_key: "*",
      scope: { schemas: ["public"] },
    };
    getGrant.mockResolvedValueOnce({ data: wildcardGrant });

    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.openGrantDetail("role", "analyst", "*");

    expect(getGrant).toHaveBeenCalledWith("role", "analyst", "*");
    expect(listAdminCatalog).not.toHaveBeenCalled();
    expect(overview.grantForm.value.datasource_key).toBe("*");
    expect(overview.grantScopeMode.value).toBe("json");
    expect(overview.grantCatalogError.value).toBeNull();
  });

  it("keeps wildcard datasource grants out of picker mode", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.grantForm.value = {
      subject_type: "role",
      subject_id: "analyst",
      datasource_key: "*",
      effect: "allow",
      scope_text: "{}",
    };

    overview.setGrantScopeMode("picker");

    expect(overview.grantScopeMode.value).toBe("all");
    expect(listAdminCatalog).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("通配数据源 * 不支持目录选择器，请使用整个数据源或 JSON 范围");
  });

  it("rejects invalid datasource grant scope JSON before calling the API", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.grantForm.value = {
      subject_type: "role",
      subject_id: "analyst",
      datasource_key: "fund",
      effect: "allow",
      scope_text: "[]",
    };
    overview.setGrantScopeMode("json");

    await overview.saveGrant();

    expect(upsertGrant).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("Scope 必须是 JSON 对象");
  });

  it("saves quotas with selected subjects and supported resources", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.quotaForm.value = {
      subject_type: "role",
      subject_id: "analyst",
      resource: "chat.stream",
      limit: 5000,
      window_seconds: 3600,
      enabled: true,
    };

    await overview.saveQuota();

    expect(upsertQuota).toHaveBeenCalledWith({
      subject_type: "role",
      subject_id: "analyst",
      resource: "chat.stream",
      limit: 5000,
      window_seconds: 3600,
      enabled: true,
    });
  });

  it("saves edited quotas with the selected enabled state", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.openEditQuotaDialog({
      subject_type: "user",
      subject_id: "alice",
      resource: "chat.stream",
      limit: 5000,
      window_seconds: 3600,
      enabled: true,
      created_at: null,
      updated_at: null,
    });
    overview.setQuotaEnabled(false);

    await overview.saveQuota();

    expect(upsertQuota).toHaveBeenCalledWith({
      subject_type: "user",
      subject_id: "alice",
      resource: "chat.stream",
      limit: 5000,
      window_seconds: 3600,
      enabled: false,
    });
  });

  it("saves global quotas with wildcard subject id", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.setQuotaSubjectType("global");
    overview.setQuotaResource("sql.execute");
    overview.quotaForm.value.limit = 50;
    overview.quotaForm.value.window_seconds = 86400;

    await overview.saveQuota();

    expect(upsertQuota).toHaveBeenCalledWith({
      subject_type: "global",
      subject_id: "*",
      resource: "sql.execute",
      limit: 50,
      window_seconds: 86400,
      enabled: true,
    });
  });

  it("rejects quota resources that are not consumed by the backend", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.quotaForm.value = {
      subject_type: "user",
      subject_id: "alice",
      resource: "chat_tokens",
      limit: 5000,
      window_seconds: 3600,
      enabled: true,
    };

    await overview.saveQuota();

    expect(upsertQuota).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("请填写有效的额度主体、资源、限制和窗口");
  });

  it("deletes quota records by their subject and resource identity", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.deleteQuota({
      subject_type: "global",
      subject_id: "*",
      resource: "chat.stream",
      limit: 5000,
      window_seconds: 3600,
      enabled: false,
      created_at: null,
      updated_at: null,
    });

    expect(deleteQuota).toHaveBeenCalledWith({
      subject_type: "global",
      subject_id: "*",
      resource: "chat.stream",
    });
    expect(listQuotas).toHaveBeenCalledWith({ limit: 20, offset: 0 });
    expect(listUsage).toHaveBeenCalledWith({ search: undefined, limit: 100, offset: 0 });
  });

  it("loads and saves secret reference details without exposing plaintext values", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    const detailPromise = overview.openSecretDetail(" openai.default ");

    expect(overview.showSecretDialog.value).toBe(true);
    expect(overview.selectedSecretName.value).toBe("openai.default");
    expect(overview.loadingSecretDetail.value).toBe(true);

    await detailPromise;

    expect(getSecret).toHaveBeenCalledWith("openai.default");
    expect(overview.editingSecret.value).toEqual(secret);
    expect(overview.secretForm.value).toEqual({
      name: "openai.default",
      provider: "env",
      reference: "",
      description: "默认 OpenAI 密钥引用",
      enabled: true,
    });

    overview.secretForm.value.reference = "OPENAI_API_KEY_NEXT";
    overview.secretForm.value.description = "更新后的引用";
    overview.secretForm.value.enabled = false;

    await overview.saveSecret();

    expect(upsertSecret).toHaveBeenCalledWith("openai.default", {
      provider: "env",
      reference: "OPENAI_API_KEY_NEXT",
      description: "更新后的引用",
      enabled: false,
    });
    expect(overview.showSecretDialog.value).toBe(false);
    expect(overview.selectedSecretName.value).toBeNull();
  });

  it("routes secret deletion through the admin secret API", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.deleteSecret(secret);

    expect(deleteSecret).toHaveBeenCalledWith("openai.default");
    expect(overview.deletingSecretName.value).toBeNull();
  });

  it("routes session stop and delete actions through admin session APIs", async () => {
    const session = {
      session_id: "session-1",
      owner_user_id: "alice",
      status: "running",
      is_running: true,
      runtime_snapshot_available: true,
      created_at: null,
      updated_at: null,
      event_count: 3,
      exists_on_disk: true,
    };
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.stopSession(session);
    await overview.deleteSession(session);

    expect(stopSession).toHaveBeenCalledWith("session-1");
    expect(deleteSession).toHaveBeenCalledWith("session-1");
  });

  it("loads and resets admin session detail state", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    const detailPromise = overview.openSessionDetail(" session-1 ");

    expect(overview.showSessionDetailDialog.value).toBe(true);
    expect(overview.selectedSessionDetailId.value).toBe("session-1");

    await detailPromise;

    expect(getSession).toHaveBeenCalledWith("session-1");
    expect(overview.selectedSessionDetail.value?.session_id).toBe("session-1");
    expect(overview.sessionDetailError.value).toBeNull();

    overview.closeSessionDetail();

    expect(overview.showSessionDetailDialog.value).toBe(false);
    expect(overview.selectedSessionDetailId.value).toBeNull();
    expect(overview.selectedSessionDetail.value).toBeNull();
  });

  it("loads artifact ACL details from a route target and saves through the selected target", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();

    await overview.loadOverview();
    const detailPromise = overview.openArtifactAclDetail("dashboard", " fund-overview ");

    expect(overview.showArtifactAclDialog.value).toBe(true);
    expect(overview.selectedArtifactAclKey.value).toBe("dashboard:fund-overview");
    expect(overview.loadingArtifactAcl.value).toBe(true);

    await detailPromise;

    expect(getAcl).toHaveBeenCalledWith("dashboard", "fund-overview");
    expect(overview.editingArtifact.value).toEqual(artifact);
    expect(overview.editingArtifactAclTarget.value).toEqual({
      artifactType: "dashboard",
      slug: "fund-overview",
    });
    expect(overview.artifactAclForm.value).toEqual({
      owner_user_id: "alice",
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["bob"],
      datasources: ["fund"],
    });

    overview.toggleArtifactAclRole("admin");
    overview.toggleArtifactAclUser("charlie");

    await overview.saveArtifactAcl();

    expect(putAcl).toHaveBeenCalledWith("dashboard", "fund-overview", {
      owner_user_id: "alice",
      visibility: "role",
      allowed_roles: ["analyst", "admin"],
      allowed_user_ids: ["bob", "charlie"],
      datasources: ["fund"],
    });
    expect(overview.showArtifactAclDialog.value).toBe(false);
    expect(overview.selectedArtifactAclKey.value).toBeNull();
  });
});
