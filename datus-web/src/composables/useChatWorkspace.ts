import { computed, shallowRef } from "vue";

import { useCatalog } from "@/composables/useCatalog";
import { useChatSettings } from "@/composables/useChatSettings";
import { useChatState } from "@/composables/useChatState";
import { useConnection } from "@/composables/useConnection";
import { useModels } from "@/composables/useModels";
import { usePermission } from "@/composables/usePermission";
import { usePersonalMcp } from "@/composables/usePersonalMcp";
import { useWorkspaceAgentPreferences } from "@/composables/useWorkspaceAgentPreferences";
import { useWorkspaceDatasourceContext } from "@/composables/useWorkspaceDatasourceContext";
import { useWorkspaceLifecycle } from "@/composables/useWorkspaceLifecycle";
import { useTheme } from "@/composables/useTheme";
import { workspaceAccessFromPermission } from "@/features/workspace/access";
import { personalMcpIdsForChat } from "@/lib/chat";

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
  const connectionContext = useConnection();
  const {
    apiBase,
    connection,
    config,
    datasourceOptions,
    isTestingDatasource: isTestingConfigDatasource,
    checkConnection,
    setApiBase,
  } = connectionContext;
  const permission = usePermission();
  const personalMcp = usePersonalMcp();
  const chatState = useChatState();
  const {
    messages,
    sessions,
    selectedSession,
    isStreaming,
    isInsertReady,
    isStopping,
    streamActivity,
    transportError,
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
    clearTransportError,
    dispose,
  } = chatState;
  const { modelOptions, defaultModelLabel, isLoadingModels, loadModels } = useModels();
  const catalogContext = useCatalog();
  const viewAccess = computed(() => workspaceAccessFromPermission(permission));
  const workspaceDatasource = useWorkspaceDatasourceContext({
    connection: {
      config,
      datasourceOptions,
      isTestingDatasource: isTestingConfigDatasource,
    },
    permission,
    catalog: catalogContext,
    viewAccess,
  });
  const {
    visibleDatasourceOptions,
    currentDatasource,
    isTestingDatasource,
    databaseOptions,
    catalogEntries,
    schemaOptions,
    isLoadingCatalog,
    isLoadingDatabases,
    isLoadingSchemas,
    datasourceStatuses,
    currentDatasourceStatus,
    isPrewarmingCurrentDatasource,
    loadCatalog,
    loadSchemaTables,
    ensureCatalogLoaded,
    loadDatasourceStatuses,
    prewarmDatasource,
    database,
    schema,
    setDatabase,
    setSchema,
    handleDatasourceSwitched,
    initializeDatasource,
    warmCurrentDatasource,
    handleDatasourceTest,
    handleDatasourceSwitch,
    canUseDatasource,
    canReadAgentConfig,
    canReadModelOptions,
  } = workspaceDatasource;
  const workspaceAgent = useWorkspaceAgentPreferences({
    effectiveBase: connectionContext.effectiveBase,
    selectSession,
    resetPersonalMcpSelection: personalMcp.resetDraftSelection,
  });
  const {
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
  } = workspaceAgent;
  const selectedModel = shallowRef("");
  const canUsePersonalMcp = computed(() =>
    permission.isAdmin()
    || (
      permission.hasPermission("module.mcp.personal")
      && permission.hasPermission("mcp.personal.list")
      && permission.hasPermission("mcp.personal.use")
    )
  );
  const showPersonalMcpPicker = computed(() =>
    canUsePersonalMcp.value
    || (
      permission.hasFeaturePermission("mcp_personal")
      && permission.hasPermission("mcp.personal.list")
      && permission.hasPermission("mcp.personal.use")
    )
  );

  const canUseElevatedPermissionMode = computed(() =>
    permission.isAdmin() || permission.hasPermission?.("module.chat.permission_mode") === true
  );
  const isPermissionSummaryLoaded = computed(() => permission.isLoaded?.value ?? true);

  const { initialize } = useWorkspaceLifecycle({
    bootstrap: {
      canReadAgentConfig,
      canViewChat: computed(() => viewAccess.value.canViewChat),
      showPersonalMcpPicker,
      canReadModelOptions,
      checkConnection,
      initializeDatasource,
      loadSessions,
      loadAgentOptions,
      loadAgentPreference,
      loadPersonalMcp: personalMcp.load,
      loadModels,
      warmCurrentDatasource,
    },
    model: {
      options: modelOptions,
      selected: selectedModel,
    },
    catalog: {
      database,
      loadCatalog,
    },
    personalMcp: {
      showPicker: showPersonalMcpPicker,
      selectedSession,
      selectedIds: personalMcp.selectedIds,
      loadSessionBinding: personalMcp.loadSessionBinding,
      resetDraftSelection: personalMcp.resetDraftSelection,
    },
    agent: {
      effectiveAgentId,
      allowsPersonalMcp: agentAllowsPersonalMcp,
    },
    permissions: {
      summaryLoaded: isPermissionSummaryLoaded,
      canUseElevatedPermissionMode,
      permissionMode,
      setPermissionMode,
    },
    dispose,
  });

  function handleSend(message: string) {
    void sendMessage({
      message,
      selectedAgent: selectedAgent.value,
      model: selectedModel.value,
      datasource: currentDatasource.value,
      database: database.value,
      schema: schema.value,
      personalMcpIds: personalMcpIdsForChat(
        showPersonalMcpPicker.value,
        agentAllowsPersonalMcp.value,
        personalMcp.selectedIds.value,
      ),
    });
  }

  function handleInsert(message: string) {
    return insertMessage(message);
  }

  function handleRefreshConnection() {
    if (!canReadAgentConfig.value) return;
    void checkConnection();
  }

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
    isInsertReady,
    isStopping,
    streamActivity,
    transportError,
    isLoadingSessions,
    isLoadingAgents,
    isSavingDefaultAgent,
    activeInteractionKey,
    personalMcp,
    showPersonalMcpPicker,
    agentAllowsPersonalMcp,
    effectiveAgentId,
    selectSession,
    stopSession,
    deleteSession,
    compactSession,
    resumeSession,
    sendInteraction,
    clearMessages,
    clearTransportError,
    agentOptions,
    modelOptions,
    defaultModelLabel,
    isLoadingModels,
    databaseOptions,
    catalogEntries,
    schemaOptions,
    isLoadingCatalog,
    isLoadingDatabases,
    isLoadingSchemas,
    datasourceStatuses,
    currentDatasourceStatus,
    isPrewarmingCurrentDatasource,
    loadSessions,
    loadAgentOptions,
    loadAgentPreference,
    loadCatalog,
    loadSchemaTables,
    ensureCatalogLoaded,
    loadDatasourceStatuses,
    prewarmDatasource,
    selectedAgent,
    defaultAgentId,
    userDefaultAgentId,
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
