import type {
  CatalogRecord,
  ActiveUserInteraction,
  ChatDisplayMessage,
  ChatMessage,
  InteractionSummaryStatus,
  MessageDisplayBlock,
  PlanConfirmationOutcome,
  ChatSessionOption,
  MessageBlock,
  MessageOperation,
  ParsedMessage,
  SelectOption,
  SseEvent,
  SseMessagePayload
} from "@/types";
import { request } from "@/lib/request";
import { isSqlExecutionTool, toolResultStatus } from "@/lib/tool-display";
import { isInteractionToolName, normalizedToolName } from "@/lib/tool-presentation";

export type ChatStreamRequestInput = {
  message: string;
  sessionId: string;
  selectedAgent: string;
  model: string;
  datasource: string;
  database: string;
  schema: string;
  language: string;
  planMode: boolean;
  permissionMode: string;
};

const MODEL_CREDENTIAL_VALUE_PREFIX = "credential:";

export function resolveChatModelSelection(value: string) {
  if (value.startsWith(MODEL_CREDENTIAL_VALUE_PREFIX)) {
    return {
      model: null,
      model_credential_id: value.slice(MODEL_CREDENTIAL_VALUE_PREFIX.length) || null,
    };
  }
  return { model: value || null, model_credential_id: null };
}

export function buildChatStreamRequest({
  message,
  sessionId,
  selectedAgent,
  model,
  datasource,
  database,
  schema,
  language,
  planMode,
  permissionMode
}: ChatStreamRequestInput) {
  const modelSelection = resolveChatModelSelection(model);
  return {
    message,
    session_id: sessionId || null,
    subagent_id: selectedAgent || null,
    ...modelSelection,
    datasource: datasource || null,
    database: database || null,
    db_schema: schema || null,
    language: language || null,
    source: "web",
    stream_response: true,
    plan_mode: planMode,
    permission_mode: permissionMode || null
  };
}

export function buildUserInteractionInput(
  sessionId: string,
  interactionKey: string,
  answers: string | string[][],
) {
  const input = typeof answers === "string" ? [[answers]] : answers;
  return {
    session_id: sessionId,
    interaction_key: interactionKey,
    input,
  };
}

export function shouldExitPlanModeAfterInteraction(
  interaction: ActiveUserInteraction | null,
  interactionKey: string,
  answers: readonly (readonly string[])[],
) {
  if (interaction?.interactionKey !== interactionKey) return false;
  if (interaction.block.actionType !== "confirm_plan") return false;

  const decision = answers[0]?.[0]?.trim().toLowerCase();
  return decision === "confirm" || decision === "cancel";
}

export function normalizeBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

export function chatSessionsPath() {
  return "/api/v1/chat/sessions";
}

export function isFeedbackSessionId(sessionId: string) {
  return sessionId.startsWith("feedback_session_");
}

export function filterVisibleChatSessions(sessions: ChatSessionOption[]) {
  return sessions.filter((session) => !isFeedbackSessionId(session.session_id));
}

function callToolIdFromPayload(payload: Record<string, unknown>) {
  return stringifyContent(payload.callToolId ?? payload.call_tool_id).trim() || undefined;
}

function toolDurationFromPayload(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
}

function parseInteractionRequests(rawRequests: readonly unknown[]) {
  return rawRequests.map((request) => {
    const req = isRecord(request) ? request : {};
    const rawOptions = Array.isArray(req.options) ? req.options : [];
    const options = rawOptions.map((option) => {
      const opt = isRecord(option) ? option : {};
      const key = stringifyContent(opt.key).trim();
      const title = stringifyContent(opt.title ?? opt.key).trim();
      return { key, title: title || key };
    });
    const title = stringifyContent(req.title).trim();
    const content = stringifyContent(req.content).trim() || title || "交互请求";
    const contentType = stringifyContent(req.contentType ?? req.content_type).trim();
    const defaultChoice = stringifyContent(req.defaultChoice ?? req.default_choice).trim();
    const allowFreeText = req.allowFreeText ?? req.allow_free_text ?? false;
    const multiSelect = req.multiSelect ?? req.multi_select ?? false;
    const parsed: Extract<MessageBlock, { type: "user-interaction" }>["requests"][number] = {
      content,
      options,
      allowFreeText: !!allowFreeText,
      multiSelect: !!multiSelect,
    };
    if (title) parsed.title = title;
    if (contentType) parsed.contentType = contentType;
    if (defaultChoice) parsed.defaultChoice = defaultChoice;
    return parsed;
  });
}

function normalizeInteractionSummaryStatus(value: unknown): InteractionSummaryStatus {
  const status = stringifyContent(value).trim().toLowerCase();
  if (status === "answered" || status === "cancelled" || status === "failed") return status;
  return "unknown";
}

