<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import {
  CircleCheckIcon,
  CircleXIcon,
  ChevronRightIcon,
  DatabaseIcon,
  LanguagesIcon,
  ListChecksIcon,
  LoaderCircleIcon,
  LogOutIcon,
  ShieldCheckIcon,
  UserRoundIcon,
} from "@lucide/vue"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Switch } from "@/components/ui/switch"
import { SidebarFooter } from "@/components/ui/sidebar"
import type { AuthState } from "@/composables/useAuth"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import type { WorkspaceAccessFlags } from "@/features/workspace/access"
import { selectedOptionLabel } from "@/lib/datasource-display"
import { datasourceStatusDescription, datasourceStatusLabel, datasourceStatusToneClass } from "@/lib/datasource-status"
import {
  FALLBACK_USERNAME_LABEL,
  FALLBACK_USER_LABEL,
} from "@/lib/constants"
import { cn } from "@/lib/utils"

type ProfileWorkspace = Pick<
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

interface WorkspaceProfileMenuProps {
  auth: AuthState
  viewAccess: Pick<WorkspaceAccessFlags, "canViewPermissions">
  workspace: ProfileWorkspace
}

const props = defineProps<WorkspaceProfileMenuProps>()
const emit = defineEmits<{
  logout: []
  openView: [view: "profile"]
  updateDatasource: [value: string]
  updateLanguage: [value: string]
  updatePermissionMode: [value: string]
  updatePlanMode: [value: boolean]
}>()

const userProfileOpen = shallowRef(false)
const datasourceTestOk = shallowRef<boolean | null>(null)
const datasourceTestMessage = shallowRef("")
const profileMenuSubTriggerClass = "h-10 rounded-xl px-2.5 text-sm [&>svg:last-child]:ml-1"
const profileMenuValueClass = "ml-auto w-12 shrink-0 text-right tracking-normal"
const profileDatasourceMenuValueClass = "ml-auto w-20 shrink-0 truncate text-right tracking-normal"
const profileMenuSwitchClass = "ml-auto flex w-14 shrink-0 justify-start"
const datasourceTestStatusIconClass = "shrink-0"

