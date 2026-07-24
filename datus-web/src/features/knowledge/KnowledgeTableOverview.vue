<script setup lang="ts">
import type { DeepReadonly } from "vue"
import { Table2Icon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import type { TableDetail } from "@/types"

defineProps<{
  title: string
  path: string
  detail: DeepReadonly<TableDetail> | null
  loading: boolean
}>()
</script>

<template>
  <div class="flex min-w-0 flex-col gap-4">
    <div class="flex min-w-0 items-start gap-3">
      <div class="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <Table2Icon aria-hidden="true" />
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <h2 class="truncate text-lg font-semibold">{{ title }}</h2>
          <Badge :variant="loading ? 'outline' : 'secondary'">
            {{ loading ? "加载中" : "已加载" }}
          </Badge>
        </div>
        <p class="truncate text-sm text-muted-foreground">{{ path }}</p>
        <p
          v-if="detail?.description"
          class="mt-1 text-sm leading-6 text-muted-foreground"
        >
          {{ detail.description }}
        </p>
      </div>
    </div>
  </div>
</template>