const friendlyChatErrors: Record<string, { title: string; message: string; tone?: "error" | "warning" | "info" }> = {
  QUOTA_EXCEEDED: {
    title: "对话额度已用完",
    message: "本轮请求已停止，因为当前账号或角色的对话额度已达到上限。请稍后再试，或联系管理员调整额度。",
  },
  AUTH_REQUIRED: {
    title: "需要重新登录",
    message: "当前会话没有有效登录凭证。请重新登录或切换到可用账号后再试。",
  },
  AUTH_TOKEN_INVALID: {
    title: "登录已过期",
    message: "当前登录凭证已失效。请重新登录后再继续本次操作。",
  },
  AUTH_USER_DISABLED: {
    title: "账号不可用",
    message: "当前账号已被停用或不再允许登录。请联系管理员确认账号状态。",
  },
  USER_DISABLED: {
    title: "账号不可用",
    message: "当前账号已被停用或不再允许登录。请联系管理员确认账号状态。",
  },
  AUTH_USERINFO_TIMEOUT: {
    title: "认证服务暂时不可用",
    message: "身份服务响应超时，请稍后重试。当前登录状态不会因此被清除。",
  },
  AUTH_USERINFO_UNAVAILABLE: {
    title: "认证服务暂时不可用",
    message: "身份服务当前无法访问，请稍后重试。当前登录状态不会因此被清除。",
  },
  AUTH_USERINFO_INVALID: {
    title: "认证服务响应异常",
    message: "身份服务返回了无法识别的结果，请稍后重试或联系管理员。",
  },
  FORBIDDEN: {
    title: "没有操作权限",
    message: "当前账号没有执行这次操作所需的权限。如需继续，请联系管理员开通对应权限。",
  },
  PERMISSION_DENIED: {
    title: "权限受限",
    message: "当前权限策略拦截了这次操作。换参数通常不会绕过限制，请联系管理员确认授权范围。",
    tone: "warning",
  },
  AGENT_FORBIDDEN: {
    title: "无法使用当前 Agent",
    message: "当前账号不在这个 Agent 的授权范围内。请选择其他可用 Agent，或联系管理员调整访问范围。",
  },
  DATASOURCE_ACCESS_DENIED: {
    title: "数据源访问受限",
    message: "当前账号无权访问本次请求使用的数据源。请选择已授权的数据源，或联系管理员调整授权范围。",
  },
  DATASOURCE_FORBIDDEN: {
    title: "数据源访问受限",
    message: "当前账号无权访问本次请求使用的数据源。请选择已授权的数据源，或联系管理员调整授权范围。",
  },
  DATASOURCE_UNAVAILABLE: {
    title: "数据源不可用",
    message: "当前数据源暂时无法访问。请检查数据源连接、授权范围或稍后重试。",
  },
  MODEL_UNAVAILABLE: {
    title: "模型暂时不可用",
    message: "当前模型服务没有完成请求。请稍后重试，或切换到其他可用模型。",
  },
  MODEL_CONFIG_REQUIRED: {
    title: "模型配置缺失",
    message: "系统还没有可用的模型配置。请先在配置中心设置模型 Provider 和模型名。",
  },
  MODEL_CREDENTIAL_UNAVAILABLE: {
    title: "模型凭证不可用",
    message: "当前模型凭证缺失、已失效或暂时不可用。请选择其他可用模型，或联系管理员检查模型配置。",
  },
  MODEL_FORBIDDEN: {
    title: "模型访问受限",
    message: "当前账号无权使用所选模型。请选择授权范围内的模型，或联系管理员调整模型权限。",
  },
  RATE_LIMITED: {
    title: "请求过于频繁",
    message: "当前请求触发了限流保护。请稍后再试。",
  },
  UPSTREAM_RATE_LIMITED: {
    title: "模型请求过于频繁",
    message: "上游模型服务当前触发了限流保护。请稍后重试，或切换到其他可用模型。",
  },
  UPSTREAM_TIMEOUT: {
    title: "模型服务响应超时",
    message: "上游模型服务未能在规定时间内完成请求。请稍后重试，或缩小本次问题范围。",
  },
  UPSTREAM_UNAVAILABLE: {
    title: "模型服务暂时不可用",
    message: "上游模型服务当前无法访问。请稍后重试，或切换到其他可用模型。",
  },
  UPSTREAM_ERROR: {
    title: "模型服务请求失败",
    message: "上游模型服务未能完成本次请求。请稍后重试；若问题持续，请联系管理员检查模型配置。",
  },
  CONTEXT_LENGTH_EXCEEDED: {
    title: "对话内容超出模型限制",
    message: "本次请求包含的上下文过长。请精简问题、减少引用内容，或新建会话后重试。",
  },
  UPSTREAM_AUTH_ERROR: {
    title: "模型服务认证失败",
    message: "上游模型凭证无效或已失效。请选择其他可用模型，或联系管理员检查模型凭证。",
  },
  CONTENT_POLICY_VIOLATION: {
    title: "请求被内容策略拦截",
    message: "本次请求不符合上游模型的内容安全策略。请调整问题内容后重试。",
    tone: "warning",
  },
  UPSTREAM_BAD_REQUEST: {
    title: "模型无法处理当前请求",
    message: "上游模型认为本次请求参数或内容无效。请调整问题内容后重试；若问题持续，请联系管理员。",
  },
  INTERNAL_ERROR: {
    title: "服务内部错误",
    message: "服务在处理本次请求时遇到内部错误。请稍后重试；若问题持续，请联系管理员查看后台日志。",
  },
  CHAT_CANCELLED: {
    title: "已停止生成",
    message: "本轮对话已停止。已完成的内容仍会保留，你可以继续发送新的消息。",
    tone: "info",
  },
  CHAT_CAPACITY_EXCEEDED: {
    title: "对话服务繁忙",
    message: "当前同时执行的对话较多，暂时无法启动本轮请求。请稍后重试。",
  },
  CHAT_EVENT_BUFFER_EXPIRED: {
    title: "实时连接已过期",
    message: "本轮对话的实时事件已经过期。请重新打开会话以加载已保存的内容。",
  },
  CHAT_EXECUTION_ERROR: {
    title: "对话执行未完成",
    message: "服务在执行本轮对话时遇到问题。请稍后重试；若问题持续，请联系管理员查看后台日志。",
  },
  CHAT_START_FAILED: {
    title: "对话启动失败",
    message: "服务暂时无法启动本轮对话。请稍后重试；若问题持续，请联系管理员查看后台日志。",
  },
  PRE_CHAT_HOOK_ERROR: {
    title: "对话准备失败",
    message: "服务在准备本轮对话时遇到问题，尚未开始执行。请稍后重试或联系管理员。",
  },
  SESSION_FORBIDDEN: {
    title: "无法访问会话",
    message: "当前账号无权查看或操作这个会话。请切换到自己的会话，或联系管理员确认会话归属。",
  },
  SQL_POLICY_PRINCIPAL_REQUIRED: {
    title: "数据访问身份缺失",
    message: "系统无法确认本次数据访问所需的执行身份，因此已停止操作。请联系管理员检查数据权限配置。",
  },
  POLICY_DENIED: {
    title: "操作被安全策略拦截",
    message: "本次操作不符合当前安全策略。换参数通常不会绕过限制，请联系管理员确认允许的操作范围。",
    tone: "warning",
  },
  PLATFORM_STATUS_FORBIDDEN: {
    title: "服务当前不可执行",
    message: "平台目前处于只读或维护状态，暂时不能执行本次操作。请稍后重试或联系管理员。",
  },
  RESOURCE_NOT_FOUND: {
    title: "资源不存在或不可访问",
    message: "目标资源可能已被删除，或当前账号没有访问权限。请刷新后重试。",
  },
  ARTIFACT_FORBIDDEN: {
    title: "无法访问产物",
    message: "当前账号无权查看或操作这个报表或仪表盘。请联系所有者或管理员确认共享范围。",
  },
  ENTERPRISE_DISABLED: {
    title: "企业功能未启用",
    message: "当前部署没有启用这项企业功能。请联系管理员检查服务配置。",
  },
  ENTERPRISE_ROUTE_DISABLED: {
    title: "当前功能不可用",
    message: "这项功能在当前企业部署中未开放。请联系管理员确认可用功能范围。",
  },
  TIMEOUT: {
    title: "请求超时",
    message: "服务处理时间过长，已停止等待。请稍后重试，或缩小本次问题范围。",
  },
};