const userLabel = computed(() => props.auth.user?.realname || props.auth.user?.username || FALLBACK_USER_LABEL)
const userFallback = computed(() => userLabel.value.slice(0, 1).toUpperCase())
const currentDatasourceName = computed(() => props.workspace.currentDatasource.value.trim())
const datasourceOptions = computed(() => props.workspace.visibleDatasourceOptions.value)
const currentDatasourceLabel = computed(() =>
  selectedOptionLabel(currentDatasourceName.value, datasourceOptions.value) || "当前数据源未选择"
)
const userMeta = computed(() => props.auth.user?.department || props.auth.user?.title || currentDatasourceLabel.value)
const userRoleLabel = computed(() => props.viewAccess.canViewPermissions ? "管理员" : "成员")
const userStatusLabel = computed(() => props.auth.user?.userStatus || "已登录")
const currentDatasourceStatus = computed(() => props.workspace.currentDatasourceStatus.value)
const hasDatasourceOptions = computed(() => datasourceOptions.value.length > 0)
const canTestDatasource = computed(() => Boolean(currentDatasourceName.value) && !props.workspace.isTestingDatasource.value)
const datasourceTestActionLabel = computed(() => {
  if (props.workspace.isTestingDatasource.value) return "正在测试数据源连接"
  if (datasourceTestOk.value === true) return "重新测试数据源连接"
  if (datasourceTestOk.value === false) return "重新测试数据源连接"
  return "测试当前数据源连接"
})
const datasourceConnectionStatusLabel = computed(() => {
  if (props.workspace.isTestingDatasource.value) return "正在测试连接"
  if (datasourceTestMessage.value) return datasourceTestMessage.value
  if (currentDatasourceName.value) return datasourceStatusDescription(currentDatasourceStatus.value)
  return "未选择数据源"
})
const datasourceStatusDisplayLabel = computed(() => {
  if (props.workspace.isPrewarmingCurrentDatasource.value) return "预热中"
  return datasourceStatusLabel(currentDatasourceStatus.value?.status)
})
const datasourceStatusDisplayClass = computed(() =>
  datasourceStatusToneClass(currentDatasourceStatus.value?.status)
)
const datasourceStatusConnecting = computed(() =>
  props.workspace.isPrewarmingCurrentDatasource.value || currentDatasourceStatus.value?.status === "connecting"
)
const datasourceStatusFailed = computed(() =>
  currentDatasourceStatus.value?.status === "failed" || currentDatasourceStatus.value?.status === "timeout"
)
const datasourceTestDisplayLabel = computed(() => {
  if (props.workspace.isTestingDatasource.value) return "测试中"
  if (datasourceTestOk.value === true) return "连接正常"
  if (datasourceTestOk.value === false) return "连接失败"
  return datasourceStatusDisplayLabel.value
})
const datasourceTestDisplayClass = computed(() => {
  if (props.workspace.isTestingDatasource.value || datasourceTestOk.value === null) {
    return datasourceTestOk.value === null ? datasourceStatusDisplayClass.value : "bg-muted text-muted-foreground"
  }
  return datasourceTestOk.value ? "bg-primary/10 text-primary" : "bg-destructive/10 text-destructive"
})
const datasourceTestIconState = computed<"loading" | "success" | "failed" | "unknown">(() => {
  if (props.workspace.isTestingDatasource.value || datasourceStatusConnecting.value) return "loading"
  if (datasourceTestOk.value === true || currentDatasourceStatus.value?.status === "connected") return "success"
  if (datasourceTestOk.value === false || datasourceStatusFailed.value) return "failed"
  return "unknown"
})
const datasourceConnectionStatusDisplayLabel = computed(() => {
  if (!currentDatasourceName.value) return "未选择"
  return datasourceTestDisplayLabel.value
})
const datasourceTestResultClass = computed(() => cn(
  "h-7 max-w-28 shrink-0 justify-start gap-1.5 rounded-full px-2.5 text-xs font-medium tracking-normal",
  "bg-background/75 text-muted-foreground hover:bg-background hover:text-foreground",
  datasourceTestDisplayClass.value,
))
const languageLabel = computed(() => props.workspace.language.value === "en" ? "英文" : "中文")
const canUseElevatedPermissionMode = computed(() => props.workspace.canUseElevatedPermissionMode.value)
const permissionModeLabel = computed(() => {
  switch (props.workspace.permissionMode.value) {
    case "auto":
      return "自动"
    case "dangerous":
      return "危险"
    default:
      return "普通"
  }
})

watch(currentDatasourceName, () => {
  datasourceTestOk.value = null
  datasourceTestMessage.value = ""
})

async function runDatasourceTest(): Promise<void> {
  if (!canTestDatasource.value) return
  datasourceTestOk.value = null
  datasourceTestMessage.value = ""
  const result = await props.workspace.handleDatasourceTest(currentDatasourceName.value)
  datasourceTestOk.value = result.ok
  datasourceTestMessage.value = result.message
}

function togglePlanMode(): void {
  emit("updatePlanMode", !props.workspace.planMode.value)
}

function openView(view: "profile"): void {
  emit("openView", view)
}

function logout(): void {
  emit("logout")
}

function updatePlanMode(value: boolean): void {
  emit("updatePlanMode", value)
}

function updateLanguage(value: unknown): void {
  if (typeof value === "string") emit("updateLanguage", value)
}

function updatePermissionMode(value: unknown): void {
  if (typeof value === "string") emit("updatePermissionMode", value)
}

