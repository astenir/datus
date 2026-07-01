import { describe, expect, it } from "vitest";

import { filterSelectOptions } from "./select-options";
import type { SelectOption } from "@/types";

const options: SelectOption[] = [
  { value: "openai/gpt-4.1", label: "GPT 4.1" },
  { value: "custom/qwen-ebd", label: "qwen-ebd" },
  { value: "agent/sql", label: "SQL Analyst" },
];

describe("filterSelectOptions", () => {
  it("returns all options for an empty query", () => {
    expect(filterSelectOptions(options, "")).toEqual(options);
  });

  it("matches labels and values case-insensitively", () => {
    expect(filterSelectOptions(options, "qWEN")).toEqual([{ value: "custom/qwen-ebd", label: "qwen-ebd" }]);
    expect(filterSelectOptions(options, "SQL")).toEqual([{ value: "agent/sql", label: "SQL Analyst" }]);
  });
});
