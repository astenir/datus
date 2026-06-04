import { Suspense, lazy } from "react";
import type { RefObject } from "react";
import { Activity, Bot, Loader2, Send, TerminalSquare } from "lucide-react";

import { ErrorBoundary } from "@/components/error-boundary";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import type { ChatMessage } from "@/types";

const MessageContent = lazy(() =>
  import("@/components/chat/message-content").then((module) => ({ default: module.MessageContent }))
);

export function MessageList({
  messages,
  isStreaming,
  scrollRef
}: {
  messages: ChatMessage[];
  isStreaming: boolean;
  scrollRef: RefObject<HTMLDivElement | null>;
}) {
  return (
    <div className="messages" ref={scrollRef}>
      {messages.length === 0 ? (
        <div className="emptyState">
          <TerminalSquare size={34} />
          <h3>开始新的分析</h3>
          <p>Datus Agent</p>
        </div>
      ) : (
        messages.map((item) => (
          <article key={`${item.role}-${item.id}`} className={`message ${item.role}`} style={{ marginLeft: item.depth ? item.depth * 18 : 0 }}>
            <Avatar className="avatar">
              <AvatarFallback>{item.role === "assistant" ? <Bot size={17} /> : item.role === "user" ? <Send size={16} /> : <Activity size={16} />}</AvatarFallback>
            </Avatar>
            <div className="bubble">
              <ErrorBoundary key={item.id} fallback={<div className="markdownBody">{item.content}</div>}>
                <Suspense fallback={<div className="markdownBody">{item.content}</div>}>
                  <MessageContent message={item} />
                </Suspense>
              </ErrorBoundary>
            </div>
          </article>
        ))
      )}
      {isStreaming && (
        <div className="streaming">
          <Loader2 className="spin" size={16} />
          正在生成响应
        </div>
      )}
    </div>
  );
}
