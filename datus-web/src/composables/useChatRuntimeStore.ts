import { activeUserInteractionKey, createClientId } from "@/lib/chat";
import { computed, readonly, shallowRef } from "vue";
import type {
  ChatErrorBlock,
  ChatMessage,
  ChatStreamActivity,
} from "@/types";
import { idleChatStreamActivity } from "@/lib/chat-activity";

export type ChatSessionRuntime = {
  messages: ChatMessage[];
  isStreaming: boolean;
  isInsertReady: boolean;
  isStopping: boolean;
  streamActivity: ChatStreamActivity;
  transportError: ChatErrorBlock | null;
  submittedInteractionKeys: ReadonlySet<string>;
  nextEventCursor: number;
  needsHistoryRefresh: boolean;
};

export type ChatRuntimeUpdater =
  (runtime: ChatSessionRuntime) => ChatSessionRuntime;

type RuntimeRekeyOptions = {
  controller: AbortController;
};

const RUNTIME_CACHE_MAX = 20;
const selectedSession = shallowRef<string | null>(null);
const selectedRuntimeKey = shallowRef<string | null>(null);
const runtimes = shallowRef<ReadonlyMap<string, ChatSessionRuntime>>(new Map());
const streamControllers = new Map<string, AbortController>();
const historyRequestIds = new Map<string, number>();
let historyRequestSequence = 0;

function newRuntime(messages: ChatMessage[] = []): ChatSessionRuntime {
  return {
    messages,
    isStreaming: false,
    isInsertReady: false,
    isStopping: false,
    streamActivity: idleChatStreamActivity(),
    transportError: null,
    submittedInteractionKeys: new Set(),
    nextEventCursor: 0,
    needsHistoryRefresh: false,
  };
}

const EMPTY_RUNTIME = newRuntime();

function pruneRuntimeCache(next: Map<string, ChatSessionRuntime>) {
  if (next.size <= RUNTIME_CACHE_MAX) return;

  for (const [key, runtime] of next) {
    if (next.size <= RUNTIME_CACHE_MAX) break;
    if (key === selectedRuntimeKey.value || runtime.isStreaming || streamControllers.has(key)) continue;
    next.delete(key);
    historyRequestIds.delete(key);
  }
}

function setRuntime(key: string, runtime: ChatSessionRuntime) {
  const next = new Map(runtimes.value);
  next.delete(key);
  next.set(key, runtime);
  pruneRuntimeCache(next);
  runtimes.value = next;
}

function updateRuntime(key: string, update: ChatRuntimeUpdater) {
  setRuntime(key, update(runtimes.value.get(key) ?? newRuntime()));
}

function removeRuntime(key: string) {
  const next = new Map(runtimes.value);
  next.delete(key);
  runtimes.value = next;
  historyRequestIds.delete(key);
}

function createDraftRuntime() {
  const key = `draft:${createClientId()}`;
  setRuntime(key, newRuntime());
  selectedRuntimeKey.value = key;
  selectedSession.value = null;
  return key;
}

function ensureSelectedRuntime() {
  return selectedRuntimeKey.value ?? createDraftRuntime();
}

function ensureRuntime(key: string) {
  if (!runtimes.value.has(key)) setRuntime(key, newRuntime());
}

function selectSession(sessionId: string | null) {
  if (!sessionId) {
    createDraftRuntime();
    return;
  }

  selectedSession.value = sessionId;
  selectedRuntimeKey.value = sessionId;
  if (!runtimes.value.has(sessionId)) {
    setRuntime(sessionId, newRuntime());
  }
}

function rekeyRuntime(oldKey: string, sessionId: string, options: RuntimeRekeyOptions) {
  if (oldKey === sessionId) return;

  const oldRuntime = runtimes.value.get(oldKey) ?? newRuntime();
  const existingRuntime = runtimes.value.get(sessionId);
  const messagesById = new Map<string, ChatMessage>();
  for (const message of existingRuntime?.messages ?? []) messagesById.set(message.id, message);
  for (const message of oldRuntime.messages) messagesById.set(message.id, message);

  const nextRuntime: ChatSessionRuntime = {
    ...(existingRuntime ?? newRuntime()),
    ...oldRuntime,
    messages: [...messagesById.values()],
  };
  const next = new Map(runtimes.value);
  next.delete(oldKey);
  next.set(sessionId, nextRuntime);
  runtimes.value = next;

  const controller = streamControllers.get(oldKey);
  if (controller === options.controller) {
    streamControllers.delete(oldKey);
    streamControllers.set(sessionId, controller);
  }

  if (selectedRuntimeKey.value === oldKey) {
    selectedRuntimeKey.value = sessionId;
    selectedSession.value = sessionId;
  }

  const historyRequestId = historyRequestIds.get(oldKey);
  historyRequestIds.delete(oldKey);
  if (historyRequestId != null) historyRequestIds.set(sessionId, historyRequestId);
}

const selectedRuntime = computed(() => {
  const key = selectedRuntimeKey.value;
  return key ? runtimes.value.get(key) ?? EMPTY_RUNTIME : EMPTY_RUNTIME;
});
const messages = computed(() => selectedRuntime.value.messages);
const isStreaming = computed(() => selectedRuntime.value.isStreaming);
const isInsertReady = computed(() => selectedRuntime.value.isInsertReady);
const isStopping = computed(() => selectedRuntime.value.isStopping);
const streamActivity = computed(() => selectedRuntime.value.streamActivity);
const transportError = computed(() => selectedRuntime.value.transportError);
const activeInteractionKey = computed(() =>
  activeUserInteractionKey(messages.value, {
    isStreaming: isStreaming.value,
    isAwaitingUser: streamActivity.value.phase === "awaiting_user",
    submittedInteractionKeys: selectedRuntime.value.submittedInteractionKeys,
  })
);

function getRuntime(key: string) {
  return runtimes.value.get(key);
}

function invalidateHistory(runtimeKey: string) {
  const requestId = ++historyRequestSequence;
  historyRequestIds.set(runtimeKey, requestId);
  return requestId;
}

function isHistoryRequestCurrent(runtimeKey: string, requestId: number) {
  return historyRequestIds.get(runtimeKey) === requestId;
}

function getController(key: string) {
  return streamControllers.get(key);
}

function hasController(key: string) {
  return streamControllers.has(key);
}

function setController(key: string, controller: AbortController) {
  streamControllers.set(key, controller);
}

function deleteController(key: string, controller?: AbortController) {
  if (controller && streamControllers.get(key) !== controller) return false;
  return streamControllers.delete(key);
}

function dispose() {
  for (const controller of streamControllers.values()) controller.abort();
  streamControllers.clear();
  historyRequestIds.clear();
  runtimes.value = new Map();
  selectedRuntimeKey.value = null;
  selectedSession.value = null;
}

export function useChatRuntimeStore() {
  return {
    messages,
    selectedSession: readonly(selectedSession),
    selectedRuntimeKey: readonly(selectedRuntimeKey),
    isStreaming,
    isInsertReady,
    isStopping,
    streamActivity,
    transportError,
    activeInteractionKey,
    getRuntime,
    ensureRuntime,
    updateRuntime,
    removeRuntime,
    createDraftRuntime,
    ensureSelectedRuntime,
    selectSession,
    rekeyRuntime,
    getController,
    hasController,
    setController,
    deleteController,
    invalidateHistory,
    isHistoryRequestCurrent,
    dispose,
  };
}
