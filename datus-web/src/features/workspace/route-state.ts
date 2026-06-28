import type { LocationQuery, LocationQueryRaw } from "vue-router"
import type { AdminViewTab } from "@/features/workspace/types"
import { isAdminViewTab } from "@/features/workspace/types"

export type WorkspaceContextQuery = {
  datasource: string | null
  database: string | null
  schema: string | null
}

export type AdminGrantRouteState = {
  subjectType: string
  subjectId: string
  datasourceKey: string
}

export type AdminArtifactRouteState = {
  artifactType: "dashboard" | "report"
  slug: string
}

export type AdminAuditRouteState = {
  userId: string | null
  action: string | null
  resourceType: string | null
  resourceId: string | null
  decision: string | null
  limit: number
}

const auditLimitValues = [50, 100, 200, 500] as const

export function routeQueryStringParam(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed || null
  }

  if (Array.isArray(value)) {
    const first = value.find(item => typeof item === "string" && item.trim())
    return typeof first === "string" ? first.trim() : null
  }

  return null
}

export function tableFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.table)
}

export function adminTabFromQuery(query: LocationQuery): AdminViewTab {
  const tab = routeQueryStringParam(query.tab)
  return tab && isAdminViewTab(tab) ? tab : "users"
}

export function adminSessionFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.session)
}

export function adminUserFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.user)
}

export function adminRoleFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.role)
}

export function adminSecretFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.secret)
}

export function adminArtifactFromQuery(query: LocationQuery): AdminArtifactRouteState | null {
  const artifactType = routeQueryStringParam(query.artifact_type)
  const slug = routeQueryStringParam(query.artifact_slug)

  if ((artifactType !== "dashboard" && artifactType !== "report") || !slug) {
    return null
  }

  return {
    artifactType,
    slug,
  }
}

export function adminAuditFromQuery(query: LocationQuery): AdminAuditRouteState {
  const limitValue = Number(routeQueryStringParam(query.audit_limit) ?? "")
  const limit = (auditLimitValues as readonly number[]).includes(limitValue) ? limitValue : 50

  return {
    userId: routeQueryStringParam(query.audit_user),
    action: routeQueryStringParam(query.audit_action),
    resourceType: routeQueryStringParam(query.audit_resource_type),
    resourceId: routeQueryStringParam(query.audit_resource_id),
    decision: routeQueryStringParam(query.audit_decision),
    limit,
  }
}

export function adminGrantFromQuery(query: LocationQuery): AdminGrantRouteState | null {
  const subjectType = routeQueryStringParam(query.grant_subject_type)
  const subjectId = routeQueryStringParam(query.grant_subject_id)
  const datasourceKey = routeQueryStringParam(query.grant_datasource)

  if (!subjectType || !subjectId || !datasourceKey) return null

  return {
    subjectType,
    subjectId,
    datasourceKey,
  }
}

export function semanticTableFromQuery(query: LocationQuery): string | null {
  return tableFromQuery(query)
}

export function datasourceFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.datasource)
}

export function databaseFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.database)
}

export function schemaFromQuery(query: LocationQuery): string | null {
  return routeQueryStringParam(query.schema)
}

export function workspaceContextFromQuery(query: LocationQuery): WorkspaceContextQuery {
  return {
    datasource: datasourceFromQuery(query),
    database: databaseFromQuery(query),
    schema: schemaFromQuery(query),
  }
}

export function replaceQueryStringParams(
  query: LocationQuery,
  updates: Record<string, string | null>,
): LocationQueryRaw {
  const next: LocationQueryRaw = {}
  const updateKeys = new Set(Object.keys(updates))

  for (const [queryKey, queryValue] of Object.entries(query)) {
    if (!updateKeys.has(queryKey) && queryValue != null) {
      next[queryKey] = queryValue
    }
  }

  for (const [key, value] of Object.entries(updates)) {
    const trimmed = value?.trim() ?? ""
    if (trimmed) {
      next[key] = trimmed
    }
  }

  return next
}

export function replaceQueryStringParam(
  query: LocationQuery,
  key: string,
  value: string | null,
): LocationQueryRaw {
  return replaceQueryStringParams(query, { [key]: value })
}
