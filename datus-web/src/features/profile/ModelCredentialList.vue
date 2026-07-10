<script setup lang="ts">
import { CircleCheckIcon, CircleXIcon, KeyRoundIcon, LoaderCircleIcon, PencilIcon, PlugZapIcon, StarIcon, Trash2Icon } from "@lucide/vue"
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
import type { ModelCredentialTestState } from "@/composables/useModelCredentials"
import type { ModelCredentialSummary } from "@/types/profile"

defineProps<{
  credentials: ModelCredentialSummary[]
  defaultCredentialId: string | null
  testResults: Record<string, ModelCredentialTestState>
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
  <div class="overflow-x-auto rounded-md border">
    <Table class="min-w-3xl">
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
              <Badge
                v-if="credential.id === defaultCredentialId"
                variant="secondary"
              >
                <StarIcon />
                默认
              </Badge>
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
            <div class="flex min-w-0 flex-col items-start gap-1">
              <Badge
                v-if="testingId === credential.id"
                variant="outline"
              >
                <LoaderCircleIcon class="animate-spin" />
                测试中
              </Badge>
              <Badge
                v-else-if="testResults[credential.id]?.ok"
                variant="secondary"
              >
                <CircleCheckIcon />
                连接正常
              </Badge>
              <Badge
                v-else-if="testResults[credential.id]"
                variant="destructive"
              >
                <CircleXIcon />
                连接失败
              </Badge>
              <Badge
                v-else
                :variant="credential.enabled ? 'secondary' : 'outline'"
              >
                {{ credential.enabled ? "启用" : "停用" }}
              </Badge>
              <span
                v-if="testResults[credential.id] && !testResults[credential.id]?.ok"
                class="max-w-48 truncate text-xs text-destructive"
                :title="testResults[credential.id]?.message"
              >
                {{ testResults[credential.id]?.message }}
              </span>
            </div>
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
                {{ testingId === credential.id ? "测试中" : "测试" }}
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                :disabled="saving"
                title="编辑"
                aria-label="编辑模型密钥"
                @click="emit('edit', credential)"
              >
                <PencilIcon />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                class="text-destructive hover:text-destructive"
                :disabled="saving"
                title="删除"
                aria-label="删除模型密钥"
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
