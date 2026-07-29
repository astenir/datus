<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronUpIcon,
  CircleXIcon,
  PauseCircleIcon,
} from "@lucide/vue"
import { Queue, QueueList } from "@/components/ai-elements/queue"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import TodoQueueItem from "@/features/chat/TodoQueueItem.vue"
import type { TodoExecutionSummaryBlock } from "@/types"

const props = defineProps<{
  block: TodoExecutionSummaryBlock
}>()

const open = shallowRef(false)
const summary = computed(() => {
  if (props.block.status === "completed") return `已完成 ${props.block.completed}/${props.block.total} 个步骤`
  if (props.block.status === "failed") return `执行失败 · 已完成 ${props.block.completed}/${props.block.total}`
  return `执行已停止 · 已完成 ${props.block.completed}/${props.block.total}`
})
</script>

<template>
  <Queue class="gap-0 overflow-hidden rounded-lg p-0 shadow-none">
    <Collapsible v-model:open="open">
      <div class="flex min-w-0 items-center gap-3 px-3 py-2">
        <CheckCircle2Icon
          v-if="block.status === 'completed'"
          class="size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <CircleXIcon
          v-else-if="block.status === 'failed'"
          class="size-4 shrink-0 text-destructive"
          aria-hidden="true"
        />
        <PauseCircleIcon
          v-else
          class="size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <span class="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
          {{ summary }}
        </span>
        <CollapsibleTrigger as-child>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            :aria-label="open ? '收起已执行步骤' : '展开已执行步骤'"
          >
            <ChevronUpIcon
              v-if="open"
              data-icon="inline-start"
            />
            <ChevronDownIcon
              v-else
              data-icon="inline-start"
            />
            {{ open ? "收起" : "详情" }}
          </Button>
        </CollapsibleTrigger>
      </div>

      <CollapsibleContent class="border-t border-border/70 bg-muted/20 px-3 pb-3">
        <QueueList class="mt-2">
          <TodoQueueItem
            v-for="item in block.items"
            :key="item.id"
            :item="item"
          />
        </QueueList>
      </CollapsibleContent>
    </Collapsible>
  </Queue>
</template>
