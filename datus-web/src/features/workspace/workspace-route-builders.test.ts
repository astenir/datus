import { describe, expect, it } from "vitest"

import type { WorkspaceContextQuery } from "./route-state"
import type { WorkspaceAdminRouteState, WorkspaceRouteState } from "./workspace-route-builders"
import {
  adminDetailRoute,
  adminTabRoute,
  artifactRouteForTab,
  chatRouteForSession,
  knowledgeTableRoute,
  workspaceRouteForView,
} from "./workspace-route-builders"

const context: WorkspaceContextQuery = {
  datasource: "fund",
  database: "analytics",
  schema: "public",
}

const adminState: WorkspaceAdminRouteState = {
  tab: "users",
  sessionId: null,
  userId: "alice",
  roleId: null,
  secretName: null,
  grant: null,
  artifact: null,
  audit: null,
}

const routeState: WorkspaceRouteState = {
  artifactTab: "report",
  semanticTable: "semantic_table",
  catalogTable: "catalog_table",
  admin: adminState,
}

describe("workspace route builders", () => {
  it("builds chat and artifact detail locations with workspace context", () => {
    expect(chatRouteForSession(context, "session-1")).toEqual({
      name: "workspace-chat-session",
      params: { sessionId: "session-1" },
      query: context,
    })
    expect(artifactRouteForTab(context, "report", "weekly-report")).toEqual({
      name: "workspace-artifact-report-detail",
      params: { slug: "weekly-report" },
      query: context,
    })
  })

  it("keeps view-specific table and admin state in view locations", () => {
    expect(workspaceRouteForView("semantic", routeState, context)).toEqual({
      name: "workspace-knowledge",
      query: {
        ...context,
        table: "semantic_table",
      },
    })
    expect(workspaceRouteForView("admin", {
      ...routeState,
      admin: {
        ...adminState,
        tab: "users",
        userId: "alice",
      },
    }, context)).toEqual({
      name: "workspace-admin",
      query: {
        ...context,
        tab: "users",
        user: "alice",
      },
    })
  })

  it("preserves unrelated query state while changing knowledge tables", () => {
    expect(knowledgeTableRoute({ datasource: "fund", mode: "edit" }, "new_table")).toEqual({
      name: "workspace-knowledge",
      query: {
        datasource: "fund",
        mode: "edit",
        table: "new_table",
      },
    })
  })

  it("clears stale admin details when switching tabs", () => {
    expect(adminTabRoute({
      datasource: "fund",
      tab: "users",
      user: "alice",
      mode: "edit",
    }, adminState, "roles")).toEqual({
      name: "workspace-admin",
      query: {
        datasource: "fund",
        mode: "edit",
        tab: "roles",
      },
    })
    expect(adminDetailRoute({
      datasource: "fund",
      tab: "users",
      user: "alice",
      mode: "edit",
    }, {
      tab: "sessions",
      session: "session-1",
    })).toEqual({
      name: "workspace-admin",
      query: {
        datasource: "fund",
        mode: "edit",
        tab: "sessions",
        session: "session-1",
      },
    })
  })
})
