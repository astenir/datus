import type { ComputedRef } from "vue"
import type { RouteLocationNormalizedLoaded, Router } from "vue-router"

import type {
  AdminArtifactRouteState,
  AdminAuditRouteState,
  AdminGrantRouteState,
  WorkspaceContextQuery,
} from "@/features/workspace/route-state"
import type {
  AdminRouteDetailUpdates,
  WorkspaceRouteState,
} from "@/features/workspace/workspace-route-builders"
import {
  adminDetailRoute,
  adminTabRoute,
  artifactRouteForTab,
  chatRouteForSession as buildChatRouteForSession,
  knowledgeTableRoute,
  workspaceRouteForView,
} from "@/features/workspace/workspace-route-builders"
import type { AdminViewTab, ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import { isWorkspaceView } from "@/features/workspace/types"

interface UseWorkspaceNavigationOptions {
  route: RouteLocationNormalizedLoaded
  router: Router
  routeState: ComputedRef<WorkspaceRouteState>
  workspaceContext: ComputedRef<WorkspaceContextQuery>
}

export function useWorkspaceNavigation(options: UseWorkspaceNavigationOptions) {
  function chatRouteForSession(sessionId: string | null = null) {
    return buildChatRouteForSession(options.workspaceContext.value, sessionId)
  }

  function navigateToView(view: WorkspaceView, routeOptions: { replace?: boolean } = {}) {
    const routeLocation = workspaceRouteForView(
      view,
      options.routeState.value,
      options.workspaceContext.value,
    )
    return routeOptions.replace ? options.router.replace(routeLocation) : options.router.push(routeLocation)
  }

  function setActiveView(value: unknown) {
    if (typeof value === "string" && isWorkspaceView(value)) {
      void navigateToView(value)
    }
  }

  function openChat(sessionId: string | null = null) {
    void options.router.push(chatRouteForSession(sessionId))
  }

  function replaceChat(sessionId: string | null = null) {
    return options.router.replace(chatRouteForSession(sessionId))
  }

  function openArtifactTab(value: ArtifactViewTab) {
    void options.router.push(artifactRouteForTab(options.workspaceContext.value, value))
  }

  function openArtifactDetail(tab: ArtifactViewTab, slug: string) {
    void options.router.push(artifactRouteForTab(options.workspaceContext.value, tab, slug))
  }

  function openSemanticTable(table: string) {
    openKnowledgeTable(table)
  }

  function openCatalogTable(table: string) {
    openKnowledgeTable(table)
  }

  function openKnowledgeTable(table: string) {
    void options.router.replace(knowledgeTableRoute(options.route.query, table))
  }

  function openAdminTab(tab: AdminViewTab) {
    void options.router.replace(adminTabRoute(options.route.query, options.routeState.value.admin, tab))
  }

  function openAdminUser(userId: string | null) {
    openAdminDetail({ tab: "users", user: userId })
  }

  function openAdminRole(roleId: string | null) {
    openAdminDetail({ tab: "roles", role: roleId })
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
    openAdminDetail({ tab: "sessions", session: sessionId })
  }

  function openAdminSecret(name: string | null) {
    openAdminDetail({ tab: "secrets", secret: name })
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
      audit_request_id: filters.requestId,
      audit_created_after: filters.createdAfter,
      audit_created_before: filters.createdBefore,
      audit_limit: String(filters.limit),
      audit_before_id: filters.beforeId != null ? String(filters.beforeId) : null,
    })
  }

  function openAdminDetail(updates: AdminRouteDetailUpdates) {
    void options.router.replace(adminDetailRoute(options.route.query, updates))
  }

  return {
    chatRouteForSession,
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
  }
}
