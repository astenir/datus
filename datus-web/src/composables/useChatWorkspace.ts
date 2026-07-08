import { computed, onBeforeUnmount, shallowRef, watch } from "vue";

import { useCatalog } from "@/composables/useCatalog";
import { useChatSettings } from "@/composables/useChatSettings";
import { useChatState } from "@/composables/useChatState";
import { useConnection } from "@/composables/useConnection";
import { useModels } from "@/composables/useModels";
import { usePermission } from "@/composables/usePermission";
import { useTheme } from "@/composables/useTheme";
import { agentApi } from "@/lib/api";
import type { AgentInfo, ArtifactEditSession, NormalizedProbeResult, SelectOption } from "@/types";

const STATUS_REFRESH_DELAYS = [1500, 5000] as const;
const REPORT_EDIT_SESSION_PREFIX = "report_edit__";
const DASHBOARD_EDIT_SESSION_PREFIX = "dashboard_edit__";

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
  const selectedModel = shallowRef("");
  const selectedDatasource = shallowRef("");
  const isTestingCatalogDatasource = shallowRef(false);
  const defaultDatasource = computed(() => config.value?.current_datasource?.trim() ?? "");
  const currentDatasource = computed(() => selectedDatasource.value || defaultDatasource.value);
  const visibleDatasourceOptions = computed(() =>
    datasourceOptions.value.filter((option) => permission.hasDatasourcePermission(option.value))
  );
  const canAccessDatasourceCatalog = computed(() =>
    permission.isAdmin() || permission.hasFeaturePermission("datasource_catalog")
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
      return visibleDatasourceOptions.value.length > 0;
    }
    return canUseDatasource(datasourceName);
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
    sendMessage({
      message,
      selectedAgent: selectedAgent.value,
      model: selectedModel.value,
      datasource: currentDatasource.value,
      database: database.value,
      schema: schema.value,
    });
  }

  function handleInsert(message: string) {
    insertMessage(message);
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

  function handleRefreshConnection() {
    checkConnection();
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

  async function initialize() {
    if (initialized.value) return;
    if (initializePromise) return initializePromise;

    initializePromise = (async () => {
      await checkConnection();
      selectedDatasource.value = defaultDatasource.value;
      selectCatalogDatasource(currentDatasource.value);
      await Promise.all([
        loadSessions(),
        loadModels(),
        loadAgentOptions(),
      ]);
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
      loadCatalog(db, currentDatasource.value);
    }
  });

  return {
    language,
    permissionMode,
    planMode,
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
    isLoadingSessions,
    isLoadingAgents,
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
    loadCatalog: refreshCatalog,
    ensureCatalogLoaded,
    loadDatasourceStatuses,
    prewarmDatasource,
    selectedAgent,
    selectedModel,
    database,
    schema,
    handleSend,
    handleInsert,
    startArtifactEditSession,
    startReportEditSession,
    handleRefreshConnection,
    handleDatasourceSwitched,
    handleDatasourceTest,
    handleDatasourceSwitch,
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
