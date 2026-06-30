<script setup lang="ts">
import { computed, onMounted } from "vue"
import {
  KeyRoundIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  UserRoundIcon,
} from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
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
import type { AuthState } from "@/composables/useAuth"

const props = defineProps<{
  auth: AuthState
}>()

const profile = useProfileOverview()

const principalUserId = computed(() => profile.userId.value === "-" ? props.auth.user?.username ?? "-" : profile.userId.value)
const displayName = computed(() => {
  if (props.auth.user?.username === principalUserId.value) {
    return props.auth.user.realname || props.auth.user.username
  }
  return principalUserId.value
})
const username = computed(() => principalUserId.value)
const userFallback = computed(() => displayName.value.slice(0, 1).toUpperCase())

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value)
}

function grantBadgeVariant(enabled: boolean) {
  return enabled ? "secondary" : "destructive"
}

function loadProfile() {
  void profile.loadProfile()
}

onMounted(loadProfile)
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-y-auto p-4 xl:overflow-hidden">
    <div class="flex min-h-0 flex-1 flex-col gap-3">
      <div class="flex shrink-0 flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">我的权限</h1>
          <p class="text-sm text-muted-foreground">
            当前登录主体的角色、功能权限和数据授权。
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
        class="grid gap-3 xl:min-h-0 xl:flex-1 xl:grid-cols-[minmax(0,1fr)_24rem]"
      >
        <Card>
          <CardHeader>
            <CardTitle class="text-lg">加载中</CardTitle>
            <CardDescription class="text-sm">正在读取当前用户权限上下文。</CardDescription>
          </CardHeader>
          <CardContent class="flex flex-col gap-3">
            <Skeleton class="h-8 w-full" />
            <Skeleton class="h-8 w-5/6" />
            <Skeleton class="h-8 w-2/3" />
          </CardContent>
        </Card>
        <Card>
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
        class="grid gap-3 xl:min-h-0 xl:flex-1 xl:grid-rows-[auto_minmax(0,1fr)]"
      >
        <Card
          size="sm"
          class="shrink-0"
        >
          <CardContent class="grid gap-3 md:grid-cols-[minmax(14rem,0.9fr)_minmax(12rem,0.7fr)_minmax(16rem,1fr)]">
            <div class="flex min-w-0 items-center gap-3">
              <Avatar class="size-10 shrink-0 text-primary">
                <AvatarFallback class="bg-primary/10 font-semibold text-primary">{{ userFallback }}</AvatarFallback>
              </Avatar>
              <div class="min-w-0 flex-1">
                <div class="truncate text-lg font-semibold">{{ displayName }}</div>
                <div class="truncate text-xs text-muted-foreground">
                  {{ profile.projectId.value }} / {{ username }}
                </div>
              </div>
            </div>

            <div class="flex min-w-0 flex-col justify-center gap-2">
              <div class="flex items-center gap-2 text-sm font-medium">
                <UserRoundIcon class="text-muted-foreground" />
                角色
              </div>
              <div class="flex flex-wrap gap-1.5">
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
            </div>

            <div class="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
              <div class="rounded-md border px-3 py-2">
                <div class="text-xs text-muted-foreground">功能</div>
                <div class="font-semibold">{{ profile.enabledFeatures.value.length }}</div>
              </div>
              <div class="rounded-md border px-3 py-2">
                <div class="text-xs text-muted-foreground">数据源</div>
                <div class="font-semibold">{{ profile.allowedDatasourceCount.value }}</div>
              </div>
              <div class="rounded-md border px-3 py-2">
                <div class="text-xs text-muted-foreground">Token</div>
                <div class="font-semibold">{{ formatNumber(profile.totalTokenCount.value) }}</div>
              </div>
              <div class="rounded-md border px-3 py-2">
                <div class="text-xs text-muted-foreground">会话</div>
                <div class="font-semibold">
                  {{ profile.sessions.value.length }} / {{ profile.runningSessionCount.value }}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div class="grid gap-3 xl:min-h-0 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <Card class="xl:flex xl:min-h-0 xl:flex-col xl:overflow-hidden">
            <CardHeader class="px-4 py-3 xl:shrink-0">
              <CardTitle class="text-lg">功能与权限</CardTitle>
              <CardDescription class="text-sm">
                后端由权限集投影出的 feature 可用性和原始权限码。
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-3 px-4 pb-4 xl:min-h-0 xl:flex-1 xl:overflow-hidden">
              <div class="rounded-md border xl:min-h-0 xl:overflow-y-auto">
                <div
                  v-for="feature in profile.featureList.value"
                  :key="feature.code"
                  class="flex items-center justify-between gap-3 border-b px-3 py-2 last:border-b-0"
                >
                  <div class="min-w-0">
                    <div class="truncate text-sm font-medium">{{ feature.label }}</div>
                    <div class="truncate text-xs text-muted-foreground">{{ feature.code }}</div>
                  </div>
                  <Badge :variant="feature.enabled ? 'secondary' : 'outline'">
                    {{ feature.enabled ? "可用" : "关闭" }}
                  </Badge>
                </div>
                <div
                  v-if="profile.featureList.value.length === 0"
                  class="px-3 py-6 text-center text-sm text-muted-foreground"
                >
                  没有功能开关数据。
                </div>
              </div>

              <div class="flex shrink-0 flex-col gap-2">
                <div class="flex items-center gap-2 text-sm font-medium">
                  <KeyRoundIcon class="text-muted-foreground" />
                  权限码
                </div>
                <div class="max-h-28 overflow-y-auto rounded-md border p-2">
                  <div class="flex flex-wrap gap-1.5">
                    <Badge
                      v-for="permission in profile.permissions.value"
                      :key="permission"
                      variant="secondary"
                    >
                      {{ permission }}
                    </Badge>
                    <span
                      v-if="profile.permissions.value.length === 0"
                      class="text-sm text-muted-foreground"
                    >
                      无权限项
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card class="xl:flex xl:min-h-0 xl:flex-col xl:overflow-hidden">
            <CardHeader class="px-4 py-3 xl:shrink-0">
              <CardTitle class="text-lg">数据源授权</CardTitle>
              <CardDescription class="text-sm">
                当前请求上下文中的有效 datasource grant；后端仍是最终授权边界。
              </CardDescription>
            </CardHeader>
            <CardContent class="overflow-x-auto px-4 pb-4 xl:min-h-0 xl:flex-1 xl:overflow-auto">
              <div class="min-w-full">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>数据源</TableHead>
                      <TableHead>决策</TableHead>
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
                          {{ grant.effect }}
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
                      当前用户没有显式数据源授权。
                    </TableEmpty>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  </section>
</template>
