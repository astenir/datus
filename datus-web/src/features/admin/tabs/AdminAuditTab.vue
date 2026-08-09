<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { CalendarIcon, DownloadIcon, EyeIcon, SearchIcon } from "@lucide/vue"
import { parseDate } from "@internationalized/date"
import type { DateValue } from "@internationalized/date"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { RangeCalendar } from "@/components/ui/range-calendar"
import { Separator } from "@/components/ui/separator"
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
import type { AdminAuditTabProps } from "@/features/admin/types"
import { auditLogLimitOptions } from "@/lib/audit-log-pagination"

const props = defineProps<AdminAuditTabProps>()

type AuditDateRange = {
  start: DateValue | undefined
  end: DateValue | undefined
}

const auditDateRangeOpen = shallowRef(false)

function parseAuditCalendarDate(value: string): DateValue | undefined {
  const datePart = value.trim().slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) {
    return undefined
  }

  try {
    return parseDate(datePart)
  } catch {
    return undefined
  }
}

function auditDatePart(date: DateValue | undefined): string {
  return date?.toString().slice(0, 10) ?? ""
}

const auditDateRange = computed<AuditDateRange>({
  get: () => ({
    start: parseAuditCalendarDate(props.audits.searchForm.value.created_after),
    end: parseAuditCalendarDate(props.audits.searchForm.value.created_before),
  }),
  set: (range) => {
    const start = auditDatePart(range.start)
    const end = auditDatePart(range.end)
    props.audits.searchForm.value.created_after = start ? start + "T00:00:00" : ""
    props.audits.searchForm.value.created_before = end ? end + "T23:59:59" : ""
  },
})

const auditDateRangeLabel = computed(() => {
  const start = auditDatePart(auditDateRange.value.start)
  const end = auditDatePart(auditDateRange.value.end)
  if (start && end) {
    return start + " - " + end
  }
  if (start) {
    return start + " 起"
  }
  if (end) {
    return end + " 前"
  }
  return "日期范围"
})

const hasAuditDateRange = computed(() =>
  Boolean(props.audits.searchForm.value.created_after.trim() || props.audits.searchForm.value.created_before.trim())
)

