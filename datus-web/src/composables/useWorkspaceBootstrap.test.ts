import { describe, expect, it, vi } from "vitest";
import { shallowRef } from "vue";

import { useWorkspaceBootstrap } from "./useWorkspaceBootstrap";

function createNoopBootstrap(overrides: Partial<Parameters<typeof useWorkspaceBootstrap>[0]> = {}) {
  return useWorkspaceBootstrap({
    canReadAgentConfig: shallowRef(false),
    canViewChat: shallowRef(false),
    showPersonalMcpPicker: shallowRef(false),
    canReadModelOptions: shallowRef(false),
    checkConnection: vi.fn(async () => {}),
    initializeDatasource: vi.fn(),
    loadSessions: vi.fn(async () => {}),
    loadAgentOptions: vi.fn(async () => true),
    loadAgentPreference: vi.fn(async () => true),
    loadPersonalMcp: vi.fn(async () => {}),
    loadModels: vi.fn(async () => {}),
    warmCurrentDatasource: vi.fn(),
    ...overrides,
  });
}

describe("useWorkspaceBootstrap", () => {
  it("keeps connection and datasource setup ahead of parallel startup tasks", async () => {
    const events: string[] = [];
    const bootstrap = createNoopBootstrap({
      canReadAgentConfig: shallowRef(true),
      canViewChat: shallowRef(true),
      showPersonalMcpPicker: shallowRef(true),
      canReadModelOptions: shallowRef(true),
      checkConnection: async () => {
        events.push("connection");
      },
      initializeDatasource: () => {
        events.push("datasource");
      },
      loadSessions: async () => {
        events.push("sessions");
      },
      loadAgentOptions: async () => {
        events.push("agent-options");
        return true;
      },
      loadAgentPreference: async () => {
        events.push("agent-preference");
        return true;
      },
      loadPersonalMcp: async () => {
        events.push("personal-mcp");
      },
      loadModels: async () => {
        events.push("models");
      },
      warmCurrentDatasource: () => {
        events.push("warm");
      },
    });

    await bootstrap.initialize();

    expect(events).toEqual([
      "connection",
      "datasource",
      "sessions",
      "agent-options",
      "personal-mcp",
      "models",
      "agent-preference",
      "warm",
    ]);
  });

  it("shares in-flight initialization and does not rerun after completion", async () => {
    let releaseSessions: (() => void) | undefined;
    const sessionsPromise = new Promise<unknown>((resolve) => {
      releaseSessions = () => resolve(undefined);
    });
    const loadSessions = vi.fn(() => sessionsPromise);
    const initializeDatasource = vi.fn();
    const warmCurrentDatasource = vi.fn();
    const bootstrap = createNoopBootstrap({
      canViewChat: shallowRef(true),
      loadSessions,
      initializeDatasource,
      warmCurrentDatasource,
    });

    const firstInitialization = bootstrap.initialize();
    const secondInitialization = bootstrap.initialize();

    expect(loadSessions).toHaveBeenCalledTimes(1);
    expect(initializeDatasource).toHaveBeenCalledTimes(1);

    releaseSessions?.();
    await Promise.all([firstInitialization, secondInitialization]);
    await bootstrap.initialize();

    expect(loadSessions).toHaveBeenCalledTimes(1);
    expect(initializeDatasource).toHaveBeenCalledTimes(1);
    expect(warmCurrentDatasource).toHaveBeenCalledTimes(1);
  });

  it("does not start gated startup tasks when their access flags are disabled", async () => {
    const checkConnection = vi.fn(async () => {});
    const loadSessions = vi.fn(async () => {});
    const loadAgentOptions = vi.fn(async () => true);
    const loadAgentPreference = vi.fn(async () => true);
    const loadPersonalMcp = vi.fn(async () => {});
    const loadModels = vi.fn(async () => {});
    const initializeDatasource = vi.fn();
    const warmCurrentDatasource = vi.fn();
    const bootstrap = createNoopBootstrap({
      checkConnection,
      loadSessions,
      loadAgentOptions,
      loadAgentPreference,
      loadPersonalMcp,
      loadModels,
      initializeDatasource,
      warmCurrentDatasource,
    });

    await bootstrap.initialize();

    expect(checkConnection).not.toHaveBeenCalled();
    expect(loadSessions).not.toHaveBeenCalled();
    expect(loadAgentOptions).not.toHaveBeenCalled();
    expect(loadAgentPreference).not.toHaveBeenCalled();
    expect(loadPersonalMcp).not.toHaveBeenCalled();
    expect(loadModels).not.toHaveBeenCalled();
    expect(initializeDatasource).toHaveBeenCalledTimes(1);
    expect(warmCurrentDatasource).toHaveBeenCalledTimes(1);
  });
});
