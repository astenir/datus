<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronUpIcon,
  CircleXIcon,
  LoaderCircleIcon,
  SquareIcon,
} from "@lucide/vue"
import { Queue, QueueList } from "@/components/ai-elements/queue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Progress } from "@/components/ui/progress"
import TodoQueueItem from "@/features/chat/TodoQueueItem.vue"
import type { TodoExecutionState } from "@/lib/todo-execution"

const props = defineProps<{
  execution: TodoExecutionState | null
}>()

const emit = defineEmits<{
  stop: []
}>()

const open = shallowRef(false)
const currentItem = computed(() =>
  props.execution?.items.find((item) => item.id === props.execution?.currentItemId),
)
const progressValue = computed(() => {
  const execution = props.execution
  if (!execution?.total) return 0
  return Math.min((execution.completed / execution.total) * 100, 100)
})
const statusLabel = computed(() => {
  const execution = props.execution
  if (!execution) return ""
  if (execution.status === "completed") return `已完成 ${execution.completed}/${execution.total}`
  if (execution.status === "failed") return `执行失败 ${execution.completed}/${execution.total}`
  return `正在执行 ${execution.completed}/${execution.total}`
})

watch(
  () => props.execution?.executionId,
  () => {
    open.value = false
  },
)
</script>

<template>
  <Queue
    v-if="execution"
    class="mb-3 gap-0 overflow-hidden rounded-lg p-0 shadow-lg shadow-muted/50"
    aria-live="polite"
    aria-label="任务执行进度"
  >
    <Collapsible v-model:open="open">
      <div class="flex min-w-0 items-center gap-3 p-3">
        <LoaderCircleIcon
          v-if="execution.status === 'running'"
          class="size-4 shrink-0 animate-spin text-primary"
          aria-hidden="true"
        />
        <CheckCircle2Icon
          v-else-if="execution.status === 'completed'"
          class="size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <CircleXIcon
          v-else
          class="size-4 shrink-0 text-destructive"
          aria-hidden="true"
        />

        <div class="min-w-0 flex-1">
          <div class="flex min-w-0 flex-wrap items-center gap-2">
            <span class="text-sm font-medium text-foreground">
              {{ statusLabel }}
            </span>
            <Badge
              v-if="currentItem"
              variant="secondary"
              class="max-w-full truncate"
            >
              当前：{{ currentItem.title }}
            </Badge>
          </div>
          <Progress
            :model-value="progressValue"
            class="mt-2 h-1.5"
            aria-label="任务完成进度"
          />
        </div>

        <div class="flex shrink-0 items-center gap-1">
          <CollapsibleTrigger as-child>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              :aria-label="open ? '收起任务详情' : '展开任务详情'"
            >
              <ChevronUpIcon
                v-if="open"
                data-icon="inline-start"
              />
              <ChevronDownIcon
                v-else
                data-icon="inline-start"
              />
              {{ open ? "收起" : "展开" }}
            </Button>
          </CollapsibleTrigger>
          <Button
            v-if="execution.status === 'running'"
            type="button"
            variant="outline"
            size="sm"
            @click="emit('stop')"
          >
            <SquareIcon data-icon="inline-start" />
            停止
          </Button>
        </div>
      </div>

      <CollapsibleContent class="border-t border-border/70 bg-muted/20 px-3 pb-3">
        <QueueList class="mt-2">
          <TodoQueueItem
            v-for="item in execution.items"
            :key="item.id"
            :item="item"
          />
        </QueueList>
      </CollapsibleContent>
    </Collapsible>
  </Queue>
</template>
