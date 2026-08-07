<script setup lang="ts">
import type { DeepReadonly } from "vue"
import { Table2Icon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"
import type { TableDetail } from "@/types"

defineProps<{
  title: string
  path: string
  detail: DeepReadonly<TableDetail> | null
  loading: boolean
}>()
</script>

<template>
  <PanelCardHeader
    :title="title"
    :description="path"
  >
    <template #icon>
      <Table2Icon aria-hidden="true" />
    </template>

    <template #meta>
      <Badge :variant="loading ? 'outline' : 'secondary'">
        {{ loading ? "加载中" : "已加载" }}
      </Badge>
    </template>

    <template #extra>
      <p
        v-if="detail?.description"
        class="text-sm leading-6 text-muted-foreground"
      >
        {{ detail.description }}
      </p>
    </template>
  </PanelCardHeader>
</template>
