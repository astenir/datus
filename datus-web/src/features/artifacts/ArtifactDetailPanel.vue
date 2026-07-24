<script setup lang="ts">
import { computed } from "vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import type { ArtifactDetail } from "@/composables/useArtifacts"
import ArtifactDetailOverview from "@/features/artifacts/ArtifactDetailOverview.vue"
import DashboardTemplateRunner from "@/features/artifacts/DashboardTemplateRunner.vue"
import type { DashboardDetail, SqlQueryResultEnvelope } from "@/types"
import type { ArtifactViewTab } from "@/features/workspace/types"

const props = defineProps<{
  tab: ArtifactViewTab
  detail: ArtifactDetail | null
  loading: boolean
  error: string | null
  queryResult: SqlQueryResultEnvelope | null
  queryLoading: boolean
  queryError: string | null
  activeQuerySlug: string | null
}>()

const emit = defineEmits<{
  runDashboardQuery: [querySlug: string, params: Record<string, unknown>]
}>()

function isDashboardDetail(detail: ArtifactDetail | null): detail is DashboardDetail {
  return Boolean(detail && "templates" in detail)
}

function runDashboardQuery(querySlug: string, params: Record<string, unknown>) {
  emit("runDashboardQuery", querySlug, params)
}

const kindLabel = computed(() => props.tab === "report" ? "报表" : "仪表盘")
const templates = computed(() => isDashboardDetail(props.detail) ? props.detail.templates ?? [] : [])
</script>

<template>
  <div class="flex flex-col gap-4">
    <div
      v-if="props.loading"
      class="flex flex-col gap-3"
    >
      <Skeleton class="h-5 w-40" />
      <Skeleton class="h-4 w-full" />
      <Skeleton class="h-4 w-2/3" />
      <Skeleton class="h-8 w-28" />
    </div>

    <Alert
      v-else-if="props.error"
      variant="destructive"
    >
      <AlertTitle>详情不可用</AlertTitle>
      <AlertDescription>{{ props.error }}</AlertDescription>
    </Alert>

    <Alert v-else-if="!props.detail">
      <AlertTitle>未选择产物</AlertTitle>
      <AlertDescription>从列表选择一个{{ kindLabel }}查看文件、数据源和预览入口。</AlertDescription>
    </Alert>

    <div
      v-else
      class="min-w-0"
    >
      <div
        v-if="props.tab === 'dashboard'"
        class="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start"
      >
        <ArtifactDetailOverview
          class="lg:col-start-2 lg:row-start-1"
          :tab="props.tab"
          :detail="props.detail"
          compact
        />

        <DashboardTemplateRunner
          class="min-w-0 lg:col-start-1 lg:row-start-1"
          :templates="templates"
          :result="props.queryResult"
          :loading="props.queryLoading"
          :error="props.queryError"
          :active-slug="props.activeQuerySlug"
          @run="runDashboardQuery"
        />
      </div>

      <ArtifactDetailOverview
        v-else
        :tab="props.tab"
        :detail="props.detail"
      />
    </div>
  </div>
</template>
