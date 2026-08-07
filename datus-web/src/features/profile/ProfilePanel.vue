<script setup lang="ts">
import { computed, onMounted, reactive, shallowRef } from "vue"
import {
  CheckCircle2Icon,
  DatabaseIcon,
  KeyRoundIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  UserRoundIcon,
} from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
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
import ProfileHeaderMeta from "@/features/profile/ProfileHeaderMeta.vue"
import PageHeaderToolbar from "@/features/shared/PageHeaderToolbar.vue"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"
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
const principalUser = computed(() => {
  const user = props.auth.user
  return user?.username === principalUserId.value ? user : null
})
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
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 w-full min-w-0 flex-1 flex-col gap-4">
      <Tabs
        :model-value="activeProfileTab"
        :unmount-on-hide="false"
        class="flex min-h-0 min-w-0 flex-1 flex-col gap-4"
        @update:model-value="setActiveProfileTab"
      >
        <PageHeaderToolbar
          title=""
          description="查看账号权限，并管理仅对自己生效的模型和数据源。"
          aria-label="个人设置页头工具栏"
        >
          <template #leading>
            <UserRoundIcon />
          </template>

          <template #meta>
            <ProfileHeaderMeta
              :user="principalUser"
              :user-id="principalUserId"
              :roles="profile.roles.value"
              :is-admin="profile.isAdmin.value"
              :loaded="profile.loaded.value"
            />
          </template>

          <template #navigation>
            <TabsList class="flex h-auto max-w-full !flex-row flex-nowrap justify-start">
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
          </template>

          <template #actions>
            <Button
              variant="outline"
              size="sm"
              :disabled="profile.loading.value"
              @click="loadProfile"
            >
              <RefreshCwIcon
                data-icon="inline-start"
                :class="profile.loading.value && 'animate-spin'"
              />
              刷新
            </Button>
          </template>
        </PageHeaderToolbar>

        <Alert v-if="profile.error.value">
          <ShieldCheckIcon />
          <AlertTitle>加载失败</AlertTitle>
          <AlertDescription>{{ profile.error.value }}</AlertDescription>
        </Alert>

        <div
          v-if="profile.loading.value && !profile.loaded.value"
          class="grid min-h-0 flex-1 gap-3 md:grid-cols-2"
        >
          <Card
            size="default"
            class="min-h-0 min-w-0 w-full flex-1 gap-4"
          >
            <PanelCardHeader
              title="加载中"
              description="正在读取账号和权限信息。"
            />
            <CardContent class="flex min-h-0 flex-1 flex-col gap-3">
              <Skeleton class="h-8 w-full" />
              <Skeleton class="h-8 w-5/6" />
              <Skeleton class="h-8 w-2/3" />
            </CardContent>
          </Card>
          <Card
            size="default"
            class="min-h-0 min-w-0 w-full flex-1 gap-4"
          >
            <PanelCardHeader title="概要" />
            <CardContent class="flex min-h-0 flex-1 flex-col gap-3">
              <Skeleton class="h-7 w-full" />
              <Skeleton class="h-7 w-4/5" />
              <Skeleton class="h-7 w-3/5" />
            </CardContent>
          </Card>
        </div>

        <template v-else>
          <TabsContent
            value="access"
            class="mt-0 flex min-h-0 flex-1 flex-col"
          >
            <div class="grid min-h-0 flex-1 gap-3 md:grid-cols-2">
              <Card
                size="default"
                class="min-h-0 min-w-0 w-full flex-1 gap-4"
              >
                <PanelCardHeader
                  title="可用功能"
                  description="这里只展示当前账号已经开放的能力。"
                />
                <CardContent class="min-h-0 flex-1 px-4 pb-4">
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

              <Card
                size="default"
                class="min-h-0 min-w-0 w-full flex-1 gap-4"
              >
                <PanelCardHeader
                  title="数据源访问"
                  description="展示当前账号可访问或被明确拒绝的数据源范围。"
                />
                <CardContent class="min-h-0 flex-1 overflow-auto px-4 pb-4">
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
            class="mt-0 flex min-h-0 flex-1 flex-col"
          >
            <ModelCredentialsPanel v-if="visitedProfileTabs.has('models')" />
          </TabsContent>

          <TabsContent
            v-if="canManagePersonalDatasources"
            value="datasources"
            class="mt-0 flex min-h-0 flex-1 flex-col"
          >
            <PersonalDatasourcesPanel v-if="visitedProfileTabs.has('datasources')" />
          </TabsContent>
        </template>
      </Tabs>
    </div>
  </section>
</template>
