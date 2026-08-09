<script setup lang="ts">
import {
  BookMarkedIcon,
  BotIcon,
  BriefcaseBusinessIcon,
  ChevronDownIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  PlusIcon,
  ServerIcon,
  ShieldIcon,
  SlidersHorizontalIcon,
  UserRoundIcon,
} from "@lucide/vue"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/components/ui/sidebar"
import type { WorkspaceAccessFlags } from "@/features/workspace/access"
import type { ArtifactViewTab, WorkspaceView } from "@/features/workspace/types"

interface WorkspacePrimaryNavigationProps {
  activeView: WorkspaceView
  artifactTab: ArtifactViewTab
  canViewWorkbench: boolean
  isWorkbenchActive: boolean
  viewAccess: WorkspaceAccessFlags
}

defineProps<WorkspacePrimaryNavigationProps>()
const emit = defineEmits<{
  createSession: []
  openArtifactTab: [tab: ArtifactViewTab]
  openView: [view: WorkspaceView]
}>()

const newSessionButtonClass = [
  "h-10 w-full justify-start rounded-xl px-3 text-sm font-medium shadow-xs",
  "has-data-[icon=inline-start]:pl-2.5",
  "hover:bg-primary/90 hover:text-primary-foreground",
  "active:bg-primary/90 active:text-primary-foreground",
].join(" ")
const secondaryNavButtonClass = [
  "h-9 w-full justify-start rounded-lg px-2.5 text-sm font-medium text-sidebar-foreground/80",
  "hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
  "data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:font-semibold",
  "data-active:shadow-none",
].join(" ")
const subNavButtonClass = [
  "h-8 w-full justify-start rounded-md px-2 !text-sm font-medium text-sidebar-foreground/75",
  "hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
  "data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground data-active:font-semibold",
  "data-active:shadow-none",
].join(" ")

function createSession(): void {
  emit("createSession")
}

function openView(view: WorkspaceView): void {
  emit("openView", view)
}

function openArtifactTab(tab: ArtifactViewTab): void {
  emit("openArtifactTab", tab)
}
</script>
<template>
      <SidebarGroup class="shrink-0 px-3 pb-1 pt-0">
        <SidebarGroupContent class="flex flex-col gap-2">
          <Button
            v-if="viewAccess.canViewChat"
            :class="newSessionButtonClass"
            @click="createSession"
          >
            <PlusIcon data-icon="inline-start" />
            <span>新会话</span>
          </Button>

          <SidebarMenu class="gap-0.5">
            <SidebarMenuItem v-if="viewAccess.canViewReportArtifacts">
              <SidebarMenuButton
                :is-active="activeView === 'artifacts' && artifactTab === 'report'"
                :class="secondaryNavButtonClass"
                @click="openArtifactTab('report')"
              >
                <FileTextIcon />
                <span>报表</span>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <SidebarMenuItem v-if="viewAccess.canViewDashboardArtifacts">
              <SidebarMenuButton
                :is-active="activeView === 'artifacts' && artifactTab === 'dashboard'"
                :class="secondaryNavButtonClass"
                @click="openArtifactTab('dashboard')"
              >
                <LayoutDashboardIcon />
                <span>仪表盘</span>
              </SidebarMenuButton>
            </SidebarMenuItem>

            <Collapsible
              v-if="canViewWorkbench"
              v-slot="{ open }"
              as-child
              :default-open="true"
            >
              <SidebarMenuItem>
                <CollapsibleTrigger as-child>
                  <SidebarMenuButton
                    :is-active="isWorkbenchActive"
                    :class="secondaryNavButtonClass"
                  >
                    <BriefcaseBusinessIcon />
                    <span>工作台</span>
                    <ChevronDownIcon
                      class="ml-auto opacity-70 transition-transform"
                      :class="{ 'rotate-180': open }"
                    />
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub class="mx-2 my-0.5 gap-0.5 border-sidebar-border/60 px-1 py-0.5">
                    <SidebarMenuSubItem
                      v-if="viewAccess.canViewKnowledge"
                      class="w-full"
                    >
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'knowledge'"
                        :class="subNavButtonClass"
                        @click="openView('knowledge')"
                      >
                        <BookMarkedIcon />
                        <span>知识库</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem
                      v-if="viewAccess.canViewMcp"
                      class="w-full"
                    >
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'mcp'"
                        :class="subNavButtonClass"
                        @click="openView('mcp')"
                      >
                        <ServerIcon />
                        <span>MCP</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem
                      v-if="viewAccess.canViewAgents"
                      class="w-full"
                    >
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'agents'"
                        :class="subNavButtonClass"
                        @click="openView('agents')"
                      >
                        <BotIcon />
                        <span>Agent</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                    <SidebarMenuSubItem
                      v-if="viewAccess.canViewConfiguration"
                      class="w-full"
                    >
                      <SidebarMenuSubButton
                        as="button"
                        :is-active="activeView === 'configuration'"
                        :class="subNavButtonClass"
                        @click="openView('configuration')"
                      >
                        <SlidersHorizontalIcon />
                        <span>配置</span>
                      </SidebarMenuSubButton>
                    </SidebarMenuSubItem>
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>

            <SidebarMenuItem v-if="viewAccess.canViewPermissions">
              <SidebarMenuButton
                :is-active="activeView === 'admin'"
                :class="secondaryNavButtonClass"
                @click="openView('admin')"
              >
                <ShieldIcon />
                <span>权限管理</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton
                :is-active="activeView === 'profile'"
                :class="secondaryNavButtonClass"
                @click="openView('profile')"
              >
                <UserRoundIcon />
                <span>个人设置</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
</template>
