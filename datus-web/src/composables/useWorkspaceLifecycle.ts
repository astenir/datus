import { onBeforeUnmount, watch, type Ref } from "vue";
import { toast } from "vue-sonner";

import type { SelectOption } from "@/types";
import { useWorkspaceBootstrap } from "./useWorkspaceBootstrap";

type ReadonlyValue<T> = Readonly<Ref<T>>;
type WorkspaceBootstrapOptions = Parameters<typeof useWorkspaceBootstrap>[0];

export interface UseWorkspaceLifecycleOptions {
  bootstrap: WorkspaceBootstrapOptions;
  model: {
    options: ReadonlyValue<readonly SelectOption[]>;
    selected: Ref<string>;
  };
  catalog: {
    database: ReadonlyValue<string>;
    loadCatalog: (databaseName?: string) => Promise<boolean>;
  };
  personalMcp: {
    showPicker: ReadonlyValue<boolean>;
    selectedSession: ReadonlyValue<string | null>;
    selectedIds: ReadonlyValue<readonly string[]>;
    loadSessionBinding: (sessionId: string) => Promise<void>;
    resetDraftSelection: () => void;
  };
  agent: {
    effectiveAgentId: ReadonlyValue<string>;
    allowsPersonalMcp: ReadonlyValue<boolean>;
  };
  permissions: {
    summaryLoaded: ReadonlyValue<boolean>;
    canUseElevatedPermissionMode: ReadonlyValue<boolean>;
    permissionMode: ReadonlyValue<string>;
    setPermissionMode: (value: string) => void;
  };
  dispose: () => void;
}

export function useWorkspaceLifecycle(options: UseWorkspaceLifecycleOptions) {
  const { initialize } = useWorkspaceBootstrap(options.bootstrap);

  watch(options.model.options, (modelOptions) => {
    if (!options.model.selected.value.startsWith("credential:")) return;
    if (!modelOptions.some(option => option.value === options.model.selected.value)) {
      options.model.selected.value = "";
    }
  });

  watch(options.catalog.database, (database) => {
    if (database) void options.catalog.loadCatalog(database);
  });

  watch(options.personalMcp.selectedSession, (sessionId) => {
    if (!options.personalMcp.showPicker.value) {
      options.personalMcp.resetDraftSelection();
      return;
    }
    if (sessionId) {
      void options.personalMcp.loadSessionBinding(sessionId);
    } else {
      options.personalMcp.resetDraftSelection();
    }
  }, { immediate: true });

  watch(
    [options.agent.effectiveAgentId, options.agent.allowsPersonalMcp],
    ([, allowsPersonalMcp], [, wasAllowed]) => {
      if (!options.personalMcp.selectedSession.value && !allowsPersonalMcp) {
        const hadDraftSelection = options.personalMcp.selectedIds.value.length > 0;
        options.personalMcp.resetDraftSelection();
        if (hadDraftSelection && wasAllowed) {
          toast.info("当前 Agent 不支持个人 MCP，已清除本次会话的个人 MCP 选择");
        }
      }
    },
  );

  watch(
    [
      options.permissions.summaryLoaded,
      options.permissions.canUseElevatedPermissionMode,
      options.permissions.permissionMode,
    ],
    ([loaded, canUseElevated, mode]) => {
      if (loaded && !canUseElevated && mode !== "normal") {
        options.permissions.setPermissionMode("normal");
      }
    },
    { immediate: true },
  );

  onBeforeUnmount(options.dispose);

  return { initialize };
}
