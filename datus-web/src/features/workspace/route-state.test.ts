import { describe, expect, it } from "vitest"

import {
  adminAuditFromQuery,
  adminArtifactFromQuery,
  adminGrantFromQuery,
  adminRoleFromQuery,
  adminTabFromQuery,
  adminSessionFromQuery,
  adminUserFromQuery,
  databaseFromQuery,
  datasourceFromQuery,
  replaceQueryStringParam,
  replaceQueryStringParams,
  routeQueryStringParam,
  schemaFromQuery,
  semanticTableFromQuery,
  tableFromQuery,
  workspaceContextFromQuery,
} from "./route-state"

describe("workspace route state", () => {
  it("normalizes string route query params", () => {
    expect(routeQueryStringParam(" fund.public.nav ")).toBe("fund.public.nav")
    expect(routeQueryStringParam(["", " fund.public.profile "])).toBe("fund.public.profile")
    expect(routeQueryStringParam(["", null])).toBeNull()
    expect(routeQueryStringParam(null)).toBeNull()
  })

  it("reads semantic table query state", () => {
    expect(tableFromQuery({ table: "fund.public.nav" })).toBe("fund.public.nav")
    expect(semanticTableFromQuery({ table: "fund.public.nav" })).toBe("fund.public.nav")
    expect(semanticTableFromQuery({ table: ["", "fund.public.profile"] })).toBe("fund.public.profile")
    expect(semanticTableFromQuery({ table: " " })).toBeNull()
  })

  it("reads admin tab query state with a stable fallback", () => {
    expect(adminTabFromQuery({ tab: "sessions" })).toBe("sessions")
    expect(adminTabFromQuery({ tab: ["", "artifacts"] })).toBe("artifacts")
    expect(adminTabFromQuery({ tab: "secrets" })).toBe("users")
    expect(adminTabFromQuery({ tab: "legacy-permissions" })).toBe("users")
    expect(adminTabFromQuery({ tab: " " })).toBe("users")
  })

  it("reads admin session detail query state", () => {
    expect(adminSessionFromQuery({ session: " session-1 " })).toBe("session-1")
    expect(adminSessionFromQuery({ session: ["", "session-2"] })).toBe("session-2")
    expect(adminSessionFromQuery({ session: " " })).toBeNull()
  })

  it("reads admin user detail query state", () => {
    expect(adminUserFromQuery({ user: " alice " })).toBe("alice")
    expect(adminUserFromQuery({ user: ["", "bob"] })).toBe("bob")
    expect(adminUserFromQuery({ user: " " })).toBeNull()
  })

  it("reads admin role detail query state", () => {
    expect(adminRoleFromQuery({ role: " analyst " })).toBe("analyst")
    expect(adminRoleFromQuery({ role: ["", "admin"] })).toBe("admin")
    expect(adminRoleFromQuery({ role: " " })).toBeNull()
  })

  it("reads admin datasource grant query state", () => {
    expect(adminGrantFromQuery({
      grant_subject_type: " role ",
      grant_subject_id: " analyst ",
      grant_datasource: " fund ",
    })).toEqual({
      subjectType: "role",
      subjectId: "analyst",
      datasourceKey: "fund",
    })
    expect(adminGrantFromQuery({
      grant_subject_type: ["", "user"],
      grant_subject_id: ["", "alice"],
      grant_datasource: ["", "warehouse"],
    })).toEqual({
      subjectType: "user",
      subjectId: "alice",
      datasourceKey: "warehouse",
    })
    expect(adminGrantFromQuery({
      grant_subject_type: "role",
      grant_subject_id: "analyst",
      grant_datasource: " ",
    })).toBeNull()
  })

  it("reads admin artifact ACL query state", () => {
    expect(adminArtifactFromQuery({
      artifact_type: " dashboard ",
      artifact_slug: " fund-overview ",
    })).toEqual({
      artifactType: "dashboard",
      slug: "fund-overview",
    })
    expect(adminArtifactFromQuery({
      artifact_type: ["", "report"],
      artifact_slug: ["", "weekly-report"],
    })).toEqual({
      artifactType: "report",
      slug: "weekly-report",
    })
    expect(adminArtifactFromQuery({
      artifact_type: "legacy",
      artifact_slug: "fund-overview",
    })).toBeNull()
    expect(adminArtifactFromQuery({
      artifact_type: "dashboard",
      artifact_slug: " ",
    })).toBeNull()
  })

  it("reads admin audit query filters with a bounded limit", () => {
    expect(adminAuditFromQuery({
      audit_user: " alice ",
      audit_action: " sql.execute ",
      audit_resource_type: " datasource ",
      audit_resource_id: " fund ",
      audit_decision: " allow ",
      audit_limit: "200",
    })).toEqual({
      userId: "alice",
      action: "sql.execute",
      resourceType: "datasource",
      resourceId: "fund",
      decision: "allow",
      limit: 200,
    })
    expect(adminAuditFromQuery({
      audit_user: ["", "bob"],
      audit_limit: "999",
    })).toEqual({
      userId: "bob",
      action: null,
      resourceType: null,
      resourceId: null,
      decision: null,
      limit: 50,
    })
  })

  it("reads workspace context query state", () => {
    expect(datasourceFromQuery({ datasource: " ccks_fund " })).toBe("ccks_fund")
    expect(databaseFromQuery({ database: " fund " })).toBe("fund")
    expect(schemaFromQuery({ schema: ["", " public "] })).toBe("public")
    expect(workspaceContextFromQuery({
      datasource: " ccks_fund ",
      database: " fund ",
      schema: " public ",
    })).toEqual({
      datasource: "ccks_fund",
      database: "fund",
      schema: "public",
    })
  })

  it("replaces one query key while preserving unrelated filters", () => {
    expect(replaceQueryStringParam({
      table: "old_table",
      mode: "edit",
      tags: ["a", "b"],
    }, "table", " new_table ")).toEqual({
      mode: "edit",
      tags: ["a", "b"],
      table: "new_table",
    })

    expect(replaceQueryStringParam({
      table: "old_table",
      mode: "edit",
    }, "table", "")).toEqual({
      mode: "edit",
    })
  })

  it("replaces multiple query keys while preserving semantic detail state", () => {
    expect(replaceQueryStringParams({
      table: "fund.public.fund_nav",
      datasource: "old-ds",
      database: "old",
      schema: "old_schema",
      mode: "edit",
    }, {
      datasource: " ccks_fund ",
      database: " fund ",
      schema: " public ",
    })).toEqual({
      table: "fund.public.fund_nav",
      mode: "edit",
      datasource: "ccks_fund",
      database: "fund",
      schema: "public",
    })
  })

  it("removes empty multi-key query updates", () => {
    expect(replaceQueryStringParams({
      table: "fund.public.fund_nav",
      datasource: "ccks_fund",
      database: "fund",
      schema: "public",
      mode: "edit",
    }, {
      datasource: "",
      database: "",
      schema: null,
    })).toEqual({
      table: "fund.public.fund_nav",
      mode: "edit",
    })
  })
})
