import { Activity, CircleStop, Loader2, MessageSquare, PanelLeft, RefreshCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { sessionUserQueryText } from "@/lib/chat";
import type { ChatSessionOption, ConnectionState } from "@/types";

export function ConversationToolbar({
  connection,
  isStreaming,
  selectedSession,
  sessionId,
  onClearMessages,
  onOpenMobileSessions,
  onRefreshConnection,
  onStopSession
}: {
  connection: ConnectionState;
  isStreaming: boolean;
  selectedSession?: ChatSessionOption;
  sessionId: string;
  onClearMessages: () => void;
  onOpenMobileSessions: () => void;
  onRefreshConnection: () => void;
  onStopSession: () => void;
}) {
  return (
    <header className="topbar">
      <div className="conversationTitle">
        <p className="eyebrow">
          {selectedSession?.is_active ? <Activity size={14} /> : <MessageSquare size={14} />}
          {sessionId ? "历史会话" : "新会话"}
        </p>
        <h2>{selectedSession ? sessionUserQueryText(selectedSession) || sessionId || "Agent 对话" : sessionId || "Agent 对话"}</h2>
      </div>
      <div className="toolbar">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              className="iconButton mobileSessionButton"
              variant="ghost"
              size="icon"
              type="button"
              aria-label="打开会话历史"
              onClick={onOpenMobileSessions}
            >
              <PanelLeft size={17} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>会话历史</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button className="iconButton" variant="ghost" size="icon" type="button" aria-label="刷新连接" onClick={onRefreshConnection}>
              {connection === "checking" ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>刷新连接</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button className="iconButton" variant="ghost" size="icon" type="button" aria-label="清空消息" onClick={onClearMessages}>
              <Trash2 size={17} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>清空消息</TooltipContent>
        </Tooltip>
        <Button className="stopButton" variant="outline" type="button" onClick={onStopSession} disabled={!isStreaming && !sessionId}>
          <CircleStop size={16} />
          停止
        </Button>
      </div>
    </header>
  );
}
