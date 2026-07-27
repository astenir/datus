import { describe, expect, it } from "vitest"

import { formatAdminDateTime } from "./admin-date"

describe("admin date display", () => {
  it("displays backend UTC timestamps in the Shanghai business timezone", () => {
    expect(formatAdminDateTime("2026-07-27T10:36:00Z")).toBe("07/27 18:36")
    expect(formatAdminDateTime("2026-07-27T10:36:00+00:00")).toBe("07/27 18:36")
    expect(formatAdminDateTime("2026-07-27T18:36:00+08:00")).toBe("07/27 18:36")
  })

  it("treats legacy timezone-less timestamps as UTC", () => {
    expect(formatAdminDateTime("2026-07-27T10:36:00")).toBe("07/27 18:36")
    expect(formatAdminDateTime("2026-07-27 10:36:00")).toBe("07/27 18:36")
  })

  it("returns a stable fallback for missing or invalid timestamps", () => {
    expect(formatAdminDateTime(null)).toBe("-")
    expect(formatAdminDateTime(undefined)).toBe("-")
    expect(formatAdminDateTime("")).toBe("-")
    expect(formatAdminDateTime("not-a-date")).toBe("-")
  })
})
