<script setup lang="ts">
import { computed, onMounted } from "vue"
import {
  ActivityIcon,
  DatabaseIcon,
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
const primaryRoleLabel = computed(() => {
  if (profile.isAdmin.value) return "管理员"
  return profile.roles.value[0] || "成员"
})

function formatOptionalDate(value: string | null | undefined) {
  if (!value) return "-"
  return new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatDuration(seconds: number | null | undefined) {
  if (!seconds) return "-"
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时`
  return `${Math.round(seconds / 86400)} 天`
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value)
}

function sessionTitle(value: unknown) {
  if (typeof value === "string" && value.trim()) return value
  return "未命名会话"
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
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">我的权限与用量</h1>
          <p class="text-sm text-muted-foreground">
            当前登录主体的角色、功能权限、数据授权、会话和额度消耗。
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

      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">身份</CardTitle>
          </CardHeader>
          <CardContent class="flex min-w-0 items-center gap-3">
            <Avatar class="size-10 shrink-0 text-primary">
              <AvatarFallback class="bg-primary/10 font-semibold text-primary">{{ userFallback }}</AvatarFallback>
            </Avatar>
            <div class="min-w-0 flex-1">
              <div class="truncate text-lg font-semibold">{{ displayName }}</div>
              <div class="truncate text-xs text-muted-foreground">{{ username }}</div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">角色</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="min-w-0 truncate text-lg font-semibold">{{ primaryRoleLabel }}</span>
            <Badge :variant="profile.isAdmin.value ? 'default' : 'outline'">
              {{ profile.isAdmin.value ? "全局管理" : "普通访问" }}
            </Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">数据源授权</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ profile.allowedDatasourceCount.value }}</span>
            <DatabaseIcon class="shrink-0 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">当前用量</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ formatNumber(profile.totalUsageCount.value) }}</span>
            <span class="text-xs text-muted-foreground">Quota units</span>
          </CardContent>
        </Card>
      </div>

      <div
        v-if="profile.loading.value && !profile.loaded.value"
        class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]"
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
        class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]"
      >
        <div class="flex min-w-0 flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">数据源授权</CardTitle>
              <CardDescription class="text-sm">
                当前请求上下文中的有效 datasource grant；后端仍是最终授权边界。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div class="overflow-x-auto">
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

          <Card>
            <CardHeader>
              <CardTitle class="text-lg">我的会话</CardTitle>
              <CardDescription class="text-sm">
                `/me/sessions` 返回的当前用户会话，不包含其他用户会话。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div class="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>会话</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>轮次</TableHead>
                      <TableHead>Token</TableHead>
                      <TableHead>更新时间</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow
                      v-for="session in profile.sessions.value"
                      :key="session.session_id"
                    >
                      <TableCell class="max-w-sm">
                        <div class="truncate text-sm font-medium">{{ sessionTitle(session.user_query) }}</div>
                        <div class="truncate text-xs text-muted-foreground">{{ session.session_id }}</div>
                      </TableCell>
                      <TableCell>
                        <Badge :variant="session.is_active ? 'secondary' : 'outline'">
                          {{ session.is_active ? "运行中" : "已停止" }}
                        </Badge>
                      </TableCell>
                      <TableCell>{{ session.total_turns }}</TableCell>
                      <TableCell>{{ formatNumber(session.token_count) }}</TableCell>
                      <TableCell>{{ formatOptionalDate(session.last_updated) }}</TableCell>
                    </TableRow>
                    <TableEmpty
                      v-if="profile.sessions.value.length === 0"
                      :colspan="5"
                    >
                      当前用户没有会话记录。
                    </TableEmpty>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle class="text-lg">额度用量</CardTitle>
              <CardDescription class="text-sm">
                `/me/usage` 返回的当前用户 quota 消耗。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div class="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>资源</TableHead>
                      <TableHead>已用</TableHead>
                      <TableHead>窗口</TableHead>
                      <TableHead>更新时间</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow
                      v-for="item in profile.usage.value"
                      :key="`${item.resource}:${item.window_start ?? ''}`"
                    >
                      <TableCell class="font-medium">{{ item.resource || "-" }}</TableCell>
                      <TableCell>{{ formatNumber(item.used) }}</TableCell>
                      <TableCell>
                        <div class="text-sm">{{ formatDuration(item.window_seconds) }}</div>
                        <div class="text-xs text-muted-foreground">{{ formatOptionalDate(item.window_start) }}</div>
                      </TableCell>
                      <TableCell>{{ formatOptionalDate(item.updated_at) }}</TableCell>
                    </TableRow>
                    <TableEmpty
                      v-if="profile.usage.value.length === 0"
                      :colspan="4"
                    >
                      当前用户没有额度消耗记录。
                    </TableEmpty>
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>

        <div class="flex min-w-0 flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">权限摘要</CardTitle>
              <CardDescription class="text-sm">
                当前请求主体的 project、角色和权限集合。
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-4">
              <div class="grid gap-2 text-sm">
                <div class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                  <span class="text-muted-foreground">用户</span>
                  <span class="truncate font-medium">{{ profile.userId.value }}</span>
                </div>
                <div class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                  <span class="text-muted-foreground">项目</span>
                  <span class="truncate font-medium">{{ profile.projectId.value }}</span>
                </div>
                <div class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                  <span class="text-muted-foreground">会话</span>
                  <span class="font-medium">
                    {{ profile.sessions.value.length }} 个，运行中 {{ profile.runningSessionCount.value }}
                  </span>
                </div>
                <div class="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                  <span class="text-muted-foreground">Token</span>
                  <span class="font-medium">{{ formatNumber(profile.totalTokenCount.value) }}</span>
                </div>
              </div>

              <div class="flex flex-col gap-2">
                <div class="flex items-center gap-2 text-sm font-medium">
                  <UserRoundIcon class="text-muted-foreground" />
                  角色
                </div>
                <div class="flex flex-wrap gap-1.5">
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

              <div class="flex flex-col gap-2">
                <div class="flex items-center gap-2 text-sm font-medium">
                  <KeyRoundIcon class="text-muted-foreground" />
                  权限
                </div>
                <div class="max-h-56 overflow-y-auto rounded-md border p-2">
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

          <Card>
            <CardHeader>
              <CardTitle class="text-lg">功能开关</CardTitle>
              <CardDescription class="text-sm">
                后端由权限集投影出的 feature 可用性。
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-2">
              <div
                v-for="feature in profile.featureList.value"
                :key="feature.code"
                class="flex items-center justify-between gap-3 rounded-md border px-3 py-2"
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
                class="rounded-md border px-3 py-6 text-center text-sm text-muted-foreground"
              >
                没有功能开关数据。
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle class="text-lg">快速指标</CardTitle>
            </CardHeader>
            <CardContent class="grid gap-3 text-sm">
              <div class="flex items-center justify-between gap-3">
                <span class="flex items-center gap-2 text-muted-foreground">
                  <ShieldCheckIcon />
                  可用功能
                </span>
                <span class="font-semibold">{{ profile.enabledFeatures.value.length }}</span>
              </div>
              <div class="flex items-center justify-between gap-3">
                <span class="flex items-center gap-2 text-muted-foreground">
                  <DatabaseIcon />
                  授权数据源
                </span>
                <span class="font-semibold">{{ profile.allowedDatasourceCount.value }}</span>
              </div>
              <div class="flex items-center justify-between gap-3">
                <span class="flex items-center gap-2 text-muted-foreground">
                  <ActivityIcon />
                  用量记录
                </span>
                <span class="font-semibold">{{ profile.usage.value.length }}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  </section>
</template>
