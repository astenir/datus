import { computed, onBeforeUnmount, shallowRef, watch } from "vue";

import { useCatalog } from "@/composables/useCatalog";
import { useChatSettings } from "@/composables/useChatSettings";
import { useChatState } from "@/composables/useChatState";
import { useConnection } from "@/composables/useConnection";
import { useModels } from "@/composables/useModels";
import { usePermission } from "@/composables/usePermission";
import { useTheme } from "@/composables/useTheme";
import type { SelectOption } from "@/types";

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
    isTestingDatasource,
    checkConnection,
    setApiBase,
    testDatasource,
    switchDatasource,
  } = useConnection();
  const permission = usePermission();
  const {
    messages,
    sessions,
    selectedSession,
    isStreaming,
    isLoadingSessions,
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
    loadCatalog,
    setDatabase,
    setSchema,
  } = useCatalog();

  // Enterprise mode disables the legacy agent-config routes; keep chat on the default agent.
  const agentOptions = computed<SelectOption[]>(() => []);
  const selectedAgent = shallowRef("");
  const selectedModel = shallowRef("");
  const currentDatasource = computed(() => config.value?.current_datasource?.trim() ?? "");
  const visibleDatasourceOptions = computed(() =>
    datasourceOptions.value.filter((option) => permission.hasDatasourcePermission(option.value))
  );
  const initialized = shallowRef(false);
  let initializePromise: Promise<void> | null = null;

  function handleSend(message: string) {
    sendMessage({
      message,
      selectedAgent: selectedAgent.value,
      model: selectedModel.value,
      database: database.value,
      schema: schema.value,
    });
  }

  function handleInsert(message: string) {
    insertMessage(message);
  }

  function handleRefreshConnection() {
    checkConnection();
  }

  function handleDatasourceSwitched() {
    setDatabase("");
    setSchema("");
    loadCatalog();
  }

  async function handleDatasourceTest(name?: string) {
    return testDatasource(name);
  }

  function canUseDatasource(name: string) {
    const datasourceName = name.trim();
    return visibleDatasourceOptions.value.some((option) => option.value === datasourceName);
  }

  async function handleDatasourceSwitch(name: string): Promise<boolean> {
    const datasourceName = name.trim();
    if (!datasourceName || !canUseDatasource(datasourceName)) return false;

    const changed = await switchDatasource(datasourceName);
    if (!changed) return false;

    setDatabase("");
    setSchema("");
    await loadCatalog();
    return true;
  }

  async function initialize() {
    if (initialized.value) return;
    if (initializePromise) return initializePromise;

    initializePromise = (async () => {
      await checkConnection();
      await Promise.all([
        loadSessions(),
        loadModels(),
        loadCatalog(),
      ]);
      initialized.value = true;
    })();

    try {
      await initializePromise;
    } finally {
      initializePromise = null;
    }
  }

  onBeforeUnmount(dispose);

  watch(database, (db) => {
    if (db) {
      loadCatalog(db);
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
    loadSessions,
    loadCatalog,
    selectedAgent,
    selectedModel,
    database,
    schema,
    handleSend,
    handleInsert,
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
