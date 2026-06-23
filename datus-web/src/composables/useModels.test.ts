import { describe, expect, it } from "vitest";

import { buildModelOption, resolveModelDisplayName } from "./useModels";
import type { ModelInfo } from "@/types";

describe("buildModelOption", () => {
  it("uses the custom model key as the selected value", () => {
    const model: ModelInfo = {
      provider: "custom",
      id: "qwen-ebd",
      model: "Qwen/Qwen3-Embedding-0.6B",
      name: "qwen-ebd"
    };

    expect(buildModelOption(model)).toEqual({
      value: "custom/qwen-ebd",
      label: "qwen-ebd"
    });
  });

  it("uses the provider model slug for provider catalog entries", () => {
    const model: ModelInfo = {
      provider: "openai",
      id: "gpt-4.1",
      model: "gpt-4.1",
      name: "GPT 4.1"
    };

    expect(buildModelOption(model)).toEqual({
      value: "openai/gpt-4.1",
      label: "GPT 4.1"
    });
  });

  it("resolves the current model to the configured option label", () => {
    expect(
      resolveModelDisplayName("openai/gpt-4.1", [
        { value: "openai/gpt-4.1", label: "GPT 4.1" },
      ])
    ).toBe("GPT 4.1");
  });

  it("keeps the raw current model when the option is missing", () => {
    expect(resolveModelDisplayName("deepseek/deepseek-v4-flash", [])).toBe("deepseek/deepseek-v4-flash");
  });
});
