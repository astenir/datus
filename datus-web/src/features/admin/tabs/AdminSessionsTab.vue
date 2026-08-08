<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { watchDebounced } from "@vueuse/core"
import { EyeIcon, SearchIcon, SquareIcon, Trash2Icon } from "@lucide/vue"
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
import type { AdminSessionsTabProps } from "@/features/admin/types"
import {
  matchesKeyword,
  normalizedSearch,
  searchKeyword,
  type SessionStateFilter,
} from "@/features/admin/tab-utils"
import { adminSessionRuntimeValueLabel, adminSessionStatusLabel } from "@/lib/admin-session"

const props = defineProps<AdminSessionsTabProps>()

const sessionStateFilter = shallowRef<SessionStateFilter>("all")
const sessionSearchKeyword = shallowRef("")

watchDebounced(
  [sessionStateFilter, sessionSearchKeyword],
  () => {
    if (props.activeTab !== "sessions") return
    props.overview.applySessionListFilters({
      state: sessionStateFilter.value === "all" ? undefined : sessionStateFilter.value,
      search: normalizedSearch(sessionSearchKeyword.value),
    })
  },
  { debounce: 300 },
)

const filteredSessions = computed(() => {
  const stateFilter = sessionStateFilter.value
  const keyword = searchKeyword(sessionSearchKeyword.value)

  return props.overview.data.value.sessions.filter((session) => {
    if (stateFilter === "running" && !session.is_running) {
      return false
    }
    if (stateFilter === "stopped" && session.is_running) {
      return false
    }

    return matchesKeyword(keyword, [
      session.session_id,
      session.owner_user_id,
      session.status,
      adminSessionStatusLabel(session.status),
      session.event_count,
    ])
  })
})
</script>
<template>
    <TabsContent
      v-if="canViewSessions"
      value="sessions"
      class="-m-1 flex min-h-0 flex-1 flex-col overflow-hidden p-1"
    >
      <Card class="min-h-0 flex-1 gap-4">
        <CardHeader class="flex min-h-8 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle class="text-lg">会话</CardTitle>
          <div class="flex w-full flex-col gap-2 sm:flex-row sm:items-center lg:w-auto">
            <Select v-model="sessionStateFilter">
              <SelectTrigger
                class="w-full sm:w-32"
                size="sm"
                aria-label="会话状态"
              >
                <SelectValue placeholder="全部状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="running">运行中</SelectItem>
                  <SelectItem value="stopped">已停止</SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div class="relative w-full sm:w-64">
              <SearchIcon class="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                v-model="sessionSearchKeyword"
                class="h-8 pl-8"
                placeholder="搜索 Session ID / 所有者"
                aria-label="搜索会话"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent class="min-h-0 flex-1 overflow-auto">
          <div class="flex flex-col gap-2 lg:hidden">
            <AdminMobileRecord
              v-for="session in filteredSessions"
              :key="session.session_id"
              :title="session.session_id"
              :description="session.owner_user_id ? `所有者 ${session.owner_user_id}` : '未记录所有者'"
            >
              <template #status>
                <Badge :variant="session.is_running ? 'default' : 'secondary'">
                  {{ adminSessionStatusLabel(session.status) }}
                </Badge>
              </template>
              <span>
                实时事件数
                {{ adminSessionRuntimeValueLabel(session.runtime_snapshot_available, session.event_count) }}
              </span>
              <span>更新于 {{ formatOptionalDate(session.updated_at || session.created_at) }}</span>
              <template #actions>
                <Button
                  variant="outline"
                  size="sm"
                  @click="requestSessionDetail(session.session_id)"
                >
                  <EyeIcon data-icon="inline-start" />
                  详情
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="!session.is_running || overview.actingSessionId.value === session.session_id"
                  @click="overview.stopSession(session)"
                >
                  <SquareIcon data-icon="inline-start" />
                  停止
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="overview.actingSessionId.value === session.session_id"
                  @click="overview.deleteSession(session)"
                >
                  <Trash2Icon data-icon="inline-start" />
                  删除
                </Button>
              </template>
            </AdminMobileRecord>
            <div
              v-if="filteredSessions.length === 0"
              class="rounded-md border p-6 text-center text-sm text-muted-foreground"
            >
              {{ overview.data.value.sessions.length === 0 ? "暂无会话" : "没有匹配的会话" }}
            </div>
          </div>
          <Table class="hidden lg:table">
            <TableHeader>
              <TableRow>
                <TableHead>Session ID</TableHead>
                <TableHead>所有者</TableHead>
                <TableHead class="text-center">状态</TableHead>
                <TableHead class="text-center">实时事件数</TableHead>
                <TableHead class="text-center">记录更新时间</TableHead>
                <TableHead class="pr-6 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="session in filteredSessions"
                :key="session.session_id"
              >
                <TableCell class="max-w-sm truncate font-medium">{{ session.session_id }}</TableCell>
                <TableCell>{{ session.owner_user_id || "-" }}</TableCell>
                <TableCell class="text-center">
                  <Badge :variant="session.is_running ? 'default' : 'secondary'">
                    {{ adminSessionStatusLabel(session.status) }}
                  </Badge>
                </TableCell>
                <TableCell class="text-center">
                  {{ adminSessionRuntimeValueLabel(session.runtime_snapshot_available, session.event_count) }}
                </TableCell>
                <TableCell class="text-center">{{ formatOptionalDate(session.updated_at || session.created_at) }}</TableCell>
                <TableCell>
                  <div class="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      @click="requestSessionDetail(session.session_id)"
                    >
                      <EyeIcon data-icon="inline-start" />
                      详情
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="!session.is_running || overview.actingSessionId.value === session.session_id"
                      @click="overview.stopSession(session)"
                    >
                      <SquareIcon data-icon="inline-start" />
                      停止
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="overview.actingSessionId.value === session.session_id"
                      @click="overview.deleteSession(session)"
                    >
                      <Trash2Icon data-icon="inline-start" />
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
              <TableRow v-if="filteredSessions.length === 0">
                <TableCell
                  colspan="6"
                  class="h-24 text-center text-sm text-muted-foreground"
                >
                  {{ overview.data.value.sessions.length === 0 ? "暂无会话" : "没有匹配的会话" }}
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
        <CardFooter>
          <AdminPaginationBar
            :page="overview.sessionPagination.currentPage.value"
            :page-size="overview.sessionPagination.pageSize.value"
            :has-previous="overview.sessionPagination.hasPrevious.value"
            :has-more="overview.sessionPagination.hasMore.value"
            :item-count="overview.data.value.sessions.length"
            :loading="overview.loading.value"
            @previous="overview.sessionPageActions.previous"
            @next="overview.sessionPageActions.next"
            @update:page-size="overview.sessionPageActions.setPageSize"
          />
        </CardFooter>
      </Card>
    </TabsContent>

</template>
