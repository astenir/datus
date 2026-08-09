import { chatApi } from "@/lib/api";
import {
  activeUserInteractionKey,
  buildUserInteractionInput,
  friendlyTransportErrorBlock,
} from "@/lib/chat";
import { continuingChatStreamActivity, idleChatStreamActivity } from "@/lib/chat-activity";
import type { InsertMessageData } from "@/types";
import type { ChatRuntimeUpdater, ChatSessionRuntime } from "./useChatRuntimeStore";

export interface ChatActionsRuntimeSource {
  getSelectedSession: () => string | null;
  getSelectedRuntimeKey: () => string | null;
  getIsStreaming: () => boolean;
  getIsInsertReady: () => boolean;
  getIsStopping: () => boolean;
  getActiveInteractionKey: () => string | null;
  getRuntime: (runtimeKey: string) => ChatSessionRuntime | undefined;
  getController: (runtimeKey: string) => AbortController | undefined;
  deleteController: (runtimeKey: string, controller?: AbortController) => boolean;
  updateRuntime: (runtimeKey: string, update: ChatRuntimeUpdater) => void;
  removeRuntime: (runtimeKey: string) => void;
}

export interface ChatActionsHistorySource {
  loadSessions: () => Promise<void>;
  loadSessionHistory: (sessionId: string) => Promise<void>;
  markSessionActive: (sessionId: string, active: boolean) => void;
  clearResumeAttempt: (sessionId: string) => void;
  removeSession: (sessionId: string) => void;
}

export interface UseChatActionsOptions {
  effectiveBase: () => string;
  runtime: ChatActionsRuntimeSource;
  history: ChatActionsHistorySource;
  clearSelectedSession: () => void;
}

export function useChatActions(options: UseChatActionsOptions) {
  async function stopSession() {
    const runtimeKey = options.runtime.getSelectedRuntimeKey();
    if (!runtimeKey) return;
    const sessionId = options.runtime.getSelectedSession();
    const currentRuntime = options.runtime.getRuntime(runtimeKey);
    if (!currentRuntime?.isStreaming || currentRuntime.isStopping) return;
    const wasInsertReady = currentRuntime.isInsertReady;
    let stopSucceeded = false;

    options.runtime.updateRuntime(runtimeKey, runtime => ({
      ...runtime,
      isStreaming: true,
      isInsertReady: false,
      isStopping: true,
      streamActivity: { ...runtime.streamActivity, phase: "stopping" },
    }));

    const controller = options.runtime.getController(runtimeKey);
    if (controller) {
      options.runtime.deleteController(runtimeKey, controller);
      controller.abort();
    }

    try {
      if (sessionId) {
        await chatApi.stop(options.effectiveBase(), sessionId);
        stopSucceeded = true;
        options.history.markSessionActive(sessionId, false);
        await options.history.loadSessionHistory(sessionId);
      }
    } catch (error) {
      console.error("Failed to stop session:", error);
      options.runtime.updateRuntime(runtimeKey, runtime => ({
        ...runtime,
        transportError: friendlyTransportErrorBlock(error, "stop"),
      }));
    } finally {
      options.runtime.updateRuntime(runtimeKey, runtime => ({
        ...runtime,
        isStreaming: false,
        isInsertReady: stopSucceeded ? false : wasInsertReady,
        isStopping: false,
        streamActivity: idleChatStreamActivity(),
        submittedInteractionKeys: new Set(),
      }));
      if (sessionId) options.history.clearResumeAttempt(sessionId);
      void options.history.loadSessions();
    }
  }

  async function deleteSession(sessionId: string) {
    const controller = options.runtime.getController(sessionId);
    if (controller) {
      options.runtime.deleteController(sessionId, controller);
      controller.abort();
    }
    try {
      await chatApi.deleteSession(options.effectiveBase(), sessionId);
      options.runtime.removeRuntime(sessionId);
      options.history.clearResumeAttempt(sessionId);
      options.history.removeSession(sessionId);
      if (options.runtime.getSelectedSession() === sessionId) options.clearSelectedSession();
      await options.history.loadSessions();
    } catch (error) {
      console.error("Failed to delete session:", error);
      throw error;
    }
  }

  async function compactSession(sessionId: string) {
    try {
      const result = await chatApi.compact(options.effectiveBase(), sessionId);
      if (result?.success) await options.history.loadSessionHistory(sessionId);
      return result;
    } catch (error) {
      console.error("Failed to compact session:", error);
      throw error;
    }
  }

  async function insertMessage(message: string): Promise<InsertMessageData> {
    const sessionId = options.runtime.getSelectedSession();
    const text = message.trim();
    if (!sessionId) throw new Error("当前会话尚未建立，无法补充消息");
    if (!text) throw new Error("补充内容不能为空");
    if (!options.runtime.getIsStreaming()) throw new Error("当前会话未在生成中，无法补充消息");
    if (options.runtime.getIsStopping()) throw new Error("正在停止当前任务");
    if (!options.runtime.getIsInsertReady()) throw new Error("正在建立会话，请稍候");

    const result = await chatApi.insert(options.effectiveBase(), sessionId, text);
    if (!result) throw new Error("后端未确认本次补充消息");
    return result;
  }

  async function sendInteraction(interactionKey: string, answers: string | string[][]) {
    const sessionId = options.runtime.getSelectedSession();
    if (!sessionId) throw new Error("会话未就绪");
    if (!interactionKey) throw new Error("交互请求未就绪");
    if (options.runtime.getActiveInteractionKey() !== interactionKey) throw new Error("交互请求已失效");

    options.runtime.updateRuntime(sessionId, runtime => ({
      ...runtime,
      submittedInteractionKeys: new Set([...runtime.submittedInteractionKeys, interactionKey]),
    }));
    try {
      const result = await chatApi.userInteraction(
        options.effectiveBase(),
        buildUserInteractionInput(sessionId, interactionKey, answers),
      );
      if (!result) throw new Error("后端未接受本次交互提交");
      options.runtime.updateRuntime(sessionId, runtime => {
        const pendingInteractionKey = activeUserInteractionKey(runtime.messages, {
          isStreaming: runtime.isStreaming,
          isAwaitingUser: runtime.streamActivity.phase === "awaiting_user",
          submittedInteractionKeys: runtime.submittedInteractionKeys,
        });

        return {
          ...runtime,
          streamActivity: pendingInteractionKey && pendingInteractionKey !== interactionKey
            ? runtime.streamActivity
            : continuingChatStreamActivity(runtime.streamActivity),
        };
      });
    } catch (error) {
      options.runtime.updateRuntime(sessionId, runtime => {
        const next = new Set(runtime.submittedInteractionKeys);
        next.delete(interactionKey);
        return { ...runtime, submittedInteractionKeys: next };
      });
      throw error;
    }
  }

  return {
    stopSession,
    deleteSession,
    compactSession,
    insertMessage,
    sendInteraction,
  };
}
