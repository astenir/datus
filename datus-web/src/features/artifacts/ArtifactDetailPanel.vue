<script setup lang="ts">
import { computed } from "vue"
import { ExternalLinkIcon, XIcon } from "@lucide/vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { ArtifactDetail } from "@/composables/useArtifacts"
import DashboardTemplateRunner from "@/features/artifacts/DashboardTemplateRunner.vue"
import type { DashboardDetail, SqlQueryResultEnvelope } from "@/types"
import type { ArtifactViewTab } from "@/features/workspace/types"

const props = defineProps<{
  tab: ArtifactViewTab
  slug: string | null
  detail: ArtifactDetail | null
  loading: boolean
  error: string | null
  previewHref: string | null
  queryResult: SqlQueryResultEnvelope | null
  queryLoading: boolean
  queryError: string | null
  activeQuerySlug: string | null
}>()

const emit = defineEmits<{
  close: []
  runDashboardQuery: [querySlug: string, params: Record<string, unknown>]
}>()

function isDashboardDetail(detail: ArtifactDetail | null): detail is DashboardDetail {
  return Boolean(detail && "templates" in detail)
}

function formatOptionalDate(value: string | null | undefined) {
  if (!value) return "-"
  return new Date(value.endsWith("Z") ? value : `${value}Z`).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function runDashboardQuery(querySlug: string, params: Record<string, unknown>) {
  emit("runDashboardQuery", querySlug, params)
}

const kindLabel = computed(() => props.tab === "report" ? "报表" : "仪表盘")
const manifest = computed(() => props.detail?.manifest ?? null)
const datasources = computed(() => manifest.value?.datasources ?? [])
const keyTables = computed(() => manifest.value?.key_tables ?? [])
const files = computed(() => props.detail?.files ?? [])
const visibleFiles = computed(() => files.value.slice(0, 5))
const templates = computed(() => isDashboardDetail(props.detail) ? props.detail.templates ?? [] : [])
</script>

<template>
  <Card class="lg:sticky lg:top-4">
    <CardHeader class="flex flex-row items-start justify-between gap-3">
      <div class="min-w-0">
        <CardTitle class="text-lg">{{ kindLabel }}详情</CardTitle>
        <p class="truncate text-xs text-muted-foreground">{{ props.slug }}</p>
      </div>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="关闭详情"
        @click="emit('close')"
      >
        <XIcon data-icon="inline-start" />
      </Button>
    </CardHeader>

    <CardContent class="flex flex-col gap-4">
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
        <AlertDescription>从左侧列表选择一个{{ kindLabel }}查看文件、数据源和预览入口。</AlertDescription>
      </Alert>

      <div
        v-else
        class="flex flex-col gap-4"
      >
        <div class="flex flex-col gap-1">
          <h2 class="text-sm font-semibold">{{ props.detail.name }}</h2>
          <p class="text-sm leading-6 text-muted-foreground">{{ props.detail.description }}</p>
        </div>

        <div class="grid gap-2 text-sm">
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">创建时间</span>
            <span class="font-medium">{{ formatOptionalDate(props.detail.created_at) }}</span>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-muted-foreground">文件</span>
            <span class="font-medium">{{ files.length }}</span>
          </div>
          <div
            v-if="props.tab === 'dashboard'"
            class="flex items-center justify-between gap-3"
          >
            <span class="text-muted-foreground">查询模板</span>
            <span class="font-medium">{{ templates.length }}</span>
          </div>
        </div>

        <div
          v-if="datasources.length > 0"
          class="flex flex-col gap-2"
        >
          <div class="text-xs font-medium text-muted-foreground">数据源</div>
          <div class="flex flex-wrap gap-1.5">
            <Badge
              v-for="datasource in datasources"
              :key="datasource"
              variant="secondary"
            >
              {{ datasource }}
            </Badge>
          </div>
        </div>

        <div
          v-if="keyTables.length > 0"
          class="flex flex-col gap-2"
        >
          <div class="text-xs font-medium text-muted-foreground">关键表</div>
          <div class="flex flex-wrap gap-1.5">
            <Badge
              v-for="table in keyTables"
              :key="table"
              variant="outline"
            >
              {{ table }}
            </Badge>
          </div>
        </div>

        <div
          v-if="visibleFiles.length > 0"
          class="flex flex-col gap-2"
        >
          <div class="text-xs font-medium text-muted-foreground">文件</div>
          <div class="flex flex-col gap-1 rounded-md border p-2">
            <div
              v-for="file in visibleFiles"
              :key="file.path"
              class="truncate font-mono text-xs"
            >
              {{ file.path }}
            </div>
          </div>
        </div>

        <DashboardTemplateRunner
          v-if="props.tab === 'dashboard'"
          :templates="templates ?? []"
          :result="props.queryResult"
          :loading="props.queryLoading"
          :error="props.queryError"
          :active-slug="props.activeQuerySlug"
          @run="runDashboardQuery"
        />

        <Button
          v-if="props.previewHref"
          as="a"
          target="_blank"
          :href="props.previewHref"
          variant="outline"
          size="sm"
        >
          <ExternalLinkIcon data-icon="inline-start" />
          打开 HTML 预览
        </Button>
      </div>
    </CardContent>
  </Card>
</template>
