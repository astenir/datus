import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { kbApi } from "@/lib/api";
import { createClientId, parseSseBuffer, stringifyContent } from "@/lib/chat";
import type {
  BootstrapComponent,
  BootstrapDocInput,
  BootstrapKbInput,
  KnowledgeBootstrapDocsForm,
  KnowledgeBootstrapForms,
  KnowledgeBootstrapKbForm,
  KnowledgeBootstrapLogEntry,
  KnowledgeBootstrapLogLevel,
  KnowledgeBootstrapMode,
  KnowledgeBootstrapStatus,
  SseEvent,
} from "@/types";

const KB_COMPONENTS: readonly BootstrapComponent[] = ["metadata", "semantic_model", "metrics", "reference_sql"];
const SENSITIVE_KEY_PATTERN = /token|authorization|password|secret|api[_-]?key/i;
const TERMINAL_EVENTS = new Set(["complete", "completed", "done", "end", "finish", "finished"]);
const ERROR_EVENTS = new Set(["error", "failed", "failure"]);

function defaultKbForm(): KnowledgeBootstrapKbForm {
  return {
    component: "metadata",
    strategy: "incremental",
    schemaLinkingType: "full",
    catalog: "",
    databaseName: "",
    successStory: "",
    subjectTreeText: "",
    sqlDir: "",
  };
}

function defaultDocsForm(): KnowledgeBootstrapDocsForm {
  return {
    platform: "",
    buildMode: "overwrite",
    poolSize: 4,
    sourceType: "",
    source: "",
    version: "",
    githubRef: "",
    githubToken: "",
    pathsText: "",
    chunkSize: "",
    maxDepth: "",
    includePatternsText: "",
    excludePatternsText: "",
  };
}

