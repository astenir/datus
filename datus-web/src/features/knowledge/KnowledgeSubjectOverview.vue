<script setup lang="ts">
import { computed } from "vue"
import type { DeepReadonly } from "vue"
import {
  ChartNoAxesCombinedIcon,
  FolderTreeIcon,
  SquareTerminalIcon,
} from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"
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
  <PanelCardHeader
    :title="subject?.name || '未选择主题'"
    :description="subject ? subject.subjectPath.join(' / ') : '从主题树选择节点后浏览详情'"
  >
    <template #icon>
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
    </template>

    <template #meta>
      <Badge variant="outline">
        {{ subjectTypeLabel }}
      </Badge>
      <Badge :variant="loading ? 'outline' : 'secondary'">
        {{ statusLabel }}
      </Badge>
    </template>
  </PanelCardHeader>
</template>
