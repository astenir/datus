import type { LocationQuery, LocationQueryRaw, RouteLocationRaw } from "vue-router"

import { defaultAuditLogLimit } from "@/lib/audit-log-pagination"
import type {
  AdminArtifactRouteState,
  AdminAuditRouteState,
  AdminGrantRouteState,
  WorkspaceContextQuery,
} from "@/features/workspace/route-state"
import { replaceQueryStringParam, replaceQueryStringParams } from "@/features/workspace/route-state"
import type { AdminViewTab, ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import { workspaceRouteNames } from "@/features/workspace/types"

export interface WorkspaceAdminRouteState {
  tab: AdminViewTab
  sessionId: string | null
  userId: string | null
  roleId: string | null
  secretName: string | null
  grant: AdminGrantRouteState | null
  artifact: AdminArtifactRouteState | null
  audit: AdminAuditRouteState | null
}

export interface WorkspaceRouteState {
  artifactTab: ArtifactViewTab
  semanticTable: string | null
  catalogTable: string | null
  admin: WorkspaceAdminRouteState
}

export interface AdminRouteDetailUpdates {
  tab: AdminViewTab
  user?: string | null
  role?: string | null
  session?: string | null
  secret?: string | null
  artifact_type?: string | null
  artifact_slug?: string | null
  audit_user?: string | null
  audit_action?: string | null
  audit_resource_type?: string | null
  audit_resource_id?: string | null
  audit_decision?: string | null
  audit_request_id?: string | null
  audit_created_after?: string | null
  audit_created_before?: string | null
  audit_limit?: string | null
  audit_before_id?: string | null
  grant_subject_type?: string | null
  grant_subject_id?: string | null
  grant_datasource?: string | null
}

export function workspaceContextRouteQuery(
  context: WorkspaceContextQuery,
  extra: Record<string, string | null> = {},
): LocationQueryRaw {
  return replaceQueryStringParams({}, {
    ...context,
    ...extra,
  })
}

export function chatRouteForSession(
  context: WorkspaceContextQuery,
  sessionId: string | null = null,
): RouteLocationRaw {
  if (sessionId) {
    return {
      name: workspaceRouteNames.chatSession,
      params: { sessionId },
      query: workspaceContextRouteQuery(context),
    }
  }

  return {
    name: workspaceRouteNames.chat,
    query: workspaceContextRouteQuery(context),
  }
}

export function artifactRouteForTab(
  context: WorkspaceContextQuery,
  tab: ArtifactViewTab,
  slug: string | null = null,
): RouteLocationRaw {
  if (slug) {
    return {
      name: tab === "report"
        ? workspaceRouteNames.artifactReportDetail
        : workspaceRouteNames.artifactDashboardDetail,
      params: { slug },
      query: workspaceContextRouteQuery(context),
    }
  }

  return {
    name: tab === "report"
      ? workspaceRouteNames.artifactReport
      : workspaceRouteNames.artifactDashboard,
    query: workspaceContextRouteQuery(context),
  }
}

export function workspaceRouteForView(
  view: WorkspaceView,
  state: WorkspaceRouteState,
  context: WorkspaceContextQuery,
): RouteLocationRaw {
  if (view === "chat") {
    return chatRouteForSession(context)
  }

  if (view === "artifacts") {
    return artifactRouteForTab(context, state.artifactTab)
  }

  if (view === "semantic") {
    return {
      name: workspaceRouteNames.knowledge,
      query: workspaceContextRouteQuery(context, { table: state.semanticTable }),
    }
  }

  if (view === "catalog") {
    return {
      name: workspaceRouteNames.knowledge,
      query: workspaceContextRouteQuery(context, { table: state.catalogTable }),
    }
  }

  if (view === "admin") {
    return adminRouteForState(context, state.admin)
  }

  return {
    name: workspaceRouteNames[view],
    query: workspaceContextRouteQuery(context),
  }
}

export function knowledgeTableRoute(query: LocationQuery, table: string): RouteLocationRaw {
  return {
    name: workspaceRouteNames.knowledge,
    query: replaceQueryStringParam(query, "table", table),
  }
}

export function adminRouteForState(
  context: WorkspaceContextQuery,
  state: WorkspaceAdminRouteState,
): RouteLocationRaw {
  return {
    name: workspaceRouteNames.admin,
    query: workspaceContextRouteQuery(context, adminQueryUpdates(state, state.tab)),
  }
}

export function adminTabRoute(
  query: LocationQuery,
  state: WorkspaceAdminRouteState,
  tab: AdminViewTab,
): RouteLocationRaw {
  return {
    name: workspaceRouteNames.admin,
    query: replaceQueryStringParams(query, adminQueryUpdates(state, tab)),
  }
}

export function adminDetailRoute(
  query: LocationQuery,
  updates: AdminRouteDetailUpdates,
): RouteLocationRaw {
  return {
    name: workspaceRouteNames.admin,
    query: replaceQueryStringParams(query, {
      tab: updates.tab,
      user: updates.user ?? null,
      role: updates.role ?? null,
      session: updates.session ?? null,
      secret: updates.secret ?? null,
      artifact_type: updates.artifact_type ?? null,
      artifact_slug: updates.artifact_slug ?? null,
      audit_user: updates.audit_user ?? null,
      audit_action: updates.audit_action ?? null,
      audit_resource_type: updates.audit_resource_type ?? null,
      audit_resource_id: updates.audit_resource_id ?? null,
      audit_decision: updates.audit_decision ?? null,
      audit_request_id: updates.audit_request_id ?? null,
      audit_created_after: updates.audit_created_after ?? null,
      audit_created_before: updates.audit_created_before ?? null,
      audit_limit: updates.audit_limit ?? null,
      audit_before_id: updates.audit_before_id ?? null,
      grant_subject_type: updates.grant_subject_type ?? null,
      grant_subject_id: updates.grant_subject_id ?? null,
      grant_datasource: updates.grant_datasource ?? null,
    }),
  }
}

function adminQueryUpdates(
  state: WorkspaceAdminRouteState,
  tab: AdminViewTab,
): Record<string, string | null> {
  return {
    tab,
    user: tab === "users" ? state.userId : null,
    role: tab === "roles" ? state.roleId : null,
    session: tab === "sessions" ? state.sessionId : null,
    secret: tab === "secrets" ? state.secretName : null,
    artifact_type: tab === "artifacts" ? state.artifact?.artifactType ?? null : null,
    artifact_slug: tab === "artifacts" ? state.artifact?.slug ?? null : null,
    audit_user: tab === "audit" ? state.audit?.userId ?? null : null,
    audit_action: tab === "audit" ? state.audit?.action ?? null : null,
    audit_resource_type: tab === "audit" ? state.audit?.resourceType ?? null : null,
    audit_resource_id: tab === "audit" ? state.audit?.resourceId ?? null : null,
    audit_decision: tab === "audit" ? state.audit?.decision ?? null : null,
    audit_request_id: tab === "audit" ? state.audit?.requestId ?? null : null,
    audit_created_after: tab === "audit" ? state.audit?.createdAfter ?? null : null,
    audit_created_before: tab === "audit" ? state.audit?.createdBefore ?? null : null,
    audit_limit: tab === "audit" ? String(state.audit?.limit ?? defaultAuditLogLimit) : null,
    audit_before_id: tab === "audit" && state.audit?.beforeId != null
      ? String(state.audit.beforeId)
      : null,
    grant_subject_type: tab === "grants" ? state.grant?.subjectType ?? null : null,
    grant_subject_id: tab === "grants" ? state.grant?.subjectId ?? null : null,
    grant_datasource: tab === "grants" ? state.grant?.datasourceKey ?? null : null,
  }
}
