import type { Ref } from "vue"

export type WorkspaceRouteContextValue = {
  datasource: string | null
  database: string | null
  schema: string | null
}

type WorkspaceRouteContextTarget = {
  currentDatasource: Readonly<Ref<string>>
  database: Readonly<Ref<string>>
  schema: Readonly<Ref<string>>
  handleDatasourceSwitch: (name: string) => Promise<boolean>
  setDatabase: (value: string) => void
  setSchema: (value: string) => void
}

export function createWorkspaceRouteContextApplier(target: WorkspaceRouteContextTarget) {
  let latestRequest = 0

  function invalidate() {
    latestRequest += 1
  }

  async function apply(context: WorkspaceRouteContextValue): Promise<void> {
    const request = ++latestRequest
    const nextDatasource = context.datasource ?? ""
    const nextDatabase = context.database ?? ""
    const nextSchema = context.schema ?? ""

    if (nextDatasource && target.currentDatasource.value !== nextDatasource) {
      const switched = await target.handleDatasourceSwitch(nextDatasource)
      if (request !== latestRequest) return
      if (!switched && target.currentDatasource.value !== nextDatasource) return
    }

    if (request !== latestRequest) return

    if (target.database.value !== nextDatabase) {
      target.setDatabase(nextDatabase)
    }

    if (target.schema.value !== nextSchema) {
      target.setSchema(nextSchema)
    }
  }

  return { apply, invalidate }
}
