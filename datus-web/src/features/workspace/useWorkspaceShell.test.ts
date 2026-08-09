import { describe, expect, it, vi } from "vitest"
import { computed, nextTick, readonly, shallowRef } from "vue"

import type { AuthState } from "@/composables/useAuth"
import type { WorkspaceAccessFlags, WorkspacePermissionReader } from "@/features/workspace/access"
import { workspaceAccessFromPermission } from "@/features/workspace/access"
import type { ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import type { ChatWorkspaceShellContract } from "@/features/workspace/workspace-contracts"
import type { ChatMessage, ChatSessionOption, ConnectionState } from "@/types"
import { useWorkspaceShell } from "./useWorkspaceShell"

function createPermission(
  overrides: Partial<WorkspacePermissionReader> = {},
): WorkspacePermissionReader {
  return {
    hasFeaturePermission: () => false,
    hasPermission: () => false,
    hasViewPermission: () => false,
    isAdmin: () => false,
    ...overrides,
  }
}

function createWorkspace() {
  const state = {
    connection: shallowRef<ConnectionState>("offline"),
    messages: shallowRef<ChatMessage[]>([]),
    selectedSession: shallowRef<string | null>(null),
    sessions: shallowRef<ChatSessionOption[]>([]),
  }
  const workspace = {
    connection: readonly(state.connection),
    ensureCatalogLoaded: vi.fn(async () => true),
    messages: computed(() => state.messages.value),
    selectedSession: readonly(state.selectedSession),
    sessions: readonly(state.sessions),
  } satisfies ChatWorkspaceShellContract

  return { state, workspace }
}

function createShell(permission = createPermission()) {
  const { state, workspace } = createWorkspace()
  const authState = shallowRef<AuthState>({
    loading: false,
    authenticated: true,
    user: null,
  })
  const activeView = shallowRef<WorkspaceView>("chat")
  const artifactTab = shallowRef<ArtifactViewTab>("dashboard")
  const artifactSlug = shallowRef<string | null>(null)
  const viewAccess = computed<WorkspaceAccessFlags>(() => workspaceAccessFromPermission(permission))
  const shell = useWorkspaceShell({
    workspace,
    authState,
    permission,
    viewAccess,
    activeView,
    artifactTab,
    artifactSlug,
  })

  return {
    activeView,
    artifactSlug,
    artifactTab,
    authState,
    shell,
    state,
    workspace,
  }
}

describe("useWorkspaceShell", () => {
  it("preloads catalog only for authenticated online catalog views", async () => {
    const { activeView, authState, state, workspace } = createShell()
    const ensureCatalogLoaded = vi.mocked(workspace.ensureCatalogLoaded)

    state.connection.value = "online"
    await nextTick()
    expect(ensureCatalogLoaded).not.toHaveBeenCalled()

    activeView.value = "knowledge"
    await nextTick()
    expect(ensureCatalogLoaded).toHaveBeenCalledTimes(1)

    activeView.value = "artifacts"
    await nextTick()
    expect(ensureCatalogLoaded).toHaveBeenCalledTimes(1)

    authState.value = { ...authState.value, authenticated: false }
    activeView.value = "catalog"
    await nextTick()
    expect(ensureCatalogLoaded).toHaveBeenCalledTimes(1)
  })

  it("derives chat and artifact titles from the current route and session", () => {
    const { activeView, artifactSlug, artifactTab, shell, state } = createShell()

    expect(shell.headerTitle.value).toBe("新对话")

    state.selectedSession.value = "session-1"
    state.sessions.value = [{
      session_id: "session-1",
      user_query: "查询当前数据源中的订单趋势",
    }]
    expect(shell.headerTitle.value).toBe("查询当前数据源中的订单趋势")

    state.sessions.value = [{ session_id: "session-1" }]
    state.messages.value = [{
      id: "message-1",
      role: "user",
      content: "分析订单趋势",
    }]
    expect(shell.headerTitle.value).toBe("分析订单趋势")

    activeView.value = "artifacts"
    artifactTab.value = "report"
    expect(shell.headerTitle.value).toBe("报表")

    artifactSlug.value = "monthly-orders"
    expect(shell.headerTitle.value).toBe("报表预览")
  })

  it("derives subject-tree and SQL capabilities from the permission reader", () => {
    const permission = createPermission({
      hasFeaturePermission: (code) => code === "datasource_catalog",
      hasPermission: (code) => code === "module.sql_executor",
    })
    const { shell } = createShell(permission)

    expect(shell.canViewSubjectTree.value).toBe(true)
    expect(shell.canExecuteSql.value).toBe(true)
  })
})
