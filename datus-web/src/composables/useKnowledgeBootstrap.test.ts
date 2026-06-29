import { describe, expect, it, vi, beforeEach } from "vitest";

const bootstrap = vi.fn();
const upload = vi.fn();
const cancelBootstrap = vi.fn();
const bootstrapDocs = vi.fn();
const cancelBootstrapDocs = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  kbApi: {
    upload,
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
      component: "metadata",
      strategy: "incremental",
      schemaLinkingType: "full",
      catalog: "main",
      databaseName: "fund",
      successStory: "success.csv",
      subjectTreeText: "基金\n风控\n",
      sqlDir: "sql_examples",
    })).toEqual({
      components: ["metadata"],
      strategy: "incremental",
      schema_linking_type: "full",
      catalog: "main",
      database_name: "fund",
    });
  });

  it("builds a metrics bootstrap request with only metrics-specific fields", async () => {
    const { knowledgeBootstrapInternals } = await import("./useKnowledgeBootstrap");

    expect(knowledgeBootstrapInternals.buildKbBootstrapInput({
      component: "metrics",
      strategy: "overwrite",
      schemaLinkingType: "full",
      catalog: "ignored",
      databaseName: "ignored",
      successStory: "success.csv",
      subjectTreeText: "基金\n风控\n",
      sqlDir: "ignored",
    })).toEqual({
      components: ["metrics"],
      strategy: "overwrite",
      success_story: "success.csv",
      subject_tree: ["基金", "风控"],
    });
  });

  it("builds a reference SQL bootstrap request with only SQL-specific fields", async () => {
    const { knowledgeBootstrapInternals } = await import("./useKnowledgeBootstrap");

    expect(knowledgeBootstrapInternals.buildKbBootstrapInput({
      component: "reference_sql",
      strategy: "check",
      schemaLinkingType: "full",
      catalog: "ignored",
      databaseName: "ignored",
      successStory: "ignored",
      subjectTreeText: "基金\n",
      sqlDir: "sql_examples",
    })).toEqual({
      components: ["reference_sql"],
      strategy: "check",
      subject_tree: ["基金"],
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
      upload_id: null,
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
    upload.mockResolvedValue({
      upload_id: "upload-1",
      purpose: "success_story_csv",
      files: [{
        file_id: "file-1",
        filename: "success.csv",
        size: 12,
        content_type: "text/csv",
        relative_path: "uploads/project/alice/upload-1/success.csv",
      }],
      created_at: "2026-06-30T00:00:00Z",
      status: "available",
      project_id: "project",
    });
  });

  it("runs business KB bootstrap and captures stream state", async () => {
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const manager = useKnowledgeBootstrap();
    manager.forms.value.kb.component = "reference_sql";
    manager.forms.value.kb.catalog = "main";
    manager.forms.value.kb.databaseName = "fund";
    manager.forms.value.kb.subjectTreeText = "基金\n风控";
    manager.forms.value.kb.sqlDir = "sql_examples";

    await manager.startKbBootstrap();

    expect(bootstrap).toHaveBeenCalledWith("http://api.test", {
      components: ["reference_sql"],
      strategy: "incremental",
      subject_tree: ["基金", "风控"],
      sql_dir: "sql_examples",
    });
    expect(manager.status.value).toBe("completed");
    expect(manager.activeStreamId.value).toBe("stream-kb-1");
    expect(manager.logs.value).toHaveLength(2);
    expect(toastSuccess).toHaveBeenCalledWith("业务知识库构建完成");
  });

  it("uploads selected success-story CSVs before bootstrap", async () => {
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const manager = useKnowledgeBootstrap();
    const file = new File(["question,sql\nq,select 1"], "success.csv", { type: "text/csv" });
    manager.forms.value.kb.component = "semantic_model";
    manager.setUploadFiles("successStory", [file]);

    await manager.startKbBootstrap();

    expect(upload).toHaveBeenCalledWith("http://api.test", {
      purpose: "success_story_csv",
      files: [file],
      description: "success_story_csv",
    });
    expect(bootstrap).toHaveBeenCalledWith("http://api.test", {
      components: ["semantic_model"],
      strategy: "incremental",
      success_story_upload_id: "upload-1",
      success_story_file_id: "file-1",
    });
  });

  it("passes the active datasource to KB uploads", async () => {
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const manager = useKnowledgeBootstrap({ currentDatasource: () => "ccks_fund" });
    const file = new File(["question,sql\nq,select 1"], "success.csv", { type: "text/csv" });
    manager.forms.value.kb.component = "semantic_model";
    manager.setUploadFiles("successStory", [file]);

    await manager.startKbBootstrap();

    expect(upload).toHaveBeenCalledWith("http://api.test", {
      purpose: "success_story_csv",
      files: [file],
      datasourceId: "ccks_fund",
      description: "success_story_csv",
    });
  });

  it("uploads selected reference SQL files before bootstrap", async () => {
    upload.mockResolvedValueOnce({
      upload_id: "upload-sql",
      purpose: "reference_sql",
      files: [{
        file_id: "file-sql",
        filename: "daily.sql",
        size: 21,
        content_type: "text/plain",
        relative_path: "uploads/project/alice/upload-sql/daily.sql",
      }],
      created_at: "2026-06-30T00:00:00Z",
      status: "available",
      project_id: "project",
    });
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const manager = useKnowledgeBootstrap();
    const file = new File(["select 1"], "daily.sql", { type: "text/plain" });
    manager.forms.value.kb.component = "reference_sql";
    manager.forms.value.kb.subjectTreeText = "基金";
    manager.setUploadFiles("referenceSql", [file]);

    await manager.startKbBootstrap();

    expect(upload).toHaveBeenCalledWith("http://api.test", {
      purpose: "reference_sql",
      files: [file],
      description: "reference_sql",
    });
    expect(bootstrap).toHaveBeenCalledWith("http://api.test", {
      components: ["reference_sql"],
      strategy: "incremental",
      reference_sql_upload_id: "upload-sql",
      subject_tree: ["基金"],
    });
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

  it("uploads selected platform docs before docs bootstrap", async () => {
    upload.mockResolvedValueOnce({
      upload_id: "upload-docs",
      purpose: "platform_docs",
      files: [{
        file_id: "file-doc",
        filename: "guide.md",
        size: 15,
        content_type: "text/markdown",
        relative_path: "uploads/project/alice/upload-docs/guide.md",
      }],
      created_at: "2026-06-30T00:00:00Z",
      status: "available",
      project_id: "project",
    });
    const { useKnowledgeBootstrap } = await import("./useKnowledgeBootstrap");
    const manager = useKnowledgeBootstrap();
    const file = new File(["# Guide"], "guide.md", { type: "text/markdown" });
    manager.forms.value.docs.platform = "datus";
    manager.setUploadFiles("docs", [file]);

    await manager.startDocsBootstrap();

    expect(upload).toHaveBeenCalledWith("http://api.test", {
      purpose: "platform_docs",
      files: [file],
      platform: "datus",
      description: "platform_docs",
    });
    expect(bootstrapDocs).toHaveBeenCalledWith("http://api.test", expect.objectContaining({
      platform: "datus",
      source_type: "local",
      source: null,
      upload_id: "upload-docs",
    }));
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
