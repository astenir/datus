<script setup lang="ts">
import { ExternalLinkIcon, FileSearchIcon, Share2Icon } from "@lucide/vue"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
}>()

const emit = defineEmits<{
  select: [slug: string]
  openPreview: [slug: string]
  share: [slug: string]
}>()
</script>

<template>
  <div
    v-if="props.loading"
    class="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
  >
    <Card
      v-for="index in 3"
      :key="index"
    >
      <CardHeader>
        <Skeleton class="h-5 w-36" />
      </CardHeader>
      <CardContent class="flex flex-col gap-3">
        <Skeleton class="h-4 w-full" />
        <Skeleton class="h-4 w-2/3" />
        <Skeleton class="h-8 w-24" />
      </CardContent>
    </Card>
  </div>

  <Card v-else-if="props.items.length === 0">
    <CardHeader>
      <CardTitle class="text-lg">{{ props.emptyTitle }}</CardTitle>
    </CardHeader>
    <CardContent>
      <p class="text-sm text-muted-foreground">当前后端没有返回可浏览的产物。</p>
    </CardContent>
  </Card>

  <div
    v-else
    class="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
  >
    <Card
      v-for="item in props.items"
      :key="item.slug"
    >
      <CardHeader>
        <CardTitle class="text-base">{{ item.name }}</CardTitle>
      </CardHeader>
      <CardContent class="flex flex-col gap-3">
        <p class="min-h-10 text-sm text-muted-foreground">{{ item.description }}</p>
        <div class="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            @click="emit('select', item.slug)"
          >
            <FileSearchIcon data-icon="inline-start" />
            详情
          </Button>
          <Button
            variant="outline"
            size="sm"
            :disabled="props.openingSlug === item.slug"
            @click="emit('openPreview', item.slug)"
          >
            <ExternalLinkIcon data-icon="inline-start" />
            {{ props.openingSlug === item.slug ? "打开中" : "打开" }}
          </Button>
          <Button
            variant="outline"
            size="sm"
            :disabled="props.sharingSlug === item.slug"
            @click="emit('share', item.slug)"
          >
            <Share2Icon data-icon="inline-start" />
            {{ props.sharingSlug === item.slug ? "加载中" : "分享" }}
          </Button>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
