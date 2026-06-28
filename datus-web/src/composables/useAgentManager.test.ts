import { beforeEach, describe, expect, it, vi } from "vitest";

const listAgents = vi.fn();
const getAgent = vi.fn();
const createAgent = vi.fn();
const editAgent = vi.fn();
const deleteAgent = vi.fn();
const agentTools = vi.fn();
const agentUseTools = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  agentApi: {
    list: listAgents,
    get: getAgent,
    create: createAgent,
    edit: editAgent,
    delete: deleteAgent,
    tools: agentTools,
    useTools: agentUseTools,
  },
}));

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "http://api.test",
  }),
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
    success: toastSuccess,
  },
}));

describe("useAgentManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listAgents.mockResolvedValue({
      agents: [
        { name: "writer", type: "text" },
        { name: "analyst", type: "analytics" },
      ],
    });
    getAgent.mockResolvedValue({
      name: "analyst",
      type: "analytics",
      system_prompt: "Analyze data",
      tools: ["read_query"],
      catalogs: ["fund"],
      subjects: ["portfolio"],
      rules: ["cite sources"],
    });
    createAgent.mockResolvedValue({ name: "analyst" });
    editAgent.mockResolvedValue({});
    deleteAgent.mockResolvedValue({});
    agentTools.mockResolvedValue({
      tools: {
        sql: ["read_query", "explain_query"],
      },
    });
    agentUseTools.mockResolvedValue({
      default_tools: ["read_query"],
      tool_types: {
        analytics: { tools: ["explain_query"] },
      },
    });
  });

  it("loads and sorts agents from the active connection", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();

    expect(listAgents).toHaveBeenCalledWith("http://api.test");
    expect(manager.agents.value.map(agent => agent.name)).toEqual(["analyst", "writer"]);
    expect(manager.agentCount.value).toBe(2);
  });

  it("surfaces enterprise disabled legacy agent routes explicitly", async () => {
    const { ApiResultError } = await import("@/lib/chat");
    listAgents.mockRejectedValue(new ApiResultError("legacy disabled", "ENTERPRISE_ROUTE_DISABLED"));
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadAgents();

    expect(manager.legacyRoutesDisabled.value).toBe(true);
    expect(manager.error.value).toContain("legacy Agent 配置接口");
    expect(toastError).toHaveBeenCalledWith(expect.stringContaining("legacy Agent 配置接口"));
  });

  it("loads selected agent detail and its usable tools", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.selectAgent("analyst");

    expect(getAgent).toHaveBeenCalledWith("http://api.test", "analyst");
    expect(agentUseTools).toHaveBeenCalledWith("http://api.test", "analytics");
    expect(manager.form.value).toMatchObject({
      id: "analyst",
      name: "analyst",
      promptTemplate: "Analyze data",
      toolsText: "read_query",
    });
    expect(manager.selectedUseToolCount.value).toBe(2);
  });

  it("loads available agent tool catalogs", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.loadToolCatalog();

    expect(agentTools).toHaveBeenCalledWith("http://api.test");
    expect(manager.toolCategoryCount.value).toBe(1);
    expect(manager.toolCount.value).toBe(2);
  });

  it("creates agents with normalized list fields", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    manager.form.value = {
      id: "",
      name: "researcher",
      type: "analytics",
      description: "Research agent",
      promptTemplate: "Answer carefully",
      toolsText: "read_query, explain_query",
      catalogsText: "fund",
      subjectsText: "portfolio\nrisk",
      rulesText: "",
      maxTurns: "8",
      workspaceRoot: "/tmp/workspace",
    };

    await manager.saveForm();

    expect(createAgent).toHaveBeenCalledWith("http://api.test", {
      name: "researcher",
      type: "analytics",
      description: "Research agent",
      prompt_template: "Answer carefully",
      tools: ["read_query", "explain_query"],
      catalogs: ["fund"],
      subjects: ["portfolio", "risk"],
      rules: undefined,
      max_turns: 8,
      workspace_root: "/tmp/workspace",
    });
    expect(toastSuccess).toHaveBeenCalledWith("Agent 已创建");
  });

  it("edits agents through the backend system_prompt field", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    await manager.selectAgent("analyst");
    manager.form.value.promptTemplate = "Updated prompt";

    await manager.saveForm();

    expect(editAgent).toHaveBeenCalledWith("http://api.test", expect.objectContaining({
      id: "analyst",
      name: "analyst",
      system_prompt: "Updated prompt",
    }));
  });

  it("rejects invalid max turn values before saving", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();
    manager.form.value.name = "bad-agent";
    manager.form.value.maxTurns = "0";

    await manager.saveForm();

    expect(createAgent).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("最大轮次必须是正整数");
  });

  it("deletes agents and reloads the list", async () => {
    const { useAgentManager } = await import("./useAgentManager");
    const manager = useAgentManager();

    await manager.deleteAgent("writer");

    expect(deleteAgent).toHaveBeenCalledWith("http://api.test", "writer");
    expect(listAgents).toHaveBeenCalledWith("http://api.test");
    expect(toastSuccess).toHaveBeenCalledWith("Agent 已删除");
  });
});

describe("agentManagerInternals", () => {
  it("normalizes comma and newline separated lists", async () => {
    const { agentManagerInternals } = await import("./useAgentManager");

    expect(agentManagerInternals.parseListText("a, b\nc")).toEqual(["a", "b", "c"]);
    expect(agentManagerInternals.parseListText(" ")).toBeUndefined();
  });
});
