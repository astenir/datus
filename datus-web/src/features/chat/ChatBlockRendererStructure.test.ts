import { describe, expect, it } from "vitest"

import rendererSource from "./ChatBlockRenderer.vue?raw"
import interactionSource from "./ChatInteractionBlock.vue?raw"
import toolExecutionSource from "./ChatToolExecutionBlock.vue?raw"

describe("Chat block rendering boundaries", () => {
  it("keeps tool execution details out of the top-level dispatcher", () => {
    expect(rendererSource).toContain("<ChatToolExecutionBlock")
    expect(rendererSource).toContain("<ChatInteractionBlock")
    expect(rendererSource).toContain("#child-block")
    expect(rendererSource).not.toContain("<ToolExecutionCard")
    expect(rendererSource).not.toContain("<ToolPayloadView")
    expect(rendererSource).not.toContain("<UserInteractionBlock")
  })

  it("keeps recursive child rendering behind the tool block slot", () => {
    expect(toolExecutionSource).toContain("<ToolExecutionCard")
    expect(toolExecutionSource).toContain('<slot\n                  name="child-block"')
    expect(toolExecutionSource).not.toContain("<ChatBlockRenderer")
  })

  it("keeps interaction state presentation in the feature wrapper", () => {
    expect(interactionSource).toContain("<UserInteractionBlock")
    expect(interactionSource).toContain('data-testid="chat-interaction-docked"')
    expect(interactionSource).toContain('data-testid="chat-interaction-read-only"')
  })
})