function canonicalErrorCode(code: string) {
  if (code === "QUATA_EXCEEDED") return "QUOTA_EXCEEDED";
  return code;
}

function errorCodeFromUnknown(value: unknown): string | undefined {
  const text = stringifyContent(value).trim();
  if (!/^[A-Z][A-Z0-9_]{2,}$/.test(text)) return undefined;
  return canonicalErrorCode(text);
}

function errorCodeFromText(value: unknown): string | undefined {
  const text = stringifyContent(value).trim();
  const exactCode = errorCodeFromUnknown(text);
  if (exactCode) return exactCode;
  const match = text.match(/^([A-Z][A-Z0-9_]{2,})(?=\s*[:：]|\s|$)/);
  return match?.[1] ? canonicalErrorCode(match[1]) : undefined;
}

function safePermissionMessage(rawMessage: string) {
  if (!rawMessage.startsWith("权限受限：")) return "";
  return rawMessage.slice("权限受限：".length).trim();
}

export function friendlyChatErrorBlock(input: {
  code?: unknown;
  message?: unknown;
  fallback?: unknown;
}): Extract<MessageBlock, { type: "error" }> {
  const rawMessage = stringifyContent(input.message ?? input.fallback).trim();
  const code = errorCodeFromUnknown(input.code) ?? errorCodeFromText(rawMessage);
  const meta = code ? friendlyChatErrors[code] : undefined;

  if (meta) {
    if (code === "CHAT_CANCELLED") {
      return {
        type: "error",
        title: meta.title,
        message: meta.message,
        tone: "info",
      };
    }

    const permissionMessage = code === "PERMISSION_DENIED"
      ? safePermissionMessage(rawMessage)
      : "";
    return {
      type: "error",
      title: meta.title,
      message: permissionMessage || meta.message,
      ...(meta.tone ? { tone: meta.tone } : {}),
      code,
    };
  }

  if (code) {
    return {
      type: "error",
      title: "请求没有完成",
      message: "服务返回了错误码，当前前端还没有对应说明。请联系管理员查看后台日志。",
      code,
    };
  }

  return {
    type: "error",
    title: "请求没有完成",
    message: "服务未能完成本次请求。请稍后重试；若问题持续，请联系管理员查看后台日志。",
  };
}

type TransportErrorContext = "history" | "stream" | "resume" | "stop" | "insert";

const transportErrorTitles: Record<TransportErrorContext, string> = {
  history: "会话历史加载失败",
  stream: "无法连接到对话服务",
  resume: "恢复对话失败",
  stop: "停止会话失败",
  insert: "消息发送失败",
};

export function friendlyTransportErrorBlock(
  error: unknown,
  context: TransportErrorContext,
): Extract<MessageBlock, { type: "error" }> {
  const record = isRecord(error) ? error : {};
  const httpCode = errorCodeFromUnknown(record.code);
  if (httpCode) return friendlyChatErrorBlock({ code: httpCode });

  const status = typeof record.status === "number" ? record.status : undefined;
  if (status === 401) return friendlyChatErrorBlock({ code: "AUTH_REQUIRED" });
  if (status === 403) return friendlyChatErrorBlock({ code: "FORBIDDEN" });

  return {
    type: "error",
    title: transportErrorTitles[context],
    message: status
      ? "服务暂时无法完成这次操作。请稍后重试；若问题持续，请联系管理员。"
      : "请检查网络连接和服务地址后重试。已保存的会话内容不会受影响。",
  };
}

function friendlyInlineErrorText(rawError: string, fallback: string) {
  const code = errorCodeFromText(rawError);
  if (!code) return fallback;
  return friendlyChatErrors[code]?.message ?? fallback;
}

function parseInteractionSummaryAnswers(rawAnswers: unknown) {
  if (!Array.isArray(rawAnswers)) return [];

  return rawAnswers.map((item) => {
    const answerItem = isRecord(item) ? item : {};
    const rawAnswer = answerItem.answer;
    const answer = Array.isArray(rawAnswer)
      ? rawAnswer.map((entry) => stringifyContent(entry).trim()).filter(Boolean)
      : stringifyContent(rawAnswer).trim();
    return {
      question: stringifyContent(answerItem.question ?? answerItem.content).trim() || "交互请求",
      answer,
    };
  });
}

function parentActionIdFromPayload(payload: SseMessagePayload) {
  const parentActionId = payload.parent_action_id ?? payload.parentActionId;
  return typeof parentActionId === "string" && parentActionId.trim() ? parentActionId.trim() : undefined;
}

function childMessagesForParent(
  messages: readonly ChatMessage[],
  parentCallIds: ReadonlySet<string>,
) {
  const childGroups = new Map<string, ChatMessage[]>();

  for (const message of messages) {
    if (!message.parentActionId || !message.depth || !parentCallIds.has(message.parentActionId)) continue;

    const group = childGroups.get(message.parentActionId);
    if (group) {
      group.push(message);
    } else {
      childGroups.set(message.parentActionId, [message]);
    }
  }

  const displayGroups = new Map<string, ChatDisplayMessage[]>();
  for (const [parentActionId, childMessages] of childGroups) {
    displayGroups.set(parentActionId, mergeToolExecutionMessages(childMessages));
  }

  return displayGroups;
}

function mergeToolCallWithResult(
  block: Extract<MessageBlock, { type: "tool-call" }>,
  result?: Extract<MessageBlock, { type: "tool-result" }>,
  childMessages: readonly ChatDisplayMessage[] = [],
): MessageDisplayBlock {
  if (!result) {
    if (childMessages.length === 0) return block;
    return { ...block, childMessages };
  }

  const callToolId = block.callToolId;
  if (!callToolId) {
    if (childMessages.length === 0) return block;
    return { ...block, childMessages };
  }

  const mergedBlock: Extract<MessageDisplayBlock, { type: "tool-execution" }> = {
    type: "tool-execution",
    callToolId,
    toolName: block.toolName,
    params: block.params,
    result: result.result,
  };
  if (block.proxied !== undefined) mergedBlock.proxied = block.proxied;
  if (result.duration != null) mergedBlock.duration = result.duration;
  if (result.shortDesc || block.shortDesc) mergedBlock.shortDesc = result.shortDesc || block.shortDesc;
  if (result.errorText) mergedBlock.errorText = result.errorText;
  if (result.resultStatus) mergedBlock.resultStatus = result.resultStatus;
  if (childMessages.length > 0) mergedBlock.childMessages = childMessages;
  return mergedBlock;
}

