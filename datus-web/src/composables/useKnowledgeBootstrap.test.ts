import { describe, expect, it, vi, beforeEach } from "vitest";

const bootstrap = vi.fn();
const cancelBootstrap = vi.fn();
const bootstrapDocs = vi.fn();
const cancelBootstrapDocs = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  kbApi: {
    bootstrap,
    cancelBootstrap,
    bootstrapDocs,
    cancelBootstrapDocs,
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

function streamFromText(value: string): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(value));
      controller.close();
    },
  });
}

function openStreamFromText(value: string): { stream: ReadableStream<Uint8Array>; cancelled: () => boolean } {
  let wasCancelled = false;
  return {
    cancelled: () => wasCancelled,
    stream: new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(value));
      },
      cancel() {
        wasCancelled = true;
      },
    }),
  };
}

async function flushPromises(count = 5) {
  for (let index = 0; index < count; index += 1) {
    await Promise.resolve();
  }
}

async function waitForCondition(condition: () => boolean) {
  for (let index = 0; index < 20; index += 1) {
    if (condition()) return;
    await flushPromises();
  }
}

describe("knowledgeBootstrapInternals", () => {
  it("normalizes business KB bootstrap requests to the current OpenAPI contract", async () => {
    const { knowledgeBootstrapInternals } = await import("./useKnowledgeBootstrap");

    expect(knowledgeBootstrapInternals.buildKbBootstrapInput({
      components: ["metadata", "metrics"],
      strategy: "incremental",
      schemaLinkingType: "full",
      catalog: "main",
      databaseName: "fund",
      successStory: "success.csv",
      subjectTreeText: "基金\n风控\n",
      sqlDir: "sql_examples",
    })).toEqual({
      components: ["metadata", "metrics"],
      strategy: "incremental",
      schema_linking_type: "full",
      catalog: "main",
      database_name: "fund",
      success_story: "success.csv",
      subject_tree: ["基金", "风控"],
      sql_dir: "sql_examples",
    });
  });

  it("normalizes docs requests and keeps transient tokens in the request body only", async () => {
    const { knowledgeBootstrapInternals } = await import("./useKnowledgeBootstrap");

    expect(knowledgeBootstrapInternals.buildDocsBootstrapInput({
      platform: "datus",
      buildMode: "overwrite",
      poolSize: 20,
      sourceType: "github",
      source: "astenir/datus",
      version: "v1",
      githubRef: "main",
      githubToken: "ghp_private",
      pathsText: "docs\nREADME.md",
      chunkSize: "800",
      maxDepth: "",
      includePatternsText: "*.md",
      excludePatternsText: "dist\nnode_modules",
    })).toEqual({
      platform: "datus",
      build_mode: "overwrite",
      pool_size: 16,
      source_type: "github",
      source: "astenir/datus",
      version: "v1",
      github_ref: "main",
      github_token: "ghp_private",
      paths: ["docs", "README.md"],
      chunk_size: 800,
      max_depth: null,
      include_patterns: ["*.md"],
      exclude_patterns: ["dist", "node_modules"],
    });
  });

  it("redacts sensitive values from stream payload logs", async () => {
    const { knowledgeBootstrapInternals } = await import("./useKnowledgeBootstrap");
    const entry = knowledgeBootstrapInternals.parseBootstrapEvent({
      event: "progress",
      data: {
        message: "cloned",
        github_token: "ghp_private",
        nested: { api_key: "sk-private" },
      },
    }, "docs");

    expect(entry.payload).toEqual({
      message: "cloned",
      github_token: "[redacted]",
      nested: { api_key: "[redacted]" },
    });
    expect(JSON.stringify(entry)).not.toContain("ghp_private");
    expect(JSON.stringify(entry)).not.toContain("sk-private");
  });
});

describe("useKnowledgeBootstrap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    bootstrap.mockResolvedValue(streamFromText([
      "id: stream-kb-1",
      "event: progress",
      "data: {\"message\":\"metadata scanned\",\"component\":\"metadata\",\"status\":\"running\"}",
      "",
      "event: complete",
      "data: {\"message\":\"done\",\"status\":\"completed\"}",
      "",
    ].join("\n")));
    bootstrapDocs.mockResolvedValue(streamFromText([
      "id: stream-docs-1",
      "event: complete",
      "data: {\"message\":\"docs done\",\"github_token\":\"ghp_private\"}",
      "",
    ].join("\n")));
    cancelBootstrap.mockResolvedValue({});
    cancelBootstrapDocs.mockResolvedValue({});
  });

  it("runs business KB bootstrap and captures stream state", async () => {
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const manager = useKnowledgeBootstrap();
    manager.forms.value.kb.components = ["metadata", "reference_sql"];
    manager.forms.value.kb.catalog = "main";
    manager.forms.value.kb.databaseName = "fund";
    manager.forms.value.kb.subjectTreeText = "基金\n风控";

    await manager.startKbBootstrap();

    expect(bootstrap).toHaveBeenCalledWith("http://api.test", {
      components: ["metadata", "reference_sql"],
      strategy: "incremental",
      schema_linking_type: "full",
      catalog: "main",
      database_name: "fund",
      success_story: null,
      subject_tree: ["基金", "风控"],
      sql_dir: null,
    });
    expect(manager.status.value).toBe("completed");
    expect(manager.activeStreamId.value).toBe("stream-kb-1");
    expect(manager.logs.value).toHaveLength(2);
    expect(toastSuccess).toHaveBeenCalledWith("业务知识库构建完成");
  });

  it("runs docs bootstrap without exposing tokens in logs", async () => {
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const manager = useKnowledgeBootstrap();
    manager.forms.value.docs.platform = "datus";
    manager.forms.value.docs.githubToken = "ghp_private";

    await manager.startDocsBootstrap();

    expect(bootstrapDocs).toHaveBeenCalledWith("http://api.test", expect.objectContaining({
      platform: "datus",
      github_token: "ghp_private",
    }));
    expect(manager.terminalOutput.value).not.toContain("ghp_private");
    expect(JSON.stringify(manager.logs.value)).not.toContain("ghp_private");
  });

  it("routes cancellation to the active KB stream endpoint", async () => {
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const source = openStreamFromText([
      "id: stream-kb-1",
      "event: progress",
      "data: {\"message\":\"running\"}",
      "",
      "",
    ].join("\n"));
    bootstrap.mockResolvedValue(source.stream);
    const manager = useKnowledgeBootstrap();

    const running = manager.startKbBootstrap();
    await waitForCondition(() => manager.activeStreamId.value === "stream-kb-1");
    await manager.cancelActiveBootstrap();
    await running;

    expect(cancelBootstrap).toHaveBeenCalledWith("http://api.test", "stream-kb-1");
    expect(source.cancelled()).toBe(true);
    expect(manager.status.value).toBe("cancelled");
  });
});