function clearAuditDateRange(): void {
  props.audits.searchForm.value.created_after = ""
  props.audits.searchForm.value.created_before = ""
}
</script>
<template>
    <TabsContent
      v-if="canViewAudit"
      value="audit"
      class="-m-1 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div class="flex items-center gap-2">
            <CardTitle class="text-lg">审计</CardTitle>
            <Badge
              v-if="audits.hasActiveFilters.value"
              variant="secondary"
            >
              {{ audits.activeFilterCount.value }} 个筛选条件
            </Badge>
          </div>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="audits.decisionFilterValue.value">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="审计决策"
              >
                <SelectValue placeholder="全部决策" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="__all__">全部决策</SelectItem>
                  <SelectItem value="allow">allow</SelectItem>
                  <SelectItem value="deny">deny</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <Popover v-model:open="auditDateRangeOpen">
              <PopoverTrigger as-child>
                <Button
                  variant="outline"
                  size="sm"
                  class="w-full justify-start sm:w-56"
                  aria-label="审计日期范围"
                >
                  <CalendarIcon data-icon="inline-start" />
                  <span :class="{ 'text-muted-foreground': !hasAuditDateRange }">
                    {{ auditDateRangeLabel }}
                  </span>
                </Button>
              </PopoverTrigger>
              <PopoverContent
                class="w-auto gap-0 rounded-lg p-0"
                align="end"
              >
                <RangeCalendar
                  v-model="auditDateRange"
                  :number-of-months="1"
                />
                <Separator />
                <div class="flex items-center justify-end gap-2 px-3 py-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    :disabled="!hasAuditDateRange"
                    @click="clearAuditDateRange"
                  >
                    清除
                  </Button>
                  <Button
                    size="sm"
                    @click="auditDateRangeOpen = false"
                  >
                    完成
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="audits.searchForm.value.user_id"
                class="h-8 pl-8"
                placeholder="搜索用户 ID"
                aria-label="搜索审计用户"
                @keydown.enter.prevent="requestAuditSearch"
              />
            </div>
            <Button
              class="shrink-0"
              size="sm"
              :disabled="audits.loading.value"
              @click="requestAuditSearch"
            >
              <SearchIcon data-icon="inline-start" />
              查询
            </Button>
            <Button
              class="shrink-0"
              variant="outline"
              size="sm"
              :disabled="audits.loading.value"
              @click="requestAuditReset"
            >
              重置
            </Button>
            <Button
              class="shrink-0"
              variant="outline"
              size="sm"
              :disabled="audits.exporting.value"
              @click="audits.exportLogs"
            >
              <DownloadIcon data-icon="inline-start" />
              导出 CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent class="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-hidden">
          <div class="min-h-0 flex-1 overflow-auto">
            <div class="flex flex-col gap-2 lg:hidden">
              <div
                v-if="audits.loading.value"
                class="rounded-md border p-6 text-center text-sm text-muted-foreground"
              >
                正在加载审计日志...
              </div>
              <AdminMobileRecord
                v-for="(log, index) in audits.loading.value ? [] : audits.logs.value"
                :key="audits.formatLogKey(log, index)"
                :title="`${log.resource_type} / ${log.resource_id || '-'}`"
                :description="log.reason || '未记录原因'"
              >
                <template #status>
                  <Badge :variant="audits.getActionVariant(log.action)">
                    {{ audits.getActionText(log.action) }}
                  </Badge>
                  <Badge :variant="log.decision === 'allow' ? 'default' : 'destructive'">
                    {{ log.decision }}
                  </Badge>
                </template>
                <span>用户 {{ log.user_id || "-" }}</span>
                <span>{{ formatOptionalDate(log.created_at) }}</span>
                <span class="font-mono">日志 {{ log.id ?? "-" }}</span>
                <template #actions>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="audits.viewDetail(log)"
                  >
                    <EyeIcon data-icon="inline-start" />
                    详情
                  </Button>
                </template>
              </AdminMobileRecord>
              <div
                v-if="!audits.loading.value && audits.logs.value.length === 0"
                class="rounded-md border p-6 text-center text-sm text-muted-foreground"
              >
                暂无匹配审计日志
              </div>
            </div>
            <Table class="hidden lg:table">
              <TableHeader>
                <TableRow>
                  <TableHead class="text-center">时间</TableHead>
                  <TableHead>日志 ID</TableHead>
                  <TableHead>用户</TableHead>
                  <TableHead class="text-center">动作</TableHead>
                  <TableHead>资源</TableHead>
                  <TableHead class="text-center">决策</TableHead>
                  <TableHead>原因</TableHead>
                  <TableHead class="pr-6 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-if="audits.loading.value">
                  <TableCell
                    colspan="8"
                    class="h-24 text-center text-sm text-muted-foreground"
                  >
                    正在加载审计日志...
                  </TableCell>
                </TableRow>
                <template v-else>
                  <TableRow
                    v-for="(log, index) in audits.logs.value"
                    :key="audits.formatLogKey(log, index)"
                  >
                    <TableCell class="text-center">{{ formatOptionalDate(log.created_at) }}</TableCell>
                    <TableCell class="font-mono text-xs">{{ log.id ?? "-" }}</TableCell>
                    <TableCell>{{ log.user_id || "-" }}</TableCell>
                    <TableCell class="text-center">
                      <Badge :variant="audits.getActionVariant(log.action)">
                        {{ audits.getActionText(log.action) }}
                      </Badge>
                    </TableCell>
                    <TableCell>{{ log.resource_type }} / {{ log.resource_id || "-" }}</TableCell>
                    <TableCell class="text-center">
                      <Badge :variant="log.decision === 'allow' ? 'default' : 'destructive'">
                        {{ log.decision }}
                      </Badge>
                    </TableCell>
                    <TableCell class="max-w-xs truncate">{{ log.reason || "-" }}</TableCell>
                    <TableCell class="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        @click="audits.viewDetail(log)"
                      >
                        <EyeIcon data-icon="inline-start" />
                        详情
                      </Button>
                    </TableCell>
                  </TableRow>
                </template>
                <TableRow v-if="!audits.loading.value && audits.logs.value.length === 0">
                  <TableCell
                    colspan="8"
                    class="h-24 text-center text-sm text-muted-foreground"
                  >
                    暂无匹配审计日志
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="audits.currentPage.value"
            :page-size="audits.limit.value"
            :page-size-options="auditLogLimitOptions"
            :has-previous="audits.hasPreviousPage.value"
            :has-more="audits.hasNextPage.value"
            :item-count="audits.total.value"
            :loading="audits.loading.value"
            @previous="requestAuditPreviousPage"
            @next="requestAuditNextPage"
            @update:page-size="requestAuditPageSizeChange"
          />
        </CardFooter>
      </Card>
    </TabsContent>
</template>
