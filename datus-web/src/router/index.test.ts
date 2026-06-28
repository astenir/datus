import { beforeEach, describe, expect, it, vi } from "vitest"
import { createMemoryHistory } from "vue-router"

import { workspaceRouteNames } from "@/features/workspace/types"
import { createDatusRouter } from "./index"

const authMock = vi.hoisted(() => ({
  state: {
    value: {
      loading: false,
      authenticated: true,
      user: null,
    },
  },
  checkAuth: vi.fn<() => Promise<void>>(),
}))

const permissionMock = vi.hoisted(() => ({
  isAdmin: vi.fn(() => true),
  hasFeaturePermission: vi.fn(() => false),
}))

vi.mock("@/features/workspace/DatusWorkspace.vue", () => ({
  default: {
    name: "DatusWorkspace",
    template: "<div />",
  },
}))

vi.mock("@/composables/useAuth", () => ({
  useAuth: () => authMock,
}))

vi.mock("@/composables/usePermission", () => ({
  usePermission: () => permissionMock,
}))

async function routeTo(path: string) {
  const router = createDatusRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()
  return router.currentRoute.value
}

describe("workspace router", () => {
  beforeEach(() => {
    authMock.state.value = {
      loading: false,
      authenticated: true,
      user: null,
    }
    authMock.checkAuth.mockReset()
    authMock.checkAuth.mockResolvedValue()
    permissionMock.isAdmin.mockReset()
    permissionMock.isAdmin.mockReturnValue(true)
    permissionMock.hasFeaturePermission.mockReset()
    permissionMock.hasFeaturePermission.mockReturnValue(false)
  })

  it("maps workspace feature URLs to typed route meta", async () => {
    await expect(routeTo("/configuration")).resolves.toMatchObject({
      name: workspaceRouteNames.configuration,
      meta: { workspaceView: "configuration" },
    })

    await expect(routeTo("/chat/session-42")).resolves.toMatchObject({
      name: workspaceRouteNames.chatSession,
      params: { sessionId: "session-42" },
      meta: { workspaceView: "chat" },
    })

    await expect(routeTo("/artifacts/reports")).resolves.toMatchObject({
      name: workspaceRouteNames.artifactReport,
      meta: { workspaceView: "artifacts", artifactTab: "report" },
    })

    await expect(routeTo("/artifacts/dashboards/fund-overview")).resolves.toMatchObject({
      name: workspaceRouteNames.artifactDashboardDetail,
      params: { slug: "fund-overview" },
      meta: { workspaceView: "artifacts", artifactTab: "dashboard" },
    })

    await expect(routeTo("/artifacts/reports/fund-report")).resolves.toMatchObject({
      name: workspaceRouteNames.artifactReportDetail,
      params: { slug: "fund-report" },
      meta: { workspaceView: "artifacts", artifactTab: "report" },
    })

    await expect(routeTo("/semantic?table=fund.public.fund_nav")).resolves.toMatchObject({
      name: workspaceRouteNames.semantic,
      query: { table: "fund.public.fund_nav" },
      meta: { workspaceView: "semantic" },
    })

    await expect(routeTo("/catalog?table=fund.public.fund_nav")).resolves.toMatchObject({
      name: workspaceRouteNames.catalog,
      query: { table: "fund.public.fund_nav" },
      meta: { workspaceView: "catalog" },
    })

    await expect(routeTo("/agents")).resolves.toMatchObject({
      name: workspaceRouteNames.agents,
      meta: { workspaceView: "agents" },
    })

    await expect(routeTo("/admin?tab=sessions&session=session-1")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: { tab: "sessions", session: "session-1" },
      meta: { workspaceView: "admin", requiresAdmin: true },
    })

    await expect(routeTo("/admin?tab=users&user=alice")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: { tab: "users", user: "alice" },
      meta: { workspaceView: "admin", requiresAdmin: true },
    })

    await expect(routeTo("/admin?tab=roles&role=analyst")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: { tab: "roles", role: "analyst" },
      meta: { workspaceView: "admin", requiresAdmin: true },
    })

    await expect(routeTo("/admin?tab=grants&grant_subject_type=role&grant_subject_id=analyst&grant_datasource=fund")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: {
        tab: "grants",
        grant_subject_type: "role",
        grant_subject_id: "analyst",
        grant_datasource: "fund",
      },
      meta: { workspaceView: "admin", requiresAdmin: true },
    })

    await expect(routeTo("/admin?tab=secrets&secret=openai.default")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: { tab: "secrets", secret: "openai.default" },
      meta: { workspaceView: "admin", requiresAdmin: true },
    })

    await expect(routeTo("/admin?tab=artifacts&artifact_type=dashboard&artifact_slug=fund-overview")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: {
        tab: "artifacts",
        artifact_type: "dashboard",
        artifact_slug: "fund-overview",
      },
      meta: { workspaceView: "admin", requiresAdmin: true },
    })

    await expect(routeTo("/admin?tab=audit&audit_user=alice&audit_action=sql.execute&audit_resource_type=datasource&audit_resource_id=fund&audit_decision=allow&audit_limit=200")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: {
        tab: "audit",
        audit_user: "alice",
        audit_action: "sql.execute",
        audit_resource_type: "datasource",
        audit_resource_id: "fund",
        audit_decision: "allow",
        audit_limit: "200",
      },
      meta: { workspaceView: "admin", requiresAdmin: true },
    })
  })

  it("redirects root, artifacts root, and unknown paths to stable workspace entries", async () => {
    await expect(routeTo("/")).resolves.toMatchObject({
      name: workspaceRouteNames.chat,
      path: "/chat",
    })

    await expect(routeTo("/artifacts")).resolves.toMatchObject({
      name: workspaceRouteNames.artifactDashboard,
      path: "/artifacts/dashboards",
    })

    await expect(routeTo("/missing-view")).resolves.toMatchObject({
      name: workspaceRouteNames.chat,
      path: "/chat",
    })
  })

  it("marks admin as a guarded workspace route", async () => {
    await expect(routeTo("/admin")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      meta: { workspaceView: "admin", requiresAdmin: true },
    })
  })

  it("redirects unauthorized admin URLs before entering the guarded workspace route", async () => {
    permissionMock.isAdmin.mockReturnValue(false)
    permissionMock.hasFeaturePermission.mockReturnValue(false)

    await expect(routeTo("/admin?tab=users&user=alice")).resolves.toMatchObject({
      name: workspaceRouteNames.chat,
      path: "/chat",
    })
  })

  it("waits for initial auth before evaluating admin route permissions", async () => {
    authMock.state.value = {
      loading: true,
      authenticated: false,
      user: null,
    }
    authMock.checkAuth.mockImplementation(async () => {
      authMock.state.value = {
        loading: false,
        authenticated: true,
        user: null,
      }
    })
    permissionMock.isAdmin.mockReturnValue(false)
    permissionMock.hasFeaturePermission.mockReturnValue(true)

    await expect(routeTo("/admin?tab=roles")).resolves.toMatchObject({
      name: workspaceRouteNames.admin,
      query: { tab: "roles" },
    })
    expect(authMock.checkAuth).toHaveBeenCalledTimes(1)
  })
})
