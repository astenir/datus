import { requestStream } from "@/lib/chat";
import { request } from "@/lib/request";
import { apiResult, apiUrl, jsonBody } from "./helpers";
import type {
  BootstrapDocInput,
  BootstrapKbInput,
  ChatSessionOption,
  CompactSessionData,
  KbUploadCreateInput,
  KbUploadRecord,
  SuccessStoryInput,
  SuccessStoryResult,
  UserInteractionInput,
} from "@/types";

export const chatApi = {
  sessions(baseUrl: string, subagentId?: string): Promise<{ sessions: ChatSessionOption[]; total_count: number } | null> {
    const query = subagentId ? `?subagent_id=${encodeURIComponent(subagentId)}` : "";
    return apiResult(baseUrl, `/api/v1/chat/sessions${query}`);
  },

  history(baseUrl: string, sessionId: string): Promise<{ messages: unknown[] } | null> {
    return apiResult(baseUrl, `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`);
  },

  stop(baseUrl: string, sessionId: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/chat/stop", jsonBody({ session_id: sessionId }));
  },

  deleteSession(baseUrl: string, sessionId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  },

  compact(baseUrl: string, sessionId: string): Promise<CompactSessionData | null> {
    return apiResult(baseUrl, `/api/v1/chat/sessions/${encodeURIComponent(sessionId)}/compact`, { method: "POST" });
  },

  async feedback(baseUrl: string, input: { source_session_id: string; reaction_emoji: string; reference_msg: string; reaction_msg?: string }): Promise<void> {
    const response = await request(apiUrl(baseUrl, "/api/v1/chat/feedback"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(input),
    });
    // Feedback runs as background SSE. Consume and discard the stream.
    const reader = response.body?.getReader();
    if (reader) {
      try {
        while (!(await reader.read()).done) {
          // drain
        }
      } catch {
        // ignore
      }
    }
  },

  userInteraction(baseUrl: string, input: UserInteractionInput): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/chat/user_interaction", jsonBody(input));
  },

  insert(baseUrl: string, sessionId: string, message: string): Promise<unknown> {
    return apiResult(baseUrl, "/api/v1/chat/insert", jsonBody({ session_id: sessionId, message }));
  },

  toolResult(baseUrl: string, sessionId: string, callToolId: string, result: { success: 0 | 1; error?: string; result?: unknown }): Promise<unknown> {
    return apiResult(
      baseUrl,
      "/api/v1/chat/tool_result",
      jsonBody({ session_id: sessionId, call_tool_id: callToolId, tool_result: result }),
    );
  },
};

export const kbApi = {
  async upload(baseUrl: string, input: KbUploadCreateInput): Promise<KbUploadRecord> {
    const body = new FormData();
    body.append("purpose", input.purpose);
    for (const file of input.files) {
      body.append("files", file);
    }
    if (input.platform?.trim()) body.append("platform", input.platform.trim());
    if (input.datasourceId?.trim()) body.append("datasource_id", input.datasourceId.trim());
    if (input.description?.trim()) body.append("description", input.description.trim());

    const response = await request(apiUrl(baseUrl, "/api/v1/kb/uploads"), {
      method: "POST",
      body,
    });
    return response.json() as Promise<KbUploadRecord>;
  },

  uploadDetail(baseUrl: string, uploadId: string): Promise<KbUploadRecord | null> {
    return apiResult(baseUrl, `/api/v1/kb/uploads/${encodeURIComponent(uploadId)}`);
  },

  deleteUpload(baseUrl: string, uploadId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/kb/uploads/${encodeURIComponent(uploadId)}`, { method: "DELETE" });
  },

  bootstrap(baseUrl: string, input: BootstrapKbInput): Promise<ReadableStream<Uint8Array> | null> {
    return requestStream(baseUrl, "/api/v1/kb/bootstrap", input);
  },

  cancelBootstrap(baseUrl: string, streamId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/kb/bootstrap/${encodeURIComponent(streamId)}/cancel`, { method: "POST" });
  },

  bootstrapDocs(baseUrl: string, input: BootstrapDocInput): Promise<ReadableStream<Uint8Array> | null> {
    return requestStream(baseUrl, "/api/v1/kb/bootstrap-docs", input);
  },

  cancelBootstrapDocs(baseUrl: string, streamId: string): Promise<unknown> {
    return apiResult(baseUrl, `/api/v1/kb/bootstrap-docs/${encodeURIComponent(streamId)}/cancel`, { method: "POST" });
  },
};

export const successStoryApi = {
  save(baseUrl: string, input: SuccessStoryInput): Promise<SuccessStoryResult | null> {
    return apiResult(baseUrl, "/api/v1/success-stories", jsonBody(input));
  },
};
