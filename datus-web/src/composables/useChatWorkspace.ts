import { computed, onBeforeUnmount, shallowRef, watch } from "vue";

import { useAgents } from "@/composables/useAgents";
import { useCatalog } from "@/composables/useCatalog";
import { useChatSettings } from "@/composables/useChatSettings";
import { useChatState } from "@/composables/useChatState";
import { useConnection } from "@/composables/useConnection";
import { useModels } from "@/composables/useModels";
import { useTheme } from "@/composables/useTheme";

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
  const { agents, loadAgents } = useAgents();
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

  const agentOptions = computed(() =>
    agents.value.map((agent) => ({ value: agent.name, label: agent.name }))
  );
  const selectedAgent = shallowRef("");
  const selectedModel = shallowRef("");
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

  async function handleDatasourceSwitch(name: string) {
    const changed = await switchDatasource(name);
    if (!changed) return;

    setDatabase("");
    setSchema("");
    await loadCatalog();
  }

  async function initialize() {
    if (initialized.value) return;
    if (initializePromise) return initializePromise;

    initializePromise = (async () => {
      await checkConnection();
      await Promise.all([
        loadSessions(),
        loadAgents(),
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
    setLanguage,
    setPermissionMode,
    setPlanMode,
    setDatabase,
    setSchema,
    initialize,
  };
}

export type ChatWorkspace = ReturnType<typeof useChatWorkspace>;
