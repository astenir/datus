<script setup lang="ts">
import { computed } from "vue"
import type { DeepReadonly } from "vue"
import {
  ChartNoAxesCombinedIcon,
  FolderTreeIcon,
  SquareTerminalIcon,
} from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import type { SubjectTreeNode } from "@/lib/subject-tree"

const props = defineProps<{
  subject: DeepReadonly<SubjectTreeNode> | null
  loading: boolean
}>()

const subjectTypeLabel = computed(() => {
  if (props.subject?.type === "metric") return "指标"
  if (props.subject?.type === "reference_sql") return "参考 SQL"
  return "主题目录"
})

const statusLabel = computed(() => {
  if (props.loading) return "加载中"
  return props.subject ? "已加载" : "未选择"
})
</script>

<template>
  <div class="flex min-w-0 items-start gap-3">
    <div class="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
      <ChartNoAxesCombinedIcon
        v-if="subject?.type === 'metric'"
        aria-hidden="true"
      />
      <SquareTerminalIcon
        v-else-if="subject?.type === 'reference_sql'"
        aria-hidden="true"
      />
      <FolderTreeIcon
        v-else
        aria-hidden="true"
      />
    </div>
    <div class="min-w-0 flex-1">
      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <h2 class="truncate text-lg font-semibold">
          {{ subject?.name || "未选择主题" }}
        </h2>
        <Badge variant="outline">
          {{ subjectTypeLabel }}
        </Badge>
        <Badge :variant="loading ? 'outline' : 'secondary'">
          {{ statusLabel }}
        </Badge>
      </div>
      <p class="truncate text-sm text-muted-foreground">
        {{ subject ? subject.subjectPath.join(" / ") : "从主题树选择节点后浏览详情" }}
      </p>
    </div>
  </div>
</template>