export function mergeToolExecutionBlocks(blocks: readonly MessageDisplayBlock[]): MessageDisplayBlock[] {
  const resultByCallId = new Map<string, Extract<MessageBlock, { type: "tool-result" }>>();
  for (const block of blocks) {
    if (block.type === "tool-result" && block.callToolId) {
      resultByCallId.set(block.callToolId, block);
    }
  }

  const consumedResultIds = new Set<string>();
  const merged: MessageDisplayBlock[] = [];

  for (const block of blocks) {
    if (block.type === "tool-call" && block.callToolId) {
      const blockWithCallId = { ...block, callToolId: block.callToolId };
      const result = resultByCallId.get(block.callToolId);
      if (result) {
        consumedResultIds.add(block.callToolId);
        merged.push(mergeToolCallWithResult(blockWithCallId, result, block.childMessages ?? []));
        continue;
      }
    }

    if (block.type === "tool-result" && block.callToolId && consumedResultIds.has(block.callToolId)) {
      continue;
    }

    merged.push(block);
  }

  return merged;
}

export function mergeToolExecutionMessages(messages: readonly ChatMessage[]): ChatDisplayMessage[] {
  const resultByCallId = new Map<string, { messageIndex: number; block: Extract<MessageBlock, { type: "tool-result" }> }>();
  const parentCallIds = new Set<string>();

  messages.forEach((message, messageIndex) => {
    for (const block of message.blocks ?? []) {
      if (block.type === "tool-call" && block.callToolId) {
        parentCallIds.add(block.callToolId);
      }
      if (block.type === "tool-result" && block.callToolId) {
        resultByCallId.set(block.callToolId, { messageIndex, block });
      }
    }
  });

  const childMessagesByParent = childMessagesForParent(messages, parentCallIds);
  const consumedResultKeys = new Set<string>();
  const mergedMessages: ChatDisplayMessage[] = [];

  messages.forEach((message, messageIndex) => {
    if (message.parentActionId && message.depth && parentCallIds.has(message.parentActionId)) {
      return;
    }

    if (!message.blocks?.length) {
      mergedMessages.push(message);
      return;
    }

    const blocks: MessageDisplayBlock[] = [];
    for (const block of message.blocks) {
      if (block.type === "tool-call" && block.callToolId) {
        const blockWithCallId = { ...block, callToolId: block.callToolId };
        const result = resultByCallId.get(block.callToolId);
        const childMessages = childMessagesByParent.get(block.callToolId) ?? [];
        if (result) {
          consumedResultKeys.add(`${result.messageIndex}:${block.callToolId}`);
          blocks.push(mergeToolCallWithResult(blockWithCallId, result.block, childMessages));
          continue;
        }
        if (childMessages.length > 0) {
          blocks.push(mergeToolCallWithResult(blockWithCallId, undefined, childMessages));
          continue;
        }
      }

      if (block.type === "tool-result" && block.callToolId && consumedResultKeys.has(`${messageIndex}:${block.callToolId}`)) {
        continue;
      }

      blocks.push(block);
    }

    if (blocks.length > 0) {
      mergedMessages.push({ ...message, blocks });
    }
  });

  return mergePlanConfirmationMessages(mergedMessages);
}

function mergePlanConfirmationMessages(messages: readonly ChatDisplayMessage[]): ChatDisplayMessage[] {
  const outcomesByContext = new Map<string, PlanConfirmationOutcome[]>();
  const withoutInteractionTools = messages.flatMap((message) => {
    if (!message.blocks?.length) return [message];

    const blocks: MessageDisplayBlock[] = [];
    for (const block of message.blocks) {
      if (!isInteractionToolBlock(block)) {
        blocks.push(block);
        continue;
      }

      if (normalizedToolName(block.toolName) === "confirm_plan") {
        const context = executionContextKey(message);
        const outcome = planOutcomeFromToolBlock(block);
        if (outcome) {
          const outcomes = outcomesByContext.get(context) ?? [];
          outcomes.push(outcome);
          outcomesByContext.set(context, outcomes);
        }
      }
    }

    if (blocks.length === 0) return [];
    return [{ ...message, blocks }];
  });

  const merged: ChatDisplayMessage[] = [];

  for (let index = 0; index < withoutInteractionTools.length; index += 1) {
    const previewMessage = withoutInteractionTools[index];
    const confirmationMessage = withoutInteractionTools[index + 1];
    const previewBlock = previewMessage?.blocks?.length === 1 ? previewMessage.blocks[0] : null;
    const interactionBlock = confirmationMessage?.blocks?.length === 1 ? confirmationMessage.blocks[0] : null;
    const sameExecutionContext = previewMessage?.depth === confirmationMessage?.depth &&
      previewMessage?.parentActionId === confirmationMessage?.parentActionId;
    const context = previewMessage ? executionContextKey(previewMessage) : "";
    const pendingOutcomes = outcomesByContext.get(context) ?? [];
    const outcome = pendingOutcomes.shift();

    if (
      previewBlock?.type === "plan-preview" &&
      interactionBlock?.type === "user-interaction" &&
      interactionBlock.actionType === "confirm_plan" &&
      sameExecutionContext
    ) {
      merged.push({
        ...confirmationMessage,
        content: previewMessage.content,
        blocks: [{
          type: "plan-confirmation",
          content: previewBlock.content,
          interaction: interactionBlock,
          ...(outcome ? { outcome } : {}),
        }],
      });
      index += 1;
      continue;
    }

    if (previewBlock?.type === "plan-preview" && outcome) {
      merged.push({
        ...previewMessage,
        blocks: [{
          type: "plan-confirmation",
          content: previewBlock.content,
          outcome,
        }],
      });
      continue;
    }

    if (previewMessage) merged.push(previewMessage);
  }

  return merged;
}

