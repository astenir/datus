import { beforeEach, describe, expect, it, vi } from "vitest";

const listDatasources = vi.fn();
const listGrants = vi.fn();
const getGrant = vi.fn();
const upsertGrant = vi.fn();
const deleteGrant = vi.fn();
const listQuotas = vi.fn();
const upsertQuota = vi.fn();
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

vi.mock("@/lib/api", () => ({
  adminDatasourceApi: {
    listDatasources,
    listGrants,
    getGrant,
    upsertGrant,
    deleteGrant,
  },
  adminQuotaApi: {
    listQuotas,
    upsertQuota,
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

const grant = {
  subject_type: "role",
  subject_id: "analyst",
  datasource_key: "fund",
  effect: "allow",
  scope: { schemas: ["public"] },
  created_at: null,
  updated_at: null,
};

const secret = {
  name: "openai.default",
  provider: "env",
  ref_hint: "OPENAI_API_KEY",
  description: "默认 OpenAI 凭据",
  enabled: true,
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
    listSecrets.mockResolvedValue({ data: [secret] });
    getSecret.mockResolvedValue({ data: secret });
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

    await overview.saveGrant();

    expect(upsertGrant).toHaveBeenCalledWith("role", "analyst", "fund", {
      effect: "allow",
      scope: { schemas: ["public"] },
    });
    expect(listDatasources).toHaveBeenCalled();
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

    await overview.saveGrant();

    expect(upsertGrant).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("Scope 必须是 JSON 对象");
  });

  it("saves quotas with numeric limits and nullable subject ids", async () => {
    const { useAdminOverview } = await import("./useAdminOverview");
    const overview = useAdminOverview();
    overview.quotaForm.value = {
      subject_type: "project",
      subject_id: "",
      resource: "chat_tokens",
      limit: 5000,
      window_seconds: 3600,
      enabled: true,
    };

    await overview.saveQuota();

    expect(upsertQuota).toHaveBeenCalledWith({
      subject_type: "project",
      subject_id: null,
      resource: "chat_tokens",
      limit: 5000,
      window_seconds: 3600,
      enabled: true,
    });
  });

  it("loads secret detail into the edit form", async () => {
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
      reference: "OPENAI_API_KEY",
      description: "默认 OpenAI 凭据",
      enabled: true,
    });
    expect(overview.secretDetailError.value).toBeNull();

    overview.closeSecretDialog();

    expect(overview.showSecretDialog.value).toBe(false);
    expect(overview.selectedSecretName.value).toBeNull();
    expect(overview.editingSecret.value).toBeNull();
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
      allowed_roles_text: "analyst",
      allowed_user_ids_text: "bob",
      datasources_text: "fund",
    });

    overview.artifactAclForm.value.allowed_roles_text = "analyst, admin";
    overview.artifactAclForm.value.allowed_user_ids_text = "bob, charlie";

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
