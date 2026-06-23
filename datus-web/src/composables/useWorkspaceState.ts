import { computed, shallowRef, watch } from "vue";

import { PRIMARY_DEVELOPER_VIEWS, developerViewFeature } from "@/lib/navigation";
import type { DeveloperViewType } from "@/types";

type DrawerWorkspaceTool = Extract<DeveloperViewType, "knowledge" | "mcp" | "sql">;

type PermissionAdapter = {
  hasFeaturePermission: (featureCode: string) => boolean;
  isAdmin: () => boolean;
};

export function useWorkspaceState(permission: PermissionAdapter) {
  const activeView = shallowRef<DeveloperViewType>("chat");

  const settingsOpen = shallowRef(false);
  const agentManagerOpen = shallowRef(false);
  const systemManagerOpen = shallowRef(false);
  const userProfileOpen = shallowRef(false);
  const knowledgeExplorerOpen = shallowRef(false);
  const mcpManagerOpen = shallowRef(false);
  const sqlConsoleOpen = shallowRef(false);
  const sqlDraft = shallowRef("");
  const sqlDraftVersion = shallowRef(0);

  function canUseView(view: DeveloperViewType): boolean {
    return permission.isAdmin() || permission.hasFeaturePermission(developerViewFeature(view));
  }

  const allowedPrimaryViews = computed(() => PRIMARY_DEVELOPER_VIEWS.filter((view) => canUseView(view)));
  const canUseActiveView = computed(() => canUseView(activeView.value));

  watch(
    allowedPrimaryViews,
    (views) => {
      if (canUseView(activeView.value)) return;
      if (views[0]) {
        activeView.value = views[0];
      }
    },
    { immediate: true }
  );

  function openSettings() {
    settingsOpen.value = true;
  }

  function openSystemManager() {
    settingsOpen.value = false;
    systemManagerOpen.value = true;
  }

  function openUserProfile() {
    userProfileOpen.value = true;
  }

  function closeUserProfile() {
    userProfileOpen.value = false;
  }

  function activateChat() {
    if (!canUseView("chat")) {
      return false;
    }
    activeView.value = "chat";
    return true;
  }

  function openAgentManager() {
    settingsOpen.value = false;
    agentManagerOpen.value = true;
  }

  function openSqlConsole(sql: string) {
    if (!canUseView("sql")) {
      return false;
    }
    sqlDraft.value = sql.trim();
    sqlDraftVersion.value += 1;
    settingsOpen.value = false;
    sqlConsoleOpen.value = true;
    return true;
  }

  function openDeveloperView(view: DeveloperViewType) {
    if (!canUseView(view)) {
      return false;
    }
    settingsOpen.value = false;
    if (view === "sql") {
      return openSqlConsole("");
    }
    if (view === "knowledge") {
      knowledgeExplorerOpen.value = true;
      return true;
    }
    if (view === "mcp") {
      mcpManagerOpen.value = true;
      return true;
    }
    activeView.value = view;
    return true;
  }

  function returnToSettings() {
    agentManagerOpen.value = false;
    settingsOpen.value = true;
  }

  function closeWorkspaceTool(tool: DrawerWorkspaceTool) {
    if (tool === "knowledge") {
      knowledgeExplorerOpen.value = false;
    } else if (tool === "mcp") {
      mcpManagerOpen.value = false;
    } else {
      sqlConsoleOpen.value = false;
    }
  }

  function returnWorkspaceToolToSettings(tool: DrawerWorkspaceTool) {
    closeWorkspaceTool(tool);
    settingsOpen.value = true;
  }

  function openArtifact(kind: string) {
    const view = kind === "report" ? "report" : "dashboard";
    if (canUseView(view)) {
      activeView.value = view;
      return true;
    }
    return false;
  }

  return {
    activeView,
    allowedPrimaryViews,
    canUseActiveView,
    settingsOpen,
    agentManagerOpen,
    systemManagerOpen,
    userProfileOpen,
    knowledgeExplorerOpen,
    mcpManagerOpen,
    sqlConsoleOpen,
    sqlDraft,
    sqlDraftVersion,
    canUseView,
    openSettings,
    openSystemManager,
    openUserProfile,
    closeUserProfile,
    activateChat,
    openAgentManager,
    openDeveloperView,
    openSqlConsole,
    returnToSettings,
    closeWorkspaceTool,
    returnWorkspaceToolToSettings,
    openArtifact,
  };
}

export type WorkspaceState = ReturnType<typeof useWorkspaceState>;
