import { computed, watch, type ComputedRef, type Ref } from "vue"

import type { AuthState } from "@/composables/useAuth"
import type { WorkspaceAccessFlags, WorkspacePermissionReader } from "@/features/workspace/access"
import type { ArtifactViewTab, WorkspaceNavItem, WorkspaceView } from "@/features/workspace/types"
import type { ChatWorkspaceShellContract } from "@/features/workspace/workspace-contracts"
import { canViewSubjectTree as canViewSubjectTreeWithPermission } from "@/lib/knowledge-access"
import { sessionUserQueryText } from "@/lib/chat"
import {
  BarChart3Icon,
  BotIcon,
  BookMarkedIcon,
  MessageSquareIcon,
  ServerIcon,
  ShieldIcon,
  SlidersHorizontalIcon,
  UserRoundIcon,
} from "@lucide/vue"

type ReadonlyValue<T> = Readonly<Ref<T>>

export interface UseWorkspaceShellOptions {
  workspace: ChatWorkspaceShellContract
  authState: ReadonlyValue<AuthState>
  permission: WorkspacePermissionReader
  viewAccess: ComputedRef<WorkspaceAccessFlags>
  activeView: ReadonlyValue<WorkspaceView>
  artifactTab: ReadonlyValue<ArtifactViewTab>
  artifactSlug: ReadonlyValue<string | null>
}

const chatNavItem: WorkspaceNavItem = {
  value: "chat",
  label: "新对话",
  icon: MessageSquareIcon,
}

const workspaceNavItems: readonly WorkspaceNavItem[] = [
  chatNavItem,
  { value: "knowledge", label: "知识库", icon: BookMarkedIcon },
  { value: "mcp", label: "MCP", icon: ServerIcon },
  { value: "agents", label: "Agent", icon: BotIcon },
  { value: "configuration", label: "配置", icon: SlidersHorizontalIcon },
  { value: "artifacts", label: "产物", icon: BarChart3Icon },
  { value: "profile", label: "个人设置", icon: UserRoundIcon },
  { value: "admin", label: "权限管理", icon: ShieldIcon },
]

export function useWorkspaceShell(options: UseWorkspaceShellOptions) {
  const canViewSubjectTree = computed(() => canViewSubjectTreeWithPermission(options.permission))
  const canExecuteSql = computed(() => {
    return options.permission.isAdmin()
      || options.permission.hasPermission("module.sql_executor")
      || options.permission.hasFeaturePermission("sql_executor")
      || options.permission.hasFeaturePermission("sql_generation")
  })

  watch(
    () => [
      options.activeView.value,
      options.authState.value.loading,
      options.authState.value.authenticated,
      options.workspace.connection.value,
    ] as const,
    ([view, loading, authenticated, connection]) => {
      if (
        authenticated
        && !loading
        && connection === "online"
        && (view === "knowledge" || view === "catalog" || view === "semantic")
      ) {
        void options.workspace.ensureCatalogLoaded()
      }
    },
    { immediate: true },
  )

  const activeNavItem = computed(() =>
    workspaceNavItems.find(item => item.value === options.activeView.value) ?? chatNavItem
  )
  const currentSession = computed(() => {
    const sessionId = options.workspace.selectedSession.value
    if (!sessionId) return null

    return options.workspace.sessions.value.find(session => session.session_id === sessionId) ?? null
  })
  const firstUserMessageTitle = computed(() => {
    const message = options.workspace.messages.value.find(item => item.role === "user" && item.content.trim())
    const text = message?.content.trim() ?? ""

    return text.length > 60 ? `${text.slice(0, 60)}…` : text
  })
  const chatHeaderTitle = computed(() => {
    if (!options.workspace.selectedSession.value) return "新对话"

    const sessionTitle = currentSession.value ? sessionUserQueryText(currentSession.value) : ""
    return sessionTitle || firstUserMessageTitle.value || "未命名会话"
  })
  const headerTitle = computed(() => {
    if (options.activeView.value === "chat") {
      return chatHeaderTitle.value
    }

    if (options.activeView.value === "artifacts") {
      if (options.artifactSlug.value) {
        return options.artifactTab.value === "report" ? "报表预览" : "仪表盘预览"
      }

      return options.artifactTab.value === "report" ? "报表" : "仪表盘"
    }

    return activeNavItem.value.label
  })

  return {
    canExecuteSql,
    canViewSubjectTree,
    headerTitle,
  }
}
