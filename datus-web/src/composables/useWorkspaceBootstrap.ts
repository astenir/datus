import { shallowRef, type Ref } from "vue";

type ReadonlyValue<T> = Readonly<Ref<T>>;

export interface UseWorkspaceBootstrapOptions {
  canReadAgentConfig: ReadonlyValue<boolean>;
  canViewChat: ReadonlyValue<boolean>;
  showPersonalMcpPicker: ReadonlyValue<boolean>;
  canReadModelOptions: ReadonlyValue<boolean>;
  checkConnection: () => Promise<void>;
  initializeDatasource: () => void;
  loadSessions: () => Promise<unknown>;
  loadAgentOptions: () => Promise<boolean>;
  loadAgentPreference: () => Promise<boolean>;
  loadPersonalMcp: () => Promise<void>;
  loadModels: () => Promise<void>;
  warmCurrentDatasource: () => void;
}

export function useWorkspaceBootstrap(options: UseWorkspaceBootstrapOptions) {
  const initialized = shallowRef(false);
  let initializePromise: Promise<void> | null = null;

  async function initialize(): Promise<void> {
    if (initialized.value) return;
    if (initializePromise) return initializePromise;

    initializePromise = (async () => {
      if (options.canReadAgentConfig.value) {
        await options.checkConnection();
      }
      options.initializeDatasource();

      const startupTasks: Promise<unknown>[] = [];
      if (options.canViewChat.value) {
        startupTasks.push(
          options.loadSessions(),
          options.loadAgentOptions().then(() => options.loadAgentPreference()),
        );
      }
      if (options.showPersonalMcpPicker.value) {
        startupTasks.push(options.loadPersonalMcp());
      }
      if (options.canReadModelOptions.value) {
        startupTasks.push(options.loadModels());
      }

      await Promise.all(startupTasks);
      options.warmCurrentDatasource();
      initialized.value = true;
    })();

    try {
      await initializePromise;
    } finally {
      initializePromise = null;
    }
  }

  return {
    initialize,
  };
}
