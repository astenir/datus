import { onBeforeUnmount, shallowRef, watch, type ComputedRef, type Ref } from "vue"
import type { RouteLocationNormalizedLoaded, Router } from "vue-router"

import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import type { WorkspaceContextQuery } from "@/features/workspace/route-state"
import { replaceQueryStringParams } from "@/features/workspace/route-state"
import { createWorkspaceRouteContextApplier } from "@/features/workspace/workspace-route-context"

interface UseWorkspaceRouteContextSyncOptions {
  route: RouteLocationNormalizedLoaded
  router: Router
  workspace: ChatWorkspace
  authState: Ref<AuthState>
  routeWorkspaceContext: ComputedRef<WorkspaceContextQuery>
}

export function useWorkspaceRouteContextSync(options: UseWorkspaceRouteContextSyncOptions) {
  const routeContextHydrated = shallowRef(false)
  const routeContextApplier = createWorkspaceRouteContextApplier(options.workspace)
  let activeRouteContextApply: Promise<void> | null = null

  async function applyRouteWorkspaceContext() {
    const applyPromise = routeContextApplier.apply(options.routeWorkspaceContext.value)
    activeRouteContextApply = applyPromise
    try {
      await applyPromise
    } finally {
      if (activeRouteContextApply === applyPromise) {
        activeRouteContextApply = null
      }
    }
  }

  function markRouteContextHydrated() {
    routeContextHydrated.value = true
  }

  function invalidateRouteWorkspaceContext() {
    routeContextApplier.invalidate()
    activeRouteContextApply = null
  }

  function syncRouteWorkspaceContext() {
    const nextQuery = replaceQueryStringParams(options.route.query, {
      datasource: options.workspace.currentDatasource.value,
      database: options.workspace.database.value,
      schema: options.workspace.schema.value,
    })
    void options.router.replace({ query: nextQuery })
  }

  onBeforeUnmount(() => {
    invalidateRouteWorkspaceContext()
  })

  watch(
    () => [
      routeContextHydrated.value,
      options.authState.value.authenticated,
      options.routeWorkspaceContext.value.datasource,
      options.routeWorkspaceContext.value.database,
      options.routeWorkspaceContext.value.schema,
    ] as const,
    ([hydrated, authenticated]) => {
      invalidateRouteWorkspaceContext()
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
      options.routeWorkspaceContext.value.datasource,
      options.routeWorkspaceContext.value.database,
      options.routeWorkspaceContext.value.schema,
    ] as const,
    ([hydrated, authenticated, datasource, database, schema, routeDatasource, routeDatabase, routeSchema]) => {
      if (!hydrated || !authenticated) return
      // Do not write intermediate workspace state back over the route that is currently being applied.
      if (activeRouteContextApply) return
      if ((routeDatasource ?? "") === datasource && (routeDatabase ?? "") === database && (routeSchema ?? "") === schema) {
        return
      }
      syncRouteWorkspaceContext()
    },
  )

  return {
    routeContextHydrated,
    applyRouteWorkspaceContext,
    markRouteContextHydrated,
  }
}
