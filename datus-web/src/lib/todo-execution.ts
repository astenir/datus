import { todoQueueFromToolResult } from "@/lib/todo-queue";
import type { TodoQueueItem, TodoQueueModel } from "@/lib/todo-queue";
import type {
  ChatDisplayMessage,
  MessageDisplayBlock,
  TodoExecutionItem,
  TodoExecutionSummaryBlock,
} from "@/types";

export type TodoExecutionState = {
  executionId: string;
  status: "running" | "completed" | "failed";
  currentItemId?: string;
  total: number;
  completed: number;
  items: readonly TodoExecutionItem[];
};

export type TodoExecutionDisplay = {
  messages: readonly ChatDisplayMessage[];
  activeExecution: TodoExecutionState | null;
};

type MutableTodoExecution = {
  executionId: string;
  status: TodoExecutionState["status"];
  explicitFailure: boolean;
  items: TodoQueueItem[];
  lastMessageIndex: number;
};

const aggregatedTodoTools = new Set(["todo_write", "todo_list", "todo_update"]);

export function deriveTodoExecutionDisplay(
  messages: readonly ChatDisplayMessage[],
  options: { isStreaming?: boolean } = {},
): TodoExecutionDisplay {
  const executions: MutableTodoExecution[] = [];
  const suppressedBlocks = new Set<string>();
  let latestUserMessageIndex = -1;
  let current: MutableTodoExecution | null = null;
  let executionSequence = 0;

  messages.forEach((message, messageIndex) => {
    if (message.role === "user") latestUserMessageIndex = messageIndex;
    message.blocks?.forEach((block, blockIndex) => {
      const toolName = todoToolName(block);
      if (!toolName || !aggregatedTodoTools.has(toolName)) return;

      const blockKey = `${messageIndex}:${blockIndex}`;
      if (block.type === "tool-call") {
        suppressedBlocks.add(blockKey);
        return;
      }
      if (block.type !== "tool-result" && block.type !== "tool-execution") return;

      if (block.errorText || block.resultStatus === "error") {
        if (current) {
          current.explicitFailure = true;
          current.lastMessageIndex = messageIndex;
          refreshExecutionStatus(current);
        }
        return;
      }

      const queue = todoQueueFromToolResult(block.toolName, block.result);
      if (!queue || queue.items.length === 0) return;

      suppressedBlocks.add(blockKey);

      if (queue.toolName === "todo_write") {
        if (current) executions.push(current);
        executionSequence += 1;
        current = createExecution(executionSequence, messageIndex, queue);
        return;
      }

      if (!current) {
        executionSequence += 1;
        current = createExecution(executionSequence, messageIndex, queue);
        return;
      }

      current.lastMessageIndex = messageIndex;
      if (queue.toolName === "todo_list") {
        current.items = [...queue.items];
      } else {
        current.items = patchTodoItems(current.items, queue.items[0]);
      }
      refreshExecutionStatus(current);
    });
  });

  if (current) executions.push(current);

  const latestExecution = executions.at(-1) ?? null;
  const active = options.isStreaming &&
    latestExecution &&
    latestExecution.lastMessageIndex > latestUserMessageIndex
    ? latestExecution
    : null;
  const summaryByMessage = new Map<number, TodoExecutionSummaryBlock[]>();

  for (const execution of executions) {
    if (execution === active) continue;
    const summaries = summaryByMessage.get(execution.lastMessageIndex) ?? [];
    summaries.push(toSummaryBlock(execution));
    summaryByMessage.set(execution.lastMessageIndex, summaries);
  }

  const displayMessages = messages.flatMap((message, messageIndex) => {
    const blocks = (message.blocks ?? []).filter(
      (_block, blockIndex) => !suppressedBlocks.has(`${messageIndex}:${blockIndex}`),
    );
    blocks.push(...(summaryByMessage.get(messageIndex) ?? []));

    if (message.blocks?.length && blocks.length === 0) return [];
    if (!message.blocks?.length) return [message];
    return [{ ...message, blocks }];
  });

  return {
    messages: displayMessages,
    activeExecution: active ? toExecutionState(active) : null,
  };
}

function createExecution(
  sequence: number,
  messageIndex: number,
  queue: TodoQueueModel,
): MutableTodoExecution {
  const execution: MutableTodoExecution = {
    executionId: `todo-execution-${sequence}`,
    status: "running",
    explicitFailure: false,
    items: [...queue.items],
    lastMessageIndex: messageIndex,
  };
  refreshExecutionStatus(execution);
  return execution;
}

function patchTodoItems(items: readonly TodoQueueItem[], update?: TodoQueueItem): TodoQueueItem[] {
  if (!update) return [...items];

  const itemIndex = items.findIndex((item) => item.id === update.id);
  if (itemIndex < 0) return [...items, update];

  return items.map((item, index) => index === itemIndex ? update : item);
}

function refreshExecutionStatus(execution: MutableTodoExecution) {
  if (execution.explicitFailure || execution.items.some((item) => item.status === "failed")) {
    execution.status = "failed";
    return;
  }

  execution.status = execution.items.length > 0 &&
    execution.items.every((item) => item.status === "completed")
    ? "completed"
    : "running";
}

function toExecutionState(execution: MutableTodoExecution): TodoExecutionState {
  const completed = execution.items.filter((item) => item.status === "completed").length;
  const currentItem = execution.items.find((item) => item.status === "in_progress") ??
    execution.items.find((item) => item.status === "pending");

  return {
    executionId: execution.executionId,
    status: execution.status,
    ...(currentItem ? { currentItemId: currentItem.id } : {}),
    total: execution.items.length,
    completed,
    items: execution.items,
  };
}

function toSummaryBlock(execution: MutableTodoExecution): TodoExecutionSummaryBlock {
  const state = toExecutionState(execution);
  return {
    type: "todo-execution-summary",
    executionId: state.executionId,
    status: state.status === "running" ? "interrupted" : state.status,
    total: state.total,
    completed: state.completed,
    items: state.items,
  };
}

function todoToolName(block: MessageDisplayBlock): string | null {
  if (
    block.type !== "tool-call" &&
    block.type !== "tool-result" &&
    block.type !== "tool-execution"
  ) {
    return null;
  }
  return block.toolName.trim().toLowerCase().split(".").at(-1) ?? "";
}
