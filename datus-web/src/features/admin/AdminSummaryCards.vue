<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { AdminOverviewController, AdminRoleController, AdminUserController } from "@/features/admin/types"

defineProps<{
  overview: AdminOverviewController
  roles: AdminRoleController
  users: AdminUserController
}>()
</script>

<template>
  <div class="grid gap-3 md:grid-cols-4">
    <Card>
      <CardHeader class="pb-2">
        <CardTitle class="text-sm">用户</CardTitle>
      </CardHeader>
      <CardContent class="flex items-end justify-between gap-3">
        <span class="text-lg font-semibold">{{ users.total.value }}</span>
        <span class="text-xs text-muted-foreground">启用 {{ users.activeUserCount.value }}</span>
      </CardContent>
    </Card>
    <Card>
      <CardHeader class="pb-2">
        <CardTitle class="text-sm">角色</CardTitle>
      </CardHeader>
      <CardContent class="flex items-end justify-between gap-3">
        <span class="text-lg font-semibold">{{ roles.total.value }}</span>
        <span class="text-xs text-muted-foreground">自定义 {{ roles.customRoleCount.value }}</span>
      </CardContent>
    </Card>
    <Card>
      <CardHeader class="pb-2">
        <CardTitle class="text-sm">运行会话</CardTitle>
      </CardHeader>
      <CardContent class="flex items-end justify-between gap-3">
        <span class="text-lg font-semibold">{{ overview.data.value.sessions.length }}</span>
        <span class="text-xs text-muted-foreground">活跃 {{ overview.runningSessionCount.value }}</span>
      </CardContent>
    </Card>
    <Card>
      <CardHeader class="pb-2">
        <CardTitle class="text-sm">授权</CardTitle>
      </CardHeader>
      <CardContent class="flex items-end justify-between gap-3">
        <span class="text-lg font-semibold">{{ overview.grantCount.value }}</span>
        <span class="text-xs text-muted-foreground">数据源 {{ overview.data.value.datasources.length }}</span>
      </CardContent>
    </Card>
  </div>
</template>
