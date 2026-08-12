import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  DEFAULT_CHAT_SUGGESTIONS,
  parseChatSuggestions,
} from "./chat-suggestions"

/** 重新加载模块以重置模块级缓存，并 stub 全局 fetch。 */
async function importFresh() {
  vi.resetModules()
  vi.stubGlobal("fetch", vi.fn())
  return import("./chat-suggestions")
}

async function stubFetchResponse(
  module: typeof import("./chat-suggestions"),
  body: string,
  ok = true,
) {
  const fetchMock = vi.mocked(fetch)
  fetchMock.mockResolvedValueOnce(
    new Response(body, { status: ok ? 200 : 404 }),
  )
  return module.loadChatSuggestions()
}

describe("parseChatSuggestions", () => {
  it("splits lines and trims whitespace", () => {
    expect(parseChatSuggestions("  帮我分析基金持仓的关键变化 \n列出当前数据源有哪些表\n")).toEqual([
      "帮我分析基金持仓的关键变化",
      "列出当前数据源有哪些表",
    ])
  })

  it("filters blank and duplicate lines", () => {
    expect(
      parseChatSuggestions("\n查询近 10 条记录\n\n查询近 10 条记录\r\n   \r\n"),
    ).toEqual(["查询近 10 条记录"])
  })
})

describe("loadChatSuggestions", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("returns parsed file content when the fetch succeeds", async () => {
    const module = await importFresh()
    const result = await stubFetchResponse(module, "语句 A\n语句 B\n")
    expect(result).toEqual(["语句 A", "语句 B"])
  })

  it("falls back to built-in defaults when the file is missing", async () => {
    const module = await importFresh()
    const result = await stubFetchResponse(module, "not found", false)
    expect(result).toEqual(DEFAULT_CHAT_SUGGESTIONS)
  })

  it("falls back to built-in defaults when the fetch throws", async () => {
    const module = await importFresh()
    vi.mocked(fetch).mockRejectedValueOnce(new Error("network down"))
    await expect(module.loadChatSuggestions()).resolves.toEqual(DEFAULT_CHAT_SUGGESTIONS)
  })

  it("treats an existing but empty file as no suggestions", async () => {
    const module = await importFresh()
    const result = await stubFetchResponse(module, "")
    expect(result).toEqual([])
  })

  it("caches the result and only fetches once", async () => {
    const module = await importFresh()
    await stubFetchResponse(module, "语句 A")
    await module.loadChatSuggestions()
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
  })
})
