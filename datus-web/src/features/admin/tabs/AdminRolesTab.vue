<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { watchDebounced } from "@vueuse/core"
import { EyeIcon, PencilIcon, PlusIcon, SearchIcon, Trash2Icon } from "@lucide/vue"
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
import AdminMobileRecord from "@/features/admin/AdminMobileRecord.vue"
import AdminPaginationBar from "@/features/admin/AdminPaginationBar.vue"
import type { AdminRolesTabProps } from "@/features/admin/types"
import {
  matchesKeyword,
  normalizedSearch,
  searchKeyword,
  type RoleTypeFilter,
} from "@/features/admin/tab-utils"
import { permissionBadgeItems } from "@/lib/permission-labels"

const props = defineProps<AdminRolesTabProps>()

const roleTypeFilter = shallowRef<RoleTypeFilter>("all")
const roleSearchKeyword = shallowRef("")

watchDebounced(
  [roleTypeFilter, roleSearchKeyword],
  () => {
    if (props.activeTab !== "roles") return
    props.roles.applyListFilters({
      builtIn: roleTypeFilter.value === "all" ? undefined : roleTypeFilter.value === "built_in",
      search: normalizedSearch(roleSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

const filteredRoles = computed(() => {
  const typeFilter = roleTypeFilter.value
  const keyword = searchKeyword(roleSearchKeyword.value)

  return props.roles.roles.value.filter((role) => {
    if (typeFilter === "built_in" && !role.built_in) {
      return false
    }
    if (typeFilter === "custom" && role.built_in) {
      return false
    }

    return matchesKeyword(keyword, [
      role.role_id,
      role.name,
      role.description,
      role.permissions?.join(" "),
    ])
  })
})
</script>
<template>
    <TabsContent
      v-if="canViewRoles"
      value="roles"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1 gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">角色</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="roleTypeFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="角色类型"
              >
                <SelectValue placeholder="全部类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部类型</SelectItem>
                  <SelectItem value="built_in">内置</SelectItem>
                  <SelectItem value="custom">自定义</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="roleSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 Role ID / 名称 / 权限"
                aria-label="搜索角色"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="roles.openCreateDialog"
            >
              <PlusIcon data-icon="inline-start" />
              新增角色
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="role in filteredRoles"
              :key="role.role_id"
              :title="role.name"
              :description="role.role_id"
            >
              <template #status>
                <Badge :variant="role.built_in ? 'secondary' : 'outline'">
                  {{ role.built_in ? "内置" : "自定义" }}
                </Badge>
              </template>
              <span>权限 {{ role.permissions?.length || 0 }}</span>
              <span>更新于 {{ formatOptionalDate(role.updated_at || role.created_at) }}</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="requestRoleDetail(role.role_id)"
                >
                  <EyeIcon data-icon="inline-start" />
                  详情
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  @click="roles.openEditDialog(role)"
                >
                  <PencilIcon data-icon="inline-start" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="role.built_in"
                  @click="roles.requestDeleteRole(role)"
                >
                  <Trash2Icon data-icon="inline-start" />
                  删除
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredRoles.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ roles.roles.value.length === 0 ? "暂无角色" : "没有匹配的角色" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>Role ID</TableHead>
                <TableHead>名称</TableHead>
                <TableHead class="text-center">类型</TableHead>
                <TableHead>权限</TableHead>
                <TableHead class="text-center">更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="role in filteredRoles"
                :key="role.role_id"
              >
                <TableCell class="font-medium">{{ role.role_id }}</TableCell>
                <TableCell>{{ role.name }}</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="role.built_in ? 'secondary' : 'outline'">
                    {{ role.built_in ? "内置" : "自定义" }}
                  </Badge>
                </TableCell>
                <TableCell class="max-w-lg">
                  <div
                    v-if="role.permissions?.length"
                    class="flex flex-wrap gap-2"
                  >
                    <Badge
                      v-for="permission in permissionBadgeItems(role.permissions)"
                      :key="permission.code"
                      :variant="permission.kind === 'wildcard' ? 'destructive' : 'secondary'"
                    >
                      {{ permission.label }}
                    </Badge>
                  </div>
                  <span
                    v-else
                    class="text-sm text-muted-foreground"
                  >
                    -
                  </span>
                </TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(role.updated_at || role.created_at) }}</TableCell>
                <TableCell>
                  <div class="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      @click="requestRoleDetail(role.role_id)"
                    >
                      <EyeIcon data-icon="inline-start" />
                      详情
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      @click="roles.openEditDialog(role)"
                    >
                      <PencilIcon data-icon="inline-start" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="role.built_in"
                      @click="roles.requestDeleteRole(role)"
                    >
                      <Trash2Icon data-icon="inline-start" />
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredRoles.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ roles.roles.value.length === 0 ? "暂无角色" : "没有匹配的角色" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="roles.pagination.currentPage.value"
            :page-size="roles.pagination.pageSize.value"
            :has-previous="roles.pagination.hasPrevious.value"
            :has-more="roles.pagination.hasMore.value"
            :item-count="roles.roles.value.length"
            :loading="roles.loading.value"
            @previous="roles.loadPreviousPage"
            @next="roles.loadNextPage"
            @update:page-size="roles.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

</template>
