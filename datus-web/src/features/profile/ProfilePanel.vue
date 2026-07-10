<script setup lang="ts">
import { computed, onMounted, reactive, shallowRef } from "vue"
import {
  CheckCircle2Icon,
  DatabaseIcon,
  KeyRoundIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
} from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useProfileOverview } from "@/composables/useProfileOverview"
import { usePermission } from "@/composables/usePermission"
import ModelCredentialsPanel from "@/features/profile/ModelCredentialsPanel.vue"
import PersonalDatasourcesPanel from "@/features/profile/PersonalDatasourcesPanel.vue"
import { workspaceAccessFromPermission } from "@/features/workspace/access"
import type { AuthState } from "@/composables/useAuth"

const props = defineProps<{
  auth: AuthState
}>()

const profile = useProfileOverview()
const permission = usePermission()
const activeProfileTab = shallowRef("access")
const visitedProfileTabs = reactive(new Set(["access"]))

const principalUserId = computed(() => profile.userId.value === "-" ? props.auth.user?.username ?? "-" : profile.userId.value)
const displayName = computed(() => {
  if (props.auth.user?.username === principalUserId.value) {
    return props.auth.user.realname || props.auth.user.username
  }
  return principalUserId.value
})
const username = computed(() => principalUserId.value)
const userFallback = computed(() => displayName.value.slice(0, 1).toUpperCase())
const hasChatFeature = computed(() =>
  profile.features.value.chat === true ||
  profile.permissions.value.includes("*") ||
  profile.permissions.value.includes("module.chat"),
)
const viewAccess = computed(() => workspaceAccessFromPermission(permission))
const canManagePersonalDatasources = computed(() =>
  viewAccess.value.canViewKnowledge ||
  profile.features.value.datasource_catalog === true ||
  profile.permissions.value.includes("*") ||
  profile.permissions.value.includes("module.datasource_catalog"),
)

function grantBadgeVariant(enabled: boolean) {
  return enabled ? "secondary" : "outline"
}

function grantEffectLabel(enabled: boolean) {
  return enabled ? "允许" : "拒绝"
}

function loadProfile() {
  void profile.loadProfile()
}

function setActiveProfileTab(value: string | number) {
  const tab = String(value)
  activeProfileTab.value = tab
  visitedProfileTabs.add(tab)
}

