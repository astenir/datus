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
    const loadAgents = vi.fn(async () => {});
    const loadModels = vi.fn(async () => {});
    const loadCatalog = vi.fn(async () => {});

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
        checkConnection,
        setApiBase: vi.fn(),
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
        compactSession: vi.fn(),
        resumeSession: vi.fn(),
        clearMessages: vi.fn(),
        dispose: vi.fn(),
      }),
    }));
    vi.doMock("@/composables/useAgents", () => ({
      useAgents: () => ({
        agents: readonly(ref([])),
        loadAgents,
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
    expect(loadAgents).toHaveBeenCalledTimes(1);
    expect(loadModels).toHaveBeenCalledTimes(1);
    expect(loadCatalog).toHaveBeenCalledTimes(1);
  });
});
