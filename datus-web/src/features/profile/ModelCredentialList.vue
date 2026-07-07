<script setup lang="ts">
import { KeyRoundIcon, PencilIcon, PlugZapIcon, Trash2Icon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { ModelCredentialSummary } from "@/types/profile"

defineProps<{
  credentials: ModelCredentialSummary[]
  testingId: string | null
  saving: boolean
}>()

const emit = defineEmits<{
  edit: [credential: ModelCredentialSummary]
  delete: [id: string]
  test: [id: string]
}>()

function labelFor(credential: ModelCredentialSummary): string {
  return credential.display_name || `${credential.provider}/${credential.model}`
}
</script>

<template>
  <div class="rounded-md border">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>名称</TableHead>
          <TableHead>模型</TableHead>
          <TableHead>密钥</TableHead>
          <TableHead>状态</TableHead>
          <TableHead class="w-[13rem] text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow
          v-for="credential in credentials"
          :key="credential.id"
        >
          <TableCell class="font-medium">
            <div class="flex min-w-0 items-center gap-2">
              <KeyRoundIcon class="text-muted-foreground" />
              <span class="truncate">{{ labelFor(credential) }}</span>
            </div>
          </TableCell>
          <TableCell>
            <div class="min-w-0">
              <div class="truncate text-sm">{{ credential.model }}</div>
              <div class="truncate text-xs text-muted-foreground">
                {{ credential.base_url || credential.provider }}
              </div>
            </div>
          </TableCell>
          <TableCell class="font-mono text-xs">{{ credential.ref_hint }}</TableCell>
          <TableCell>
            <Badge :variant="credential.enabled ? 'secondary' : 'outline'">
              {{ credential.enabled ? "启用" : "停用" }}
            </Badge>
          </TableCell>
          <TableCell>
            <div class="flex justify-end gap-1.5">
              <Button
                variant="outline"
                size="sm"
                :disabled="testingId === credential.id || saving"
                @click="emit('test', credential.id)"
              >
                <PlugZapIcon data-icon="inline-start" />
                测试
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                :disabled="saving"
                title="编辑"
                @click="emit('edit', credential)"
              >
                <PencilIcon />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                :disabled="saving"
                title="删除"
                @click="emit('delete', credential.id)"
              >
                <Trash2Icon />
              </Button>
            </div>
          </TableCell>
        </TableRow>
        <TableEmpty
          v-if="credentials.length === 0"
          :colspan="5"
        >
          还没有个人模型密钥。
        </TableEmpty>
      </TableBody>
    </Table>
  </div>
</template>
