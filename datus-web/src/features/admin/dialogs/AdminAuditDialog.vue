<script setup lang="ts">
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { AdminAuditDialogProps } from "@/features/admin/types"

const props = defineProps<AdminAuditDialogProps>()
</script>
<template>
  <Dialog v-model:open="audits.showDetail.value">
    <DialogContent class="max-h-[calc(100vh-2rem)] overflow-y-auto bg-background sm:max-w-2xl">
      <DialogHeader>
        <DialogTitle>审计详情</DialogTitle>
        <DialogDescription>
          {{ audits.selectedLog.value?.id != null ? `#${audits.selectedLog.value.id}` : "未记录日志 ID" }}
          ·
          {{ formatOptionalDate(audits.selectedLog.value?.created_at) }}
        </DialogDescription>
      </DialogHeader>
      <div
        v-if="audits.selectedLog.value"
        class="grid gap-3 text-sm md:grid-cols-2"
      >
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">日志 ID</div>
          <div class="font-medium">{{ audits.selectedLog.value.id ?? "-" }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">创建时间</div>
          <div class="font-medium">{{ formatOptionalDate(audits.selectedLog.value.created_at) }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">用户</div>
          <div class="font-medium">{{ audits.selectedLog.value.user_id || "-" }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">动作</div>
          <div class="font-medium">{{ audits.getActionText(audits.selectedLog.value.action) }}</div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">资源</div>
          <div class="font-medium">
            {{ audits.selectedLog.value.resource_type }} / {{ audits.selectedLog.value.resource_id || "-" }}
          </div>
        </div>
        <div class="rounded-md border p-3">
          <div class="text-xs text-muted-foreground">决策</div>
          <div class="font-medium">{{ audits.selectedLog.value.decision }}</div>
        </div>
        <div class="rounded-md border p-3 md:col-span-2">
          <div class="text-xs text-muted-foreground">Request ID</div>
          <div class="font-medium">{{ audits.selectedLog.value.request_id || "-" }}</div>
        </div>
        <div class="rounded-md border p-3 md:col-span-2">
          <div class="text-xs text-muted-foreground">原因</div>
          <div class="font-medium">{{ audits.selectedLog.value.reason || "-" }}</div>
        </div>
        <div class="rounded-md border p-3 md:col-span-2">
          <div class="text-xs text-muted-foreground">Metadata</div>
          <pre class="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs">{{ JSON.stringify(audits.selectedLog.value.metadata ?? {}, null, 2) }}</pre>
        </div>
      </div>
      <DialogFooter>
        <Button
          variant="outline"
          @click="audits.showDetail.value = false"
        >
          关闭
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
