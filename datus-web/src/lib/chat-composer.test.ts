import { describe, expect, it } from "vitest";

import { shouldSubmitChatComposer } from "./chat-composer";

function key(overrides: Partial<Pick<KeyboardEvent, "key" | "shiftKey" | "ctrlKey" | "metaKey" | "altKey" | "isComposing">>): KeyboardEvent {
  return overrides as KeyboardEvent;
}

describe("shouldSubmitChatComposer", () => {
  it("submits on plain Enter", () => {
    expect(shouldSubmitChatComposer(key({ key: "Enter" }))).toBe(true);
  });

  it("keeps Shift+Enter available for new lines", () => {
    expect(shouldSubmitChatComposer(key({ key: "Enter", shiftKey: true }))).toBe(false);
  });

  it("keeps Ctrl/Cmd+Enter as submit shortcuts", () => {
    expect(shouldSubmitChatComposer(key({ key: "Enter", ctrlKey: true }))).toBe(true);
    expect(shouldSubmitChatComposer(key({ key: "Enter", metaKey: true }))).toBe(true);
  });
});
