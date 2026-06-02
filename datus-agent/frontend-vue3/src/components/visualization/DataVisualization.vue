<script setup lang="ts">
import { ref } from "vue";
import { BarChart3, Loader2, PieChart } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import Badge from "@/components/ui/Badge.vue";
import { visualizationApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import type { VisualizationResult } from "@/types";

const props = defineProps<{
  columns: string[];
  data: Record<string, unknown>[];
  sql?: string;
}>();

const loading = ref(false);
const result = ref<VisualizationResult | null>(null);
const error = ref("");

const chartTypeIcons: Record<string, typeof BarChart3> = {
  Bar: BarChart3,
  Line: BarChart3,
  Pie: PieChart,
  Scatter: BarChart3,
};

async function handleRecommend() {
  if (props.columns.length === 0 || props.data.length === 0) return;
  loading.value = true;
  error.value = "";
  try {
    const { effectiveBase } = useConnection();
    result.value = await visualizationApi.recommend(effectiveBase(), {
      columns: props.columns,
      data: props.data,
    }, { sql: props.sql });
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="dataViz">
    <Button v-if="!result" variant="ghost" size="sm" :disabled="loading || data.length === 0" @click="handleRecommend">
      <Loader2 v-if="loading" class="spin" :size="14" />
      <BarChart3 v-else :size="14" />
      推荐图表
    </Button>
    <div v-if="result" class="dataVizResult">
      <div class="dataVizChart">
        <component :is="chartTypeIcons[result.chart.chart_type] || BarChart3" :size="16" />
        <strong>{{ result.chart.chart_type }}</strong>
        <Badge variant="secondary">{{ result.chart.reason }}</Badge>
      </div>
      <p v-if="result.chart.x_col">X: {{ result.chart.x_col }}</p>
      <p v-if="result.chart.y_cols?.length">Y: {{ result.chart.y_cols.join(', ') }}</p>
      <div v-if="result.data_insight" class="dataVizInsight">
        <p v-if="result.data_insight.insight">{{ result.data_insight.insight }}</p>
      </div>
    </div>
    <p v-if="error" class="dataVizError">{{ error }}</p>
  </div>
</template>
