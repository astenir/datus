export type TodoQueueStatus = "pending" | "in_progress" | "completed" | "failed" | "unknown";

export type TodoQueueItem = {
  id: string;
  title: string;
  status: TodoQueueStatus;
  content?: string;
};

export type TodoQueueModel = {
  toolName: "todo_write" | "todo_list" | "todo_update" | "todo_read";
  variant: "snapshot" | "item";
  title: string;
  actionLabel: string;
  total: number;
  completed: number;
  items: readonly TodoQueueItem[];
};

export type TodoQueueGroup = {
  status: TodoQueueStatus;
  label: string;
  items: readonly TodoQueueItem[];
};

const todoToolNames = new Set<TodoQueueModel["toolName"]>([
  "todo_write",
  "todo_list",
  "todo_update",
  "todo_read",
]);

const statusOrder: readonly TodoQueueStatus[] = [
  "in_progress",
  "pending",
  "completed",
  "failed",
  "unknown",
];

const statusLabels: Record<TodoQueueStatus, string> = {
  pending: "待执行",
  in_progress: "进行中",
  completed: "已完成",
  failed: "执行失败",
  unknown: "状态未知",
};

const toolPresentation: Record<
  TodoQueueModel["toolName"],
  { variant: TodoQueueModel["variant"]; title: string; actionLabel: string }
> = {
  todo_write: { variant: "snapshot", title: "执行队列已更新", actionLabel: "已写入" },
  todo_list: { variant: "snapshot", title: "执行队列", actionLabel: "已读取" },
  todo_update: { variant: "item", title: "任务状态已更新", actionLabel: "已更新" },
  todo_read: { variant: "item", title: "任务详情", actionLabel: "已读取" },
};

export function todoQueueFromToolResult(toolName: string, value: unknown): TodoQueueModel | null {
  const normalizedToolName = normalizeTodoToolName(toolName);
  if (!todoToolNames.has(normalizedToolName as TodoQueueModel["toolName"])) return null;

  const payload = unwrapTodoResultEnvelope(value);
  if (!isPlainRecord(payload)) return null;

  const typedToolName = normalizedToolName as TodoQueueModel["toolName"];
  const items = itemsFromPayload(typedToolName, payload);
  if (!items) return null;

  const presentation = toolPresentation[typedToolName];
  const calculatedCompleted = items.filter((item) => item.status === "completed").length;
  const actionLabel = presentation.variant === "item" && items[0]
    ? statusLabels[items[0].status]
    : presentation.actionLabel;

  return {
    toolName: typedToolName,
    variant: presentation.variant,
    title: presentation.title,
    actionLabel,
    total: nonNegativeInteger(payload.total) ?? items.length,
    completed: nonNegativeInteger(payload.completed) ?? calculatedCompleted,
    items,
  };
}

export function groupTodoQueueItems(items: readonly TodoQueueItem[]): TodoQueueGroup[] {
  return statusOrder.flatMap((status) => {
    const statusItems = items.filter((item) => item.status === status);
    return statusItems.length > 0
      ? [{ status, label: statusLabels[status], items: statusItems }]
      : [];
  });
}

function normalizeTodoToolName(toolName: string): string {
  return toolName.trim().toLowerCase().split(".").at(-1) ?? "";
}

function itemsFromPayload(
  toolName: TodoQueueModel["toolName"],
  payload: Record<string, unknown>,
): TodoQueueItem[] | null {
  if (toolName === "todo_write" || toolName === "todo_list") {
    if (!Array.isArray(payload.items)) return null;
    return payload.items.flatMap((item) => {
      const normalized = normalizeTodoItem(item);
      return normalized ? [normalized] : [];
    });
  }

  if (toolName === "todo_update") {
    const item = normalizeTodoItem(payload.updated_item);
    return item ? [item] : null;
  }

  const item = normalizeTodoItem(payload);
  return item ? [item] : null;
}

function unwrapTodoResultEnvelope(value: unknown): unknown {
  if (!isPlainRecord(value) || !("result" in value)) return value;

  const keys = Object.keys(value);
  const isEnvelope = "success" in value || "error" in value || keys.every((key) => key === "result");
  return isEnvelope ? value.result : value;
}

function normalizeTodoItem(value: unknown): TodoQueueItem | null {
  if (!isPlainRecord(value)) return null;

  const id = value.id;
  const title = typeof value.title === "string" ? value.title.trim() : "";
  if ((typeof id !== "string" && typeof id !== "number") || !title) return null;

  const content = typeof value.content === "string" ? value.content.trim() : "";
  return {
    id: String(id),
    title,
    status: normalizeTodoStatus(value.status),
    ...(content ? { content } : {}),
  };
}

function normalizeTodoStatus(value: unknown): TodoQueueStatus {
  if (
    value === "pending" ||
    value === "in_progress" ||
    value === "completed" ||
    value === "failed"
  ) {
    return value;
  }
  return "unknown";
}

function nonNegativeInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
