<script setup lang="ts">
import { defineAsyncComponent } from "vue"
import { ShieldIcon } from "@lucide/vue"
import { TabsContent } from "@/components/ui/tabs"
import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import ChatPanel from "@/features/chat/ChatPanel.vue"
import type { WorkspaceAccessFlags } from "@/features/workspace/access"
import type {
  AdminArtifactRouteState,
  AdminAuditRouteState,
  AdminGrantRouteState,
} from "@/features/workspace/route-state"
import type { AdminViewTab, ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"
import type { ArtifactEditSession } from "@/types"

const AdminPanel = defineAsyncComponent(() => import("@/features/admin/AdminPanel.vue"))
const AgentManagerPanel = defineAsyncComponent(() => import("@/features/agent/AgentManagerPanel.vue"))
const ArtifactsPanel = defineAsyncComponent(() => import("@/features/artifacts/ArtifactsPanel.vue"))
const ConfigurationPanel = defineAsyncComponent(() => import("@/features/config/ConfigurationPanel.vue"))
const KnowledgeBasePanel = defineAsyncComponent(() => import("@/features/knowledge/KnowledgeBasePanel.vue"))
const McpPanel = defineAsyncComponent(() => import("@/features/mcp/McpPanel.vue"))
const ProfilePanel = defineAsyncComponent(() => import("@/features/profile/ProfilePanel.vue"))

interface WorkspaceViewContentProps {
  activeArtifact: AdminArtifactRouteState | null
  activeAudit: AdminAuditRouteState | null
  activeGrant: AdminGrantRouteState | null
  activeRoleId: string | null
  activeSecretName: string | null
  activeSessionId: string | null
  activeTab: AdminViewTab
  activeView: WorkspaceView
  activeUserId: string | null
  auth: AuthState
  artifactSlug: string | null
  artifactTab: ArtifactViewTab
  canRenderAdminPanel: boolean
  canViewSubjectTree: boolean
  knowledgeTable: string | null
  viewAccess: WorkspaceAccessFlags
  workspace: ChatWorkspace
}

defineProps<WorkspaceViewContentProps>()
const emit = defineEmits<{
  editArtifact: [session: ArtifactEditSession]
  openArtifact: [tab: ArtifactViewTab, slug: string]
  updateAdminArtifact: [value: AdminArtifactRouteState | null]
  updateAdminAudit: [value: AdminAuditRouteState]
  updateAdminGrant: [value: AdminGrantRouteState | null]
  updateAdminRoleId: [value: string | null]
  updateAdminSecretName: [value: string | null]
  updateAdminSessionId: [value: string | null]
  updateAdminTab: [value: AdminViewTab]
  updateAdminUserId: [value: string | null]
  updateKnowledgeTable: [table: string]
}>()

function openArtifact(tab: ArtifactViewTab, slug: string): void {
  emit("openArtifact", tab, slug)
}

function editArtifact(session: ArtifactEditSession): void {
  emit("editArtifact", session)
}

function updateKnowledgeTable(table: string): void {
  emit("updateKnowledgeTable", table)
}

function updateAdminTab(value: AdminViewTab): void {
  emit("updateAdminTab", value)
}

function updateAdminUserId(value: string | null): void {
  emit("updateAdminUserId", value)
}

function updateAdminRoleId(value: string | null): void {
  emit("updateAdminRoleId", value)
}

function updateAdminSecretName(value: string | null): void {
  emit("updateAdminSecretName", value)
}

function updateAdminGrant(value: AdminGrantRouteState | null): void {
  emit("updateAdminGrant", value)
}

function updateAdminSessionId(value: string | null): void {
  emit("updateAdminSessionId", value)
}

function updateAdminArtifact(value: AdminArtifactRouteState | null): void {
  emit("updateAdminArtifact", value)
}

function updateAdminAudit(value: AdminAuditRouteState): void {
  emit("updateAdminAudit", value)
}
</script>

<template>
  <TabsContent
    value="chat"
    class="m-0 flex min-h-0 flex-1"
  >
    <ChatPanel
      :workspace="workspace"
      @open-artifact="openArtifact"
    />
  </TabsContent>

  <TabsContent
    value="knowledge"
    class="m-0 flex min-h-0 flex-1"
  >
    <KnowledgeBasePanel
      :workspace="workspace"
      :selected-table="knowledgeTable"
      :can-view-subject-tree="canViewSubjectTree"
      @update-table="updateKnowledgeTable"
    />
  </TabsContent>

  <TabsContent
    value="mcp"
    class="m-0 flex min-h-0 flex-1"
  >
    <McpPanel v-if="viewAccess.canViewMcp" />
  </TabsContent>

  <TabsContent
    value="agents"
    class="m-0 flex min-h-0 flex-1"
  >
    <AgentManagerPanel
      v-if="viewAccess.canViewAgents"
    />
  </TabsContent>

  <TabsContent
    value="configuration"
    class="m-0 flex min-h-0 flex-1"
  >
    <ConfigurationPanel
      v-if="viewAccess.canViewConfiguration"
      :can-edit="viewAccess.canEditConfiguration"
    />
  </TabsContent>

  <TabsContent
    value="artifacts"
    class="m-0 flex min-h-0 flex-1"
  >
    <ArtifactsPanel
      v-if="viewAccess.canViewArtifacts"
      :tab="artifactTab"
      :selected-slug="artifactSlug"
      @open-artifact="openArtifact"
      @edit-artifact="editArtifact"
    />
  </TabsContent>

  <TabsContent
    value="profile"
    class="m-0 flex min-h-0 flex-1"
  >
    <ProfilePanel :auth="auth" />
  </TabsContent>

  <TabsContent
    value="admin"
    class="m-0 flex min-h-0 flex-1"
  >
    <AdminPanel
      v-if="activeView === 'admin' && canRenderAdminPanel"
      :active-tab="activeTab"
      :active-user-id="activeUserId"
      :active-role-id="activeRoleId"
      :active-secret-name="activeSecretName"
      :active-grant="activeGrant"
      :active-session-id="activeSessionId"
      :active-artifact="activeArtifact"
      :active-audit="activeAudit"
      @update:active-tab="updateAdminTab"
      @update:active-user-id="updateAdminUserId"
      @update:active-role-id="updateAdminRoleId"
      @update:active-secret-name="updateAdminSecretName"
      @update:active-grant="updateAdminGrant"
      @update:active-session-id="updateAdminSessionId"
      @update:active-artifact="updateAdminArtifact"
      @update:active-audit="updateAdminAudit"
    />
    <section
      v-else
      class="flex min-h-0 flex-1 items-center justify-center p-6 text-center"
    >
      <div class="flex max-w-sm flex-col items-center gap-3">
        <ShieldIcon class="size-8 text-muted-foreground" />
        <h1 class="text-lg font-semibold">无权限访问</h1>
        <p class="text-sm text-muted-foreground">
          正在返回可用工作区。权限管理入口仅对授权管理员开放。
        </p>
      </div>
    </section>
  </TabsContent>
</template>
