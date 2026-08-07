<script setup lang="ts">
import type { HTMLAttributes } from "vue"

import { CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

const props = defineProps<{
  title: string
  description?: string
  class?: HTMLAttributes["class"]
}>()
</script>

<template>
  <CardHeader :class="cn('shrink-0', props.class)">
    <div class="flex min-w-0 items-start justify-between gap-3">
      <div class="flex min-w-0 flex-1 items-start gap-3">
        <div
          v-if="$slots.icon"
          aria-hidden="true"
          class="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground"
        >
          <slot name="icon" />
        </div>

        <div class="flex min-w-0 flex-1 flex-col gap-1">
          <div class="flex min-h-7 min-w-0 flex-wrap items-center gap-2">
            <CardTitle class="min-w-0 truncate text-lg font-medium">
              {{ props.title }}
            </CardTitle>
            <div
              v-if="$slots.meta"
              class="flex shrink-0 flex-wrap items-center gap-2"
            >
              <slot name="meta" />
            </div>
          </div>

          <CardDescription
            v-if="props.description"
            class="break-all text-sm"
          >
            {{ props.description }}
          </CardDescription>

          <slot name="extra" />
        </div>
      </div>

      <div
        v-if="$slots.action"
        class="flex shrink-0 items-center"
      >
        <slot name="action" />
      </div>
    </div>
  </CardHeader>
</template>
