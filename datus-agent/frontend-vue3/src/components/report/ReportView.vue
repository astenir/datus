<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { ArrowLeft, Clock, Database, FileText, Loader2, RefreshCw, Table2 } from "@lucide/vue";

import Badge from "@/components/ui/Badge.vue";
import Button from "@/components/ui/Button.vue";
import ScrollArea from "@/components/ui/ScrollArea.vue";
import { reportApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import type { ArtifactManifest } from "@/types";

// ─── State ───────────────────────────────────────────────────────────────────

const reports = ref<ArtifactManifest[]>([]);
const loading = ref(false);
const selectedSlug = ref<string | null>(null);
const iframeLoading = ref(false);

// ─── Load list ───────────────────────────────────────────────────────────────

async function loadReports() {
  loading.value = true;
  try {
    const { effectiveBase } = useConnection();
    const result = await reportApi.list(effectiveBase());
    if (result) reports.value = result;
  } catch (e) {
    console.error("Failed to load reports:", e);
  } finally {
    loading.value = false;
  }
}

// ─── Select report ───────────────────────────────────────────────────────────

function selectReport(slug: string) {
  selectedSlug.value = slug;
  iframeLoading.value = true;
}

function goBack() {
  selectedSlug.value = null;
}

// ─── Derived ─────────────────────────────────────────────────────────────────

const iframeSrc = computed(() => {
  if (!selectedSlug.value) return "";
  const { effectiveBase } = useConnection();
  return reportApi.htmlUrl(effectiveBase(), selectedSlug.value);
});

const selectedManifest = computed(() =>
  reports.value.find((d) => d.slug === selectedSlug.value) ?? null
);

function formatDate(iso?: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

// ─── Init ────────────────────────────────────────────────────────────────────

onMounted(loadReports);
</script>

<template>
  <div class="reportView">
    <!-- List view -->
    <template v-if="!selectedSlug">
      <div class="reportHeader">
        <h2>可视化报告</h2>
        <div class="reportHeaderActions">
          <Button variant="ghost" size="icon" :disabled="loading" @click="loadReports">
            <Loader2 v-if="loading" class="spin" :size="16" />
            <RefreshCw v-else :size="16" />
          </Button>
        </div>
      </div>

      <ScrollArea class="reportList">
        <div v-if="loading && reports.length === 0" class="reportEmpty">
          <Loader2 class="spin" :size="24" />
          <p>加载中...</p>
        </div>
        <div v-else-if="reports.length === 0" class="reportEmpty">
          <FileText :size="32" />
          <p>暂无报告</p>
          <p class="reportEmptyHint">在对话中让 Agent 生成可视化报告</p>
        </div>
        <div v-else class="reportGrid">
          <button
            v-for="d in reports"
            :key="d.slug"
            class="reportCard"
            type="button"
            @click="selectReport(d.slug)"
          >
            <div class="reportCardHeader">
              <FileText :size="16" />
              <strong>{{ d.name }}</strong>
            </div>
            <p class="reportCardDesc">{{ d.description }}</p>
            <div class="reportCardMeta">
              <span v-if="d.created_at" class="reportCardDate">
                <Clock :size="12" />
                {{ formatDate(d.updated_at || d.created_at) }}
              </span>
              <Badge v-if="d.datasources && d.datasources.length > 0" variant="secondary">
                <Database :size="10" />
                {{ d.datasources.length }}
              </Badge>
              <Badge v-if="d.key_tables && d.key_tables.length > 0" variant="outline">
                <Table2 :size="10" />
                {{ d.key_tables.length }}
              </Badge>
            </div>
          </button>
        </div>
      </ScrollArea>
    </template>

    <!-- Detail view: iframe-rendered report -->
    <template v-else>
      <div class="reportHeader">
        <Button variant="ghost" size="icon" @click="goBack">
          <ArrowLeft :size="16" />
        </Button>
        <h2>{{ selectedManifest?.name ?? selectedSlug }}</h2>
        <div class="reportHeaderActions">
          <Badge v-if="selectedManifest?.datasources?.length" variant="secondary">
            <Database :size="10" />
            {{ selectedManifest.datasources.join(", ") }}
          </Badge>
          <span v-if="selectedManifest?.created_at" class="reportCardDate">
            <Clock :size="12" />
            {{ formatDate(selectedManifest.updated_at || selectedManifest.created_at) }}
          </span>
        </div>
      </div>

      <div class="reportIframeWrap">
        <div v-if="iframeLoading" class="reportIframeLoading">
          <Loader2 class="spin" :size="24" />
          <p>加载报告...</p>
        </div>
        <iframe
          v-if="iframeSrc"
          :src="iframeSrc"
          class="reportIframe"
          sandbox="allow-scripts allow-same-origin"
          frameborder="0"
          @load="iframeLoading = false"
        />
      </div>
    </template>
  </div>
</template>
