<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { watchDebounced } from "@vueuse/core"
import { EyeIcon, PlusIcon, SearchIcon, Trash2Icon } from "@lucide/vue"
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
import type { AdminGrantsTabProps } from "@/features/admin/types"
import {
  matchesKeyword,
  normalizedSearch,
  searchKeyword,
  type GrantEffectFilter,
} from "@/features/admin/tab-utils"

const props = defineProps<AdminGrantsTabProps>()

const grantEffectFilter = shallowRef<GrantEffectFilter>("all")
const grantSearchKeyword = shallowRef("")

watchDebounced(
  [grantEffectFilter, grantSearchKeyword],
  () => {
    if (props.activeTab !== "grants") return
    props.overview.applyGrantListFilters({
      effect: grantEffectFilter.value === "all" ? undefined : grantEffectFilter.value,
      search: normalizedSearch(grantSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

const filteredGrants = computed(() => {
  const effectFilter = grantEffectFilter.value
  const keyword = searchKeyword(grantSearchKeyword.value)

  return props.overview.data.value.datasourceGrants.filter((grant) => {
    if (effectFilter !== "all" && grant.effect !== effectFilter) {
      return false
    }

    return matchesKeyword(keyword, [
      grant.subject_type,
      grant.subject_id,
      grant.datasource_key,
      grant.effect,
      props.formatScope(grant.scope),
    ])
  })
})
</script>
<template>
    <TabsContent
      v-if="canViewDatasourceGrants"
      value="grants"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1 gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">数据授权</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="grantEffectFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="授权效果"
              >
                <SelectValue placeholder="全部效果" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部效果</SelectItem>
                  <SelectItem value="allow">allow</SelectItem>
                  <SelectItem value="deny">deny</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="grantSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索主体 / 数据源 / 范围"
                aria-label="搜索数据授权"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="overview.openCreateGrantDialog"
            >
              <PlusIcon data-icon="inline-start" />
              新增授权
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="grant in filteredGrants"
              :key="grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
              :title="`${grant.subject_type} / ${grant.subject_id}`"
              :description="grant.datasource_key"
            >
              <template #status>
                <Badge :variant="grant.effect === 'allow' ? 'default' : 'destructive'">
                  {{ grant.effect }}
                </Badge>
              </template>
              <span class="break-all">范围 {{ formatScope(grant.scope) }}</span>
              <span>更新于 {{ formatOptionalDate(grant.updated_at || grant.created_at) }}</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="requestGrantDetail(grant)"
                >
                  <EyeIcon data-icon="inline-start" />
                  详情
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="overview.deletingGrantKey.value === grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
                  @click="overview.deleteGrant(grant)"
                >
                  <Trash2Icon data-icon="inline-start" />
                  删除
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredGrants.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.datasourceGrants.length === 0 ? "暂无数据授权" : "没有匹配的数据授权" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>主体</TableHead>
                <TableHead>数据源</TableHead>
                <TableHead class="text-center">效果</TableHead>
                <TableHead>范围</TableHead>
                <TableHead class="text-center">更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="grant in filteredGrants"
                :key="grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
              >
                <TableCell class="font-medium">{{ grant.subject_type }} / {{ grant.subject_id }}</TableCell>
                <TableCell>{{ grant.datasource_key }}</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="grant.effect === 'allow' ? 'default' : 'destructive'">
                    {{ grant.effect }}
                  </Badge>
                </TableCell>
                <TableCell class="max-w-md truncate">{{ formatScope(grant.scope) }}</TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(grant.updated_at || grant.created_at) }}</TableCell>
                <TableCell>
                  <div class="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      @click="requestGrantDetail(grant)"
                    >
                      <EyeIcon data-icon="inline-start" />
                      详情
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="overview.deletingGrantKey.value === grantKey(grant.subject_type, grant.subject_id, grant.datasource_key)"
                      @click="overview.deleteGrant(grant)"
                    >
                      <Trash2Icon data-icon="inline-start" />
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredGrants.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.datasourceGrants.length === 0 ? "暂无数据授权" : "没有匹配的数据授权" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.grantPagination.currentPage.value"
            :page-size="overview.grantPagination.pageSize.value"
            :has-previous="overview.grantPagination.hasPrevious.value"
            :has-more="overview.grantPagination.hasMore.value"
            :item-count="overview.data.value.datasourceGrants.length"
            :loading="overview.loading.value"
            @previous="overview.grantPageActions.previous"
            @next="overview.grantPageActions.next"
            @update:page-size="overview.grantPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

</template>
