import { describe, expect, it } from "vitest"

import {
  adminSessionBodyStateLabel,
  adminSessionRuntimeValueLabel,
  adminSessionStatusDescription,
  adminSessionStatusLabel,
} from "./admin-session"

describe("admin session display", () => {
  it("maps runtime and persisted states to clear Chinese labels", () => {
    expect(adminSessionStatusLabel("running")).toBe("运行中")
    expect(adminSessionStatusLabel("completed")).toBe("已完成")
    expect(adminSessionStatusLabel("error")).toBe("执行失败")
    expect(adminSessionStatusLabel("cancelled")).toBe("已取消")
    expect(adminSessionStatusLabel("persisted")).toBe("已保存会话记录")
    expect(adminSessionStatusLabel("custom")).toBe("custom")
  })

  it("explains persisted records without process-specific terminology", () => {
    expect(adminSessionStatusDescription("persisted")).toBe("会话记录已保存，可继续查看。")
  })

  it("keeps missing and unknown session body states distinct", () => {
    expect(adminSessionBodyStateLabel(true)).toBe("存在")
    expect(adminSessionBodyStateLabel(false)).toBe("缺失")
    expect(adminSessionBodyStateLabel(null)).toBe("无法确认")
    expect(adminSessionBodyStateLabel(undefined)).toBe("无法确认")
  })

  it("keeps real runtime values and uses one placeholder when data is unavailable", () => {
    expect(adminSessionRuntimeValueLabel(true, 0)).toBe("0")
    expect(adminSessionRuntimeValueLabel(true, "执行失败")).toBe("执行失败")
    expect(adminSessionRuntimeValueLabel(true, null)).toBe("—")
    expect(adminSessionRuntimeValueLabel(false, 0)).toBe("—")
    expect(adminSessionRuntimeValueLabel(false, null)).toBe("—")
  })
})
