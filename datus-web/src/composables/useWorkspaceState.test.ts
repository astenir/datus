import { describe, expect, it } from "vitest";

import { useWorkspaceState } from "./useWorkspaceState";

function createState(features: string[] = [], admin = false) {
  return useWorkspaceState({
    isAdmin: () => admin,
    hasFeaturePermission: (feature) => features.includes(feature),
  });
}

describe("useWorkspaceState", () => {
  it("falls back to the first allowed primary view when chat is unavailable", () => {
    const state = createState(["report"]);

    expect(state.allowedPrimaryViews.value).toEqual(["report"]);
    expect(state.activeView.value).toBe("report");
    expect(state.canUseActiveView.value).toBe(true);
  });

  it("keeps workspace tools in right-side drawer state", () => {
    const state = createState(["admin", "sql_generation"]);

    expect(state.openDeveloperView("knowledge")).toBe(true);
    expect(state.activeView.value).toBe("chat");
    expect(state.knowledgeExplorerOpen.value).toBe(true);

    expect(state.openDeveloperView("mcp")).toBe(true);
    expect(state.activeView.value).toBe("chat");
    expect(state.mcpManagerOpen.value).toBe(true);

    expect(state.openDeveloperView("sql")).toBe(true);
    expect(state.activeView.value).toBe("chat");
    expect(state.sqlConsoleOpen.value).toBe(true);
  });

  it("closes workspace tool drawers independently", () => {
    const state = createState(["admin", "sql_generation"]);

    state.openDeveloperView("knowledge");
    state.openDeveloperView("mcp");
    state.openDeveloperView("sql");

    state.closeWorkspaceTool("knowledge");
    expect(state.knowledgeExplorerOpen.value).toBe(false);
    expect(state.mcpManagerOpen.value).toBe(true);
    expect(state.sqlConsoleOpen.value).toBe(true);

    state.closeWorkspaceTool("mcp");
    state.closeWorkspaceTool("sql");
    expect(state.mcpManagerOpen.value).toBe(false);
    expect(state.sqlConsoleOpen.value).toBe(false);
  });

  it("returns workspace tool drawers to the settings console", () => {
    const state = createState(["admin", "sql_generation"]);

    state.openSettings();
    state.openDeveloperView("knowledge");
    expect(state.settingsOpen.value).toBe(false);
    expect(state.knowledgeExplorerOpen.value).toBe(true);

    state.returnWorkspaceToolToSettings("knowledge");
    expect(state.knowledgeExplorerOpen.value).toBe(false);
    expect(state.settingsOpen.value).toBe(true);
  });

  it("trims SQL drafts and increments the version for each open", () => {
    const state = createState(["sql_generation"]);

    expect(state.openSqlConsole("  select 1  ")).toBe(true);
    expect(state.sqlDraft.value).toBe("select 1");
    expect(state.sqlDraftVersion.value).toBe(1);

    expect(state.openSqlConsole("select 2")).toBe(true);
    expect(state.sqlDraft.value).toBe("select 2");
    expect(state.sqlDraftVersion.value).toBe(2);
  });

  it("opens system management as an independent drawer", () => {
    const state = createState(["admin"]);

    state.openSettings();
    state.openSystemManager();

    expect(state.settingsOpen.value).toBe(false);
    expect(state.systemManagerOpen.value).toBe(true);
  });

  it("does not open restricted tools", () => {
    const state = createState(["chat"]);

    expect(state.openDeveloperView("sql")).toBe(false);
    expect(state.sqlConsoleOpen.value).toBe(false);
    expect(state.sqlDraftVersion.value).toBe(0);
  });

  it("opens artifact destinations only when permitted", () => {
    const state = createState(["dashboard"]);

    expect(state.openArtifact("dashboard")).toBe(true);
    expect(state.activeView.value).toBe("dashboard");

    expect(state.openArtifact("report")).toBe(false);
    expect(state.activeView.value).toBe("dashboard");
  });
});
