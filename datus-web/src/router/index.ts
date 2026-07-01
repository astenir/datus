import { createRouter, createWebHistory, type Router, type RouterHistory, type RouteRecordRaw } from "vue-router"

import { useAuth } from "@/composables/useAuth"
import { usePermission } from "@/composables/usePermission"
import DatusWorkspace from "@/features/workspace/DatusWorkspace.vue"
import type { ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import { workspaceRouteNames } from "@/features/workspace/types"

declare module "vue-router" {
  interface RouteMeta {
    workspaceView?: WorkspaceView
    artifactTab?: ArtifactViewTab
    requiresAdmin?: boolean
  }
}

export const workspaceRoutes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: { name: workspaceRouteNames.chat },
  },
  {
    path: "/chat",
    name: workspaceRouteNames.chat,
    component: DatusWorkspace,
    meta: { workspaceView: "chat" },
  },
  {
    path: "/chat/:sessionId",
    name: workspaceRouteNames.chatSession,
    component: DatusWorkspace,
    meta: { workspaceView: "chat" },
  },
  {
    path: "/catalog",
    name: workspaceRouteNames.catalog,
    component: DatusWorkspace,
    meta: { workspaceView: "knowledge" },
  },
  {
    path: "/semantic",
    name: workspaceRouteNames.semantic,
    component: DatusWorkspace,
    meta: { workspaceView: "knowledge" },
  },
  {
    path: "/knowledge",
    name: workspaceRouteNames.knowledge,
    component: DatusWorkspace,
    meta: { workspaceView: "knowledge" },
  },
  {
    path: "/sql",
    name: workspaceRouteNames.sql,
    redirect: { name: workspaceRouteNames.chat },
  },
  {
    path: "/mcp",
    name: workspaceRouteNames.mcp,
    component: DatusWorkspace,
    meta: { workspaceView: "mcp" },
  },
  {
    path: "/agents",
    name: workspaceRouteNames.agents,
    component: DatusWorkspace,
    meta: { workspaceView: "agents" },
  },
  {
    path: "/configuration",
    name: workspaceRouteNames.configuration,
    component: DatusWorkspace,
    meta: { workspaceView: "configuration" },
  },
  {
    path: "/artifacts",
    redirect: { name: workspaceRouteNames.artifactDashboard },
  },
  {
    path: "/artifacts/dashboards",
    name: workspaceRouteNames.artifactDashboard,
    component: DatusWorkspace,
    meta: { workspaceView: "artifacts", artifactTab: "dashboard" },
  },
  {
    path: "/artifacts/dashboards/:slug",
    name: workspaceRouteNames.artifactDashboardDetail,
    component: DatusWorkspace,
    meta: { workspaceView: "artifacts", artifactTab: "dashboard" },
  },
  {
    path: "/artifacts/reports",
    name: workspaceRouteNames.artifactReport,
    component: DatusWorkspace,
    meta: { workspaceView: "artifacts", artifactTab: "report" },
  },
  {
    path: "/artifacts/reports/:slug",
    name: workspaceRouteNames.artifactReportDetail,
    component: DatusWorkspace,
    meta: { workspaceView: "artifacts", artifactTab: "report" },
  },
  {
    path: "/profile",
    name: workspaceRouteNames.profile,
    component: DatusWorkspace,
    meta: { workspaceView: "profile" },
  },
  {
    path: "/admin",
    name: workspaceRouteNames.admin,
    component: DatusWorkspace,
    meta: { workspaceView: "admin", requiresAdmin: true },
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/chat",
  },
]

export function createDatusRouter(history: RouterHistory = createWebHistory()): Router {
  const router = createRouter({
    history,
    routes: workspaceRoutes,
    scrollBehavior(_to, _from, savedPosition) {
      return savedPosition ?? { top: 0 }
    },
  })

  router.beforeEach(async (to) => {
    if (!to.meta.requiresAdmin) return true

    const auth = useAuth()
    const permission = usePermission()
    if (auth.state.value.loading) {
      await auth.checkAuth()
    }

    if (!auth.state.value.authenticated) {
      return { name: workspaceRouteNames.chat }
    }

    if (!permission.isAdmin() && !permission.hasFeaturePermission("admin")) {
      return { name: workspaceRouteNames.chat }
    }

    return true
  })

  return router
}
