import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import { describe, expect, it } from "vitest";

import AgentPromptVersionControl from "./AgentPromptVersionControl.vue";

function props(overrides: Record<string, unknown> = {}) {
  return {
    versions: [],
    activeVersionId: null,
    selectedVersionId: null,
    selectedVersion: null,
    activeVersion: null,
    loading: false,
    detailLoading: false,
    creating: false,
    activating: false,
    error: null,
    promptSource: "builtin_fallback",
    basePromptContent: "Builtin fallback prompt body",
    basePromptLanguage: "en",
    basePromptVersion: "1.2",
    basePromptRevision: "1234567890abcdef",
    ...overrides,
  };
}

function buttonMarkup(html: string, label: string): string {
  return html.match(/<button\b[^>]*>[\s\S]*?<\/button>/g)?.find(button => button.includes(label)) ?? "";
}

function isDisabledButton(markup: string): boolean {
  return /\sdisabled(?:\s|>)/.test(markup);
}

describe("AgentPromptVersionControl", () => {
  it("allows creating the first enterprise version from a builtin fallback prompt", async () => {
    const html = await renderToString(createSSRApp(AgentPromptVersionControl, props()));

    expect(html).toContain("内置回退");
    expect(html).toContain("生效 v1.2");
    expect(html).toContain("rev 12345678");
    expect(isDisabledButton(buttonMarkup(html, "新建版本"))).toBe(false);
  });

  it("identifies a fallback that comes from the configured user template directory", async () => {
    const html = await renderToString(createSSRApp(AgentPromptVersionControl, props({
      promptSource: "user_override_fallback",
    })));

    expect(html).toContain("用户模板覆盖回退");
  });

  it("disables first-version creation when no persisted or fallback prompt exists", async () => {
    const html = await renderToString(createSSRApp(AgentPromptVersionControl, props({
      promptSource: "enterprise",
      basePromptContent: "",
      basePromptVersion: null,
      basePromptRevision: null,
    })));

    expect(isDisabledButton(buttonMarkup(html, "新建版本"))).toBe(true);
  });

  it("renders version metadata without exposing the selected prompt body in the list controls", async () => {
    const html = await renderToString(createSSRApp(AgentPromptVersionControl, props({
      versions: [{
        version_id: "version-2",
        version: "2.0",
        content_sha256: "abcdef1234567890",
        change_note: "Tighten constraints",
        based_on_version_id: "version-1",
        created_by: "alice",
        created_at: "2026-08-04T10:00:00Z",
        active: false,
      }],
      activeVersionId: "version-1",
      selectedVersionId: "version-2",
      selectedVersion: {
        version_id: "version-2",
        version: "2.0",
        content_sha256: "abcdef1234567890",
        change_note: "Tighten constraints",
        based_on_version_id: "version-1",
        created_by: "alice",
        created_at: "2026-08-04T10:00:00Z",
        active: false,
        prompt_template: "SECRET PROMPT BODY",
        prompt_language: "en",
      },
    })));

    expect(html).toContain("预览 v2.0");
    expect(html).toContain("说明：Tighten constraints");
    expect(html).not.toContain("SECRET PROMPT BODY");
  });
});
