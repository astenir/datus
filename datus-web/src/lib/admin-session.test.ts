import { describe, expect, it } from "vitest"

import {
  adminSessionBodyStateLabel,
  adminSessionStatusDescription,
  adminSessionStatusLabel,
} from "./admin-session"

describe("admin session display", () => {
  it("maps runtime and persisted states to clear Chinese labels", () => {
    expect(adminSessionStatusLabel("running")).toBe("运行中")
    expect(adminSessionStatusLabel("completed")).toBe("已完成")
    expect(adminSessionStatusLabel("error")).toBe("执行失败")
    expect(adminSessionStatusLabel("cancelled")).toBe("已取消")
    expect(adminSessionStatusLabel("persisted")).toBe("仅保留记录")
    expect(adminSessionStatusLabel("custom")).toBe("custom")
  })

  it("explains when only the persisted owner record remains", () => {
    expect(adminSessionStatusDescription("persisted")).toContain("无运行态快照")
  })

  it("keeps missing and unknown session body states distinct", () => {
    expect(adminSessionBodyStateLabel(true)).toBe("存在")
    expect(adminSessionBodyStateLabel(false)).toBe("缺失")
    expect(adminSessionBodyStateLabel(null)).toBe("无法确认")
    expect(adminSessionBodyStateLabel(undefined)).toBe("无法确认")
  })
})
