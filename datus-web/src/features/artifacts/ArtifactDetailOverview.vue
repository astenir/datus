<script setup lang="ts">
import { computed } from "vue"

import { Badge } from "@/components/ui/badge"
import type { ArtifactDetail } from "@/composables/useArtifacts"
import { cn } from "@/lib/utils"
import type { DashboardDetail } from "@/types"
import type { ArtifactViewTab } from "@/features/workspace/types"

const props = withDefaults(defineProps<{
  tab: ArtifactViewTab
  detail: ArtifactDetail
  compact?: boolean
}>(), {
  compact: false,
})

function isDashboardDetail(detail: ArtifactDetail): detail is DashboardDetail {
  return "templates" in detail
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

const datasources = computed(() => props.detail.manifest?.datasources ?? [])
const keyTables = computed(() => props.detail.manifest?.key_tables ?? [])
// Prefer the manifest timestamps (the same values the collection card shows);
// `detail.created_at` is derived from render/app.jsx mtime by the backend and
// only serves as a fallback for manifests written before created_at existed.
const createdAt = computed(() => props.detail.manifest?.created_at || props.detail.created_at)
const updatedAt = computed(() => props.detail.manifest?.updated_at ?? null)
const files = computed(() => props.detail.files ?? [])
const visibleFiles = computed(() => files.value.slice(0, 5))
const hiddenFileCount = computed(() => Math.max(files.value.length - visibleFiles.value.length, 0))
const templateCount = computed(() => isDashboardDetail(props.detail) ? props.detail.templates?.length ?? 0 : 0)
const overviewClass = computed(() => cn(
  "grid min-w-0 gap-5",
  props.compact ? "grid-cols-1" : "lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start",
))
const statsClass = computed(() => cn(
  "grid gap-x-4 gap-y-3",
  props.compact ? "grid-cols-2" : "grid-cols-2 sm:grid-cols-3",
))
</script>

<template>
  <div :class="overviewClass">
    <div class="flex min-w-0 flex-col gap-5">
      <section class="flex flex-col gap-2">
        <h2 class="text-sm font-semibold">概览</h2>
        <p class="text-sm leading-6 text-muted-foreground">
          {{ props.detail.description || "暂无描述。" }}
        </p>
      </section>

      <dl :class="statsClass">
        <div class="min-w-0">
          <dt class="text-xs text-muted-foreground">创建时间</dt>
          <dd class="mt-1 truncate text-sm font-medium">
            {{ formatOptionalDate(createdAt) }}
          </dd>
        </div>
        <div
          v-if="updatedAt"
          class="min-w-0"
        >
          <dt class="text-xs text-muted-foreground">更新时间</dt>
          <dd class="mt-1 truncate text-sm font-medium">
            {{ formatOptionalDate(updatedAt) }}
          </dd>
        </div>
        <div class="min-w-0">
          <dt class="text-xs text-muted-foreground">文件</dt>
          <dd class="mt-1 text-sm font-medium">{{ files.length }}</dd>
        </div>
        <div
          v-if="props.tab === 'dashboard'"
          class="min-w-0"
        >
          <dt class="text-xs text-muted-foreground">查询模板</dt>
          <dd class="mt-1 text-sm font-medium">{{ templateCount }}</dd>
        </div>
      </dl>

      <section
        v-if="datasources.length > 0"
        class="flex flex-col gap-2"
      >
        <h3 class="text-xs font-medium text-muted-foreground">数据源</h3>
        <div class="flex flex-wrap gap-1.5">
          <Badge
            v-for="datasource in datasources"
            :key="datasource"
            variant="secondary"
          >
            {{ datasource }}
          </Badge>
        </div>
      </section>

      <section
        v-if="keyTables.length > 0"
        class="flex flex-col gap-2"
      >
        <h3 class="text-xs font-medium text-muted-foreground">关键表</h3>
        <div class="flex flex-wrap gap-1.5">
          <Badge
            v-for="table in keyTables"
            :key="table"
            variant="outline"
          >
            {{ table }}
          </Badge>
        </div>
      </section>
    </div>

    <section
      v-if="visibleFiles.length > 0"
      class="flex min-w-0 flex-col gap-2"
    >
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-xs font-medium text-muted-foreground">文件</h3>
        <span class="text-xs text-muted-foreground">{{ files.length }} 个</span>
      </div>
      <div class="flex min-w-0 flex-col gap-1 rounded-md border p-3">
        <div
          v-for="file in visibleFiles"
          :key="file.path"
          class="truncate font-mono text-xs"
          :title="file.path"
        >
          {{ file.path }}
        </div>
        <p
          v-if="hiddenFileCount > 0"
          class="pt-1 text-xs text-muted-foreground"
        >
          另有 {{ hiddenFileCount }} 个文件
        </p>
      </div>
    </section>
  </div>
</template>
