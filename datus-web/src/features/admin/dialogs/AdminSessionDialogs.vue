<script setup lang="ts">
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ChevronDownIcon, InfoIcon } from "@lucide/vue"
import type { AdminSessionDialogsProps } from "@/features/admin/types"
import {
  adminSessionBodyStateLabel,
  adminSessionRuntimeValueLabel,
  adminSessionStatusDescription,
  adminSessionStatusLabel,
} from "@/lib/admin-session"

defineProps<AdminSessionDialogsProps>()
</script>
<template>
  <Dialog
    :open="overview.showSessionDetailDialog.value"
    @update:open="setSessionDetailDialogOpen"
  >
    <DialogContent class="max-h-[calc(100vh-2rem)] overflow-y-auto sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>会话详情</DialogTitle>
        <DialogDescription>
          {{ overview.selectedSessionDetailId.value || "未选择会话" }}
        </DialogDescription>
      </DialogHeader>

      <div
        v-if="overview.loadingSessionDetail.value"
        class="rounded-md border p-4 text-sm text-muted-foreground"
      >
        正在加载会话详情...
      </div>
      <div
        v-else-if="overview.sessionDetailError.value"
        class="rounded-md border p-4 text-sm text-muted-foreground"
      >
        {{ overview.sessionDetailError.value }}
      </div>
      <div
        v-else-if="overview.selectedSessionDetail.value"
        class="grid gap-3 text-sm md:grid-cols-2"
      >
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">Session ID</div>
          <div class="break-all font-medium">{{ overview.selectedSessionDetail.value.session_id }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">所有者</div>
          <div class="font-medium">{{ overview.selectedSessionDetail.value.owner_user_id || "-" }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">状态</div>
          <Badge :variant="overview.selectedSessionDetail.value.is_running ? 'default' : 'secondary'">
            {{ adminSessionStatusLabel(overview.selectedSessionDetail.value.status) }}
          </Badge>
          <div class="mt-1 text-xs text-muted-foreground">
            {{ adminSessionStatusDescription(overview.selectedSessionDetail.value.status) }}
          </div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">会话记录</div>
          <div class="font-medium">
            {{ adminSessionBodyStateLabel(overview.selectedSessionDetail.value.exists_on_disk) }}
          </div>
          <div class="mt-1 text-xs text-muted-foreground">表示是否可以继续查看这次会话的已保存内容。</div>
        </div>
        <Alert
          v-if="!overview.selectedSessionDetail.value.runtime_snapshot_available"
          class="md:col-span-2"
        >
          <InfoIcon />
          <AlertTitle>实时运行信息当前不可获取</AlertTitle>
          <AlertDescription>
            会话记录仍可正常查看。任务可能已经结束、服务曾重启，或由其他服务实例处理。
          </AlertDescription>
        </Alert>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">记录创建时间</div>
          <div class="font-medium">{{ formatOptionalDate(overview.selectedSessionDetail.value.created_at) }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">记录更新时间</div>
          <div class="font-medium">{{ formatOptionalDate(overview.selectedSessionDetail.value.updated_at) }}</div>
          <div class="mt-1 text-xs text-muted-foreground">所有者索引最近一次写入时间，不代表每条消息活动。</div>
        </div>
        <Collapsible
          v-slot="{ open }"
          class="rounded-md border md:col-span-2"
        >
          <CollapsibleTrigger as-child>
            <Button
              type="button"
              variant="ghost"
              class="h-auto w-full justify-between gap-3 px-3 py-3 text-left"
            >
              <span class="flex min-w-0 flex-col items-start gap-1 whitespace-normal">
                <span class="font-medium">技术诊断信息</span>
                <span class="text-xs font-normal text-muted-foreground">
                  仅供技术排查，展开后查看当前服务实例保留的实时数据。
                </span>
              </span>
              <ChevronDownIcon
                class="size-4 shrink-0 transition-transform"
                :class="{ 'rotate-180': open }"
                aria-hidden="true"
              />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent class="border-t p-3">
            <div class="grid gap-3 md:grid-cols-2">
              <div class="rounded-md bg-muted/50 p-3">
                <div class="text-xs text-muted-foreground">实时事件数</div>
                <div class="font-medium">
                  {{ adminSessionRuntimeValueLabel(
                    overview.selectedSessionDetail.value.runtime_snapshot_available,
                    overview.selectedSessionDetail.value.event_count,
                  ) }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">用于断线续传的临时事件数量，不等同于会话消息数。</div>
              </div>
              <div class="rounded-md bg-muted/50 p-3">
                <div class="text-xs text-muted-foreground">流式传输进度</div>
                <div class="font-medium">
                  {{ adminSessionRuntimeValueLabel(
                    overview.selectedSessionDetail.value.runtime_snapshot_available,
                    overview.selectedSessionDetail.value.consumer_offset,
                  ) }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">表示当前服务实例已处理实时事件的位置。</div>
              </div>
              <div class="rounded-md bg-muted/50 p-3 md:col-span-2">
                <div class="text-xs text-muted-foreground">实时运行错误</div>
                <pre class="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-background p-3 font-mono text-xs">{{ adminSessionRuntimeValueLabel(
                  overview.selectedSessionDetail.value.runtime_snapshot_available,
                  overview.selectedSessionDetail.value.error,
                ) }}</pre>
                <div class="mt-1 text-xs text-muted-foreground">只显示当前实时任务保留的错误，不是完整的历史错误记录。</div>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      <DialogFooter>
        <Button
          variant="outline"
          @click="setSessionDetailDialogOpen(false)"
        >
          关闭
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
