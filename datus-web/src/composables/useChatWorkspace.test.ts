import { afterEach, describe, expect, it, vi } from "vitest";

function mockMeApi() {
  return {
    agentPreference: vi.fn(async () => ({
      success: true,
      data: {
        default_agent_id: "chat",
        source: "builtin_chat",
        user_default_agent_id: null,
        enterprise_default_agent_id: null,
      },
    })),
    updateAgentPreference: vi.fn(async (input: { default_agent_id?: string | null }) => {
      const userDefaultAgentId = input.default_agent_id ?? null;
      return {
        success: true,
        data: {
          default_agent_id: userDefaultAgentId || "chat",
          source: userDefaultAgentId ? "user" : "builtin_chat",
          user_default_agent_id: userDefaultAgentId,
          enterprise_default_agent_id: null,
        },
      };
    }),
  };
}

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
    const initialAgents = [
      { agent_id: "chat", name: "chat", node_class: "chat", status: "published", source: "builtin" },
      { agent_id: "research", name: "Research", node_class: "chat", status: "published", source: "enterprise" },
      { agent_id: "draft_bot", name: "Draft Bot", node_class: "chat", status: "draft", source: "enterprise" },
    ];
    const loadAgentOptions = vi.fn(async () => initialAgents);
    const loadCatalog = vi.fn(async () => true);
    const loadDatasourceStatuses = vi.fn(async () => true);
    const prewarmDatasource = vi.fn(async () => false);
    const compactSession = vi.fn(async () => ({ session_id: "s1", success: true }));
    const selectSession = vi.fn();
    const sendMessage = vi.fn();
    const clearMessages = vi.fn();
    const agentPreference = vi.fn(async () => ({
      success: true,
      data: {
        default_agent_id: "research",
        source: "user",
        user_default_agent_id: "research",
        enterprise_default_agent_id: null,
      },
    }));
    const updateAgentPreference = vi.fn(async (input: { default_agent_id?: string | null }) => {
      const userDefaultAgentId = input.default_agent_id ?? null;
      return {
        success: true,
        data: {
          default_agent_id: userDefaultAgentId || "chat",
          source: userDefaultAgentId ? "user" : "builtin_chat",
          user_default_agent_id: userDefaultAgentId,
          enterprise_default_agent_id: null,
        },
      };
    });

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
      meApi: {
        agentPreference,
        updateAgentPreference,
      },
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        isAdmin: vi.fn(() => false),
        hasPermission: vi.fn((permission: string) => ["module.chat", "module.config.view"].includes(permission)),
        hasViewPermission: vi.fn(() => false),
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
        clearMessages,
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
    expect(workspace.agentOptions.value).toEqual([
      { value: "chat", label: "chat" },
      { value: "research", label: "Research" },
    ]);
    expect(agentPreference).toHaveBeenCalledTimes(1);
    expect(workspace.defaultAgentId.value).toBe("research");
    expect(workspace.userDefaultAgentId.value).toBe("research");
    expect(workspace.selectedAgent.value).toBe("");

    let resolveAgentRefresh: ((value: typeof initialAgents) => void) | undefined;
    loadAgentOptions.mockImplementationOnce(() => new Promise<typeof initialAgents>((resolve) => {
      resolveAgentRefresh = resolve;
    }));

    const firstAgentRefresh = workspace.loadAgentOptions();
    const secondAgentRefresh = workspace.loadAgentOptions();
    expect(loadAgentOptions).toHaveBeenCalledTimes(2);
    expect(workspace.isLoadingAgents.value).toBe(true);

    resolveAgentRefresh?.(initialAgents);
    await Promise.all([firstAgentRefresh, secondAgentRefresh]);
    expect(workspace.isLoadingAgents.value).toBe(false);
    expect(loadAgentOptions).toHaveBeenCalledTimes(2);

    vi.spyOn(console, "error").mockImplementation(() => {});
    loadAgentOptions.mockRejectedValueOnce(new Error("network unavailable"));
    await expect(workspace.loadAgentOptions()).resolves.toBe(false);
    expect(workspace.agentOptions.value).toEqual([
      { value: "chat", label: "chat" },
      { value: "research", label: "Research" },
    ]);

    workspace.startNewSession();
    expect(workspace.selectedAgent.value).toBe("");
    expect(clearMessages).toHaveBeenCalledTimes(1);
    expect(selectSession).toHaveBeenCalledWith(null);

    await expect(workspace.setDefaultAgent("")).resolves.toBe(true);
    expect(updateAgentPreference).toHaveBeenCalledWith({ default_agent_id: null });
    expect(workspace.defaultAgentId.value).toBe("chat");
    expect(workspace.userDefaultAgentId.value).toBe("");
    expect(workspace.selectedAgent.value).toBe("");

    await expect(workspace.setDefaultAgent("chat")).resolves.toBe(true);
    expect(updateAgentPreference).toHaveBeenLastCalledWith({ default_agent_id: "chat" });
    expect(workspace.defaultAgentId.value).toBe("chat");
    expect(workspace.userDefaultAgentId.value).toBe("chat");
    expect(workspace.selectedAgent.value).toBe("chat");

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
      { value: "chat", label: "chat" },
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
      { value: "chat", label: "chat" },
      { value: "research", label: "Research" },
      { value: "dashboard_edit__edit_2", label: "编辑仪表盘：fund-overview" },
    ]);
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("initializes chat-only users without touching config or catalog APIs", async () => {
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
    ]);
    const loadCatalog = vi.fn(async () => true);
    const loadDatasourceStatuses = vi.fn(async () => true);
    const prewarmDatasource = vi.fn(async () => true);

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
      meApi: mockMeApi(),
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        isAdmin: () => false,
        hasPermission: (permission: string) => permission === "module.chat",
        hasViewPermission: (view: string) => view === "chat",
        hasFeaturePermission: () => false,
        hasDatasourcePermission: () => false,
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

    await workspace.initialize();
    workspace.handleRefreshConnection();

    expect(loadSessions).toHaveBeenCalledTimes(1);
    expect(loadAgentOptions).toHaveBeenCalledTimes(1);
    expect(checkConnection).not.toHaveBeenCalled();
    expect(loadModels).toHaveBeenCalledTimes(1);
    expect(loadCatalog).not.toHaveBeenCalled();
    expect(loadDatasourceStatuses).not.toHaveBeenCalled();
    expect(prewarmDatasource).not.toHaveBeenCalled();
  });

  it("lets chat users with datasource grants load scoped chat catalog context", async () => {
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
    const loadAgentOptions = vi.fn(async () => []);
    const loadCatalog = vi.fn(async () => true);
    const loadDatasourceStatuses = vi.fn(async () => true);
    const prewarmDatasource = vi.fn(async () => true);
    const selectCatalogDatasource = vi.fn();

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
      meApi: mockMeApi(),
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        permissions: readonly(ref({
          user_id: "u1",
          features: [],
          views: ["chat"],
          datasources: ["fund"],
          permissions: ["module.chat"],
          datasource_grants: {
            fund: {
              effect: "allow",
              allow_catalog: true,
              schemas: ["public"],
              tables: ["position"],
            },
          },
          is_admin: false,
        })),
        isAdmin: () => false,
        hasPermission: (permission: string) => permission === "module.chat",
        hasViewPermission: (view: string) => view === "chat",
        hasFeaturePermission: () => false,
        hasDatasourcePermission: (name: string) => name === "fund",
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
        selectCatalogDatasource,
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

    await workspace.initialize();
    await workspace.ensureCatalogLoaded();

    expect(workspace.visibleDatasourceOptions.value).toEqual([{ value: "fund", label: "fund" }]);
    expect(workspace.currentDatasource.value).toBe("fund");
    expect(checkConnection).not.toHaveBeenCalled();
    expect(loadModels).toHaveBeenCalledTimes(1);
    expect(loadSessions).toHaveBeenCalledTimes(1);
    expect(loadDatasourceStatuses).toHaveBeenCalledWith(undefined);
    expect(loadDatasourceStatuses).toHaveBeenCalledWith("fund");
    expect(prewarmDatasource).toHaveBeenCalledWith("fund");
    expect(loadCatalog).toHaveBeenCalledWith(undefined, "fund");
    expect(selectCatalogDatasource).toHaveBeenCalledWith("fund");
  });

  it("does not warm catalog context for artifact-only users with datasource grants", async () => {
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
    const loadAgentOptions = vi.fn(async () => []);
    const loadCatalog = vi.fn(async () => true);
    const loadDatasourceStatuses = vi.fn(async () => true);
    const prewarmDatasource = vi.fn(async () => true);
    const selectCatalogDatasource = vi.fn();

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
      meApi: mockMeApi(),
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        permissions: readonly(ref({
          user_id: "u1",
          features: [],
          views: ["artifacts", "artifact_reports"],
          datasources: ["fund"],
          permissions: ["module.report.view"],
          datasource_grants: {
            fund: {
              effect: "allow",
              allow_catalog: true,
              schemas: ["public"],
              tables: ["position"],
            },
          },
          is_admin: false,
        })),
        isAdmin: () => false,
        hasPermission: (permission: string) => permission === "module.report.view",
        hasViewPermission: (view: string) => ["artifacts", "artifact_reports"].includes(view),
        hasFeaturePermission: () => false,
        hasDatasourcePermission: (name: string) => name === "fund",
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
        selectCatalogDatasource,
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

    await workspace.initialize();
    await workspace.ensureCatalogLoaded();

    expect(workspace.visibleDatasourceOptions.value).toEqual([{ value: "fund", label: "fund" }]);
    expect(workspace.currentDatasource.value).toBe("fund");
    expect(checkConnection).not.toHaveBeenCalled();
    expect(loadSessions).not.toHaveBeenCalled();
    expect(loadAgentOptions).not.toHaveBeenCalled();
    expect(loadModels).not.toHaveBeenCalled();
    expect(loadDatasourceStatuses).not.toHaveBeenCalled();
    expect(prewarmDatasource).not.toHaveBeenCalled();
    expect(loadCatalog).not.toHaveBeenCalled();
    expect(selectCatalogDatasource).toHaveBeenCalledWith("fund");
  });

  it("falls back to an authorized datasource for admins without full data grants", async () => {
    vi.doMock("vue", async () => {
      const actual = await vi.importActual<typeof import("vue")>("vue");
      return {
        ...actual,
        onBeforeUnmount: vi.fn(),
      };
    });

    const { ref, shallowRef, readonly } = await import("vue");
    const config = ref({
      current_datasource: "blocked",
      datasources: {
        fund: { type: "postgres" },
        demo: { type: "sqlite" },
        sql_only: { type: "postgres" },
        blocked: { type: "postgres" },
      },
    });
    const datasourceOptions = ref([
      { value: "fund", label: "fund" },
      { value: "demo", label: "demo" },
      { value: "sql_only", label: "sql_only" },
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
      meApi: mockMeApi(),
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        permissions: readonly(ref({
          datasource_grants: {
            fund: { effect: "allow", allow_catalog: true },
            demo: { effect: "allow", allow_catalog: true },
            sql_only: { effect: "allow", allow_catalog: false },
          },
          is_admin: true,
        })),
        isAdmin: () => true,
        hasPermission: () => false,
        hasViewPermission: () => false,
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

    await workspace.initialize();

    expect(workspace.currentDatasource.value).toBe("fund");
    expect(workspace.visibleDatasourceOptions.value).toEqual([
      { value: "fund", label: "fund" },
      { value: "demo", label: "demo" },
      { value: "sql_only", label: "sql_only" },
    ]);
    expect(selectCatalogDatasource).toHaveBeenCalledWith("fund");
    expect(loadDatasourceStatuses).toHaveBeenCalledWith("fund");
    expect(prewarmDatasource).toHaveBeenCalledWith("fund");
    expect(loadDatasourceStatuses).not.toHaveBeenCalledWith("blocked");
    expect(prewarmDatasource).not.toHaveBeenCalledWith("blocked");

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
    prewarmDatasource.mockClear();
    await expect(workspace.handleDatasourceSwitch("sql_only")).resolves.toBe(true);
    expect(workspace.currentDatasource.value).toBe("sql_only");
    expect(loadCatalog).not.toHaveBeenCalled();
    expect(loadDatasourceStatuses).not.toHaveBeenCalled();
    expect(prewarmDatasource).not.toHaveBeenCalled();

    loadCatalog.mockClear();
    loadDatasourceStatuses.mockClear();
    await expect(workspace.handleDatasourceTest("demo")).resolves.toEqual({ ok: true, message: "连接正常" });
    expect(loadCatalog).toHaveBeenCalledWith(undefined, "demo");
    expect(loadDatasourceStatuses).toHaveBeenCalledWith("demo");
    expect(testDatasource).not.toHaveBeenCalled();
  });

  it("forces ordinary users back to normal permission mode", async () => {
    vi.doMock("vue", async () => {
      const actual = await vi.importActual<typeof import("vue")>("vue");
      return {
        ...actual,
        onBeforeUnmount: vi.fn(),
      };
    });

    const { ref, shallowRef, readonly } = await import("vue");
    const permissionMode = shallowRef("dangerous");
    const setPermissionMode = vi.fn((value: string) => {
      permissionMode.value = value;
    });

    vi.doMock("@/composables/useTheme", () => ({
      useTheme: () => ({}),
    }));
    vi.doMock("@/composables/useChatSettings", () => ({
      useChatSettings: () => ({
        language: readonly(shallowRef("zh")),
        permissionMode: readonly(permissionMode),
        planMode: readonly(shallowRef(false)),
        setLanguage: vi.fn(),
        setPermissionMode,
        setPlanMode: vi.fn(),
      }),
    }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({
        apiBase: readonly(shallowRef("")),
        connection: readonly(shallowRef("online")),
        config: readonly(ref(null)),
        datasourceOptions: readonly(ref([])),
        isTestingDatasource: readonly(shallowRef(false)),
        checkConnection: vi.fn(),
        effectiveBase: () => "http://api.test",
        setApiBase: vi.fn(),
        testDatasource: vi.fn(),
        switchDatasource: vi.fn(),
      }),
    }));
    vi.doMock("@/lib/api", () => ({
      agentApi: {
        availableList: vi.fn(async () => []),
      },
      meApi: mockMeApi(),
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
        isLoaded: readonly(shallowRef(true)),
        isAdmin: () => false,
        hasPermission: () => false,
        hasFeaturePermission: () => false,
        hasDatasourcePermission: () => false,
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
        database: shallowRef(""),
        schema: shallowRef(""),
        schemaOptions: readonly(ref([])),
        isLoadingCatalog: readonly(shallowRef(false)),
        datasourceStatuses: readonly(ref({})),
        prewarmingDatasources: readonly(shallowRef(new Set<string>())),
        selectCatalogDatasource: vi.fn(),
        hasCatalogSnapshot: vi.fn(() => false),
        loadCatalog: vi.fn(async () => true),
        loadDatasourceStatuses: vi.fn(),
        prewarmDatasource: vi.fn(),
        setDatabase: vi.fn(),
        setSchema: vi.fn(),
      }),
    }));

    const { useChatWorkspace } = await import("./useChatWorkspace");
    const workspace = useChatWorkspace();

    expect(workspace.canUseElevatedPermissionMode.value).toBe(false);
    expect(setPermissionMode).toHaveBeenCalledWith("normal");
  });
});
