<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { watchDebounced } from "@vueuse/core"
import { PencilIcon, PlusIcon, SearchIcon, Trash2Icon } from "@lucide/vue"
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
import type { AdminQuotasTabProps } from "@/features/admin/types"
import {
  enabledFilterValue,
  matchesEnabledStatus,
  matchesKeyword,
  normalizedSearch,
  searchKeyword,
  type EnabledStatusFilter,
} from "@/features/admin/tab-utils"

const props = defineProps<AdminQuotasTabProps>()

const quotaStatusFilter = shallowRef<EnabledStatusFilter>("all")
const quotaSearchKeyword = shallowRef("")

watchDebounced(
  [quotaStatusFilter, quotaSearchKeyword],
  () => {
    if (props.activeTab !== "quotas") return
    props.overview.applyQuotaListFilters({
      enabled: enabledFilterValue(quotaStatusFilter.value),
      search: normalizedSearch(quotaSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

const filteredQuotas = computed(() => {
  const statusFilter = quotaStatusFilter.value
  const keyword = searchKeyword(quotaSearchKeyword.value)

  return props.overview.data.value.quotas.filter((quota) =>
    matchesEnabledStatus(statusFilter, quota.enabled)
    && matchesKeyword(keyword, [
      quota.subject_type,
      quota.subject_id,
      quota.resource,
      quota.limit,
      quota.window_seconds,
    ])
  )
})
</script>
<template>
    <TabsContent
      v-if="canViewQuotas"
      value="quotas"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1 gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">额度与用量</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="quotaStatusFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="额度状态"
              >
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="enabled">启用</SelectItem>
                  <SelectItem value="disabled">停用</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="quotaSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索主体 / 资源"
                aria-label="搜索额度"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="overview.openCreateQuotaDialog"
            >
              <PlusIcon data-icon="inline-start" />
              新增额度
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="quota in filteredQuotas"
              :key="`${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
              :title="`${quota.subject_type} / ${quota.subject_id || '*'}`"
              :description="quota.resource"
            >
              <template #status>
                <Badge :variant="quota.enabled ? 'default' : 'secondary'">
                  {{ quota.enabled ? "启用" : "停用" }}
                </Badge>
              </template>
              <span>额度 {{ quota.limit }}</span>
              <span>已用 {{ usageByKey.get(`${quota.subject_type}:${quota.subject_id}:${quota.resource}`)?.used ?? 0 }}</span>
              <span>窗口 {{ quota.window_seconds }}s</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="overview.openEditQuotaDialog(quota)"
                >
                  <PencilIcon data-icon="inline-start" />
                  编辑
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="overview.deletingQuotaKey.value === `${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
                  @click="overview.deleteQuota(quota)"
                >
                  <Trash2Icon data-icon="inline-start" />
                  删除
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredQuotas.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.quotas.length === 0 ? "暂无额度配置" : "没有匹配的额度配置" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>主体</TableHead>
                <TableHead>资源</TableHead>
                <TableHead class="text-center">额度</TableHead>
                <TableHead class="text-center">已用</TableHead>
                <TableHead class="text-center">窗口</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="quota in filteredQuotas"
                :key="`${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
              >
                <TableCell class="font-medium">{{ quota.subject_type }} / {{ quota.subject_id || "*" }}</TableCell>
                <TableCell>{{ quota.resource }}</TableCell>
                <TableCell class="text-center">{{ quota.limit }}</TableCell>
                <TableCell class="text-center">
                  {{ usageByKey.get(`${quota.subject_type}:${quota.subject_id}:${quota.resource}`)?.used ?? 0 }}
                </TableCell>
                <TableCell class="text-center">{{ quota.window_seconds }}s</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="quota.enabled ? 'default' : 'secondary'">
                    {{ quota.enabled ? "启用" : "停用" }}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div class="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      @click="overview.openEditQuotaDialog(quota)"
                    >
                      <PencilIcon data-icon="inline-start" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="overview.deletingQuotaKey.value === `${quota.subject_type}:${quota.subject_id}:${quota.resource}`"
                      @click="overview.deleteQuota(quota)"
                    >
                      <Trash2Icon data-icon="inline-start" />
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredQuotas.length === 0">
                <TableCell
                  colspan="7"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.quotas.length === 0 ? "暂无额度配置" : "没有匹配的额度配置" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.quotaPagination.currentPage.value"
            :page-size="overview.quotaPagination.pageSize.value"
            :has-previous="overview.quotaPagination.hasPrevious.value"
            :has-more="overview.quotaPagination.hasMore.value"
            :item-count="overview.data.value.quotas.length"
            :loading="overview.loading.value"
            @previous="overview.quotaPageActions.previous"
            @next="overview.quotaPageActions.next"
            @update:page-size="overview.quotaPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

</template>
