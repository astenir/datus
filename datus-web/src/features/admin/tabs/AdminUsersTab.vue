<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { watchDebounced } from "@vueuse/core"
import { toast } from "vue-sonner"
import { EyeIcon, PencilIcon, SearchIcon, UserCheckIcon, UserPlusIcon, UserXIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { TabsContent } from "@/components/ui/tabs"
import AdminMobileRecord from "@/features/admin/AdminMobileRecord.vue"
import AdminPaginationBar from "@/features/admin/AdminPaginationBar.vue"
import type { AdminUsersTabProps } from "@/features/admin/types"
import { userDisableBlockedReason as disableBlockedReasonForUser } from "@/features/admin/user-disable-guard"
import {
  enabledFilterValue,
  matchesEnabledStatus,
  matchesKeyword,
  normalizedSearch,
  searchKeyword,
  type EnabledStatusFilter,
} from "@/features/admin/tab-utils"
import { usePermission } from "@/composables/usePermission"
import type { AdminUser } from "@/types/admin"

const props = defineProps<AdminUsersTabProps>()
const permission = usePermission()
const currentUserId = computed(() => permission.permissions.value?.user_id.trim() ?? "")

const userStatusFilter = shallowRef<EnabledStatusFilter>("all")
const userSearchKeyword = shallowRef("")

watchDebounced(
  [userStatusFilter, userSearchKeyword],
  () => {
    if (props.activeTab !== "users") return
    props.users.applyListFilters({
      enabled: enabledFilterValue(userStatusFilter.value),
      search: normalizedSearch(userSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

const filteredUsers = computed(() => {
  const statusFilter = userStatusFilter.value
  const keyword = searchKeyword(userSearchKeyword.value)

  return props.users.users.value.filter((user) =>
    matchesEnabledStatus(statusFilter, user.enabled)
    && matchesKeyword(keyword, [
      user.user_id,
      user.display_name,
      user.email,
      user.external_user_id,
      user.department,
      user.title,
      user.role_ids?.join(" "),
    ])
  )
})

function userDisableBlockedReason(user: AdminUser): string | null {
  return disableBlockedReasonForUser(user, props.roles.roles.value, currentUserId.value)
}

function requestSetUserEnabled(user: AdminUser, enabled: boolean): void {
  const blockedReason = enabled ? null : userDisableBlockedReason(user)
  if (blockedReason) {
    toast.error(blockedReason)
    return
  }
  void props.users.setUserEnabled(user, enabled)
}
</script>
<template>
    <TabsContent
      v-if="canViewUsers"
      value="users"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1 gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">用户</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="userStatusFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="用户状态"
              >
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="enabled">启用</SelectItem>
                  <SelectItem value="disabled">禁用</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="userSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 ID / 姓名 / 邮箱"
                aria-label="搜索用户"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="users.openAddUserDialog"
            >
              <UserPlusIcon data-icon="inline-start" />
              新增用户
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="user in filteredUsers"
              :key="user.user_id"
              :title="user.display_name || user.user_id"
              :description="user.display_name ? user.user_id : user.email || undefined"
            >
              <template #status>
                <Badge :variant="user.enabled ? 'default' : 'secondary'">
                  {{ user.enabled ? "启用" : "禁用" }}
                </Badge>
              </template>
              <span>{{ user.department || "未设置部门" }}</span>
              <span>角色 {{ user.role_count }}</span>
              <span>直接授权 {{ user.direct_datasource_grant_count }}</span>
              <span>最近活跃 {{ formatOptionalDate(user.last_seen_at || user.updated_at || user.created_at) }}</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="requestUserDetail(user.user_id)"
                >
                  <EyeIcon data-icon="inline-start" />
                  详情
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  @click="users.openEditUserDialog(user)"
                >
                  <PencilIcon data-icon="inline-start" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="Boolean(userDisableBlockedReason(user))"
                  :title="userDisableBlockedReason(user) ?? undefined"
                  @click="requestSetUserEnabled(user, !user.enabled)"
                >
                  <UserXIcon
                    v-if="user.enabled"
                    data-icon="inline-start"
                  />
                  <UserCheckIcon
                    v-else
                    data-icon="inline-start"
                  />
                  {{ user.enabled ? "禁用" : "启用" }}
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredUsers.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ users.users.value.length === 0 ? "暂无用户" : "没有匹配的用户" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>User ID</TableHead>
                <TableHead>姓名</TableHead>
                <TableHead>部门</TableHead>
                <TableHead class="text-center">角色</TableHead>
                <TableHead class="text-center">直接授权</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead class="text-center">最近活跃</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="user in filteredUsers"
                :key="user.user_id"
              >
                <TableCell class="font-medium">{{ user.user_id }}</TableCell>
                <TableCell>{{ user.display_name || "-" }}</TableCell>
                <TableCell>{{ user.department || "-" }}</TableCell>
                <TableCell class="text-center">
                  <Badge variant="outline">{{ user.role_count }}</Badge>
                </TableCell>
                <TableCell class="text-center">
                  <Badge variant="outline">{{ user.direct_datasource_grant_count }}</Badge>
                </TableCell>
                <TableCell class="text-center">
                  <Badge :variant="user.enabled ? 'default' : 'secondary'">
                    {{ user.enabled ? "启用" : "禁用" }}
                  </Badge>
                </TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(user.last_seen_at || user.updated_at || user.created_at) }}</TableCell>
                <TableCell>
                  <div class="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      @click="requestUserDetail(user.user_id)"
                    >
                      <EyeIcon data-icon="inline-start" />
                      详情
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      @click="users.openEditUserDialog(user)"
                    >
                      <PencilIcon data-icon="inline-start" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="Boolean(userDisableBlockedReason(user))"
                      :title="userDisableBlockedReason(user) ?? undefined"
                      @click="requestSetUserEnabled(user, !user.enabled)"
                    >
                      <UserXIcon
                        v-if="user.enabled"
                        data-icon="inline-start"
                      />
                      <UserCheckIcon
                        v-else
                        data-icon="inline-start"
                      />
                      {{ user.enabled ? "禁用" : "启用" }}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredUsers.length === 0">
                <TableCell
                  colspan="8"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ users.users.value.length === 0 ? "暂无用户" : "没有匹配的用户" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="users.pagination.currentPage.value"
            :page-size="users.pagination.pageSize.value"
            :has-previous="users.pagination.hasPrevious.value"
            :has-more="users.pagination.hasMore.value"
            :item-count="users.users.value.length"
            :loading="users.loading.value"
            @previous="users.loadPreviousPage"
            @next="users.loadNextPage"
            @update:page-size="users.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

</template>
