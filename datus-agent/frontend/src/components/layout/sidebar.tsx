import {
  CheckCircle2,
  Loader2,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  Sun,
  WifiOff
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Sidebar as ShadcnSidebar,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupHeader,
  SidebarHeader
} from "@/components/ui/sidebar";
import { formatSessionTime, sessionTitle, sessionUserQueryText } from "@/lib/chat";
import type { ChatSessionOption, ConnectionState } from "@/types";

export function Sidebar({
  connection,
  connectionLabel,
  sessions,
  sessionId,
  isLoadingSessions,
  isStreaming,
  collapsed,
  theme,
  onToggleCollapse,
  onToggleTheme,
  onOpenSettings,
  onNewSession,
  onRefreshSessions,
  onSelectSession
}: {
  connection: ConnectionState;
  connectionLabel: string;
  sessions: ChatSessionOption[];
  sessionId: string;
  isLoadingSessions: boolean;
  isStreaming: boolean;
  collapsed: boolean;
  theme: "light" | "dark";
  onToggleCollapse: () => void;
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  onNewSession: () => void;
  onRefreshSessions: () => void;
  onSelectSession: (sessionId: string) => void;
}) {
  return (
    <ShadcnSidebar className={collapsed ? "collapsed" : ""}>
      <div>
        <SidebarHeader>
          <div className="brand">
            <div className="brandMark">
              <Sparkles size={22} />
            </div>
            <div>
              <h1>Datus Agent</h1>
              <p>Chat Console</p>
            </div>
          </div>
          <div className="sidebarActions">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  className="iconButton sidebarCollapseBtn"
                  variant="ghost"
                  size="icon"
                  type="button"
                  aria-label={collapsed ? "展开侧栏" : "收起侧栏"}
                  onClick={onToggleCollapse}
                >
                  {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
                </Button>
              </TooltipTrigger>
              <TooltipContent side={collapsed ? "right" : "bottom"}>{collapsed ? "展开侧栏" : "收起侧栏"}</TooltipContent>
            </Tooltip>
          </div>
        </SidebarHeader>
      </div>

      <SidebarGroup>
        <SidebarGroupHeader>
          <div>
            <h2>会话</h2>
            <p>{sessions.length} 个会话</p>
          </div>
          <div className="sessionActions">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button className="iconButton" variant="ghost" size="icon" type="button" aria-label="新会话" onClick={onNewSession} disabled={isStreaming}>
                  <Plus size={17} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>新会话</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button className="iconButton" variant="ghost" size="icon" type="button" aria-label="刷新会话" onClick={onRefreshSessions} disabled={isLoadingSessions}>
                  {isLoadingSessions ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
                </Button>
              </TooltipTrigger>
              <TooltipContent>刷新会话</TooltipContent>
            </Tooltip>
          </div>
        </SidebarGroupHeader>

        <button className={`sessionItem ${!sessionId ? "active" : ""}`} type="button" onClick={onNewSession} disabled={isStreaming}>
          <span className="sessionIcon">
            <Plus size={16} />
          </span>
          <span className="sessionText">
            <strong>新会话</strong>
            <small>自动生成 ID</small>
          </span>
        </button>

        <SidebarGroupContent className="sessionListFrame">
          <ScrollArea className="sessionList">
            <div className="sessionListInner">
              {isLoadingSessions ? (
                Array.from({ length: 5 }).map((_, index) => (
                  <div className="skeletonSessionItem" key={`skeleton-${index}`}>
                    <Skeleton className="skeletonSessionIcon" />
                    <div className="skeletonSessionLine">
                      <Skeleton className="skeletonSessionLineShort" />
                      <Skeleton className="skeletonSessionLineLong" />
                    </div>
                  </div>
                ))
              ) : (
                sessions.map((session) => {
                  const userQuery = sessionUserQueryText(session);
                  return (
                    <button
                      className={`sessionItem ${session.session_id === sessionId ? "active" : ""}`}
                      key={session.session_id}
                      type="button"
                      title={sessionTitle(session)}
                      onClick={() => onSelectSession(session.session_id)}
                      disabled={isStreaming}
                    >
                      <span className="sessionIcon">
                        <MessageSquare size={16} />
                      </span>
                      <span className="sessionText">
                        <strong>{userQuery || session.session_id}</strong>
                        <small>
                          {formatSessionTime(session.last_updated || session.created_at) || session.session_id}
                          {typeof session.total_turns === "number" && session.total_turns > 0 ? ` · ${session.total_turns} turns` : ""}
                        </small>
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </SidebarGroupContent>
      </SidebarGroup>

      <div className="sidebarFooter">
        <Badge
          variant={
            connection === "online" ? "success"
            : connection === "offline" ? "destructive"
            : connection === "checking" ? "secondary"
            : "outline"
          }
          className="connectionPill"
        >
          {connection === "online" ? <CheckCircle2 size={14} /> : connection === "checking" ? <Loader2 className="spin" size={14} /> : <WifiOff size={14} />}
          {connectionLabel}
        </Badge>
        <div className="sidebarFooterActions">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button className="sidebarThemeBtn" variant="ghost" size="icon" type="button" aria-label="切换主题" onClick={onToggleTheme}>
                {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>切换主题</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button className="iconButton" variant="ghost" size="icon" type="button" aria-label="打开设置" onClick={onOpenSettings}>
                <Settings2 size={17} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>设置</TooltipContent>
          </Tooltip>
        </div>
      </div>

      <div className="sidebarActionsStack">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button className="sidebarThemeBtn" variant="ghost" size="icon" type="button" aria-label="切换主题" onClick={onToggleTheme}>
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">切换主题</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button className="iconButton" variant="ghost" size="icon" type="button" aria-label="打开设置" onClick={onOpenSettings}>
              <Settings2 size={17} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">设置</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button className="iconButton" variant="ghost" size="icon" type="button" aria-label="新会话" onClick={onNewSession} disabled={isStreaming}>
              <Plus size={17} />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">新会话</TooltipContent>
        </Tooltip>
      </div>
    </ShadcnSidebar>
  );
}