onMounted(loadProfile)
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-y-auto p-4">
    <div class="mx-auto flex w-full max-w-7xl min-w-0 flex-col gap-4">
      <div class="flex shrink-0 flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">个人设置</h1>
          <p class="text-sm text-muted-foreground">
            查看账号权限，并管理仅对自己生效的模型和数据源。
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          :disabled="profile.loading.value"
          @click="loadProfile"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>

      <Alert v-if="profile.error.value">
        <ShieldCheckIcon />
        <AlertTitle>加载失败</AlertTitle>
        <AlertDescription>{{ profile.error.value }}</AlertDescription>
      </Alert>

      <div
        v-if="profile.loading.value && !profile.loaded.value"
        class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_20rem]"
      >
        <Card size="sm">
          <CardHeader>
            <CardTitle class="text-lg">加载中</CardTitle>
            <CardDescription class="text-sm">正在读取账号和权限信息。</CardDescription>
          </CardHeader>
          <CardContent class="flex flex-col gap-3">
            <Skeleton class="h-8 w-full" />
            <Skeleton class="h-8 w-5/6" />
            <Skeleton class="h-8 w-2/3" />
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle class="text-lg">概要</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-3">
            <Skeleton class="h-7 w-full" />
            <Skeleton class="h-7 w-4/5" />
            <Skeleton class="h-7 w-3/5" />
          </CardContent>
        </Card>
      </div>

      <div
        v-else
        class="flex min-w-0 flex-col gap-4"
      >
        <Card
          size="sm"
          class="shrink-0"
        >
          <CardContent class="grid gap-4 md:grid-cols-[minmax(14rem,1fr)_minmax(18rem,1.4fr)] md:items-center">
            <div class="flex min-w-0 items-center gap-3">
              <Avatar class="size-12 shrink-0 text-primary">
                <AvatarFallback class="bg-primary/10 font-semibold text-primary">{{ userFallback }}</AvatarFallback>
              </Avatar>
              <div class="min-w-0 flex-1">
                <div class="truncate text-lg font-semibold">{{ displayName }}</div>
                <div class="truncate text-xs text-muted-foreground">
                  {{ username }} · 项目 {{ profile.projectId.value }}
                </div>
              </div>
            </div>

            <div class="flex min-w-0 flex-col gap-2 md:border-l md:pl-4">
              <div class="text-xs font-medium text-muted-foreground">当前角色</div>
              <div class="flex min-h-6 flex-wrap items-center gap-1.5">
                <Badge
                  v-if="profile.isAdmin.value"
                  variant="default"
                >
                  全局管理
                </Badge>
                <Badge
                  v-for="role in profile.roles.value"
                  :key="role"
                  variant="outline"
                >
                  {{ role }}
                </Badge>
                <span
                  v-if="profile.roles.value.length === 0"
                  class="text-sm text-muted-foreground"
                >
                  无角色
                </span>
              </div>
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span>{{ profile.enabledFeatures.value.length }} 项功能可用</span>
                <span>{{ profile.allowedDatasourceCount.value }} 个数据源可访问</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Tabs
          :model-value="activeProfileTab"
          :unmount-on-hide="false"
          class="min-w-0 gap-3"
          @update:model-value="setActiveProfileTab"
        >
          <TabsList class="flex h-auto max-w-full !flex-row flex-wrap justify-start">
            <TabsTrigger value="access">
              <ShieldCheckIcon />
              权限概览
            </TabsTrigger>
            <TabsTrigger
              v-if="hasChatFeature"
              value="models"
            >
              <KeyRoundIcon />
              我的模型
            </TabsTrigger>
            <TabsTrigger
              v-if="canManagePersonalDatasources"
              value="datasources"
            >
              <DatabaseIcon />
              个人数据源
            </TabsTrigger>
          </TabsList>

          <TabsContent
            value="access"
            class="mt-0"
          >
            <div class="grid gap-3 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
              <Card size="sm">
                <CardHeader class="px-4 py-3">
                  <CardTitle class="text-lg">可用功能</CardTitle>
                  <CardDescription class="text-sm">
                    这里只展示当前账号已经开放的能力。
                  </CardDescription>
                </CardHeader>
                <CardContent class="px-4 pb-4">
                  <div
                    v-if="profile.enabledFeatures.value.length > 0"
                    class="flex flex-wrap gap-2"
                  >
                    <Badge
                      v-for="feature in profile.enabledFeatures.value"
                      :key="feature.code"
                      variant="outline"
                      class="h-8 rounded-md px-2.5 text-sm font-normal"
                    >
                      <CheckCircle2Icon class="text-emerald-600 dark:text-emerald-400" />
                      {{ feature.label }}
                    </Badge>
                  </div>
                  <div
                    v-else
                    class="rounded-md border border-dashed px-3 py-8 text-center text-sm text-muted-foreground"
                  >
                    当前账号没有可展示的功能权限。
                  </div>
                </CardContent>
              </Card>

              <Card size="sm">
                <CardHeader class="px-4 py-3">
                  <CardTitle class="text-lg">数据源访问</CardTitle>
                  <CardDescription class="text-sm">
                    展示当前账号可访问或被明确拒绝的数据源范围。
                  </CardDescription>
                </CardHeader>
                <CardContent class="overflow-x-auto px-4 pb-4">
                  <div class="min-w-full">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>数据源</TableHead>
                          <TableHead>访问</TableHead>
                          <TableHead>范围</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow
                          v-for="grant in profile.datasourceGrantList.value"
                          :key="grant.datasource"
                        >
                          <TableCell class="font-medium">{{ grant.datasource }}</TableCell>
                          <TableCell>
                            <Badge :variant="grantBadgeVariant(grant.enabled)">
                              {{ grantEffectLabel(grant.enabled) }}
                            </Badge>
                          </TableCell>
                          <TableCell class="max-w-md truncate text-xs text-muted-foreground">
                            {{ grant.scopeText }}
                          </TableCell>
                        </TableRow>
                        <TableEmpty
                          v-if="profile.datasourceGrantList.value.length === 0"
                          :colspan="3"
                        >
                          当前账号没有单独配置数据源授权。
                        </TableEmpty>
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent
            v-if="hasChatFeature"
            value="models"
            class="mt-0"
          >
            <ModelCredentialsPanel v-if="visitedProfileTabs.has('models')" />
          </TabsContent>

          <TabsContent
            v-if="canManagePersonalDatasources"
            value="datasources"
            class="mt-0"
          >
            <PersonalDatasourcesPanel v-if="visitedProfileTabs.has('datasources')" />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  </section>
</template>
