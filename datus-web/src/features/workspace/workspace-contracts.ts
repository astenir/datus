import type { ChatWorkspace } from "@/composables/useChatWorkspace"

export type ChatWorkspaceCatalogContract = Pick<
  ChatWorkspace,
  | "catalogEntries"
  | "currentDatasource"
  | "isLoadingCatalog"
  | "loadCatalog"
  | "visibleDatasourceOptions"
>

export type ChatWorkspaceChatContract = Pick<
  ChatWorkspace,
  | "activeInteractionKey"
  | "agentAllowsPersonalMcp"
  | "agentOptions"
  | "clearTransportError"
  | "currentDatasource"
  | "database"
  | "databaseOptions"
  | "datasourceStatuses"
  | "defaultAgentId"
  | "defaultModelLabel"
  | "ensureCatalogLoaded"
  | "handleDatasourceSwitch"
  | "handleInsert"
  | "handleSend"
  | "isInsertReady"
  | "isLoadingAgents"
  | "isLoadingCatalog"
  | "isLoadingDatabases"
  | "isLoadingModels"
  | "isLoadingSchemas"
  | "isPrewarmingCurrentDatasource"
  | "isSavingDefaultAgent"
  | "isStopping"
  | "isStreaming"
  | "loadAgentOptions"
  | "messages"
  | "modelOptions"
  | "personalMcp"
  | "schema"
  | "schemaOptions"
  | "selectedAgent"
  | "selectedModel"
  | "selectedSession"
  | "sendInteraction"
  | "setDatabase"
  | "setDefaultAgent"
  | "setPlanMode"
  | "setSchema"
  | "showPersonalMcpPicker"
  | "stopSession"
  | "streamActivity"
  | "transportError"
  | "userDefaultAgentId"
  | "visibleDatasourceOptions"
>

export type ChatWorkspaceProfileContract = Pick<
  ChatWorkspace,
  | "canUseElevatedPermissionMode"
  | "currentDatasource"
  | "currentDatasourceStatus"
  | "handleDatasourceTest"
  | "isPrewarmingCurrentDatasource"
  | "isTestingDatasource"
  | "language"
  | "permissionMode"
  | "planMode"
  | "visibleDatasourceOptions"
>

export type ChatWorkspaceSessionRailContract = ChatWorkspaceProfileContract & Pick<
  ChatWorkspace,
  | "compactSession"
  | "connection"
  | "deleteSession"
  | "handleDatasourceSwitch"
  | "isLoadingSessions"
  | "selectedSession"
  | "sessions"
  | "setLanguage"
  | "setPermissionMode"
  | "setPlanMode"
  | "startNewSession"
>

export type ChatWorkspaceRoutingContract = ChatWorkspaceRouteContextContract & Pick<
  ChatWorkspace,
  | "initialize"
  | "selectSession"
  | "selectedSession"
>

export type ChatWorkspaceRouteContextContract = Pick<
  ChatWorkspace,
  | "currentDatasource"
  | "database"
  | "handleDatasourceSwitch"
  | "schema"
  | "setDatabase"
  | "setSchema"
>

export type ChatWorkspaceShellContract = Pick<
  ChatWorkspace,
  | "connection"
  | "ensureCatalogLoaded"
  | "messages"
  | "selectedSession"
  | "sessions"
>
