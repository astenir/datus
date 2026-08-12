import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { DEFAULT_WELCOME_TITLE, parseWelcomeTitle } from "./chat-welcome"

/** 重新加载模块以重置模块级缓存，并 stub 全局 fetch。 */
async function importFresh() {
  vi.resetModules()
  vi.stubGlobal("fetch", vi.fn())
  return import("./chat-welcome")
}

async function stubFetchResponse(
  module: typeof import("./chat-welcome"),
  body: string,
  ok = true,
) {
  const fetchMock = vi.mocked(fetch)
  fetchMock.mockResolvedValueOnce(
    new Response(body, { status: ok ? 200 : 404 }),
  )
  return module.loadWelcomeTitle()
}

describe("parseWelcomeTitle", () => {
  it("returns the first non-blank line, trimmed", () => {
    expect(parseWelcomeTitle("\n  有什么我能帮你的吗？ \n第二行\n")).toBe(
      "有什么我能帮你的吗？",
    )
  })

  it("returns an empty string when there is no valid line", () => {
    expect(parseWelcomeTitle(" \n\r\n")).toBe("")
  })
})

describe("loadWelcomeTitle", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("returns the file content when the fetch succeeds", async () => {
    const module = await importFresh()
    await expect(stubFetchResponse(module, "今天想分析点什么？\n")).resolves.toBe(
      "今天想分析点什么？",
    )
  })

  it("falls back to the default title when the file is missing", async () => {
    const module = await importFresh()
    await expect(stubFetchResponse(module, "not found", false)).resolves.toBe(
      DEFAULT_WELCOME_TITLE,
    )
  })

  it("falls back to the default title when the fetch throws", async () => {
    const module = await importFresh()
    vi.mocked(fetch).mockRejectedValueOnce(new Error("network down"))
    await expect(module.loadWelcomeTitle()).resolves.toBe(DEFAULT_WELCOME_TITLE)
  })

  it("falls back to the default title when the file is empty", async () => {
    const module = await importFresh()
    await expect(stubFetchResponse(module, "  \n")).resolves.toBe(
      DEFAULT_WELCOME_TITLE,
    )
  })

  it("caches the result and only fetches once", async () => {
    const module = await importFresh()
    await stubFetchResponse(module, "自定义标题")
    await module.loadWelcomeTitle()
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
  })
})