function updateDatasource(value: unknown): void {
  if (typeof value === "string") emit("updateDatasource", value)
}
</script>
<template>
    <SidebarFooter class="px-3 pb-3 pt-1.5">
      <DropdownMenu
        v-model:open="userProfileOpen"
        modal
      >
        <DropdownMenuTrigger as-child>
          <Button
            variant="ghost"
            class="h-12 w-full min-w-0 justify-start rounded-lg px-2 py-1.5 hover:bg-sidebar-accent/80"
          >
            <Avatar class="size-8 shrink-0 text-primary">
              <AvatarFallback class="bg-primary/10 font-semibold text-primary">{{ userFallback }}</AvatarFallback>
            </Avatar>
            <span class="min-w-0 flex-1 text-left">
              <span class="block truncate text-sm font-semibold leading-5">{{ userLabel }}</span>
              <span class="block truncate text-xs font-normal leading-4 text-muted-foreground">{{ userMeta }}</span>
            </span>
            <ChevronRightIcon
              class="text-muted-foreground"
              data-icon="inline-end"
            />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          side="top"
          align="start"
          :avoid-collisions="false"
          class="w-72 overflow-hidden rounded-2xl p-0 shadow-lg"
        >
            <div class="px-3 pb-3 pt-3">
              <div class="flex items-center gap-3 rounded-xl bg-muted/35 p-2">
                <Avatar class="size-11 shrink-0 text-primary">
                  <AvatarFallback class="bg-primary/10 font-semibold text-primary">{{ userFallback }}</AvatarFallback>
                </Avatar>
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-semibold leading-5">{{ userLabel }}</div>
                  <div class="truncate text-xs leading-4 text-muted-foreground">{{ props.auth.user?.username || FALLBACK_USERNAME_LABEL }}</div>
                  <div class="mt-1.5 flex flex-wrap gap-1.5">
                    <Badge
                      variant="secondary"
                      class="h-5 px-1.5 text-xs"
                    >
                      {{ userRoleLabel }}
                    </Badge>
                    <Badge
                      variant="outline"
                      class="h-5 bg-background/70 px-1.5 text-xs"
                    >
                      {{ userStatusLabel }}
                    </Badge>
                  </div>
                </div>
              </div>

              <dl class="mt-2 grid gap-1.5 text-xs">
                <div class="rounded-xl bg-muted/30 p-2.5">
                  <div class="flex items-center">
                    <dt class="text-muted-foreground">当前数据源</dt>
                  </div>
                  <dd class="mt-1.5 flex min-w-0 items-center gap-2">
                    <span class="min-w-0 flex-1 truncate text-sm font-semibold">{{ currentDatasourceLabel }}</span>
                    <Button
                      variant="ghost"
                      :disabled="!canTestDatasource"
                      :aria-label="datasourceTestActionLabel"
                      :title="datasourceConnectionStatusLabel"
                      :class="datasourceTestResultClass"
                      @click.stop="runDatasourceTest"
                    >
                      <LoaderCircleIcon
                        v-if="datasourceTestIconState === 'loading'"
                        :class="[datasourceTestStatusIconClass, 'animate-spin']"
                        data-icon="inline-start"
                      />
                      <CircleCheckIcon
                        v-else-if="datasourceTestIconState === 'success'"
                        :class="datasourceTestStatusIconClass"
                        data-icon="inline-start"
                      />
                      <CircleXIcon
                        v-else-if="datasourceTestIconState === 'failed'"
                        :class="datasourceTestStatusIconClass"
                        data-icon="inline-start"
                      />
                      <span
                        v-else
                        class="size-2 shrink-0 rounded-full bg-current opacity-50"
                        data-icon="inline-start"
                      />
                      <span
                        class="min-w-0 truncate"
                        role="status"
                        aria-live="polite"
                      >
                        {{ datasourceConnectionStatusDisplayLabel }}
                      </span>
                    </Button>
                  </dd>
                </div>
                <div
                  v-if="props.auth.user?.department"
                  class="grid grid-cols-[4.75rem_minmax(0,1fr)] items-center gap-2 px-2.5 py-0.5"
                >
                  <dt class="text-muted-foreground">部门</dt>
                  <dd class="truncate font-medium">{{ props.auth.user.department }}</dd>
                </div>
                <div
                  v-if="props.auth.user?.title"
                  class="grid grid-cols-[4.75rem_minmax(0,1fr)] items-center gap-2 px-2.5 py-0.5"
                >
                  <dt class="text-muted-foreground">职位</dt>
                  <dd class="truncate font-medium">{{ props.auth.user.title }}</dd>
                </div>
                <div
                  v-if="props.auth.user?.email"
                  class="grid grid-cols-[4.75rem_minmax(0,1fr)] items-center gap-2 px-2.5 py-0.5"
                >
                  <dt class="text-muted-foreground">邮箱</dt>
                  <dd class="truncate font-medium">{{ props.auth.user.email }}</dd>
                </div>
              </dl>
            </div>

            <DropdownMenuSeparator />

            <DropdownMenuGroup class="p-1.5">
              <DropdownMenuItem
                class="h-10 rounded-xl px-2.5 text-sm"
                @select="openView('profile')"
              >
                <UserRoundIcon />
                <span>个人设置</span>
              </DropdownMenuItem>

              <DropdownMenuSeparator />

              <DropdownMenuItem
                class="h-10 rounded-xl px-2.5 text-sm"
                @select.prevent="togglePlanMode"
              >
                <ListChecksIcon />
                <span>计划模式</span>
                <span :class="profileMenuSwitchClass">
                  <Switch
                    :model-value="props.workspace.planMode.value"
                    size="sm"
                    aria-label="计划模式"
                    @click.stop
                    @update:model-value="updatePlanMode"
                  />
                </span>
              </DropdownMenuItem>

              <DropdownMenuSub>
                <DropdownMenuSubTrigger
                  :disabled="!hasDatasourceOptions"
                  :class="profileMenuSubTriggerClass"
                >
                  <DatabaseIcon />
                  <span>切换数据源</span>
                  <DropdownMenuShortcut :class="profileDatasourceMenuValueClass">{{ currentDatasourceLabel }}</DropdownMenuShortcut>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent class="w-52 rounded-2xl">
                  <DropdownMenuRadioGroup
                    :model-value="currentDatasourceName"
                    @update:model-value="updateDatasource"
                  >
                    <DropdownMenuRadioItem
                      v-for="datasource in datasourceOptions"
                      :key="datasource.value"
                      :value="datasource.value"
                    >
                      {{ datasource.label }}
                    </DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>

              <DropdownMenuSub>
                <DropdownMenuSubTrigger :class="profileMenuSubTriggerClass">
                  <LanguagesIcon />
                  <span>语言</span>
                  <DropdownMenuShortcut :class="profileMenuValueClass">{{ languageLabel }}</DropdownMenuShortcut>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent class="w-40 rounded-2xl">
                  <DropdownMenuRadioGroup
                    :model-value="props.workspace.language.value"
                    @update:model-value="updateLanguage"
                  >
                    <DropdownMenuRadioItem value="zh">中文</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem value="en">英文</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>

              <DropdownMenuSub>
                <DropdownMenuSubTrigger :class="profileMenuSubTriggerClass">
                  <ShieldCheckIcon />
                  <span>权限模式</span>
                  <DropdownMenuShortcut :class="profileMenuValueClass">{{ permissionModeLabel }}</DropdownMenuShortcut>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent class="w-44 rounded-2xl">
                  <DropdownMenuRadioGroup
                    :model-value="props.workspace.permissionMode.value"
                    @update:model-value="updatePermissionMode"
                  >
                    <DropdownMenuRadioItem value="normal">普通</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem v-if="canUseElevatedPermissionMode" value="auto">自动</DropdownMenuRadioItem>
                    <DropdownMenuRadioItem v-if="canUseElevatedPermissionMode" value="dangerous">危险</DropdownMenuRadioItem>
                  </DropdownMenuRadioGroup>
                </DropdownMenuSubContent>
              </DropdownMenuSub>

              <DropdownMenuSeparator />

              <DropdownMenuItem
                class="h-10 rounded-xl px-2.5 text-sm text-destructive focus:text-destructive"
                @select="logout"
              >
                <LogOutIcon />
                <span>退出登录</span>
              </DropdownMenuItem>
            </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarFooter>
</template>
