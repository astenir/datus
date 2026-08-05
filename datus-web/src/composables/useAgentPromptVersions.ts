import { readonly, ref, shallowRef } from "vue";

import { useConnection } from "@/composables/useConnection";
import { agentApi } from "@/lib/api";
import type {
  AgentPromptVersionDetail,
  AgentPromptVersionSummary,
  CreateAgentPromptVersionInput,
} from "@/types";

export function useAgentPromptVersions() {
  const connection = useConnection();
  const versions = ref<AgentPromptVersionSummary[]>([]);
  const activeVersionId = shallowRef<string | null>(null);
  const selectedVersionId = shallowRef<string | null>(null);
  const selectedVersion = ref<AgentPromptVersionDetail | null>(null);
  const activeVersion = ref<AgentPromptVersionDetail | null>(null);
  const loading = shallowRef(false);
  const detailLoading = shallowRef(false);
  const creating = shallowRef(false);
  const activating = shallowRef(false);
  const error = shallowRef<string | null>(null);
  let listRequestId = 0;
  let detailRequestId = 0;
  let activeDetailRequestId = 0;
  let actionRequestId = 0;

  function reset() {
    listRequestId += 1;
    detailRequestId += 1;
    activeDetailRequestId += 1;
    actionRequestId += 1;
    versions.value = [];
    activeVersionId.value = null;
    selectedVersionId.value = null;
    selectedVersion.value = null;
    activeVersion.value = null;
    loading.value = false;
    detailLoading.value = false;
    creating.value = false;
    activating.value = false;
    error.value = null;
  }

  async function select(agentId: string, versionId: string | null): Promise<AgentPromptVersionDetail | null> {
    const currentRequestId = ++detailRequestId;
    selectedVersionId.value = versionId;
    selectedVersion.value = null;
    error.value = null;
    if (!versionId) {
      detailLoading.value = false;
      return null;
    }
    detailLoading.value = true;
    try {
      const detail = await agentApi.promptVersion(connection.effectiveBase(), agentId, versionId);
      if (currentRequestId !== detailRequestId) return null;
      selectedVersion.value = detail;
      if (versionId === activeVersionId.value) activeVersion.value = detail;
      return detail;
    } catch (cause) {
      if (currentRequestId !== detailRequestId) return null;
      error.value = cause instanceof Error ? cause.message : "读取提示词版本失败";
      throw cause;
    } finally {
      if (currentRequestId === detailRequestId) detailLoading.value = false;
    }
  }

  async function loadActiveDetail(agentId: string, versionId: string | null) {
    const currentRequestId = ++activeDetailRequestId;
    activeVersion.value = null;
    if (!versionId) return;
    try {
      const detail = await agentApi.promptVersion(connection.effectiveBase(), agentId, versionId);
      if (currentRequestId === activeDetailRequestId) activeVersion.value = detail;
    } catch (cause) {
      if (currentRequestId !== activeDetailRequestId) return;
      error.value = cause instanceof Error ? cause.message : "读取当前提示词版本失败";
      throw cause;
    }
  }

  async function load(agentId: string, preferredVersionId?: string | null) {
    const currentRequestId = ++listRequestId;
    detailRequestId += 1;
    activeDetailRequestId += 1;
    loading.value = true;
    error.value = null;
    versions.value = [];
    activeVersionId.value = null;
    selectedVersionId.value = null;
    selectedVersion.value = null;
    activeVersion.value = null;
    let nextSelectedVersionId: string | null;
    let nextActiveVersionId: string | null;
    try {
      const collection = await agentApi.promptVersions(connection.effectiveBase(), agentId);
      if (currentRequestId !== listRequestId) return;
      versions.value = collection?.versions ?? [];
      activeVersionId.value = collection?.active_version_id ?? null;
      nextActiveVersionId = activeVersionId.value;
      nextSelectedVersionId = preferredVersionId
        && versions.value.some(version => version.version_id === preferredVersionId)
        ? preferredVersionId
        : activeVersionId.value ?? versions.value[0]?.version_id ?? null;
    } catch (cause) {
      if (currentRequestId !== listRequestId) return;
      error.value = cause instanceof Error ? cause.message : "读取提示词版本列表失败";
      throw cause;
    } finally {
      if (currentRequestId === listRequestId) loading.value = false;
    }
    if (currentRequestId !== listRequestId) return;

    const selectedPromise = select(agentId, nextSelectedVersionId);
    if (!nextActiveVersionId || nextActiveVersionId === nextSelectedVersionId) {
      await selectedPromise;
      return;
    }
    await Promise.all([
      selectedPromise,
      loadActiveDetail(agentId, nextActiveVersionId),
    ]);
  }

  async function create(
    agentId: string,
    input: CreateAgentPromptVersionInput,
  ): Promise<AgentPromptVersionDetail | null> {
    const currentRequestId = ++actionRequestId;
    creating.value = true;
    error.value = null;
    try {
      const created = await agentApi.createPromptVersion(connection.effectiveBase(), agentId, input);
      if (currentRequestId !== actionRequestId || !created) return null;
      await load(agentId, created.version_id);
      if (currentRequestId !== actionRequestId) return null;
      return selectedVersion.value;
    } catch (cause) {
      if (currentRequestId !== actionRequestId) return null;
      error.value = cause instanceof Error ? cause.message : "创建提示词版本失败";
      throw cause;
    } finally {
      if (currentRequestId === actionRequestId) creating.value = false;
    }
  }

  async function activate(agentId: string, versionId: string): Promise<AgentPromptVersionDetail | null> {
    const currentRequestId = ++actionRequestId;
    activating.value = true;
    error.value = null;
    try {
      const activated = await agentApi.activatePromptVersion(connection.effectiveBase(), agentId, {
        version_id: versionId,
        expected_active_version_id: activeVersionId.value,
      });
      if (currentRequestId !== actionRequestId || !activated) return null;
      await load(agentId, activated.version_id);
      if (currentRequestId !== actionRequestId) return null;
      return selectedVersion.value;
    } catch (cause) {
      if (currentRequestId !== actionRequestId) return null;
      error.value = cause instanceof Error ? cause.message : "激活提示词版本失败";
      throw cause;
    } finally {
      if (currentRequestId === actionRequestId) activating.value = false;
    }
  }

  return {
    versions: readonly(versions),
    activeVersionId: readonly(activeVersionId),
    selectedVersionId: readonly(selectedVersionId),
    selectedVersion: readonly(selectedVersion),
    activeVersion: readonly(activeVersion),
    loading: readonly(loading),
    detailLoading: readonly(detailLoading),
    creating: readonly(creating),
    activating: readonly(activating),
    error: readonly(error),
    reset,
    load,
    select,
    create,
    activate,
  };
}

export type AgentPromptVersionsController = ReturnType<typeof useAgentPromptVersions>;