function isInteractionToolBlock(
  block: MessageDisplayBlock,
): block is Extract<MessageDisplayBlock, { type: "tool-call" | "tool-result" | "tool-execution" }> {
  return (
    block.type === "tool-call" ||
    block.type === "tool-result" ||
    block.type === "tool-execution"
  ) && isInteractionToolName(block.toolName);
}

function executionContextKey(message: Pick<ChatDisplayMessage, "depth" | "parentActionId">) {
  return `${message.depth ?? 0}:${message.parentActionId ?? "root"}`;
}

function planOutcomeFromToolBlock(
  block: Extract<MessageDisplayBlock, { type: "tool-call" | "tool-result" | "tool-execution" }>,
): PlanConfirmationOutcome | undefined {
  if (block.type === "tool-call") return undefined;
  if (block.errorText || block.resultStatus === "error") {
    return {
      status: "error",
      error: block.errorText || "计划确认失败，请重试。",
    };
  }

  const result = unwrapResultRecord(block.result);
  const status = typeof result?.status === "string" ? result.status.trim().toLowerCase() : "";
  if (status === "confirmed") return { status: "confirmed" };
  if (status === "cancelled") return { status: "cancelled" };
  if (status === "feedback") {
    const feedback = typeof result?.feedback === "string" ? result.feedback.trim() : "";
    return { status: "feedback", ...(feedback ? { feedback } : {}) };
  }
  return undefined;
}

function unwrapResultRecord(value: unknown): Record<string, unknown> | null {
  if (!isRecord(value)) return null;
  if (isRecord(value.result) && ("success" in value || Object.keys(value).length === 1)) return value.result;
  return value;
}

function isReviewableMessageBlock(block: MessageBlock) {
  if (block.type === "artifact") return true;
  if (block.type === "code") return true;
  if (block.type === "plan-preview") return block.content.trim().length > 0;
  if (block.type !== "markdown") return false;

  const content = block.content.trim();
  return content.length > 0 && !content.startsWith("**子 Agent 完成**");
}

export function isReviewableAssistantMessage(message: ChatMessage) {
  if (message.role !== "assistant") return false;
  if (message.depth && message.depth > 0) return false;

  const blocks = message.blocks?.length
    ? message.blocks
    : [{ type: "markdown" as const, content: message.content }];

  return blocks.some(isReviewableMessageBlock);
}

export function visibleMessageActionTargetId(
  messages: readonly ChatMessage[],
  options: { isStreaming?: boolean } = {},
) {
  const target = [...messages].reverse().find(isReviewableAssistantMessage);
  if (!target) return null;

  const latest = messages[messages.length - 1];
  if (options.isStreaming && latest?.id === target.id) return null;

  return target.id;
}

export function activeStreamingMessageId(messages: readonly ChatMessage[]) {
  return messages[messages.length - 1]?.id ?? null;
}

export function activeUserInteractionKey(
  messages: readonly ChatMessage[],
  options: {
    isStreaming?: boolean;
    submittedInteractionKeys?: ReadonlySet<string>;
  } = {},
) {
  if (!options.isStreaming) return null;

  const latestMessage = messages[messages.length - 1];
  const latestBlock = latestUserInteractionBlock(latestMessage);
  if (latestBlock?.type !== "user-interaction") return null;

  const interactionKey = latestBlock.interactionKey.trim();
  if (!interactionKey || options.submittedInteractionKeys?.has(interactionKey)) return null;

  return interactionKey;
}

export function activeUserInteractionRequest(
  messages: readonly ChatMessage[],
  activeInteractionKey: string | null | undefined,
): ActiveUserInteraction | null {
  const key = activeInteractionKey?.trim();
  if (!key) return null;

  for (const message of [...messages].reverse()) {
    const block = latestUserInteractionBlock(message);
    if (block?.interactionKey.trim() !== key) continue;

    const interaction: ActiveUserInteraction = {
      interactionKey: key,
      block,
      messageId: message.id,
    };
    if (message.depth != null) interaction.depth = message.depth;
    if (message.parentActionId) interaction.parentActionId = message.parentActionId;
    return interaction;
  }

  return null;
}

function latestUserInteractionBlock(message: ChatMessage | undefined) {
  const block = message?.blocks?.[message.blocks.length - 1];
  return block?.type === "user-interaction" ? block : null;
}

