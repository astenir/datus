import { computed, onMounted, shallowRef, watch, type ComputedRef, type Ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import { canRenderWorkspaceView, workspaceRedirectTarget } from "@/features/workspace/access"
import {
  adminAuditFromQuery,
  adminArtifactFromQuery,
  adminGrantFromQuery,
  adminRoleFromQuery,
  adminSecretFromQuery,
  adminSessionFromQuery,
  adminTabFromQuery,
  adminUserFromQuery,
  replaceQueryStringParam,
  replaceQueryStringParams,
  routeQueryStringParam,
  semanticTableFromQuery,
  tableFromQuery,
  workspaceContextFromQuery,
} from "@/features/workspace/route-state"
import type {
  AdminArtifactRouteState,
  AdminAuditRouteState,
  AdminGrantRouteState,
} from "@/features/workspace/route-state"
import type { AdminViewTab, ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import { isWorkspaceView, workspaceRouteNames } from "@/features/workspace/types"

interface UseWorkspaceRoutingOptions {
  workspace: ChatWorkspace
  authState: Ref<AuthState>
  canManagePermissions: ComputedRef<boolean>
  checkAuth: () => Promise<void>
}

export function useWorkspaceRouting(options: UseWorkspaceRoutingOptions) {
  const route = useRoute()
  const router = useRouter()
  const routeContextHydrated = shallowRef(false)

  const activeView = computed<WorkspaceView>(() => route.meta.workspaceView ?? "chat")
  const chatSessionId = computed(() => routeStringParam(route.params.sessionId))
  const artifactTab = computed<ArtifactViewTab>(() => {
    if (activeView.value !== "artifacts") return "dashboard"
    return route.meta.artifactTab ?? "dashboard"
  })
  const artifactSlug = computed(() => routeStringParam(route.params.slug))
  const adminTab = computed<AdminViewTab>(() => adminTabFromQuery(route.query))
  const adminSessionId = computed(() => adminTab.value === "sessions" ? adminSessionFromQuery(route.query) : null)
  const adminUserId = computed(() => adminTab.value === "users" ? adminUserFromQuery(route.query) : null)
  const adminRoleId = computed(() => adminTab.value === "roles" ? adminRoleFromQuery(route.query) : null)
  const adminGrant = computed(() => adminTab.value === "grants" ? adminGrantFromQuery(route.query) : null)
  const adminSecretName = computed(() => adminTab.value === "secrets" ? adminSecretFromQuery(route.query) : null)
  const adminArtifact = computed(() => adminTab.value === "artifacts" ? adminArtifactFromQuery(route.query) : null)
  const adminAudit = computed(() => adminTab.value === "audit" ? adminAuditFromQuery(route.query) : null)
  const semanticTable = computed(() => semanticTableFromQuery(route.query))
  const catalogTable = computed(() => tableFromQuery(route.query))
  const routeWorkspaceContext = computed(() => workspaceContextFromQuery(route.query))
  const canRenderAdminPanel = computed(() => canRenderWorkspaceView("admin", {
    canManagePermissions: options.canManagePermissions.value,
  }))

  function workspaceRouteForView(view: WorkspaceView, tab: ArtifactViewTab = artifactTab.value) {
    if (view === "chat") {
      return chatRouteForSession()
    }

    if (view === "artifacts") {
      return {
        name: tab === "report"
          ? workspaceRouteNames.artifactReport
          : workspaceRouteNames.artifactDashboard,
        query: workspaceContextRouteQuery(),
      }
    }

    if (view === "semantic") {
      return {
        name: workspaceRouteNames.semantic,
        query: workspaceContextRouteQuery({ table: semanticTable.value }),
      }
    }

    if (view === "admin") {
      return {
        name: workspaceRouteNames.admin,
        query: workspaceContextRouteQuery({
          tab: adminTab.value,
          user: adminTab.value === "users" ? adminUserId.value : null,
          role: adminTab.value === "roles" ? adminRoleId.value : null,
          session: adminTab.value === "sessions" ? adminSessionId.value : null,
          secret: adminTab.value === "secrets" ? adminSecretName.value : null,
          artifact_type: adminTab.value === "artifacts" ? adminArtifact.value?.artifactType ?? null : null,
          artifact_slug: adminTab.value === "artifacts" ? adminArtifact.value?.slug ?? null : null,
          audit_user: adminTab.value === "audit" ? adminAudit.value?.userId ?? null : null,
          audit_action: adminTab.value === "audit" ? adminAudit.value?.action ?? null : null,
          audit_resource_type: adminTab.value === "audit" ? adminAudit.value?.resourceType ?? null : null,
          audit_resource_id: adminTab.value === "audit" ? adminAudit.value?.resourceId ?? null : null,
          audit_decision: adminTab.value === "audit" ? adminAudit.value?.decision ?? null : null,
          audit_limit: adminTab.value === "audit" ? String(adminAudit.value?.limit ?? 50) : null,
          grant_subject_type: adminTab.value === "grants" ? adminGrant.value?.subjectType ?? null : null,
          grant_subject_id: adminTab.value === "grants" ? adminGrant.value?.subjectId ?? null : null,
          grant_datasource: adminTab.value === "grants" ? adminGrant.value?.datasourceKey ?? null : null,
        }),
      }
    }

    return {
      name: workspaceRouteNames[view],
      query: workspaceContextRouteQuery(),
    }
  }

  function chatRouteForSession(sessionId: string | null = null) {
    if (sessionId) {
      return {
        name: workspaceRouteNames.chatSession,
        params: { sessionId },
        query: workspaceContextRouteQuery(),
      }
    }

    return {
      name: workspaceRouteNames.chat,
      query: workspaceContextRouteQuery(),
    }
  }

  function artifactRouteForTab(tab: ArtifactViewTab, slug: string | null = null) {
    if (slug) {
      return {
        name: tab === "report"
          ? workspaceRouteNames.artifactReportDetail
          : workspaceRouteNames.artifactDashboardDetail,
        params: { slug },
        query: workspaceContextRouteQuery(),
      }
    }

    return {
      name: tab === "report"
        ? workspaceRouteNames.artifactReport
        : workspaceRouteNames.artifactDashboard,
      query: workspaceContextRouteQuery(),
    }
  }

  function navigateToView(view: WorkspaceView, routeOptions: { replace?: boolean } = {}) {
    const routeLocation = workspaceRouteForView(view)
    return routeOptions.replace ? router.replace(routeLocation) : router.push(routeLocation)
  }

  function setActiveView(value: unknown) {
    if (typeof value === "string" && isWorkspaceView(value)) {
      void navigateToView(value)
    }
  }

  function openChat(sessionId: string | null = null) {
    void router.push(chatRouteForSession(sessionId))
  }

  function openArtifactTab(value: ArtifactViewTab) {
    void router.push(artifactRouteForTab(value))
  }

  function openArtifactDetail(tab: ArtifactViewTab, slug: string) {
    void router.push(artifactRouteForTab(tab, slug))
  }

  function openSemanticTable(table: string) {
    void router.replace({
      name: workspaceRouteNames.semantic,
      query: replaceQueryStringParam(route.query, "table", table),
    })
  }

  function openCatalogTable(table: string) {
    void router.replace({
      name: workspaceRouteNames.catalog,
      query: replaceQueryStringParam(route.query, "table", table),
    })
  }

  function openAdminTab(tab: AdminViewTab) {
    void router.replace({
      name: workspaceRouteNames.admin,
      query: replaceQueryStringParams(route.query, {
        tab,
        user: tab === "users" ? adminUserId.value : null,
        role: tab === "roles" ? adminRoleId.value : null,
        session: tab === "sessions" ? adminSessionId.value : null,
        secret: tab === "secrets" ? adminSecretName.value : null,
        artifact_type: tab === "artifacts" ? adminArtifact.value?.artifactType ?? null : null,
        artifact_slug: tab === "artifacts" ? adminArtifact.value?.slug ?? null : null,
        audit_user: tab === "audit" ? adminAudit.value?.userId ?? null : null,
        audit_action: tab === "audit" ? adminAudit.value?.action ?? null : null,
        audit_resource_type: tab === "audit" ? adminAudit.value?.resourceType ?? null : null,
        audit_resource_id: tab === "audit" ? adminAudit.value?.resourceId ?? null : null,
        audit_decision: tab === "audit" ? adminAudit.value?.decision ?? null : null,
        audit_limit: tab === "audit" ? String(adminAudit.value?.limit ?? 50) : null,
        grant_subject_type: tab === "grants" ? adminGrant.value?.subjectType ?? null : null,
        grant_subject_id: tab === "grants" ? adminGrant.value?.subjectId ?? null : null,
        grant_datasource: tab === "grants" ? adminGrant.value?.datasourceKey ?? null : null,
      }),
    })
  }

  function openAdminUser(userId: string | null) {
    openAdminDetail({
      tab: "users",
      user: userId,
    })
  }

  function openAdminRole(roleId: string | null) {
    openAdminDetail({
      tab: "roles",
      role: roleId,
    })
  }

  function openAdminGrant(grant: AdminGrantRouteState | null) {
    openAdminDetail({
      tab: "grants",
      grant_subject_type: grant?.subjectType ?? null,
      grant_subject_id: grant?.subjectId ?? null,
      grant_datasource: grant?.datasourceKey ?? null,
    })
  }

  function openAdminSession(sessionId: string | null) {
    openAdminDetail({
      tab: "sessions",
      session: sessionId,
    })
  }

  function openAdminSecret(secretName: string | null) {
    openAdminDetail({
      tab: "secrets",
      secret: secretName,
    })
  }

  function openAdminArtifact(artifact: AdminArtifactRouteState | null) {
    openAdminDetail({
      tab: "artifacts",
      artifact_type: artifact?.artifactType ?? null,
      artifact_slug: artifact?.slug ?? null,
    })
  }

  function openAdminAudit(filters: AdminAuditRouteState) {
    openAdminDetail({
      tab: "audit",
      audit_user: filters.userId,
      audit_action: filters.action,
      audit_resource_type: filters.resourceType,
      audit_resource_id: filters.resourceId,
      audit_decision: filters.decision,
      audit_limit: String(filters.limit),
    })
  }

  function openAdminDetail(updates: { tab: AdminViewTab } & Record<string, string | null>) {
    const { tab, ...detailUpdates } = updates

    void router.replace({
      name: workspaceRouteNames.admin,
      query: replaceQueryStringParams(route.query, {
        tab,
        user: null,
        role: null,
        session: null,
        secret: null,
        artifact_type: null,
        artifact_slug: null,
        audit_user: null,
        audit_action: null,
        audit_resource_type: null,
        audit_resource_id: null,
        audit_decision: null,
        audit_limit: null,
        grant_subject_type: null,
        grant_subject_id: null,
        grant_datasource: null,
        ...detailUpdates,
      }),
    })
  }

  function routeStringParam(value: unknown): string | null {
    return routeQueryStringParam(value)
  }

  function workspaceContextRouteQuery(extra: Record<string, string | null> = {}) {
    const context = {
      datasource: options.workspace.currentDatasource.value,
      database: options.workspace.database.value,
      schema: options.workspace.schema.value,
      ...extra,
    }
    return replaceQueryStringParams({}, context)
  }

  async function applyRouteWorkspaceContext() {
    const nextDatasource = routeWorkspaceContext.value.datasource ?? ""
    const nextDatabase = routeWorkspaceContext.value.database ?? ""
    const nextSchema = routeWorkspaceContext.value.schema ?? ""

    if (nextDatasource && options.workspace.currentDatasource.value !== nextDatasource) {
      const switched = await options.workspace.handleDatasourceSwitch(nextDatasource)
      if (!switched && options.workspace.currentDatasource.value !== nextDatasource) {
        return
      }
    }

    if (options.workspace.database.value !== nextDatabase) {
      options.workspace.setDatabase(nextDatabase)
    }

    if (options.workspace.schema.value !== nextSchema) {
      options.workspace.setSchema(nextSchema)
    }
  }

  function syncRouteWorkspaceContext() {
    const nextQuery = replaceQueryStringParams(route.query, {
      datasource: options.workspace.currentDatasource.value,
      database: options.workspace.database.value,
      schema: options.workspace.schema.value,
    })
    void router.replace({ query: nextQuery })
  }

  onMounted(async () => {
    if (options.authState.value.loading) {
      await options.checkAuth()
    }
    if (options.authState.value.authenticated) {
      await options.workspace.initialize()
      await applyRouteWorkspaceContext()
      routeContextHydrated.value = true
    }
  })

  watch(
    () => [
      activeView.value,
      options.canManagePermissions.value,
      options.authState.value.loading,
      options.authState.value.authenticated,
    ] as const,
    ([view, canManage, loading, authenticated]) => {
      const redirectTarget = workspaceRedirectTarget(view, {
        authenticated,
        loading,
        canManagePermissions: canManage,
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
      void router.replace(chatRouteForSession(selectedSession))
    },
  )

  watch(
    () => [
      routeContextHydrated.value,
      options.authState.value.authenticated,
      routeWorkspaceContext.value.datasource,
      routeWorkspaceContext.value.database,
      routeWorkspaceContext.value.schema,
    ] as const,
    ([hydrated, authenticated]) => {
      if (!hydrated || !authenticated) return
      void applyRouteWorkspaceContext()
    },
  )

  watch(
    () => [
      routeContextHydrated.value,
      options.authState.value.authenticated,
      options.workspace.currentDatasource.value,
      options.workspace.database.value,
      options.workspace.schema.value,
      routeWorkspaceContext.value.datasource,
      routeWorkspaceContext.value.database,
      routeWorkspaceContext.value.schema,
    ] as const,
    ([hydrated, authenticated, datasource, database, schema, routeDatasource, routeDatabase, routeSchema]) => {
      if (!hydrated || !authenticated) return
      if ((routeDatasource ?? "") === datasource && (routeDatabase ?? "") === database && (routeSchema ?? "") === schema) {
        return
      }
      syncRouteWorkspaceContext()
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
    adminGrant,
    adminSecretName,
    adminArtifact,
    adminAudit,
    semanticTable,
    catalogTable,
    canRenderAdminPanel,
    navigateToView,
    setActiveView,
    openChat,
    openArtifactTab,
    openArtifactDetail,
    openSemanticTable,
    openCatalogTable,
    openAdminTab,
    openAdminUser,
    openAdminRole,
    openAdminGrant,
    openAdminSession,
    openAdminSecret,
    openAdminArtifact,
    openAdminAudit,
  }
}
