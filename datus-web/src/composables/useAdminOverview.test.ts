import { beforeEach, describe, expect, it, vi } from "vitest";

const listDatasources = vi.fn();
const listGrants = vi.fn();
const getGrant = vi.fn();
const upsertGrant = vi.fn();
const deleteGrant = vi.fn();
const listQuotas = vi.fn();
const upsertQuota = vi.fn();
const listUsage = vi.fn();
const listSessions = vi.fn();
const getSession = vi.fn();
const stopSession = vi.fn();
const deleteSession = vi.fn();
const listArtifacts = vi.fn();
const getAcl = vi.fn();
const putAcl = vi.fn();
const toastError = vi.fn();
const listCatalog = vi.fn();

vi.mock("@/lib/api", () => ({
  adminDatasourceApi: {
    listDatasources,
    listGrants,
    getGrant,
    upsertGrant,
    deleteGrant,
  },
  catalogApi: {
    list: listCatalog,
  },
  adminQuotaApi: {
    listQuotas,
    upsertQuota,
    listUsage,
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

describe("useAdminOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listDatasources.mockResolvedValue({ data: [{ name: "fund", type: "postgres", is_default: true }] });
    listGrants.mockResolvedValue({ data: [grant] });
    getGrant.mockResolvedValue({ data: grant });
    listQuotas.mockResolvedValue({ data: [] });
    listUsage.mockResolvedValue({ data: [] });
    listSessions.mockResolvedValue({ data: [] });
    getSession.mockResolvedValue({
      data: {
        session_id: "session-1",
        owner_user_id: "alice",
        status: "running",
        is_running: true,
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
    listCatalog.mockResolvedValue({
      databases: [
        {
          name: "analytics",
          type: "postgres",
          schema_name: "public",
          tables: ["orders", "accounts"],
        },
      ],
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
    expect(listSessions).toHaveBeenCalled();
    expect(listArtifacts).toHaveBeenCalled();
    expect(overview.defaultDatasourceName.value).toBe("fund");
    expect(overview.data.value.datasourceGrants).toEqual([grant]);
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
        databases: [],
        schemas: [],
        tables: ["analytics.public.orders"],
      },
    });
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
        databases: [],
        schemas: [],
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
        databases: [],
        schemas: ["analytics.public"],
        tables: [],
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

  it("routes session stop and delete actions through admin session APIs", async () => {
    const session = {
      session_id: "session-1",
      owner_user_id: "alice",
      status: "running",
      is_running: true,
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
