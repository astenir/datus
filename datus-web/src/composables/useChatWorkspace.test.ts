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
    const loadCatalog = vi.fn(async () => {});
    const compactSession = vi.fn(async () => ({ session_id: "s1", success: true }));

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
        setApiBase: vi.fn(),
        testDatasource: vi.fn(),
        switchDatasource: vi.fn(),
      }),
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
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
        loadSessions,
        selectSession: vi.fn(),
        sendMessage: vi.fn(),
        insertMessage: vi.fn(),
        stopSession: vi.fn(),
        deleteSession: vi.fn(),
        compactSession,
        resumeSession: vi.fn(),
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
        loadCatalog,
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
    expect(loadCatalog).toHaveBeenCalledTimes(1);
    expect(workspace.agentOptions.value).toEqual([]);

    await expect(workspace.compactSession("s1")).resolves.toEqual({ session_id: "s1", success: true });
    expect(compactSession).toHaveBeenCalledWith("s1");
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
    const loadCatalog = vi.fn(async () => {});
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
        setApiBase: vi.fn(),
        testDatasource: vi.fn(),
        switchDatasource,
      }),
    }));
    vi.doMock("@/composables/usePermission", () => ({
      usePermission: () => ({
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
        loadCatalog,
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
    expect(setDatabase).toHaveBeenCalledWith("");
    expect(setSchema).toHaveBeenCalledWith("");
    expect(loadCatalog).toHaveBeenCalledWith(undefined, "demo");
    expect(workspace.currentDatasource.value).toBe("demo");
  });
});
