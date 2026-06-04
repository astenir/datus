import { describe, expect, it } from "vitest";

import { scrollBehaviorForChatUpdate } from "./scroll";

describe("scrollBehaviorForChatUpdate", () => {
  it("uses instant scrolling while streaming to avoid interrupting smooth animations", () => {
    expect(scrollBehaviorForChatUpdate(true)).toBe("auto");
  });

  it("keeps smooth scrolling for non-streaming message changes", () => {
    expect(scrollBehaviorForChatUpdate(false)).toBe("smooth");
  });
});