export function shouldResetConversationOnAgentChange() {
  return false;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export async function requestJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const callerSignal = init?.signal;
  const abortFromCaller = () => controller.abort(callerSignal?.reason);
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  if (callerSignal?.aborted) {
    abortFromCaller();
  } else {
    callerSignal?.addEventListener("abort", abortFromCaller, { once: true });
  }

  try {
    const hasBody = init?.body != null;
    const response = await request(`${normalizeBaseUrl(baseUrl)}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        ...init?.headers
      }
    });

    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", abortFromCaller);
  }
}

export class ApiResultError extends Error {
  constructor(
    message: string,
    readonly errorCode?: string,
    readonly data?: unknown,
  ) {
    super(message);
    this.name = "ApiResultError";
  }
}

export async function requestStream(baseUrl: string, path: string, body: unknown): Promise<ReadableStream<Uint8Array> | null> {
  const response = await request(`${normalizeBaseUrl(baseUrl)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  return response.body;
}

export function extractResultData<T>(payload: unknown): T | null {
  if (payload && typeof payload === "object" && "success" in payload) {
    const result = payload as { success?: boolean; data?: T; errorCode?: string; errorMessage?: string };
    if (!result.success) {
      throw new ApiResultError(
        result.errorMessage || result.errorCode || "Backend request failed",
        result.errorCode,
        result.data,
      );
    }
    return result.data ?? null;
  }
  return payload as T;
}

export function uniqueOptions(options: SelectOption[]) {
  const seen = new Set<string>();
  return options.filter((option) => {
    if (!option.value || seen.has(option.value)) return false;
    seen.add(option.value);
    return true;
  });
}

export function stringifyContent(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  return JSON.stringify(value, null, 2);
}

export function createClientId(prefix = "msg") {
  const cryptoApi = globalThis.crypto;
  if (typeof cryptoApi?.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  if (typeof cryptoApi?.getRandomValues === "function") {
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
  }

  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function databaseNameFromCatalog(item: CatalogRecord) {
  const name = stringifyContent(item.name);
  const schemaName = stringifyContent(item.schema_name);
  if (name && schemaName && name.endsWith(`.${schemaName}`)) {
    return name.slice(0, -schemaName.length - 1);
  }
  return name;
}

export function schemaNameFromCatalog(item: CatalogRecord) {
  return stringifyContent(item.schema_name);
}

export function schemaOptionsForDatabase(entries: readonly CatalogRecord[], databaseName: string) {
  return uniqueOptions(
    entries
      .filter((entry) => !databaseName || databaseNameFromCatalog(entry) === databaseName)
      .map((entry) => {
        const schemaName = schemaNameFromCatalog(entry);
        return { value: schemaName, label: schemaName };
      })
      .filter((option) => option.value)
  );
}

export function sessionTitle(session: ChatSessionOption) {
  const updatedAt = session.last_updated || session.created_at || "";
  return [session.session_id, sessionUserQueryText(session), updatedAt].filter(Boolean).join("\n");
}

export function sessionUserQueryText(session: ChatSessionOption): string {
  const text = stringifyContent(session.user_query).trim();
  if (text) return text.length > 60 ? `${text.slice(0, 60)}…` : text;
  if (session.total_turns && session.total_turns > 0) return `${session.total_turns} 轮对话`;
  return "";
}

export function formatSessionTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

export function contentFromPayloadBlocks(
  content: Array<{ type?: string; payload?: Record<string, unknown> }> | null | undefined = [],
  _operation: MessageOperation = "createMessage"
) {
  const items = Array.isArray(content) ? content : [];
  const blocks: MessageBlock[] = [];

  for (const item of items) {
    const payload = item && typeof item.payload === "object" && item.payload ? item.payload : {};
    const type = item?.type ?? "markdown";

    if (type === "markdown") {
      blocks.push({ type: "markdown", content: stringifyContent(payload.content) });
    } else if (type === "plan-preview") {
      blocks.push({ type: "plan-preview", content: stringifyContent(payload.content) });
    } else if (type === "thinking") {
      blocks.push({ type: "thinking", content: stringifyContent(payload.content) });
    } else if (type === "code") {
      const language = stringifyContent(payload.codeType ?? payload.code_type ?? "text") || "text";
      blocks.push({ type: "code", language, content: stringifyContent(payload.content ?? payload.code) });
    } else if (type === "call-tool") {
      const callToolId = callToolIdFromPayload(payload);
      const toolName = stringifyContent(payload.toolName ?? payload.tool_name ?? "tool");
      const toolParams = payload.toolParams ?? payload.tool_params ?? {};
      const shortDesc = stringifyContent(payload.shortDesc ?? payload.short_desc);
      const proxied = typeof payload.proxied === "boolean" ? payload.proxied : undefined;
      const block: Extract<MessageBlock, { type: "tool-call" }> = {
        type: "tool-call",
        callToolId,
        toolName,
        params: toolParams,
        ...(proxied !== undefined ? { proxied } : {}),
      };
      if (shortDesc) block.shortDesc = shortDesc;
      blocks.push(block);
    } else if (type === "call-tool-result") {
      const callToolId = callToolIdFromPayload(payload);
      const toolName = stringifyContent(payload.toolName ?? payload.tool_name ?? "tool");
      const duration = toolDurationFromPayload(payload.duration);
      const shortDesc = stringifyContent(payload.shortDesc ?? payload.short_desc);
      const errorText = toolErrorText(payload, toolName);
      const resultStatus = toolResultStatus(payload.result);
      const block: Extract<MessageBlock, { type: "tool-result" }> = {
        type: "tool-result",
        toolName,
        result: unwrapToolResult(payload.result),
      };
      if (callToolId) block.callToolId = callToolId;
      if (duration != null) block.duration = duration;
      if (shortDesc) block.shortDesc = shortDesc;
      if (errorText) block.errorText = errorText;
      if (resultStatus !== "unknown") block.resultStatus = resultStatus;
      blocks.push(block);
    } else if (type === "error") {
      blocks.push(friendlyChatErrorBlock({
        code: payload.errorType ?? payload.error_type ?? payload.errorCode ?? payload.error_code ?? payload.code,
        message: payload.error ?? payload.errorMessage ?? payload.error_message ?? payload.message ?? payload.content,
        fallback: payload,
      }));
    } else if (type === "user-interaction") {
      const interactionKey = stringifyContent(payload.interactionKey ?? payload.interaction_key);
      const actionType = stringifyContent(payload.actionType ?? payload.action_type ?? "interaction");
      const legacyRequest =
        payload.content || payload.options
          ? [{ content: payload.content, options: payload.options }]
          : [];
      const rawRequests = Array.isArray(payload.requests) ? payload.requests : legacyRequest;
      const requests = parseInteractionRequests(rawRequests);
      blocks.push({ type: "user-interaction", interactionKey, actionType, requests });
    } else if (type === "interaction-summary") {
      const actionType = stringifyContent(payload.actionType ?? payload.action_type ?? "interaction");
      const requests = parseInteractionRequests(Array.isArray(payload.requests) ? payload.requests : []);
      const answers = parseInteractionSummaryAnswers(payload.answers);
      const error = stringifyContent(payload.error).trim();
      const block: Extract<MessageBlock, { type: "interaction-summary" }> = {
        type: "interaction-summary",
        status: normalizeInteractionSummaryStatus(payload.status),
        actionType,
        requests,
        answers,
      };
      if (error) {
        block.error = friendlyInlineErrorText(
          error,
          "本次交互处理失败。请稍后重试；若问题持续，请联系管理员。",
        );
      }
      blocks.push(block);
    } else if (type === "subagent-complete") {
      const subagent = stringifyContent(payload.subagentType ?? payload.subagent_type ?? "subagent");
      const toolCount = payload.toolCount ?? payload.tool_count;
      const duration = toolDurationFromPayload(payload.duration);
      const rawErrorText = stringifyContent(payload.error).trim();
      const block: Extract<MessageBlock, { type: "subagent-complete" }> = {
        type: "subagent-complete",
        subagent,
      };
      if (typeof toolCount === "number") block.toolCount = toolCount;
      if (duration != null) block.duration = duration;
      if (rawErrorText) {
        block.errorText = friendlyInlineErrorText(
          rawErrorText,
          "子 Agent 执行失败。请稍后重试；若问题持续，请联系管理员。",
        );
      }
      blocks.push(block);
    } else if (type === "artifact") {
      const kind = stringifyContent(payload.kind ?? "dashboard");
      const slug = stringifyContent(payload.slug ?? "");
      const name = stringifyContent(payload.name ?? payload.slug ?? "artifact");
      const description = stringifyContent(payload.preview_summary ?? payload.description ?? "");
      const mode = stringifyContent(payload.mode);
      const block: Extract<MessageBlock, { type: "artifact" }> = { type: "artifact", kind, slug, name };
      if (description) block.description = description;
      if (mode) block.mode = mode;
      blocks.push(block);
    } else {
      if (typeof payload.content === "string") blocks.push({ type: "markdown", content: payload.content });
      else if (typeof payload.code === "string") blocks.push({ type: "markdown", content: payload.code });
      else blocks.push({ type: "markdown", content: stringifyContent(payload) });
    }
  }

  const text = blocks
    .map((block) => {
      if (block.type === "markdown") return block.content;
      if (block.type === "plan-preview") return block.content;
      if (block.type === "thinking") return block.content;
      if (block.type === "code") return block.content;
      if (block.type === "error") return `${block.title}\n${block.message}`;
      if (block.type === "tool-call") return `调用工具 ${block.toolName}`;
      if (block.type === "tool-result") return `工具结果 ${block.toolName}${block.shortDesc ? `\n${block.shortDesc}` : ""}`;
      if (block.type === "user-interaction") return `需要用户确认 (${block.actionType})`;
      if (block.type === "interaction-summary") return `交互摘要 (${block.status})`;
      if (block.type === "subagent-complete") return `子 Agent 完成 ${block.subagent}`;
      if (block.type === "artifact") return block.name;
      return "";
    })
    .filter(Boolean)
    .join("\n\n");

  return { text, blocks };
}

function unwrapToolResult(value: unknown): unknown {
  if (isRecord(value) && "result" in value) {
    return value.result;
  }
  return value;
}

const permissionDeniedToolPattern =
  /PERMISSION_DENIED:\s*Tool\s+'([^']+)'\s+\(([^)]+)\)\s+is blocked by the\s+'([^']+)'\s+permission profile/i;
const permissionModeDeniedPattern = /Permission mode '([^']+)' requires module\.chat\.permission_mode/i;
const datusSqlExecutionErrorPattern =
  /error_code=(500005|500006),\s*error_message=(?:Invalid SQL syntax in query|Failed to execute query on database)\.\s*Error details:\s*([\s\S]+)$/i;
const unsafeDatabaseDiagnosticPattern =
  /(?:https?:\/\/|(?:postgres(?:ql)?|mysql|oracle):\/\/|traceback\s+\(most recent call last\)|(?:password|passwd|credential|secret|token)\s*[=:]|(?:^|\s)\/(?:[^/\s]+\/){2,}[^/\s]+)/i;
const filesystemWriteTools = new Set(["write_file", "edit_file", "delete_file"]);

function permissionProfileLabel(profile: string) {
  const labels: Record<string, string> = {
    normal: "普通",
    auto: "自动",
    dangerous: "危险",
  };
  return labels[profile] ?? profile;
}

function friendlyDatusSqlExecutionError(rawError: string): string | undefined {
  const match = rawError.match(datusSqlExecutionErrorPattern);
  const errorCode = match?.[1];
  const details = match?.[2]?.trim();
  if (!errorCode || !details) return undefined;

  const hintMatch = details.match(/\bHINT:\s*([\s\S]*)$/i);
  const hint = hintMatch?.[1]?.trim() ?? "";
  const detailsBeforeHint = details.slice(0, hintMatch?.index ?? details.length).trim();
  const lineMatch = detailsBeforeHint.match(/\bLINE\s+(\d+):/i);
  const primary = detailsBeforeHint.replace(/\bLINE\s+\d+:[\s\S]*$/i, "").trim();

  if (!primary || primary.length > 800 || hint.length > 800) return undefined;
  if (unsafeDatabaseDiagnosticPattern.test(primary) || unsafeDatabaseDiagnosticPattern.test(hint)) {
    return undefined;
  }

  const parts = [`SQL 执行失败（错误码 ${errorCode}）：${primary}`];
  if (lineMatch?.[1]) parts.push(`错误位置：第 ${lineMatch[1]} 行`);
  if (hint) parts.push(`数据库提示：${hint}`);
  return parts.join("；");
}

export function friendlyToolErrorText(toolName: string, rawError: string): string {
  const error = rawError.trim();
  if (!error) return "";

  const toolDenied = error.match(permissionDeniedToolPattern);
  if (toolDenied) {
    const deniedTool = toolDenied[1] || toolName;
    const category = toolDenied[2] || "";
    const profile = toolDenied[3] || "";
    const profileText = profile ? `“${permissionProfileLabel(profile)}”权限模式` : "当前权限策略";

    if (category === "filesystem_tools" && filesystemWriteTools.has(deniedTool)) {
      return `权限受限：当前 Agent 或会话的工具策略不允许直接修改文件。${deniedTool} 已被${profileText}拦截，换路径或重试不会绕过限制。请联系管理员核对该 Agent 的工具策略。`;
    }

    return `权限受限：当前账号没有执行工具 ${deniedTool} 的权限，已被${profileText}拦截，换参数或重试不会绕过限制。`;
  }

  const modeDenied = error.match(permissionModeDeniedPattern);
  if (modeDenied) {
    const mode = modeDenied[1] || "高危";
    return `权限受限：当前账号不能切换到 ${permissionProfileLabel(mode)} 对话模式。如确需使用自动或危险工具权限，请联系管理员授予“高危对话模式”权限。`;
  }

  if (isSqlExecutionTool(toolName)) {
    const sqlExecutionError = friendlyDatusSqlExecutionError(error);
    if (sqlExecutionError) return sqlExecutionError;
  }

  return friendlyInlineErrorText(
    error,
    "工具执行失败。请稍后重试；若问题持续，请联系管理员。",
  );
}

function toolErrorText(payload: Record<string, unknown>, toolName: string): string | undefined {
  const directError = stringifyContent(payload.error).trim();
  if (directError) return friendlyToolErrorText(toolName, directError);

  const result = payload.result;
  if (isRecord(result)) {
    const nestedError = stringifyContent(result.error).trim();
    if (nestedError) return friendlyToolErrorText(toolName, nestedError);
  }

  return undefined;
}

export function parseSseBuffer(
  buffer: string,
  options: { flush?: boolean } = {}
): { events: SseEvent[]; rest: string } {
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = options.flush ? "" : (parts.pop() ?? "");
  if (options.flush && parts.length === 0 && buffer) parts.push(buffer);
  const events = parts
    .map((part) => {
      const event: SseEvent = {};
      const dataLines: string[] = [];

      for (const rawLine of part.split(/\r?\n/)) {
        const line = rawLine.trimEnd();
        if (!line || line.startsWith(":")) continue;
        const separator = line.indexOf(":");
        const field = separator >= 0 ? line.slice(0, separator) : line;
        const value = separator >= 0 ? line.slice(separator + 1).replace(/^ /, "") : "";

        if (field === "id") event.id = value;
        if (field === "event") event.event = value;
        if (field === "data") dataLines.push(value);
      }

      if (dataLines.length > 0) {
        const dataText = dataLines.join("\n");
        try {
          event.data = JSON.parse(dataText);
        } catch {
          event.data = dataText;
        }
      }

      return event;
    })
    .filter((event) => event.event || event.data);

  return { events, rest };
}

export function messageFromPayload(
  payload: SseMessagePayload,
  operation: MessageOperation = "createMessage",
  fallbackId: string = createClientId()
): ChatMessage | null {
  if (!payload.role) return null;

  const { text: content, blocks } = contentFromPayloadBlocks(payload.content, operation);
  if (!content) return null;

  return {
    id: String(payload.message_id ?? fallbackId),
    role: payload.role,
    content,
    blocks,
    depth: payload.depth,
    parentActionId: parentActionIdFromPayload(payload)
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isRole(value: unknown): value is NonNullable<SseMessagePayload["role"]> {
  return value === "user" || value === "assistant" || value === "system";
}

function normalizePayloadContent(value: unknown): SseMessagePayload["content"] {
  if (!Array.isArray(value)) return undefined;

  return value
    .map((item) => {
      if (!isRecord(item)) return null;
      const type = typeof item.type === "string" ? item.type : undefined;
      const payload = isRecord(item.payload) ? item.payload : undefined;
      const normalized: { type?: string; payload?: Record<string, unknown> } = {};
      if (type) normalized.type = type;
      if (payload) normalized.payload = payload;
      return normalized;
    })
    .filter((item): item is { type?: string; payload?: Record<string, unknown> } => item !== null);
}

function historyPayloadFromUnknown(value: unknown): SseMessagePayload | null {
  if (!isRecord(value) || !isRole(value.role)) return null;

  const messageId = value.message_id ?? value.messageId;
  const depth = typeof value.depth === "number" ? value.depth : undefined;
  const parentActionId = value.parent_action_id ?? value.parentActionId;

  return {
    message_id: typeof messageId === "string" || typeof messageId === "number" ? messageId : undefined,
    role: value.role,
    content: normalizePayloadContent(value.content),
    depth,
    parent_action_id: typeof parentActionId === "string" ? parentActionId : undefined
  };
}

export function normalizeHistoryMessages(items: readonly unknown[]) {
  let parsed: ChatMessage[] = [];

  for (const item of items) {
    const payload = historyPayloadFromUnknown(item);
    if (!payload) continue;

    const incoming = messageFromEvent({
      event: "message",
      data: { type: "createMessage", payload }
    });
    if (incoming) parsed = mergeMessage(parsed, incoming);
  }

  return parsed;
}

export function messageFromEvent(event: SseEvent): ParsedMessage | null {
  const data = event.data as
    | {
        type?: MessageOperation;
        payload?: SseMessagePayload;
        error?: string;
        error_type?: string;
        error_code?: string;
        errorCode?: string;
        errorMessage?: string;
        error_message?: string;
        code?: string;
        session_id?: string;
        total_tokens?: number;
        duration?: number;
      }
    | undefined;

  if (!data) return null;

  const errorMessage = data.error ?? data.errorMessage ?? data.error_message;
  const errorCode = data.error_type ?? data.error_code ?? data.errorCode ?? data.code;
  if (event.event === "error" || errorMessage || errorCode) {
    const errorBlock = friendlyChatErrorBlock({
      code: errorCode,
      message: errorMessage,
      fallback: data,
    });
    return {
      operation: "createMessage",
      message: {
        id: `error-${event.id ?? Date.now()}`,
        role: "system",
        content: `${errorBlock.title}\n${errorBlock.message}`,
        blocks: [errorBlock],
      }
    };
  }

  if (event.event === "end") {
    return null;
  }

  const payload = data.payload;
  const operation = data.type ?? "createMessage";
  if (!payload) return null;

  const message = messageFromPayload(payload, operation, event.id ?? createClientId());
  return message ? { operation, message } : null;
}

export function mergeMessage(messages: ChatMessage[], incoming: ParsedMessage) {
  const { message: incomingMessage, operation } = incoming;
  const index = messages.findIndex(
    (message) => message.id === incomingMessage.id && message.role === incomingMessage.role
  );
  if (index < 0) return [...messages, incomingMessage];

  const next = [...messages];
  const previous = next[index];
  const content =
    operation === "appendMessage"
      ? `${previous.content}${incomingMessage.content}`
      : incomingMessage.content ?? previous.content;

  next[index] = {
    ...previous,
    content,
    blocks: operation === "appendMessage" ? mergeBlocks(previous.blocks, incomingMessage.blocks) : incomingMessage.blocks ?? previous.blocks,
    depth: incomingMessage.depth ?? previous.depth,
    parentActionId: incomingMessage.parentActionId ?? previous.parentActionId
  };
  return next;
}

function mergeBlocks(previous: readonly MessageBlock[] = [], incoming: readonly MessageBlock[] = []) {
  if (incoming.length === 0) return previous;
  const next = [...previous];
  for (const block of incoming) {
    const last = next[next.length - 1];
    if (last?.type === "markdown" && block.type === "markdown") {
      next[next.length - 1] = { type: "markdown", content: `${last.content}${block.content}` };
    } else if (last?.type === "thinking" && block.type === "thinking") {
      next[next.length - 1] = { type: "thinking", content: `${last.content}${block.content}` };
    } else {
      next.push(block);
    }
  }
  return next;
}

// ─── SSE stream consumer ────────────────────────────────────────────────────

/**
 * Read an SSE stream from a Response body, parse events, and invoke a callback for each.
 * Returns the trailing buffer (for optional flush after the loop).
 */
export async function consumeSseStream(
  response: Response,
  onEvent: (event: SseEvent) => void,
): Promise<string> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseBuffer(buffer);
    buffer = rest;

    for (const event of events) {
      onEvent(event);
    }
  }

  return buffer;
}