function defaultForms(): KnowledgeBootstrapForms {
  return {
    kb: defaultKbForm(),
    docs: defaultDocsForm(),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function parseLines(value: string): string[] | null {
  const lines = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.length > 0 ? lines : null;
}

function parseOptionalPositiveInteger(value: string, label: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;

  const numberValue = Number(trimmed);
  if (!Number.isInteger(numberValue) || numberValue <= 0) {
    throw new Error(`${label} 必须是正整数`);
  }

  return numberValue;
}

function normalizePoolSize(value: number): number {
  if (!Number.isFinite(value)) return 4;
  return Math.min(16, Math.max(1, Math.trunc(value)));
}

function redactValue(value: unknown, depth = 0): unknown {
  if (depth > 8) return "[depth-limit]";
  if (Array.isArray(value)) {
    return value.map((item) => redactValue(item, depth + 1));
  }
  if (!isRecord(value)) return value;

  const redacted: Record<string, unknown> = {};
  for (const [key, nestedValue] of Object.entries(value)) {
    redacted[key] = SENSITIVE_KEY_PATTERN.test(key)
      ? "[redacted]"
      : redactValue(nestedValue, depth + 1);
  }
  return redacted;
}

function stringField(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function payloadStatus(payload: unknown): string {
  if (!isRecord(payload)) return "";
  return stringField(payload.status ?? payload.stage ?? payload.state);
}

function payloadStreamId(payload: unknown): string {
  if (!isRecord(payload)) return "";
  return stringField(payload.stream_id ?? payload.streamId ?? payload.streamID);
}

function payloadComponent(payload: unknown): string {
  if (!isRecord(payload)) return "";
  return stringField(payload.component ?? payload.name ?? payload.step);
}

function payloadMessage(payload: unknown): string {
  if (typeof payload === "string") return payload.trim();
  if (!isRecord(payload)) return stringifyContent(payload).trim();

  const direct = stringField(payload.message)
    || stringField(payload.detail)
    || stringField(payload.error)
    || stringField(payload.status)
    || stringField(payload.stage)
    || stringField(payload.step);
  if (direct) return direct;

  const component = payloadComponent(payload);
  return component ? `处理 ${component}` : stringifyContent(payload).trim();
}

function eventLevel(eventName: string, payload: unknown): KnowledgeBootstrapLogLevel {
  const normalizedEvent = eventName.toLowerCase();
  const status = payloadStatus(payload).toLowerCase();
  const hasErrorPayload = isRecord(payload) && Boolean(payload.error);

  if (ERROR_EVENTS.has(normalizedEvent) || hasErrorPayload || ERROR_EVENTS.has(status)) return "error";
  if (TERMINAL_EVENTS.has(normalizedEvent) || TERMINAL_EVENTS.has(status)) return "success";
  if (status === "cancelled" || status === "canceled" || status === "skipped") return "warning";
  return "info";
}

function isTerminalEvent(eventName: string, payload: unknown): boolean {
  const normalizedEvent = eventName.toLowerCase();
  const status = payloadStatus(payload).toLowerCase();
  return TERMINAL_EVENTS.has(normalizedEvent) || TERMINAL_EVENTS.has(status);
}

function isErrorEvent(eventName: string, payload: unknown): boolean {
  return eventLevel(eventName, payload) === "error";
}

function buildKbBootstrapInput(form: KnowledgeBootstrapKbForm): BootstrapKbInput {
  const component = KB_COMPONENTS.includes(form.component) ? form.component : "metadata";
  const input: BootstrapKbInput = {
    components: [component],
    strategy: form.strategy,
  };

  if (component === "metadata") {
    input.schema_linking_type = form.schemaLinkingType;
    input.catalog = form.catalog.trim();
    input.database_name = form.databaseName.trim();
    return input;
  }

  if (component === "semantic_model" || component === "metrics") {
    const successStory = optionalString(form.successStory);
    if (!successStory) {
      throw new Error(component === "semantic_model" ? "请填写历史 SQL CSV 文件" : "请填写指标构建 CSV 文件");
    }
    input.success_story = successStory;
  }

  if (component === "metrics") {
    input.subject_tree = parseLines(form.subjectTreeText);
  }

  if (component === "reference_sql") {
    const sqlDir = optionalString(form.sqlDir);
    if (!sqlDir) {
      throw new Error("请填写 SQL 文件目录");
    }
    input.sql_dir = sqlDir;
    input.subject_tree = parseLines(form.subjectTreeText);
  }

  return input;
}

function buildDocsBootstrapInput(form: KnowledgeBootstrapDocsForm): BootstrapDocInput {
  const platform = form.platform.trim();
  if (!platform) {
    throw new Error("请填写文档平台");
  }

  return {
    platform,
    build_mode: form.buildMode,
    pool_size: normalizePoolSize(form.poolSize),
    source_type: optionalString(form.sourceType),
    source: optionalString(form.source),
    version: optionalString(form.version),
    github_ref: optionalString(form.githubRef),
    github_token: optionalString(form.githubToken),
    paths: parseLines(form.pathsText),
    chunk_size: parseOptionalPositiveInteger(form.chunkSize, "分块大小"),
    max_depth: parseOptionalPositiveInteger(form.maxDepth, "最大深度"),
    include_patterns: parseLines(form.includePatternsText),
    exclude_patterns: parseLines(form.excludePatternsText),
  };
}

function parseBootstrapEvent(event: SseEvent, mode: KnowledgeBootstrapMode): KnowledgeBootstrapLogEntry & { terminal: boolean } {
  const eventName = event.event?.trim() || "message";
  const redactedPayload = redactValue(event.data);
  const streamId = payloadStreamId(event.data) || event.id;
  const component = payloadComponent(event.data);
  const level = eventLevel(eventName, event.data);
  const message = payloadMessage(event.data) || eventName;
  const entry: KnowledgeBootstrapLogEntry & { terminal: boolean } = {
    id: createClientId("kb-log"),
    mode,
    event: eventName,
    level,
    message,
    createdAt: new Date().toISOString(),
    payload: redactedPayload,
    terminal: isTerminalEvent(eventName, event.data),
  };

  if (streamId) entry.streamId = streamId;
  if (component) entry.component = component;

  return entry;
}

function formatLogLine(entry: KnowledgeBootstrapLogEntry): string {
  const timestamp = new Date(entry.createdAt).toLocaleTimeString("zh-CN", { hour12: false });
  const scope = [entry.mode === "kb" ? "kb" : "docs", entry.event, entry.component].filter(Boolean).join(":");
  const suffix = entry.streamId ? ` #${entry.streamId}` : "";
  return `[${timestamp}] ${entry.level.toUpperCase()} ${scope}${suffix} ${entry.message}`;
}

export function useKnowledgeBootstrap() {
  const connection = useConnection();

  const forms = ref<KnowledgeBootstrapForms>(defaultForms());
  const logs = ref<KnowledgeBootstrapLogEntry[]>([]);
  const status = shallowRef<KnowledgeBootstrapStatus>("idle");
  const activeMode = shallowRef<KnowledgeBootstrapMode>("kb");
  const activeStreamId = shallowRef("");
  const cancellationRequested = shallowRef(false);
  const activeReader = shallowRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  const isRunning = computed(() => status.value === "running");
  const canCancel = computed(() => isRunning.value);
  const terminalOutput = computed(() => logs.value.map(formatLogLine).join("\n"));
  const latestLog = computed(() => logs.value[logs.value.length - 1] ?? null);

  function appendEntry(entry: KnowledgeBootstrapLogEntry & { terminal?: boolean }) {
    const { terminal: _terminal, ...logEntry } = entry;
    logs.value = [...logs.value, logEntry];
    if (entry.streamId) activeStreamId.value = entry.streamId;
    if (entry.level === "error") status.value = "error";
    if (entry.terminal && status.value === "running") status.value = "completed";
  }

  function clearLogs() {
    logs.value = [];
  }

  function currentStatus(): KnowledgeBootstrapStatus {
    return status.value;
  }

  async function consumeStream(stream: ReadableStream<Uint8Array>, mode: KnowledgeBootstrapMode) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    activeReader.value = reader;

    try {
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;

        buffer += decoder.decode(chunk.value, { stream: true });
        const parsed = parseSseBuffer(buffer);
        buffer = parsed.rest;
        for (const event of parsed.events) {
          const entry = parseBootstrapEvent(event, mode);
          appendEntry(entry);
          if (isErrorEvent(entry.event, event.data)) {
            status.value = "error";
          }
        }
      }

      const parsed = parseSseBuffer(buffer + decoder.decode(), { flush: true });
      for (const event of parsed.events) {
        appendEntry(parseBootstrapEvent(event, mode));
      }

      if (cancellationRequested.value) {
        status.value = "cancelled";
      } else if (status.value === "running") {
        status.value = "completed";
      }
    } catch (error) {
      if (cancellationRequested.value) {
        status.value = "cancelled";
        return;
      }
      console.error("知识库构建事件流读取失败:", error);
      appendEntry({
        id: createClientId("kb-log"),
        mode,
        event: "error",
        level: "error",
        message: error instanceof Error ? error.message : "事件流读取失败",
        createdAt: new Date().toISOString(),
      });
      toast.error("知识库构建失败");
    } finally {
      activeReader.value = null;
    }
  }

  async function runBootstrap(mode: KnowledgeBootstrapMode, input: BootstrapKbInput | BootstrapDocInput) {
    if (isRunning.value) return;

    activeMode.value = mode;
    activeStreamId.value = "";
    cancellationRequested.value = false;
    status.value = "running";

    try {
      const stream = mode === "kb"
        ? await kbApi.bootstrap(connection.effectiveBase(), input as BootstrapKbInput)
        : await kbApi.bootstrapDocs(connection.effectiveBase(), input as BootstrapDocInput);

      if (!stream) {
        throw new Error("后端没有返回事件流");
      }

      await consumeStream(stream, mode);
      if (currentStatus() === "completed") {
        toast.success(mode === "kb" ? "业务知识库构建完成" : "平台文档构建完成");
      }
    } catch (error) {
      if (cancellationRequested.value) {
        status.value = "cancelled";
        return;
      }
      console.error("启动知识库构建失败:", error);
      status.value = "error";
      toast.error(error instanceof Error ? error.message : "启动知识库构建失败");
    }
  }

  async function startKbBootstrap() {
    let input: BootstrapKbInput;
    try {
      input = buildKbBootstrapInput(forms.value.kb);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "知识库构建参数无效");
      return;
    }
    await runBootstrap("kb", input);
  }

  async function startDocsBootstrap() {
    let input: BootstrapDocInput;
    try {
      input = buildDocsBootstrapInput(forms.value.docs);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "文档构建参数无效");
      return;
    }
    await runBootstrap("docs", input);
  }

  async function cancelActiveBootstrap() {
    if (!isRunning.value) return;

    cancellationRequested.value = true;
    const streamId = activeStreamId.value.trim();
    try {
      if (streamId) {
        if (activeMode.value === "kb") {
          await kbApi.cancelBootstrap(connection.effectiveBase(), streamId);
        } else {
          await kbApi.cancelBootstrapDocs(connection.effectiveBase(), streamId);
        }
      }
      await activeReader.value?.cancel();
      status.value = "cancelled";
      toast.success("已请求取消构建任务");
    } catch (error) {
      console.error("取消知识库构建失败:", error);
      toast.error("取消知识库构建失败");
    }
  }

  return {
    forms,
    logs: readonly(logs),
    status: readonly(status),
    activeMode: readonly(activeMode),
    activeStreamId: readonly(activeStreamId),
    isRunning,
    canCancel,
    terminalOutput,
    latestLog,
    startKbBootstrap,
    startDocsBootstrap,
    cancelActiveBootstrap,
    clearLogs,
  };
}

export const knowledgeBootstrapInternals = {
  buildKbBootstrapInput,
  buildDocsBootstrapInput,
  parseBootstrapEvent,
  parseLines,
  redactValue,
};
