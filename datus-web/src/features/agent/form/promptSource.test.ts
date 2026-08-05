import { describe, expect, it } from "vitest"

import { promptSourceLabel } from "./promptSource"

describe("promptSourceLabel", () => {
  it.each([
    ["builtin", "系统内置"],
    ["user_override", "用户模板覆盖"],
    ["runtime", "运行时配置"],
    ["enterprise", "企业自定义"],
    ["builtin_fallback", "内置回退"],
    ["user_override_fallback", "用户模板覆盖回退"],
    ["runtime_fallback", "运行时配置回退"],
  ])("maps %s to %s", (source, label) => {
    expect(promptSourceLabel(source)).toBe(label)
  })

  it("preserves an unknown non-empty source for forward compatibility", () => {
    expect(promptSourceLabel("future_source")).toBe("future_source")
    expect(promptSourceLabel(null)).toBe("-")
  })
})
