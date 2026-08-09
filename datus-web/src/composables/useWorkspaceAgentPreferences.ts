import { computed, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { agentAllowsPersonalMcpSelection } from "@/lib/chat";
import { agentApi, meApi } from "@/lib/api";
import type { AgentInfo, ArtifactEditSession, SelectOption } from "@/types";
import type { AgentPreferenceSummary, ApiResponse } from "@/types/profile";

const REPORT_EDIT_SESSION_PREFIX = "report_edit__";
const DASHBOARD_EDIT_SESSION_PREFIX = "dashboard_edit__";

interface UseWorkspaceAgentPreferencesOptions {
  effectiveBase: () => string;
  selectSession: (sessionId: string | null) => void;
  resetPersonalMcpSelection: () => void;
}

export function useWorkspaceAgentPreferences(options: UseWorkspaceAgentPreferencesOptions) {
  const availableAgents = shallowRef<AgentInfo[]>([]);
  const isLoadingAgents = shallowRef(false);
  const artifactEditSession = shallowRef<ArtifactEditSession | null>(null);
  const selectedAgent = shallowRef("");
  const defaultAgentId = shallowRef("");
  const userDefaultAgentId = shallowRef("");
  const isSavingDefaultAgent = shallowRef(false);
  let agentOptionsPromise: Promise<boolean> | null = null;

  const agentOptions = computed<SelectOption[]>(() => [
    ...availableAgents.value
      .filter((agent) => agent.status === "published")
      .map((agent) => ({
        value: agent.agent_id,
        label: agent.name || agent.agent_id,
      }))
      .sort((left, right) => left.label.localeCompare(right.label) || left.value.localeCompare(right.value)),
    ...(artifactEditSession.value
      ? [
        {
          value: artifactEditSession.value.subagent_id,
          label: `编辑${artifactKindLabel(artifactEditSession.value)}：${artifactEditSession.value.artifact_slug}`,
        },
      ]
      : []),
  ]);
  const effectiveAgentId = computed(() => selectedAgent.value.trim() || defaultAgentId.value.trim());
  const agentAllowsPersonalMcp = computed(() =>
    agentAllowsPersonalMcpSelection(
      availableAgents.value,
      selectedAgent.value,
      defaultAgentId.value,
      artifactEditSession.value !== null,
    )
  );

  function artifactKindLabel(session: ArtifactEditSession) {
    return session.artifact_type === "dashboard" ? "仪表盘" : "报表";
  }

  function isArtifactEditAgent(agentId: string) {
    return agentId.startsWith(REPORT_EDIT_SESSION_PREFIX) || agentId.startsWith(DASHBOARD_EDIT_SESSION_PREFIX);
  }

  function startArtifactEditSession(session: ArtifactEditSession) {
    artifactEditSession.value = session;
    selectedAgent.value = session.subagent_id;
    options.selectSession(null);
    options.resetPersonalMcpSelection();
  }

  function startReportEditSession(session: ArtifactEditSession) {
    startArtifactEditSession(session);
  }

  function startNewSession() {
    artifactEditSession.value = null;
    selectedAgent.value = "";
    options.selectSession(null);
    options.resetPersonalMcpSelection();
  }

  function loadAgentOptions(): Promise<boolean> {
    if (agentOptionsPromise) return agentOptionsPromise;

    isLoadingAgents.value = true;
    agentOptionsPromise = (async () => {
      try {
        const loadedAgents = await agentApi.availableList(options.effectiveBase());
        availableAgents.value = loadedAgents ?? [];
        if (selectedAgent.value && !isArtifactEditAgent(selectedAgent.value) && !agentOptions.value.some((option) => option.value === selectedAgent.value)) {
          selectedAgent.value = "";
        }
        if (defaultAgentId.value && !agentOptions.value.some((option) => option.value === defaultAgentId.value)) {
          defaultAgentId.value = "";
        }
        if (userDefaultAgentId.value && !agentOptions.value.some((option) => option.value === userDefaultAgentId.value)) {
          userDefaultAgentId.value = "";
        }
        return true;
      } catch (error) {
        console.error("Failed to load chat agent options:", error);
        return false;
      } finally {
        isLoadingAgents.value = false;
        agentOptionsPromise = null;
      }
    })();
    return agentOptionsPromise;
  }

  function preferenceData(response: ApiResponse<AgentPreferenceSummary>): AgentPreferenceSummary {
    if (!response.success) {
      throw new Error(response.errorMessage || response.errorCode || "Agent 偏好请求失败");
    }
    return response.data ?? { source: "none" };
  }

  function availableAgentId(agentId: string | null | undefined): string {
    const normalizedAgentId = agentId?.trim() ?? "";
    return agentOptions.value.some((option) => option.value === normalizedAgentId)
      ? normalizedAgentId
      : "";
  }

  function applyAgentPreference(preference: AgentPreferenceSummary) {
    defaultAgentId.value = availableAgentId(preference.default_agent_id);
    userDefaultAgentId.value = availableAgentId(preference.user_default_agent_id);
  }

  async function loadAgentPreference(): Promise<boolean> {
    try {
      const preference = preferenceData(await meApi.agentPreference());
      applyAgentPreference(preference);
      return true;
    } catch (error) {
      console.error("Failed to load default Agent preference:", error);
      defaultAgentId.value = "";
      userDefaultAgentId.value = "";
      return false;
    }
  }

  async function setDefaultAgent(agentId: string): Promise<boolean> {
    const normalizedAgentId = agentId.trim();
    if (normalizedAgentId && !agentOptions.value.some((option) => option.value === normalizedAgentId)) {
      toast.error("当前 Agent 不可用，无法设为默认");
      return false;
    }

    isSavingDefaultAgent.value = true;
    try {
      const preference = preferenceData(await meApi.updateAgentPreference({
        default_agent_id: normalizedAgentId || null,
      }));
      applyAgentPreference(preference);
      selectedAgent.value = normalizedAgentId;
      if (normalizedAgentId) {
        toast.success("已设为我的默认 Agent");
      } else {
        const effectiveDefaultLabel = agentOptions.value.find(
          (option) => option.value === defaultAgentId.value,
        )?.label ?? defaultAgentId.value;
        toast.success(
          effectiveDefaultLabel
            ? `已清除我的默认设置，当前跟随 ${effectiveDefaultLabel}`
            : "已清除我的默认设置",
        );
      }
      return true;
    } catch (error) {
      console.error("Failed to update default Agent preference:", error);
      toast.error("默认 Agent 设置失败");
      return false;
    } finally {
      isSavingDefaultAgent.value = false;
    }
  }

  return {
    isLoadingAgents,
    isSavingDefaultAgent,
    agentAllowsPersonalMcp,
    effectiveAgentId,
    agentOptions,
    selectedAgent,
    defaultAgentId,
    userDefaultAgentId,
    loadAgentOptions,
    loadAgentPreference,
    startArtifactEditSession,
    startReportEditSession,
    startNewSession,
    setDefaultAgent,
  };
}
