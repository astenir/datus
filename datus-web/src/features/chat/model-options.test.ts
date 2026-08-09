import { describe, expect, it } from "vitest"

import type { SelectOption } from "@/types"
import {
  groupModelOptions,
  modelOptionLabel,
  modelProviderKey,
  modelProviderLabel,
} from "./model-options"

const options: SelectOption[] = [
  { value: "openai/gpt-4.1", label: "GPT 4.1" },
  { value: "openai/gpt-4o", label: "GPT 4o" },
  { value: "dashscope/qwen", label: "通义千问", group: "阿里云" },
  { value: "custom-model", label: "自定义模型" },
  { value: "label-model", label: "internal: 标签模型" },
]

describe("model options", () => {
  it("resolves a selected label and keeps unknown values visible", () => {
    expect(modelOptionLabel("openai/gpt-4.1", options)).toBe("GPT 4.1")
    expect(modelOptionLabel("missing/model", options)).toBe("missing/model")
    expect(modelOptionLabel("", options)).toBe("")
  })

  it("prefers explicit groups and supports provider/value label fallbacks", () => {
    expect(modelProviderKey(options[2])).toBe("阿里云")
    expect(modelProviderLabel(options[2])).toBe("阿里云")
    expect(modelProviderKey(options[0])).toBe("openai")
    expect(modelProviderLabel(options[0])).toBe("openai")
    expect(modelProviderKey(options[4])).toBe("internal")
    expect(modelProviderLabel(options[4])).toBe("internal")
    expect(modelProviderKey(options[3])).toBe("other")
    expect(modelProviderLabel(options[3])).toBe("其他模型")
  })

  it("keeps first-seen provider order while grouping model options", () => {
    expect(groupModelOptions(options)).toEqual([
      {
        provider: "openai",
        label: "openai",
        options: [options[0], options[1]],
      },
      {
        provider: "阿里云",
        label: "阿里云",
        options: [options[2]],
      },
      {
        provider: "other",
        label: "其他模型",
        options: [options[3]],
      },
      {
        provider: "internal",
        label: "internal",
        options: [options[4]],
      },
    ])
  })
})
