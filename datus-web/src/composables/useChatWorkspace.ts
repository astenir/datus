import { computed, onBeforeUnmount, shallowRef, watch } from "vue";
import { toast } from "vue-sonner";

import { useCatalog } from "@/composables/useCatalog";
import { useChatSettings } from "@/composables/useChatSettings";
import { useChatState } from "@/composables/useChatState";
import { useConnection } from "@/composables/useConnection";
import { useModels } from "@/composables/useModels";
import { usePermission } from "@/composables/usePermission";
import { useTheme } from "@/composables/useTheme";
import { workspaceAccessFromPermission } from "@/features/workspace/access";
import { agentApi, meApi } from "@/lib/api";
import type { AgentInfo, ArtifactEditSession, NormalizedProbeResult, SelectOption } from "@/types";
import type { AgentPreferenceSummary, ApiResponse } from "@/types/profile";

const STATUS_REFRESH_DELAYS = [1500, 5000] as const;
const REPORT_EDIT_SESSION_PREFIX = "report_edit__";
const DASHBOARD_EDIT_SESSION_PREFIX = "dashboard_edit__";
const WILDCARD_DATASOURCE_GRANT = "*";

function mergeSelectOptions(...groups: readonly SelectOption[][]): SelectOption[] {
  const seen = new Set<string>();
  const options: SelectOption[] = [];
  for (const group of groups) {
    for (const option of group) {
      if (!option.value || seen.has(option.value)) continue;
      seen.add(option.value);
      options.push(option);
    }
  }
  return options;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function datasourceGrantAllowsCatalog(grant: unknown): boolean {
  if (grant === true) return true;
  if (!isRecord(grant)) return false;
  const effect = typeof grant.effect === "string" ? grant.effect.trim().toLowerCase() : "allow";
  return effect === "allow" && grant.allow_catalog !== false;
}

export function useChatWorkspace() {
  useTheme();

  const {
    language,
    permissionMode,
    planMode,
    setLanguage,
    setPermissionMode,
    setPlanMode,
  } = useChatSettings();
  const {
    apiBase,
    connection,
    config,
    datasourceOptions,
    isTestingDatasource: isTestingConfigDatasource,
    checkConnection,
    effectiveBase,
    setApiBase,
  } = useConnection();
  const permission = usePermission();
  const {
    messages,
    sessions,
    selectedSession,
    isStreaming,
    streamActivity,
    isLoadingSessions,
    activeInteractionKey,
    loadSessions,
    selectSession,
    sendMessage,
    insertMessage,
    stopSession,
    deleteSession,
    compactSession,
    resumeSession,
    sendInteraction,
    clearMessages,
    dispose,
  } = useChatState();
  const { modelOptions, defaultModelLabel, isLoadingModels, loadModels } = useModels();
  const {
    catalogEntries,
    databaseOptions,
    database,
    schema,
    schemaOptions,
    isLoadingCatalog,
    datasourceStatuses,
    prewarmingDatasources,
    selectCatalogDatasource,
    hasCatalogSnapshot,
    loadCatalog,
    loadDatasourceStatuses,
    prewarmDatasource,
    setDatabase,
    setSchema,
  } = useCatalog();

  const availableAgents = shallowRef<AgentInfo[]>([]);
  const isLoadingAgents = shallowRef(false);
  const artifactEditSession = shallowRef<ArtifactEditSession | null>(null);
  const agentOptions = computed<SelectOption[]>(() => [
    ...availableAgents.value
      .filter((agent) => agent.agent_id !== "chat" && agent.status === "published")
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
  const selectedAgent = shallowRef("");
  const defaultAgentId = shallowRef("");
  const isSavingDefaultAgent = shallowRef(false);
  const selectedModel = shallowRef("");
  const selectedDatasource = shallowRef("");
  const isTestingCatalogDatasource = shallowRef(false);
  const grantedDatasourceOptions = computed<SelectOption[]>(() =>
    (permission.permissions?.value?.datasources ?? [])
      .filter((name) => name !== WILDCARD_DATASOURCE_GRANT)
      .map((name) => ({ value: name, label: name }))
  );
  const statusDatasourceOptions = computed<SelectOption[]>(() =>
    Object.keys(datasourceStatuses.value).map((name) => ({ value: name, label: name }))
  );
  const availableDatasourceOptions = computed(() =>
    datasourceOptions.value.length > 0
      ? datasourceOptions.value
      : mergeSelectOptions(grantedDatasourceOptions.value, statusDatasourceOptions.value)
  );

  watch(modelOptions, (options) => {
    if (!selectedModel.value.startsWith("credential:")) return;
    if (!options.some(option => option.value === selectedModel.value)) {
      selectedModel.value = "";
    }
  });
  const viewAccess = computed(() => workspaceAccessFromPermission(permission));
  const canUseElevatedPermissionMode = computed(() =>
    permission.isAdmin() || permission.hasPermission?.("module.chat.permission_mode") === true
  );
  const isPermissionSummaryLoaded = computed(() => permission.isLoaded?.value ?? true);
  const visibleDatasourceOptions = computed(() =>
    availableDatasourceOptions.value.filter((option) => permission.hasDatasourcePermission(option.value))
  );
  const defaultDatasource = computed(() => {
    const configuredDatasource = config.value?.current_datasource?.trim() ?? "";
    if (visibleDatasourceOptions.value.some((option) => option.value === configuredDatasource)) {
      return configuredDatasource;
    }
    return visibleDatasourceOptions.value[0]?.value ?? "";
  });
  const currentDatasource = computed(() => {
    const selected = selectedDatasource.value.trim();
    if (visibleDatasourceOptions.value.some((option) => option.value === selected)) {
      return selected;
    }
    return defaultDatasource.value;
  });
  const catalogDatasourceOptions = computed(() =>
    visibleDatasourceOptions.value.filter((option) => canBrowseDatasourceCatalog(option.value))
  );
  const hasCatalogBrowseGrant = computed(() =>
    catalogDatasourceOptions.value.length > 0 || hasWildcardCatalogGrant()
  );
  const canUseDatasourceCatalogSupport = computed(() =>
    permission.hasPermission("module.datasource_catalog")
    || permission.hasFeaturePermission("datasource_catalog")
  );
  const canAccessDatasourceCatalog = computed(() =>
    viewAccess.value.canViewKnowledge
    || canUseDatasourceCatalogSupport.value
    || (viewAccess.value.canViewChat && hasCatalogBrowseGrant.value)
  );
  const canReadAgentConfig = computed(() =>
    viewAccess.value.canViewConfiguration
  );
  const canReadModelOptions = computed(() =>
    viewAccess.value.canViewChat || canReadAgentConfig.value
  );
  const isTestingDatasource = computed(() =>
    isTestingConfigDatasource.value || isTestingCatalogDatasource.value
  );
  const initialized = shallowRef(false);
  const currentDatasourceStatus = computed(() => {
    const datasource = currentDatasource.value.trim();
    return datasource ? (datasourceStatuses.value[datasource] ?? null) : null;
  });
  const isPrewarmingCurrentDatasource = computed(() => {
    const datasource = currentDatasource.value.trim();
    return Boolean(datasource && prewarmingDatasources.value.has(datasource));
  });
  let initializePromise: Promise<void> | null = null;
  const statusRefreshTimers = new Set<ReturnType<typeof setTimeout>>();

  function clearStatusRefreshTimers() {
    for (const timer of statusRefreshTimers) {
      clearTimeout(timer);
    }
    statusRefreshTimers.clear();
  }

  function scheduleDatasourceStatusRefresh(datasource: string) {
    for (const delay of STATUS_REFRESH_DELAYS) {
      const timer = setTimeout(() => {
        statusRefreshTimers.delete(timer);
        void loadAuthorizedDatasourceStatuses(datasource);
      }, delay);
      statusRefreshTimers.add(timer);
    }
  }

  function canQueryDatasourceCatalog(datasource?: string) {
    if (!canAccessDatasourceCatalog.value) return false;
    const datasourceName = datasource?.trim();
    if (!datasourceName) {
      return hasCatalogBrowseGrant.value;
    }
    return canUseDatasource(datasourceName) && (
      canBrowseDatasourceCatalog(datasourceName)
      || hasWildcardCatalogGrant()
    );
  }

  function loadAuthorizedDatasourceStatuses(datasource?: string) {
    if (!canQueryDatasourceCatalog(datasource)) {
      return false;
    }
    void loadDatasourceStatuses(datasource);
    return true;
  }

  function warmDatasource(datasource: string) {
    const datasourceName = datasource.trim();
    if (!datasourceName || !canQueryDatasourceCatalog(datasourceName)) return;
    void loadDatasourceStatuses(datasourceName);
    void prewarmDatasource(datasourceName).then((started) => {
      if (started) {
        scheduleDatasourceStatusRefresh(datasourceName);
      }
    });
  }

  function handleSend(message: string) {
    void sendMessage({
      message,
      selectedAgent: selectedAgent.value,
      model: selectedModel.value,
      datasource: currentDatasource.value,
      database: database.value,
      schema: schema.value,
    });
  }

  function handleInsert(message: string) {
    void insertMessage(message);
  }

  function artifactKindLabel(session: ArtifactEditSession) {
    return session.artifact_type === "dashboard" ? "仪表盘" : "报表";
  }

  function isArtifactEditAgent(agentId: string) {
    return agentId.startsWith(REPORT_EDIT_SESSION_PREFIX) || agentId.startsWith(DASHBOARD_EDIT_SESSION_PREFIX);
  }

  function startArtifactEditSession(session: ArtifactEditSession) {
    artifactEditSession.value = session;
    selectedAgent.value = session.subagent_id;
    selectSession(null);
  }

  function startReportEditSession(session: ArtifactEditSession) {
    startArtifactEditSession(session);
  }

  function startNewSession() {
    artifactEditSession.value = null;
    selectedAgent.value = defaultAgentId.value;
    clearMessages();
    selectSession(null);
  }

  function handleRefreshConnection() {
    if (!canReadAgentConfig.value) return;
    void checkConnection();
  }

  function handleDatasourceSwitched() {
    selectedDatasource.value = defaultDatasource.value;
    selectCatalogDatasource(currentDatasource.value);
    warmDatasource(currentDatasource.value);
  }

  async function handleDatasourceTest(name?: string): Promise<NormalizedProbeResult> {
    const datasourceName = (name?.trim() || currentDatasource.value.trim());
    if (!datasourceName) {
      return { ok: false, message: "当前数据源未选择" };
    }
    if (!canAccessDatasourceCatalog.value) {
      return { ok: false, message: "当前用户无权访问数据源目录" };
    }
    if (!canUseDatasource(datasourceName)) {
      return { ok: false, message: "当前用户无权访问该数据源" };
    }

    isTestingCatalogDatasource.value = true;
    try {
      const ok = await loadCatalog(undefined, datasourceName);
      await loadDatasourceStatuses(datasourceName);
      if (ok) {
        return { ok: true, message: "连接正常" };
      }
      const status = datasourceStatuses.value[datasourceName];
      return {
        ok: false,
        message: status?.error_message || "连接失败，请确认权限或数据源配置",
      };
    } finally {
      isTestingCatalogDatasource.value = false;
    }
  }

  function refreshCatalog(databaseName?: string) {
    if (!canQueryDatasourceCatalog(currentDatasource.value)) {
      return Promise.resolve(false);
    }
    return loadCatalog(databaseName, currentDatasource.value);
  }

  function ensureCatalogLoaded() {
    if (isLoadingCatalog.value || hasCatalogSnapshot(currentDatasource.value)) {
      return Promise.resolve(true);
    }
    return refreshCatalog();
  }

  function canUseDatasource(name: string) {
    const datasourceName = name.trim();
    return visibleDatasourceOptions.value.some((option) => option.value === datasourceName);
  }

  function hasWildcardCatalogGrant() {
    const grants = permission.permissions?.value?.datasource_grants ?? {};
    return datasourceGrantAllowsCatalog(grants[WILDCARD_DATASOURCE_GRANT]);
  }

  function canBrowseDatasourceCatalog(name: string) {
    const datasourceName = name.trim();
    if (!datasourceName) return false;
    const grants = permission.permissions?.value?.datasource_grants ?? {};
    return datasourceGrantAllowsCatalog(grants[datasourceName]);
  }

  async function handleDatasourceSwitch(name: string): Promise<boolean> {
    const datasourceName = name.trim();
    if (!datasourceName || !canUseDatasource(datasourceName)) return false;
    if (datasourceName === currentDatasource.value) return true;

    selectedDatasource.value = datasourceName;
    selectCatalogDatasource(datasourceName);
    if (canQueryDatasourceCatalog(datasourceName)) {
      warmDatasource(datasourceName);
      void loadCatalog(undefined, datasourceName);
    }
    return true;
  }

  async function loadAgentOptions(): Promise<boolean> {
    isLoadingAgents.value = true;
    try {
      const loadedAgents = await agentApi.availableList(effectiveBase());
      availableAgents.value = loadedAgents ?? [];
      if (selectedAgent.value && !isArtifactEditAgent(selectedAgent.value) && !agentOptions.value.some((option) => option.value === selectedAgent.value)) {
        selectedAgent.value = "";
      }
      if (defaultAgentId.value && !agentOptions.value.some((option) => option.value === defaultAgentId.value)) {
        if (selectedAgent.value === defaultAgentId.value) {
          selectedAgent.value = "";
        }
        defaultAgentId.value = "";
      }
      return true;
    } catch (error) {
      console.error("Failed to load chat agent options:", error);
      availableAgents.value = [];
      if (!isArtifactEditAgent(selectedAgent.value)) {
        selectedAgent.value = "";
      }
      return false;
    } finally {
      isLoadingAgents.value = false;
    }
  }

  function preferenceData(response: ApiResponse<AgentPreferenceSummary>): AgentPreferenceSummary {
    if (!response.success) {
      throw new Error(response.errorMessage || response.errorCode || "Agent 偏好请求失败");
    }
    return response.data ?? {};
  }

  async function loadAgentPreference(): Promise<boolean> {
    try {
      const preference = preferenceData(await meApi.agentPreference());
      const preferredAgent = preference.default_agent_id?.trim() ?? "";
      defaultAgentId.value = agentOptions.value.some((option) => option.value === preferredAgent)
        ? preferredAgent
        : "";
      if (!selectedAgent.value) {
        selectedAgent.value = defaultAgentId.value;
      }
      return true;
    } catch (error) {
      console.error("Failed to load default Agent preference:", error);
      defaultAgentId.value = "";
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
      const savedAgentId = preference.default_agent_id?.trim() ?? "";
      defaultAgentId.value = savedAgentId;
      selectedAgent.value = savedAgentId;
      toast.success(savedAgentId ? "已设为我的默认 Agent" : "已恢复系统默认 Agent");
      return true;
    } catch (error) {
      console.error("Failed to update default Agent preference:", error);
      toast.error(error instanceof Error ? error.message : "默认 Agent 设置失败");
      return false;
    } finally {
      isSavingDefaultAgent.value = false;
    }
  }

  async function initialize() {
    if (initialized.value) return;
    if (initializePromise) return initializePromise;

    initializePromise = (async () => {
      if (canReadAgentConfig.value) {
        await checkConnection();
      }
      selectedDatasource.value = defaultDatasource.value;
      selectCatalogDatasource(currentDatasource.value);
      const startupTasks: Promise<unknown>[] = [];
      if (viewAccess.value.canViewChat) {
        startupTasks.push(loadSessions(), loadAgentOptions().then(() => loadAgentPreference()));
      }
      if (canReadModelOptions.value) {
        startupTasks.push(loadModels());
      }
      await Promise.all(startupTasks);
      loadAuthorizedDatasourceStatuses();
      warmDatasource(currentDatasource.value);
      initialized.value = true;
    })();

    try {
      await initializePromise;
    } finally {
      initializePromise = null;
    }
  }

  onBeforeUnmount(() => {
    clearStatusRefreshTimers();
    dispose();
  });

  watch(database, (db) => {
    if (db && canQueryDatasourceCatalog(currentDatasource.value)) {
      void loadCatalog(db, currentDatasource.value);
    }
  });

  watch([isPermissionSummaryLoaded, canUseElevatedPermissionMode, permissionMode], ([loaded, canUseElevated, mode]) => {
    if (loaded && !canUseElevated && mode !== "normal") {
      setPermissionMode("normal");
    }
  }, { immediate: true });

  return {
    language,
    permissionMode,
    planMode,
    canUseElevatedPermissionMode,
    apiBase,
    connection,
    config,
    datasourceOptions,
    visibleDatasourceOptions,
    currentDatasource,
    isTestingDatasource,
    setApiBase,
    messages,
    sessions,
    selectedSession,
    isStreaming,
    streamActivity,
    isLoadingSessions,
    isLoadingAgents,
    isSavingDefaultAgent,
    activeInteractionKey,
    selectSession,
    stopSession,
    deleteSession,
    compactSession,
    resumeSession,
    sendInteraction,
    clearMessages,
    agentOptions,
    modelOptions,
    defaultModelLabel,
    isLoadingModels,
    databaseOptions,
    catalogEntries,
    schemaOptions,
    isLoadingCatalog,
    datasourceStatuses,
    currentDatasourceStatus,
    isPrewarmingCurrentDatasource,
    loadSessions,
    loadAgentOptions,
    loadAgentPreference,
    loadCatalog: refreshCatalog,
    ensureCatalogLoaded,
    loadDatasourceStatuses,
    prewarmDatasource,
    selectedAgent,
    defaultAgentId,
    selectedModel,
    database,
    schema,
    handleSend,
    handleInsert,
    startArtifactEditSession,
    startReportEditSession,
    startNewSession,
    handleRefreshConnection,
    handleDatasourceSwitched,
    handleDatasourceTest,
    handleDatasourceSwitch,
    setDefaultAgent,
    canUseDatasource,
    setLanguage,
    setPermissionMode,
    setPlanMode,
    setDatabase,
    setSchema,
    initialize,
  };
}

export type ChatWorkspace = ReturnType<typeof useChatWorkspace>;
