import { describe, expect, it } from "vitest"

import rendererSource from "./ChatBlockRenderer.vue?raw"
import toolExecutionSource from "./ChatToolExecutionBlock.vue?raw"

describe("Chat block rendering boundaries", () => {
  it("keeps tool execution details out of the top-level dispatcher", () => {
    expect(rendererSource).toContain("<ChatToolExecutionBlock")
    expect(rendererSource).toContain("#child-block")
    expect(rendererSource).not.toContain("<ToolExecutionCard")
    expect(rendererSource).not.toContain("<ToolPayloadView")
  })

  it("keeps recursive child rendering behind the tool block slot", () => {
    expect(toolExecutionSource).toContain("<ToolExecutionCard")
    expect(toolExecutionSource).toContain('<slot\n                  name="child-block"')
    expect(toolExecutionSource).not.toContain("<ChatBlockRenderer")
  })
})
