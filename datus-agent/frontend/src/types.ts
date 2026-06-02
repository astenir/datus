export type Role = "user" | "assistant" | "system";

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  blocks?: MessageBlock[];
  depth?: number;
};

export type MessageOperation = "createMessage" | "appendMessage" | "updateMessage";

export type MessageBlock =
  | { type: "markdown"; content: string }
  | { type: "tool-call"; toolName: string; params: unknown }
  | { type: "tool-result"; toolName: string; duration?: number; shortDesc?: string; result?: unknown };

export type ParsedMessage = {
  message: ChatMessage;
  operation: MessageOperation;
};

export type AgentOption = {
  id: string;
  name: string;
  type?: string;
};

export type ChatSessionOption = {
  session_id: string;
  user_query?: unknown;
  created_at?: string;
  last_updated?: string;
  total_turns?: number;
  is_active?: boolean;
};

export type ConfigSummary = {
  target?: string;
  current_datasource?: string;
  home?: string;
};

export type SelectOption = {
  value: string;
  label: string;
};

export type ConnectionState = "idle" | "checking" | "online" | "offline";

export type SseEvent = {
  id?: string;
  event?: string;
  data?: unknown;
};

export type SseMessagePayload = {
  message_id?: string | number;
  role?: Role;
  content?: Array<{ type?: string; payload?: Record<string, unknown> }>;
  depth?: number;
};

export type CatalogRecord = Record<string, unknown>;
