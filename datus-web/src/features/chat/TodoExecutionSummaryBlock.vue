<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleXIcon,
  PauseCircleIcon,
} from "@lucide/vue"
import { Queue, QueueList } from "@/components/ai-elements/queue"
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
    <Collapsible
      v-model:open="open"
      class="group"
    >
      <CollapsibleTrigger
        class="grid w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-3 px-3 py-2.5 text-left"
        :aria-label="open ? '收起已执行步骤' : '展开已执行步骤'"
        data-testid="todo-summary-trigger"
      >
        <div class="col-start-1 row-start-1 flex min-w-0 items-center gap-2">
          <CheckCircle2Icon
            v-if="block.status === 'completed'"
            class="size-4 shrink-0 text-muted-foreground"
            data-testid="todo-summary-leading-icon"
            aria-hidden="true"
          />
          <CircleXIcon
            v-else-if="block.status === 'failed'"
            class="size-4 shrink-0 text-destructive"
            data-testid="todo-summary-leading-icon"
            aria-hidden="true"
          />
          <PauseCircleIcon
            v-else
            class="size-4 shrink-0 text-muted-foreground"
            data-testid="todo-summary-leading-icon"
            aria-hidden="true"
          />
          <span
            class="min-w-0 truncate text-sm font-medium text-foreground"
            data-testid="todo-summary-title"
          >
            {{ summary }}
          </span>
        </div>

        <ChevronDownIcon
          class="col-start-2 row-start-1 size-4 self-center text-muted-foreground transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none"
          aria-hidden="true"
        />
      </CollapsibleTrigger>

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
