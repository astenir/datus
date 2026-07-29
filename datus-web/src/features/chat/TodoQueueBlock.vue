<script setup lang="ts">
import { computed } from "vue"
import {
  Queue,
  QueueItem,
  QueueItemContent,
  QueueList,
  QueueSection,
  QueueSectionContent,
  QueueSectionLabel,
  QueueSectionTrigger,
} from "@/components/ai-elements/queue"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import TodoQueueItem from "@/features/chat/TodoQueueItem.vue"
import { groupTodoQueueItems } from "@/lib/todo-queue"
import type { TodoQueueModel } from "@/lib/todo-queue"

const props = defineProps<{
  queue: TodoQueueModel
  duration?: number
}>()

const groups = computed(() => groupTodoQueueItems(props.queue.items))
const progressValue = computed(() => (
  props.queue.total > 0
    ? Math.min((props.queue.completed / props.queue.total) * 100, 100)
    : 0
))
const summary = computed(() => {
  if (props.queue.total === 0) return "当前没有待执行任务"
  if (props.queue.variant === "item" && props.queue.items[0]) {
    return `任务 #${props.queue.items[0].id}`
  }
  return `${props.queue.completed}/${props.queue.total} 项已完成`
})
</script>

<template>
  <Queue>
    <div class="flex min-w-0 items-start justify-between gap-3 px-1 py-1">
      <div class="min-w-0">
        <h4 class="text-sm font-medium">
          {{ queue.title }}
        </h4>
        <p class="mt-1 text-xs text-muted-foreground">
          {{ summary }}<template v-if="duration != null"> · {{ duration.toFixed(2) }}s</template>
        </p>
      </div>
      <Badge variant="outline">
        {{ queue.actionLabel }}
      </Badge>
    </div>

    <Progress
      v-if="queue.variant === 'snapshot' && queue.total > 0"
      :model-value="progressValue"
      class="h-1.5"
      aria-label="任务完成进度"
    />

    <QueueList v-if="queue.variant === 'item'">
      <TodoQueueItem
        v-for="item in queue.items"
        :key="item.id"
        :item="item"
      />
    </QueueList>

    <template v-else-if="groups.length > 0">
      <QueueSection
        v-for="group in groups"
        :key="group.status"
      >
        <QueueSectionTrigger>
          <QueueSectionLabel
            :count="group.items.length"
            :label="group.label"
          />
        </QueueSectionTrigger>
        <QueueSectionContent>
          <QueueList>
            <TodoQueueItem
              v-for="item in group.items"
              :key="item.id"
              :item="item"
            />
          </QueueList>
        </QueueSectionContent>
      </QueueSection>
    </template>

    <QueueList v-else>
      <QueueItem>
        <QueueItemContent>暂无任务，队列为空。</QueueItemContent>
      </QueueItem>
    </QueueList>
  </Queue>
</template>
