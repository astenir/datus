<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { watchDebounced } from "@vueuse/core"
import { EyeIcon, KeyRoundIcon, SearchIcon, Trash2Icon } from "@lucide/vue"
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
import type { AdminSecretsTabProps } from "@/features/admin/types"
import {
  enabledFilterValue,
  matchesEnabledStatus,
  matchesKeyword,
  normalizedSearch,
  searchKeyword,
  type EnabledStatusFilter,
} from "@/features/admin/tab-utils"

const props = defineProps<AdminSecretsTabProps>()

const secretStatusFilter = shallowRef<EnabledStatusFilter>("all")
const secretSearchKeyword = shallowRef("")

watchDebounced(
  [secretStatusFilter, secretSearchKeyword],
  () => {
    if (props.activeTab !== "secrets") return
    props.overview.applySecretListFilters({
      enabled: enabledFilterValue(secretStatusFilter.value),
      search: normalizedSearch(secretSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

const filteredSecrets = computed(() => {
  const statusFilter = secretStatusFilter.value
  const keyword = searchKeyword(secretSearchKeyword.value)

  return props.overview.data.value.secrets.filter((secret) =>
    matchesEnabledStatus(statusFilter, secret.enabled)
    && matchesKeyword(keyword, [
      secret.name,
      secret.provider,
      secret.ref_hint,
      secret.description,
    ])
  )
})
</script>
<template>
    <TabsContent
      v-if="canViewSecrets"
      value="secrets"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1 gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">密钥引用</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="secretStatusFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="密钥状态"
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
                v-model="secretSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索名称 / Provider / 说明"
                aria-label="搜索密钥"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              @click="overview.openCreateSecretDialog"
            >
              <KeyRoundIcon data-icon="inline-start" />
              新增密钥
            </Button>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="secret in filteredSecrets"
              :key="secret.name"
              :title="secret.name"
              :description="secret.description || secret.ref_hint"
            >
              <template #status>
                <Badge :variant="secret.enabled ? 'default' : 'secondary'">
                  {{ secret.enabled ? "启用" : "停用" }}
                </Badge>
              </template>
              <span>Provider {{ secret.provider }}</span>
              <span class="break-all">引用 {{ secret.ref_hint }}</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="requestSecretDetail(secret.name)"
                >
                  <EyeIcon data-icon="inline-start" />
                  详情
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="overview.deletingSecretName.value === secret.name"
                  @click="overview.deleteSecret(secret)"
                >
                  <Trash2Icon data-icon="inline-start" />
                  删除
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredSecrets.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.secrets.length === 0 ? "暂无密钥引用" : "没有匹配的密钥引用" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead class="text-center">Provider</TableHead>
                <TableHead>引用</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead>说明</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="secret in filteredSecrets"
                :key="secret.name"
              >
                <TableCell class="font-medium">{{ secret.name }}</TableCell>
                <TableCell class="text-center">{{ secret.provider }}</TableCell>
                <TableCell>{{ secret.ref_hint }}</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="secret.enabled ? 'default' : 'secondary'">
                    {{ secret.enabled ? "启用" : "停用" }}
                  </Badge>
                </TableCell>
                <TableCell>{{ secret.description || "-" }}</TableCell>
                <TableCell>
                  <div class="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      @click="requestSecretDetail(secret.name)"
                    >
                      <EyeIcon data-icon="inline-start" />
                      详情
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="overview.deletingSecretName.value === secret.name"
                      @click="overview.deleteSecret(secret)"
                    >
                      <Trash2Icon data-icon="inline-start" />
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredSecrets.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.secrets.length === 0 ? "暂无密钥引用" : "没有匹配的密钥引用" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.secretPagination.currentPage.value"
            :page-size="overview.secretPagination.pageSize.value"
            :has-previous="overview.secretPagination.hasPrevious.value"
            :has-more="overview.secretPagination.hasMore.value"
            :item-count="overview.data.value.secrets.length"
            :loading="overview.loading.value"
            @previous="overview.secretPageActions.previous"
            @next="overview.secretPageActions.next"
            @update:page-size="overview.secretPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

</template>
