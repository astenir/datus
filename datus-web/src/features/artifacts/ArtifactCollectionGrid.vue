<script setup lang="ts">
import { EyeIcon, FilePenLineIcon, FileSearchIcon, Share2Icon, UserRoundIcon } from "@lucide/vue"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { ArtifactManifest } from "@/types"

type ReadonlyArtifactManifest = Readonly<
  Omit<ArtifactManifest, "datasources" | "key_tables"> & {
    datasources?: readonly string[]
    key_tables?: readonly string[]
  }
>

const props = defineProps<{
  items: readonly ReadonlyArtifactManifest[]
  emptyTitle: string
  loading: boolean
  openingSlug: string | null
  sharingSlug: string | null
  editingSlug: string | null
  editEnabled: boolean
}>()

const emit = defineEmits<{
  select: [slug: string]
  openPreview: [slug: string]
  share: [slug: string]
  edit: [slug: string]
}>()

function authorLabel(item: ReadonlyArtifactManifest): string {
  return item.owner_display_name?.trim() || item.owner_user_id?.trim() || "未知作者"
}

function authorTitle(item: ReadonlyArtifactManifest): string {
  const displayName = item.owner_display_name?.trim()
  const userId = item.owner_user_id?.trim()

  if (displayName && userId && displayName !== userId) {
    return `作者：${displayName}（${userId}）`
  }

  return `作者：${displayName || userId || "未知"}`
}
</script>

<template>
  <div
    v-if="props.loading && props.items.length === 0"
    role="status"
    aria-live="polite"
    aria-busy="true"
    class="flex flex-wrap items-start gap-3"
  >
    <span class="sr-only">正在加载产物列表...</span>
    <Card
      v-for="index in 3"
      :key="index"
      size="sm"
      class="h-52 w-88 max-w-full flex-none"
    >
      <CardHeader class="min-w-0">
        <Skeleton class="h-5 w-36" />
        <Skeleton class="h-3 w-24" />
        <div class="flex min-h-16 flex-col gap-2">
          <Skeleton class="h-3 w-full" />
          <Skeleton class="h-3 w-full" />
          <Skeleton class="h-3 w-full" />
        </div>
      </CardHeader>
      <CardFooter class="mt-auto grid h-8 shrink-0 grid-cols-4 gap-1">
        <Skeleton
          v-for="actionIndex in 4"
          :key="actionIndex"
          class="h-8 w-full"
        />
      </CardFooter>
    </Card>
  </div>

  <Card v-else-if="props.items.length === 0" class="gap-4">
    <CardHeader>
      <CardTitle class="text-lg">{{ props.emptyTitle }}</CardTitle>
    </CardHeader>
    <CardContent>
      <p class="text-sm text-muted-foreground">当前后端没有返回可浏览的产物。</p>
    </CardContent>
  </Card>

  <div
    v-else
    :aria-busy="props.loading"
    class="flex flex-wrap items-start gap-3"
  >
    <span
      v-if="props.loading"
      role="status"
      aria-live="polite"
      class="sr-only"
    >
      正在刷新产物列表...
    </span>
    <Card
      v-for="item in props.items"
      :key="item.slug"
      size="sm"
      class="h-52 w-88 max-w-full flex-none"
    >
      <CardHeader class="min-w-0">
        <CardTitle
          class="truncate text-base"
          :title="item.name"
        >
          {{ item.name }}
        </CardTitle>
        <div
          class="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground"
          :title="authorTitle(item)"
        >
          <UserRoundIcon
            class="size-3.5 shrink-0"
            aria-hidden="true"
          />
          <span class="shrink-0">作者</span>
          <span class="truncate font-medium">
            {{ authorLabel(item) }}
          </span>
        </div>
        <CardDescription
          class="line-clamp-3 min-h-16"
          :title="item.description"
        >
          {{ item.description }}
        </CardDescription>
      </CardHeader>
      <CardFooter class="mt-auto grid h-8 shrink-0 grid-cols-4 gap-1">
        <Button
          class="col-start-1 w-full min-w-0"
          variant="outline"
          size="sm"
          @click="emit('select', item.slug)"
        >
          <FileSearchIcon data-icon="inline-start" />
          详情
        </Button>
        <Button
          class="col-start-2 w-full min-w-0"
          variant="outline"
          size="sm"
          :disabled="props.openingSlug === item.slug"
          @click="emit('openPreview', item.slug)"
        >
          <EyeIcon data-icon="inline-start" />
          {{ props.openingSlug === item.slug ? "加载中" : "查看" }}
        </Button>
        <Button
          v-if="item.can_manage_share"
          class="col-start-3 w-full min-w-0"
          variant="outline"
          size="sm"
          :disabled="props.sharingSlug === item.slug"
          @click="emit('share', item.slug)"
        >
          <Share2Icon data-icon="inline-start" />
          {{ props.sharingSlug === item.slug ? "加载中" : "分享" }}
        </Button>
        <Button
          v-if="props.editEnabled && item.can_edit"
          class="col-start-4 w-full min-w-0"
          variant="outline"
          size="sm"
          :disabled="Boolean(props.editingSlug)"
          @click="emit('edit', item.slug)"
        >
          <FilePenLineIcon data-icon="inline-start" />
          {{ props.editingSlug === item.slug ? "创建中" : "编辑" }}
        </Button>
      </CardFooter>
    </Card>
  </div>
</template>
