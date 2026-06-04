<script setup lang="ts">
import { computed, ref } from "vue";
import { BarChart3, Loader2, PieChart } from "@lucide/vue";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { BarChart, LineChart, PieChart as EchartsPie, ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

import Button from "@/components/ui/Button.vue";
import Badge from "@/components/ui/Badge.vue";
import { visualizationApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import type { VisualizationResult } from "@/types";

use([BarChart, LineChart, EchartsPie, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

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

const isDark = computed(() => document.documentElement.classList.contains("dark"));

const chartOption = computed(() => {
  if (!result.value?.chart || props.columns.length === 0 || props.data.length === 0) return null;

  const { chart } = result.value;
  const chartType = chart.chart_type;
  const xCol = chart.x_col || props.columns[0];
  const yCols = chart.y_cols?.length ? chart.y_cols : chart.numeric_columns;

  if (chartType === "Unknown" || !xCol) return null;

  const textColor = isDark.value ? "#d4d4d4" : "#333";
  const gridBg = isDark.value ? "#1a1a1a" : "#fff";
  const lineColor = isDark.value ? "#444" : "#e5e5e5";

  if (chartType === "Pie") {
    const pieData = props.data.map((row) => ({
      name: String(row[xCol] ?? ""),
      value: Number(row[yCols[0]] ?? 0),
    }));
    return {
      backgroundColor: gridBg,
      tooltip: { trigger: "item" as const },
      legend: { show: false },
      series: [
        {
          type: "pie" as const,
          data: pieData,
          radius: ["30%", "65%"],
          label: { color: textColor, fontSize: 11 },
        },
      ],
    };
  }

  // Bar / Line / Scatter
  const xData = props.data.map((row) => String(row[xCol] ?? ""));
  const series = yCols.map((col) => ({
    name: col,
    type: chartType.toLowerCase() as "bar" | "line" | "scatter",
    data: props.data.map((row) => Number(row[col] ?? 0)),
    smooth: chartType === "Line",
  }));

  return {
    backgroundColor: gridBg,
    tooltip: { trigger: "axis" as const },
    legend: yCols.length > 1 ? { show: true, textStyle: { color: textColor }, top: 4 } : undefined,
    grid: { left: 40, right: 16, top: yCols.length > 1 ? 30 : 16, bottom: 36 },
    xAxis: {
      type: "category" as const,
      data: xData,
      axisLabel: { color: textColor, fontSize: 10, rotate: xData.length > 10 ? 30 : 0 },
      axisLine: { lineStyle: { color: lineColor } },
    },
    yAxis: {
      type: "value" as const,
      axisLabel: { color: textColor, fontSize: 10 },
      splitLine: { lineStyle: { color: lineColor } },
    },
    dataZoom: xData.length > 20 ? [{ type: "inside" as const }] : undefined,
    series,
  };
});

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
      <div v-if="chartOption" class="dataVizChartRender">
        <VChart :option="chartOption" autoresize style="width: 100%; height: 260px;" />
      </div>
      <div v-if="result.data_insight" class="dataVizInsight">
        <p v-if="result.data_insight.insight">{{ result.data_insight.insight }}</p>
      </div>
    </div>
    <p v-if="error" class="dataVizError">{{ error }}</p>
  </div>
</template>
