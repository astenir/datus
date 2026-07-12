import { describe, expect, it, vi } from "vitest"
import { shallowRef } from "vue"

import { createWorkspaceRouteContextApplier } from "./workspace-route-context"

function deferred<T>() {
  let resolve: (value: T) => void = () => {
    throw new Error("deferred promise was not initialized")
  }
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

function createTarget() {
  const currentDatasource = shallowRef("initial")
  const database = shallowRef("")
  const schema = shallowRef("")
  const handleDatasourceSwitch = vi.fn(async (name: string) => {
    currentDatasource.value = name
    return true
  })
  const setDatabase = vi.fn((value: string) => {
    database.value = value
  })
  const setSchema = vi.fn((value: string) => {
    schema.value = value
  })

  return {
    state: { currentDatasource, database, schema },
    target: {
      currentDatasource,
      database,
      schema,
      handleDatasourceSwitch,
      setDatabase,
      setSchema,
    },
  }
}

describe("workspace route context applier", () => {
  it("applies datasource, database, and schema from one route context", async () => {
    const { state, target } = createTarget()
    const applier = createWorkspaceRouteContextApplier(target)

    await applier.apply({
      datasource: "fund",
      database: "analytics",
      schema: "public",
    })

    expect(target.handleDatasourceSwitch).toHaveBeenCalledWith("fund")
    expect(state.currentDatasource.value).toBe("fund")
    expect(state.database.value).toBe("analytics")
    expect(state.schema.value).toBe("public")
  })

  it("does not let an older delayed context overwrite the latest context", async () => {
    const { state, target } = createTarget()
    const firstSwitch = deferred<boolean>()
    const secondSwitch = deferred<boolean>()
    target.handleDatasourceSwitch.mockImplementation((name: string) => {
      state.currentDatasource.value = name
      return name === "first" ? firstSwitch.promise : secondSwitch.promise
    })
    const applier = createWorkspaceRouteContextApplier(target)

    const firstApply = applier.apply({
      datasource: "first",
      database: "first_db",
      schema: "first_schema",
    })
    const secondApply = applier.apply({
      datasource: "second",
      database: "second_db",
      schema: "second_schema",
    })

    secondSwitch.resolve(true)
    await secondApply
    firstSwitch.resolve(true)
    await firstApply

    expect(state.currentDatasource.value).toBe("second")
    expect(state.database.value).toBe("second_db")
    expect(state.schema.value).toBe("second_schema")
    expect(target.setDatabase).toHaveBeenCalledTimes(1)
    expect(target.setSchema).toHaveBeenCalledTimes(1)
  })

  it("invalidates a pending context without committing its database or schema", async () => {
    const { state, target } = createTarget()
    const pendingSwitch = deferred<boolean>()
    target.handleDatasourceSwitch.mockImplementation((name: string) => {
      state.currentDatasource.value = name
      return pendingSwitch.promise
    })
    const applier = createWorkspaceRouteContextApplier(target)

    const pendingApply = applier.apply({
      datasource: "fund",
      database: "analytics",
      schema: "public",
    })
    applier.invalidate()
    pendingSwitch.resolve(true)
    await pendingApply

    expect(target.setDatabase).not.toHaveBeenCalled()
    expect(target.setSchema).not.toHaveBeenCalled()
  })
})
