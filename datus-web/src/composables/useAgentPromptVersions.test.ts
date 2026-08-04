import { beforeEach, describe, expect, it, vi } from "vitest";

const promptVersions = vi.fn();
const promptVersion = vi.fn();
const createPromptVersion = vi.fn();
const activatePromptVersion = vi.fn();

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function versionSummary(versionId: string, version: string, active: boolean) {
  return {
    version_id: versionId,
    version,
    prompt_language: "en",
    content_sha256: `${versionId}-sha256`,
    change_note: null,
    created_by: "alice",
    created_at: "2026-08-04T10:00:00Z",
    active,
    legacy: false,
  };
}

function versionDetail(versionId: string, version: string, active: boolean) {
  return {
    ...versionSummary(versionId, version, active),
    agent_id: "analyst",
    prompt_template: `prompt ${version}`,
    based_on_version_id: null,
  };
}

vi.mock("@/lib/api", () => ({
  agentApi: {
    promptVersions,
    promptVersion,
    createPromptVersion,
    activatePromptVersion,
  },
}));

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "http://api.test",
  }),
}));

describe("useAgentPromptVersions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    promptVersions.mockResolvedValue({
      active_version_id: "version-1",
      versions: [
        versionSummary("version-1", "1.0", true),
        versionSummary("version-2", "1.1", false),
      ],
    });
    promptVersion.mockImplementation((_baseUrl: string, _agentId: string, versionId: string) =>
      Promise.resolve(versionId === "version-1"
        ? versionDetail("version-1", "1.0", true)
        : versionDetail("version-2", "1.1", false))
    );
    createPromptVersion.mockResolvedValue(versionDetail("version-2", "1.1", false));
    activatePromptVersion.mockResolvedValue(versionDetail("version-2", "1.1", true));
  });

  it("loads the list and the active version detail", async () => {
    const { useAgentPromptVersions } = await import("./useAgentPromptVersions");
    const controller = useAgentPromptVersions();

    await controller.load("analyst");

    expect(controller.activeVersionId.value).toBe("version-1");
    expect(controller.selectedVersionId.value).toBe("version-1");
    expect(controller.selectedVersion.value?.prompt_template).toBe("prompt 1.0");
    expect(controller.activeVersion.value?.version_id).toBe("version-1");
  });

  it("keeps the latest selection when an older detail request finishes last", async () => {
    const first = deferred<ReturnType<typeof versionDetail>>();
    const second = deferred<ReturnType<typeof versionDetail>>();
    promptVersion.mockImplementation((_baseUrl: string, _agentId: string, versionId: string) =>
      versionId === "version-1" ? first.promise : second.promise
    );
    const { useAgentPromptVersions } = await import("./useAgentPromptVersions");
    const controller = useAgentPromptVersions();

    const firstSelection = controller.select("analyst", "version-1");
    const secondSelection = controller.select("analyst", "version-2");
    second.resolve(versionDetail("version-2", "1.1", false));
    await secondSelection;
    first.resolve(versionDetail("version-1", "1.0", true));
    await firstSelection;

    expect(controller.selectedVersionId.value).toBe("version-2");
    expect(controller.selectedVersion.value?.version_id).toBe("version-2");
  });

  it("selects a newly created version while retaining the active version for comparison", async () => {
    const { useAgentPromptVersions } = await import("./useAgentPromptVersions");
    const controller = useAgentPromptVersions();
    const input = {
      version: "1.1",
      prompt_template: "prompt 1.1",
      prompt_language: "en",
      change_note: "clarify policy",
      based_on_version_id: "version-1",
      activate: false,
    };

    const created = await controller.create("analyst", input);

    expect(createPromptVersion).toHaveBeenCalledWith("http://api.test", "analyst", input);
    expect(created?.version_id).toBe("version-2");
    expect(controller.selectedVersionId.value).toBe("version-2");
    expect(controller.activeVersion.value?.version_id).toBe("version-1");
  });

  it("activates with the expected active version id", async () => {
    const { useAgentPromptVersions } = await import("./useAgentPromptVersions");
    const controller = useAgentPromptVersions();
    await controller.load("analyst", "version-2");
    promptVersions.mockResolvedValueOnce({
      active_version_id: "version-2",
      versions: [
        versionSummary("version-1", "1.0", false),
        versionSummary("version-2", "1.1", true),
      ],
    });

    await controller.activate("analyst", "version-2");

    expect(activatePromptVersion).toHaveBeenCalledWith("http://api.test", "analyst", {
      version_id: "version-2",
      expected_active_version_id: "version-1",
    });
    expect(controller.activeVersionId.value).toBe("version-2");
  });

  it("preserves an activation conflict for the caller and visible error state", async () => {
    const conflict = new Error("409 AGENT_PROMPT_ACTIVE_VERSION_CONFLICT");
    activatePromptVersion.mockRejectedValue(conflict);
    const { useAgentPromptVersions } = await import("./useAgentPromptVersions");
    const controller = useAgentPromptVersions();

    await expect(controller.activate("analyst", "version-2")).rejects.toBe(conflict);

    expect(controller.error.value).toBe(conflict.message);
    expect(controller.activating.value).toBe(false);
  });

  it("discards a list response after reset", async () => {
    const pending = deferred<{
      active_version_id: string;
      versions: ReturnType<typeof versionSummary>[];
    }>();
    promptVersions.mockReturnValueOnce(pending.promise);
    const { useAgentPromptVersions } = await import("./useAgentPromptVersions");
    const controller = useAgentPromptVersions();

    const loading = controller.load("analyst");
    controller.reset();
    pending.resolve({
      active_version_id: "version-1",
      versions: [versionSummary("version-1", "1.0", true)],
    });
    await loading;

    expect(controller.versions.value).toEqual([]);
    expect(controller.selectedVersion.value).toBeNull();
  });
});
