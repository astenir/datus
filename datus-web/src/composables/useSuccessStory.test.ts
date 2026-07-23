import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiResultError } from "@/lib/chat"
import type { SuccessStoryResult, SuccessStorySource } from "@/types"

const mocks = vi.hoisted(() => ({
  save: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({ effectiveBase: () => "http://api.test" }),
}))

vi.mock("@/lib/api", () => ({
  successStoryApi: { save: mocks.save },
}))

vi.mock("vue-sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}))

import { useSuccessStory } from "./useSuccessStory"

const source: SuccessStorySource = {
  sessionId: "chat_session_1",
  callToolId: "call_1",
  sessionLink: "/chat/chat_session_1",
}

function result(created: boolean): SuccessStoryResult {
  return {
    story_id: "ss_1",
    created,
    datasource_id: "ccks_fund",
    subagent_name: "gen_sql",
    storage_key: "ccks_fund/gen_sql/success_story.csv",
    session_id: "chat_session_1",
    timestamp: "2026-07-23T00:00:00Z",
  }
}

describe("useSuccessStory", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("saves the canonical source and remembers local saved state", async () => {
    mocks.save.mockResolvedValue(result(true))
    const manager = useSuccessStory()

    await expect(manager.save(source)).resolves.toBe(true)

    expect(mocks.save).toHaveBeenCalledWith("http://api.test", {
      session_id: "chat_session_1",
      call_tool_id: "call_1",
      session_link: "/chat/chat_session_1",
    })
    expect(manager.isSaving(source)).toBe(false)
    expect(manager.isSaved(source)).toBe(true)
    expect(mocks.toastSuccess).toHaveBeenCalledWith("已保存为成功案例")
  })

  it("coalesces duplicate concurrent requests", async () => {
    let resolveRequest: ((value: SuccessStoryResult) => void) | undefined
    mocks.save.mockImplementation(() => new Promise((resolve) => {
      resolveRequest = resolve
    }))
    const manager = useSuccessStory()

    const first = manager.save(source)
    const second = manager.save(source)

    expect(manager.isSaving(source)).toBe(true)
    await expect(second).resolves.toBe(false)
    expect(mocks.save).toHaveBeenCalledTimes(1)
    resolveRequest?.(result(false))
    await expect(first).resolves.toBe(true)
    expect(mocks.toastSuccess).toHaveBeenCalledWith("该 SQL 已保存")
  })

  it("maps backend errors to safe user copy", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    mocks.save.mockRejectedValue(new ApiResultError("private backend detail", "SUCCESS_STORY_SQL_NOT_READ_ONLY"))
    const manager = useSuccessStory()

    await expect(manager.save(source)).resolves.toBe(false)

    expect(manager.isSaved(source)).toBe(false)
    expect(mocks.toastError).toHaveBeenCalledWith("仅支持保存只读 SQL")
    expect(mocks.toastError).not.toHaveBeenCalledWith("private backend detail")
  })

  it.each([
    ["SUCCESS_STORY_DATASOURCE_NOT_FOUND", "未找到该 SQL 实际使用的数据源"],
    ["SUCCESS_STORY_DATASOURCE_CONFLICT", "SQL 执行记录中的数据源不一致，无法保存"],
  ])("maps datasource error %s to actionable copy", async (errorCode, message) => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    mocks.save.mockRejectedValue(new ApiResultError("private backend detail", errorCode))
    const manager = useSuccessStory()

    await expect(manager.save(source)).resolves.toBe(false)

    expect(mocks.toastError).toHaveBeenCalledWith(message)
    expect(mocks.toastError).not.toHaveBeenCalledWith("private backend detail")
  })
})
