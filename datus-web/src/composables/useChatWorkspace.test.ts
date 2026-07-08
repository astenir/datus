import { afterEach, describe, expect, it, vi } from "vitest";

describe("useChatWorkspace", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it("waits for explicit initialization and initializes only once", async () => {
    vi.doMock("vue", async () => {
      const actual = await vi.importActual<typeof import("vue")>("vue");
      return {
        ...actual,
        onBeforeUnmount: vi.fn(),
      };
    });

    const { ref, shallowRef, readonly } = await import("vue");
    const checkConnection = vi.fn(async () => {});
    const loadSessions = vi.fn(async () => {});
    const loadModels = vi.fn(async () => {});
    const loadAgentOptions = vi.fn(async () => [
      { agent_id: "chat", name: "chat", node_class: "chat", status: "published", source: "builtin" },
      { agent_id: "research", name: "Research", node_class: "chat", status: "published", source: "enterprise" },
      { agent_id: "draft_bot", name: "Draft Bot", node_class: "chat", status: "draft", source: "enterprise" },
    ]);
    const loadCatalog = vi.fn(async () => true);
    const loadDatasourceStatuses = vi.fn(async () => true);
    const prewarmDatasource = vi.fn(async () => false);
    const compactSession = vi.fn(async () => ({ session_id: "s1", success: true }));
    const selectSession = vi.fn();
    const sendMessage = vi.fn();

    vi.doMock("@/composables/useTheme", () => ({
      useTheme: () => ({}),
    }));
    vi.doMock("@/composables/useChatSettings", () => ({
      useChatSettings: () => {
        const language = shallowRef("zh");
        const permissionMode = shallowRef("normal");
        const planMode = shallowRef(false);
        return {
          language: readonly(language),
          permissionMode: readonly(permissionMode),
          planMode: readonly(planMode),
          setLanguage: vi.fn(),
          setPermissionMode: vi.fn(),
          setPlanMode: vi.fn(),
        };
      },
    }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({
        apiBase: readonly(shallowRef("")),
        connection: readonly(shallowRef("idle")),
        config: readonly(ref(null)),
        datasourceOptions: readonly(ref([])),
        isTestingDatasource: readonly(shallowRef(false)),
        checkConnection,
        effectiveBase: () => "http://api.test",
        setApiBase: vi.fn(),
        testDatasource: vi.fn(),
        switchDatasource: vi.fn(),
      }),
    }));
    vi.doMock("@/lib/api", () => ({
      agentApi: {
        availableList: loadAgentOptions,
      },
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        isAdmin: vi.fn(() => false),
        hasFeaturePermission: vi.fn(() => false),
        hasDatasourcePermission: vi.fn(() => false),
      }),
    }));
    vi.doMock("@/composables/useChatState", () => ({
      useChatState: () => ({
        messages: readonly(ref([])),
        sessions: readonly(ref([])),
        selectedSession: readonly(shallowRef(null)),
        isStreaming: readonly(shallowRef(false)),
        isLoadingSessions: readonly(shallowRef(false)),
        activeInteractionKey: readonly(shallowRef(null)),
        loadSessions,
        selectSession,
        sendMessage,
        insertMessage: vi.fn(),
        stopSession: vi.fn(),
        deleteSession: vi.fn(),
        compactSession,
        resumeSession: vi.fn(),
        sendInteraction: vi.fn(),
        clearMessages: vi.fn(),
        dispose: vi.fn(),
      }),
    }));
    vi.doMock("@/composables/useModels", () => ({
      useModels: () => ({
        modelOptions: readonly(ref([])),
        defaultModelLabel: readonly(shallowRef("")),
        isLoadingModels: readonly(shallowRef(false)),
        loadModels,
      }),
    }));
    vi.doMock("@/composables/useCatalog", () => ({
      useCatalog: () => ({
        catalogEntries: readonly(ref([])),
        databaseOptions: readonly(ref([])),
        database: shallowRef(""),
        schema: shallowRef(""),
        schemaOptions: readonly(ref([])),
        isLoadingCatalog: readonly(shallowRef(false)),
        datasourceStatuses: readonly(ref({})),
        prewarmingDatasources: readonly(shallowRef(new Set<string>())),
        selectCatalogDatasource: vi.fn(),
        hasCatalogSnapshot: vi.fn(() => false),
        loadCatalog,
        loadDatasourceStatuses,
        prewarmDatasource,
        setDatabase: vi.fn(),
        setSchema: vi.fn(),
      }),
    }));

    const { useChatWorkspace } = await import("./useChatWorkspace");
    const workspace = useChatWorkspace();

    expect(checkConnection).not.toHaveBeenCalled();
    expect(loadSessions).not.toHaveBeenCalled();

    await workspace.initialize();
    await workspace.initialize();

    expect(checkConnection).toHaveBeenCalledTimes(1);
    expect(loadSessions).toHaveBeenCalledTimes(1);
    expect(loadModels).toHaveBeenCalledTimes(1);
    expect(loadAgentOptions).toHaveBeenCalledTimes(1);
    expect(loadCatalog).not.toHaveBeenCalled();
    expect(loadDatasourceStatuses).not.toHaveBeenCalled();
    expect(prewarmDatasource).not.toHaveBeenCalled();
    expect(workspace.agentOptions.value).toEqual([{ value: "research", label: "Research" }]);

    await expect(workspace.compactSession("s1")).resolves.toEqual({ session_id: "s1", success: true });
    expect(compactSession).toHaveBeenCalledWith("s1");

    workspace.startReportEditSession({
      edit_session_id: "edit-1",
      subagent_id: "report_edit__edit_1",
      artifact_type: "report",
      artifact_slug: "fund-report",
      owner_user_id: "alice",
      created_at: "2026-07-08T00:00:00Z",
    });

    expect(workspace.selectedAgent.value).toBe("report_edit__edit_1");
    expect(workspace.agentOptions.value).toEqual([
      { value: "research", label: "Research" },
      { value: "report_edit__edit_1", label: "编辑报表：fund-report" },
    ]);
    expect(selectSession).toHaveBeenCalledWith(null);
    expect(sendMessage).not.toHaveBeenCalled();

    workspace.startArtifactEditSession({
      edit_session_id: "edit-2",
      subagent_id: "dashboard_edit__edit_2",
      artifact_type: "dashboard",
      artifact_slug: "fund-overview",
      owner_user_id: "alice",
      created_at: "2026-07-08T00:00:00Z",
    });

    expect(workspace.selectedAgent.value).toBe("dashboard_edit__edit_2");
    expect(workspace.agentOptions.value).toEqual([
      { value: "research", label: "Research" },
      { value: "dashboard_edit__edit_2", label: "编辑仪表盘：fund-overview" },
    ]);
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("filters datasource switching through current permissions", async () => {
    vi.doMock("vue", async () => {
      const actual = await vi.importActual<typeof import("vue")>("vue");
      return {
        ...actual,
        onBeforeUnmount: vi.fn(),
      };
    });

    const { ref, shallowRef, readonly } = await import("vue");
    const config = ref({
      current_datasource: "fund",
      datasources: {
        fund: { type: "postgres" },
        demo: { type: "sqlite" },
        blocked: { type: "postgres" },
      },
    });
    const datasourceOptions = ref([
      { value: "fund", label: "fund" },
      { value: "demo", label: "demo" },
      { value: "blocked", label: "blocked" },
    ]);
    const switchDatasource = vi.fn();
    const testDatasource = vi.fn();
    const loadAgentOptions = vi.fn(async () => []);
    const loadCatalog = vi.fn(async () => true);
    const loadDatasourceStatuses = vi.fn(async () => true);
    const prewarmDatasource = vi.fn(async () => true);
    const selectCatalogDatasource = vi.fn();
    const setDatabase = vi.fn();
    const setSchema = vi.fn();

    vi.doMock("@/composables/useTheme", () => ({
      useTheme: () => ({}),
    }));
    vi.doMock("@/composables/useChatSettings", () => ({
      useChatSettings: () => {
        const language = shallowRef("zh");
        const permissionMode = shallowRef("normal");
        const planMode = shallowRef(false);
        return {
          language: readonly(language),
          permissionMode: readonly(permissionMode),
          planMode: readonly(planMode),
          setLanguage: vi.fn(),
          setPermissionMode: vi.fn(),
          setPlanMode: vi.fn(),
        };
      },
    }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({
        apiBase: readonly(shallowRef("")),
        connection: readonly(shallowRef("online")),
        config: readonly(config),
        datasourceOptions: readonly(datasourceOptions),
        isTestingDatasource: readonly(shallowRef(false)),
        checkConnection: vi.fn(),
        effectiveBase: () => "http://api.test",
        setApiBase: vi.fn(),
        testDatasource,
        switchDatasource,
      }),
    }));
    vi.doMock("@/lib/api", () => ({
      agentApi: {
        availableList: loadAgentOptions,
      },
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        isAdmin: () => false,
        hasFeaturePermission: (feature: string) => feature === "datasource_catalog",
        hasDatasourcePermission: (name: string) => name !== "blocked",
      }),
    }));
    vi.doMock("@/composables/useChatState", () => ({
      useChatState: () => ({
        messages: readonly(ref([])),
        sessions: readonly(ref([])),
        selectedSession: readonly(shallowRef(null)),
        isStreaming: readonly(shallowRef(false)),
        isLoadingSessions: readonly(shallowRef(false)),
        activeInteractionKey: readonly(shallowRef(null)),
        loadSessions: vi.fn(),
        selectSession: vi.fn(),
        sendMessage: vi.fn(),
        insertMessage: vi.fn(),
        stopSession: vi.fn(),
        deleteSession: vi.fn(),
        compactSession: vi.fn(),
        resumeSession: vi.fn(),
        sendInteraction: vi.fn(),
        clearMessages: vi.fn(),
        dispose: vi.fn(),
      }),
    }));
    vi.doMock("@/composables/useModels", () => ({
      useModels: () => ({
        modelOptions: readonly(ref([])),
        defaultModelLabel: readonly(shallowRef("")),
        isLoadingModels: readonly(shallowRef(false)),
        loadModels: vi.fn(),
      }),
    }));
    vi.doMock("@/composables/useCatalog", () => ({
      useCatalog: () => ({
        catalogEntries: readonly(ref([])),
        databaseOptions: readonly(ref([])),
        database: shallowRef("fund"),
        schema: shallowRef("public"),
        schemaOptions: readonly(ref([])),
        isLoadingCatalog: readonly(shallowRef(false)),
        datasourceStatuses: readonly(ref({})),
        prewarmingDatasources: readonly(shallowRef(new Set<string>())),
        selectCatalogDatasource,
        hasCatalogSnapshot: vi.fn(() => false),
        loadCatalog,
        loadDatasourceStatuses,
        prewarmDatasource,
        setDatabase,
        setSchema,
      }),
    }));

    const { useChatWorkspace } = await import("./useChatWorkspace");
    const workspace = useChatWorkspace();

    expect(workspace.currentDatasource.value).toBe("fund");
    expect(workspace.visibleDatasourceOptions.value).toEqual([
      { value: "fund", label: "fund" },
      { value: "demo", label: "demo" },
    ]);

    await expect(workspace.handleDatasourceSwitch("blocked")).resolves.toBe(false);
    expect(switchDatasource).not.toHaveBeenCalled();

    await expect(workspace.handleDatasourceSwitch("demo")).resolves.toBe(true);
    expect(switchDatasource).not.toHaveBeenCalled();
    expect(selectCatalogDatasource).toHaveBeenCalledWith("demo");
    expect(setDatabase).not.toHaveBeenCalled();
    expect(setSchema).not.toHaveBeenCalled();
    expect(loadDatasourceStatuses).toHaveBeenCalledWith("demo");
    expect(prewarmDatasource).toHaveBeenCalledWith("demo");
    expect(loadCatalog).toHaveBeenCalledWith(undefined, "demo");
    expect(workspace.currentDatasource.value).toBe("demo");

    loadCatalog.mockClear();
    loadDatasourceStatuses.mockClear();
    await expect(workspace.handleDatasourceTest("demo")).resolves.toEqual({ ok: true, message: "连接正常" });
    expect(loadCatalog).toHaveBeenCalledWith(undefined, "demo");
    expect(loadDatasourceStatuses).toHaveBeenCalledWith("demo");
    expect(testDatasource).not.toHaveBeenCalled();
  });
});
