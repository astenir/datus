<script setup lang="ts">
import {
  CircleCheckIcon,
  CircleIcon,
  CircleQuestionMarkIcon,
  CircleXIcon,
  LoaderCircleIcon,
} from "@lucide/vue"
import {
  QueueItem,
  QueueItemContent,
  QueueItemDescription,
} from "@/components/ai-elements/queue"
import { Badge } from "@/components/ui/badge"
import type { TodoQueueItem as TodoQueueItemModel } from "@/lib/todo-queue"

defineProps<{
  item: TodoQueueItemModel
}>()
</script>

<template>
  <QueueItem>
    <div class="flex min-w-0 items-start gap-2">
      <LoaderCircleIcon
        v-if="item.status === 'in_progress'"
        class="mt-0.5 size-4 shrink-0 animate-spin text-primary"
        aria-hidden="true"
      />
      <CircleCheckIcon
        v-else-if="item.status === 'completed'"
        class="mt-0.5 size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
      <CircleXIcon
        v-else-if="item.status === 'failed'"
        class="mt-0.5 size-4 shrink-0 text-destructive"
        aria-hidden="true"
      />
      <CircleQuestionMarkIcon
        v-else-if="item.status === 'unknown'"
        class="mt-0.5 size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
      <CircleIcon
        v-else
        class="mt-0.5 size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
      <QueueItemContent :completed="item.status === 'completed'">
        {{ item.title }}
      </QueueItemContent>
      <Badge
        variant="outline"
        class="shrink-0"
      >
        #{{ item.id }}
      </Badge>
    </div>
    <QueueItemDescription
      v-if="item.content"
      :completed="item.status === 'completed'"
    >
      {{ item.content }}
    </QueueItemDescription>
  </QueueItem>
</template>
