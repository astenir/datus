import { computed, onMounted, watch, type ComputedRef, type Ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { consumePostLoginRedirect, type AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import { canRenderWorkspaceView, workspaceRedirectTarget, type WorkspaceAccessFlags } from "@/features/workspace/access"
import {
  adminAuditFromQuery,
  adminArtifactFromQuery,
  adminGrantFromQuery,
  adminRoleFromQuery,
  adminSecretFromQuery,
  adminSessionFromQuery,
  adminTabFromQuery,
  adminUserFromQuery,
  routeQueryStringParam,
  semanticTableFromQuery,
  tableFromQuery,
  workspaceContextFromQuery,
} from "@/features/workspace/route-state"
import type { WorkspaceContextQuery } from "@/features/workspace/route-state"
import type { AdminViewTab, ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import type { WorkspaceRouteState } from "@/features/workspace/workspace-route-builders"
import { useWorkspaceNavigation } from "@/features/workspace/useWorkspaceNavigation"
import { useWorkspaceRouteContextSync } from "@/features/workspace/useWorkspaceRouteContextSync"

interface UseWorkspaceRoutingOptions {
  workspace: ChatWorkspace
  authState: Ref<AuthState>
  viewAccess: ComputedRef<WorkspaceAccessFlags>
  checkAuth: () => Promise<void>
}

export function useWorkspaceRouting(options: UseWorkspaceRoutingOptions) {
  const route = useRoute()
  const router = useRouter()

  const activeView = computed<WorkspaceView>(() => route.meta.workspaceView ?? "chat")
  const chatSessionId = computed(() => routeQueryStringParam(route.params.sessionId))
  const artifactTab = computed<ArtifactViewTab>(() => {
    if (activeView.value !== "artifacts") return "dashboard"
    return route.meta.artifactTab ?? "dashboard"
  })
  const artifactSlug = computed(() => routeQueryStringParam(route.params.slug))
  const adminTab = computed<AdminViewTab>(() => adminTabFromQuery(route.query))
  const adminSessionId = computed(() => adminTab.value === "sessions" ? adminSessionFromQuery(route.query) : null)
  const adminUserId = computed(() => adminTab.value === "users" ? adminUserFromQuery(route.query) : null)
  const adminRoleId = computed(() => adminTab.value === "roles" ? adminRoleFromQuery(route.query) : null)
  const adminSecretName = computed(() => adminTab.value === "secrets" ? adminSecretFromQuery(route.query) : null)
  const adminGrant = computed(() => adminTab.value === "grants" ? adminGrantFromQuery(route.query) : null)
  const adminArtifact = computed(() => adminTab.value === "artifacts" ? adminArtifactFromQuery(route.query) : null)
  const adminAudit = computed(() => adminTab.value === "audit" ? adminAuditFromQuery(route.query) : null)
  const semanticTable = computed(() => semanticTableFromQuery(route.query))
  const catalogTable = computed(() => tableFromQuery(route.query))
  const knowledgeTable = computed(() => tableFromQuery(route.query))
  const routeWorkspaceContext = computed(() => workspaceContextFromQuery(route.query))
  const canRenderAdminPanel = computed(() => canRenderWorkspaceView("admin", {
    ...options.viewAccess.value,
  }))

  const workspaceRouteState = computed<WorkspaceRouteState>(() => ({
    artifactTab: artifactTab.value,
    semanticTable: semanticTable.value,
    catalogTable: catalogTable.value,
    admin: {
      tab: adminTab.value,
      sessionId: adminSessionId.value,
      userId: adminUserId.value,
      roleId: adminRoleId.value,
      secretName: adminSecretName.value,
      grant: adminGrant.value,
      artifact: adminArtifact.value,
      audit: adminAudit.value,
    },
  }))
  const workspaceContext = computed<WorkspaceContextQuery>(() => ({
    datasource: options.workspace.currentDatasource.value,
    database: options.workspace.database.value,
    schema: options.workspace.schema.value,
  }))

  const {
    replaceChat,
    navigateToView,
    setActiveView,
    openChat,
    openArtifactTab,
    openArtifactDetail,
    openSemanticTable,
    openCatalogTable,
    openKnowledgeTable,
    openAdminTab,
    openAdminUser,
    openAdminRole,
    openAdminSecret,
    openAdminGrant,
    openAdminSession,
    openAdminArtifact,
    openAdminAudit,
  } = useWorkspaceNavigation({
    route,
    router,
    routeState: workspaceRouteState,
    workspaceContext,
  })
  const {
    applyRouteWorkspaceContext,
    markRouteContextHydrated,
  } = useWorkspaceRouteContextSync({
    route,
    router,
    workspace: options.workspace,
    authState: options.authState,
    routeWorkspaceContext,
  })

  async function redirectPostLoginToChat() {
    if (!consumePostLoginRedirect()) return
    if (activeView.value === "chat" && !chatSessionId.value) return

    await replaceChat()
  }

  onMounted(async () => {
    if (options.authState.value.loading) {
      await options.checkAuth()
    }
    if (options.authState.value.authenticated) {
      await redirectPostLoginToChat()
      await options.workspace.initialize()
      await applyRouteWorkspaceContext()
      markRouteContextHydrated()
    }
  })

  watch(
    () => [
      activeView.value,
      options.viewAccess.value,
      options.authState.value.loading,
      options.authState.value.authenticated,
    ] as const,
    ([view, access, loading, authenticated]) => {
      const redirectTarget = workspaceRedirectTarget(view, {
        authenticated,
        loading,
        ...access,
      })
      if (!redirectTarget) return
      void navigateToView(redirectTarget, { replace: true })
    },
    { immediate: true },
  )

  watch(
    () => [
      activeView.value,
      chatSessionId.value,
      options.authState.value.loading,
      options.authState.value.authenticated,
    ] as const,
    ([view, sessionId, loading, authenticated]) => {
      if (loading || !authenticated || view !== "chat") return
      if (options.workspace.selectedSession.value === sessionId) return
      options.workspace.selectSession(sessionId)
    },
    { immediate: true },
  )

  watch(
    () => [
      activeView.value,
      options.workspace.selectedSession.value,
      chatSessionId.value,
      options.authState.value.authenticated,
    ] as const,
    ([view, selectedSession, routeSessionId, authenticated]) => {
      if (!authenticated || view !== "chat" || !selectedSession || selectedSession === routeSessionId) return
      void replaceChat(selectedSession)
    },
  )

  return {
    activeView,
    artifactTab,
    artifactSlug,
    adminTab,
    adminSessionId,
    adminUserId,
    adminRoleId,
    adminSecretName,
    adminGrant,
    adminArtifact,
    adminAudit,
    semanticTable,
    catalogTable,
    knowledgeTable,
    canRenderAdminPanel,
    navigateToView,
    setActiveView,
    openChat,
    openArtifactTab,
    openArtifactDetail,
    openSemanticTable,
    openCatalogTable,
    openKnowledgeTable,
    openAdminTab,
    openAdminUser,
    openAdminRole,
    openAdminSecret,
    openAdminGrant,
    openAdminSession,
    openAdminArtifact,
    openAdminAudit,
  }
}
