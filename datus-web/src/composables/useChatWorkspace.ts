import { computed, onBeforeUnmount, shallowRef, watch } from "vue";

import { useCatalog } from "@/composables/useCatalog";
import { useChatSettings } from "@/composables/useChatSettings";
import { useChatState } from "@/composables/useChatState";
import { useConnection } from "@/composables/useConnection";
import { useModels } from "@/composables/useModels";
import { usePermission } from "@/composables/usePermission";
import { useTheme } from "@/composables/useTheme";
import type { SelectOption } from "@/types";

const STATUS_REFRESH_DELAYS = [1500, 5000] as const;

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

  // Enterprise mode disables the legacy agent-config routes; keep chat on the default agent.
  const agentOptions = computed<SelectOption[]>(() => []);
  const selectedAgent = shallowRef("");
  const selectedModel = shallowRef("");
  const selectedDatasource = shallowRef("");
  const defaultDatasource = computed(() => config.value?.current_datasource?.trim() ?? "");
  const currentDatasource = computed(() => selectedDatasource.value || defaultDatasource.value);
  const visibleDatasourceOptions = computed(() =>
    datasourceOptions.value.filter((option) => permission.hasDatasourcePermission(option.value))
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
        void loadDatasourceStatuses(datasource);
      }, delay);
      statusRefreshTimers.add(timer);
    }
  }

  function warmDatasource(datasource: string) {
    const datasourceName = datasource.trim();
    if (!datasourceName) return;
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

  function handleRefreshConnection() {
    checkConnection();
  }

  function handleDatasourceSwitched() {
    selectedDatasource.value = defaultDatasource.value;
    selectCatalogDatasource(currentDatasource.value);
    warmDatasource(currentDatasource.value);
  }

  async function handleDatasourceTest(name?: string) {
    return testDatasource(name);
  }

  function refreshCatalog(databaseName?: string) {
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
    warmDatasource(datasourceName);
    void loadCatalog(undefined, datasourceName);
    return true;
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
      ]);
      void loadDatasourceStatuses();
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
    if (db) {
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
