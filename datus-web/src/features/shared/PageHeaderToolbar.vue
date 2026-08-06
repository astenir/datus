<script setup lang="ts">
import { computed } from "vue"

const props = withDefaults(defineProps<{
  title: string
  description?: string
  ariaLabel?: string
}>(), {
  description: "",
  ariaLabel: "",
})

const accessibleLabel = computed(() => props.ariaLabel.trim() || `${props.title}页头工具栏`)
</script>

<template>
  <header
    role="toolbar"
    :aria-label="accessibleLabel"
    class="flex min-h-15 shrink-0 flex-wrap items-center gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm"
  >
    <div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1.5">
      <div
        v-if="$slots.leading"
        class="flex size-8 shrink-0 items-center justify-center rounded-md bg-background/70 text-muted-foreground ring-1 ring-border/60 [&>svg]:size-4"
      >
        <slot name="leading" />
      </div>

      <div class="min-w-0">
        <div class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <h1 class="truncate text-sm font-semibold">
            {{ props.title }}
          </h1>
          <div
            v-if="$slots.meta"
            class="flex shrink-0 flex-wrap items-center gap-1.5"
          >
            <slot name="meta" />
          </div>
        </div>
        <p
          v-if="props.description"
          class="hidden max-w-[42rem] truncate text-xs text-muted-foreground sm:block"
        >
          {{ props.description }}
        </p>
      </div>
    </div>

    <div
      v-if="$slots.navigation"
      class="order-3 min-w-0 max-w-full overflow-x-auto md:order-none md:max-w-[60%]"
    >
      <slot name="navigation" />
    </div>

    <div
      v-if="$slots.actions"
      class="order-2 ml-auto flex shrink-0 flex-wrap items-center justify-end gap-2 md:order-none"
    >
      <slot name="actions" />
    </div>
  </header>
</template>
