import { describe, expect, it } from "vitest";

import { buildModelOption, buildPersonalModelOption, resolveModelDisplayName } from "./useModels";
import type { ModelInfo } from "@/types";
import type { ModelCredentialSummary } from "@/types/profile";

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

describe("buildPersonalModelOption", () => {
  it("uses the credential ID so duplicate providers stay selectable", () => {
    const credential: ModelCredentialSummary = {
      id: "cred-1",
      provider: "openai",
      model: "gpt-4.1",
      ref_hint: "***cret",
      display_name: "工作账号",
      enabled: true,
    };

    expect(buildPersonalModelOption(credential)).toEqual({
      value: "credential:cred-1",
      label: "工作账号 / gpt-4.1",
      group: "我的模型",
    });
  });
});
