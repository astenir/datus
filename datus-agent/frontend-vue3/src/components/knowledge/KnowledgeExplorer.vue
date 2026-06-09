<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { BookOpen, ChevronRight, Copy, Database, Folder, FolderPlus, Loader2, Pencil, Check, Table2, RotateCw, X } from "@lucide/vue";
import yaml from "js-yaml";
import MarkdownIt from "markdown-it";

import Badge from "@/components/ui/Badge.vue";
import Button from "@/components/ui/Button.vue";
import ScrollArea from "@/components/ui/ScrollArea.vue";
import Input from "@/components/ui/Input.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Label from "@/components/ui/Label.vue";
import Sheet from "@/components/ui/Sheet.vue";
import SheetContent from "@/components/ui/SheetContent.vue";
import SheetHeader from "@/components/ui/SheetHeader.vue";
import SheetTitle from "@/components/ui/SheetTitle.vue";
import { subjectApi, catalogApi, tableApi } from "@/lib/api";
import BootstrapDialog from "./BootstrapDialog.vue";
import TreeNode from "./TreeNode.vue";
import CatalogTree from "./CatalogTree.vue";
import { useConnection } from "@/composables/useConnection";
import type { SubjectNode, MetricInfo, ReferenceSQLInfo, KnowledgeInfo, SubjectNodeType, DatabaseInfo, TableDetail } from "@/types";

const md = new MarkdownIt({ html: false, linkify: true });

interface ParsedMetric {
  name: string;
  description: string;
  type: string;
  typeParams: Record<string, unknown>;
  tags: string[];
  // Type-specific parsed fields
  numerator?: string;
  denominator?: string;
  expr?: string;
  measures: string[];
}

interface SmIdentifier { name: string; description: string; type: string; expr: string; }
interface SmMeasure { name: string; description: string; agg: string; expr: string; }
interface SmDimension { name: string; description: string; type: string; expr: string; typeParams?: Record<string, unknown>; }
interface ParsedSemanticModel {
  name: string;
  description: string;
  sqlQuery: string;
  identifiers: SmIdentifier[];
  measures: SmMeasure[];
  dimensions: SmDimension[];
  mutability: string;
}

const parsedMetric = computed<ParsedMetric | null>(() => {
  if (!metricDetail.value?.yaml) return null;
  try {
    const doc = yaml.load(metricDetail.value.yaml) as Record<string, unknown>;
    const m = doc?.metric as Record<string, unknown> | undefined;
    if (!m) return null;
    const locked = m.locked_metadata as Record<string, unknown> | undefined;
    const tags = (locked?.tags as string[]) ?? [];
    const typeParams = (m.type_params as Record<string, unknown>) ?? {};
    const type = String(m.type ?? "");

    // Parse type-specific fields
    let numerator: string | undefined;
    let denominator: string | undefined;
    let expr: string | undefined;
    let measures: string[] = [];

    if (type === "ratio") {
      const num = typeParams.numerator as Record<string, unknown> | undefined;
      const den = typeParams.denominator as Record<string, unknown> | undefined;
      numerator = num?.name ? String(num.name) : undefined;
      denominator = den?.name ? String(den.name) : undefined;
    } else if (type === "derived") {
      measures = ((typeParams.metrics as unknown[]) ?? []).map(String);
      expr = typeParams.expr ? String(typeParams.expr) : undefined;
    } else if (type === "expr" || type === "cumulative") {
      measures = ((typeParams.measures as unknown[]) ?? []).map(String);
      expr = typeParams.expr ? String(typeParams.expr) : undefined;
    } else {
      // simple / measure_proxy / unknown
      const raw = typeParams.measures ?? typeParams.measure;
      if (Array.isArray(raw)) {
        measures = raw.map((v) => (typeof v === "object" && v !== null ? String((v as Record<string, unknown>).name ?? v) : String(v)));
      } else if (raw != null) {
        measures = [typeof raw === "object" ? String((raw as Record<string, unknown>).name ?? raw) : String(raw)];
      }
    }

    return { name: String(m.name ?? ""), description: String(m.description ?? ""), type, typeParams, tags, numerator, denominator, expr, measures };
  } catch {
    return null;
  }
});

const parsedSemanticModel = computed<ParsedSemanticModel | null>(() => {
  if (!semanticModelYaml.value) return null;
  try {
    const doc = yaml.load(semanticModelYaml.value) as Record<string, unknown>;
    const ds = doc?.data_source as Record<string, unknown> | undefined;
    if (!ds) return null;
    const identifiers = ((ds.identifiers as unknown[]) ?? []).map((i) => {
      const item = i as Record<string, unknown>;
      return { name: String(item.name ?? ""), description: String(item.description ?? ""), type: String(item.type ?? ""), expr: String(item.expr ?? "") };
    });
    const measures = ((ds.measures as unknown[]) ?? []).map((m) => {
      const item = m as Record<string, unknown>;
      return { name: String(item.name ?? ""), description: String(item.description ?? ""), agg: String(item.agg ?? ""), expr: String(item.expr ?? "") };
    });
    const dimensions = ((ds.dimensions as unknown[]) ?? []).map((d) => {
      const item = d as Record<string, unknown>;
      return {
        name: String(item.name ?? ""),
        description: String(item.description ?? ""),
        type: String(item.type ?? ""),
        expr: String(item.expr ?? ""),
        typeParams: item.type_params as Record<string, unknown> | undefined,
      };
    });
    const mut = doc.mutability as Record<string, unknown> | undefined;
    return {
      name: String(ds.name ?? ""),
      description: String(ds.description ?? ""),
      sqlQuery: String(ds.sql_query ?? ""),
      identifiers,
      measures,
      dimensions,
      mutability: String(mut?.type ?? ""),
    };
  } catch {
    return null;
  }
});

const knowledgeHtml = computed(() => {
  if (!knowledgeDetail.value?.explanation) return "";
  return md.render(knowledgeDetail.value.explanation);
});

const metricTypeColors: Record<string, "default" | "secondary" | "destructive" | "outline" | "success"> = {
  simple: "success",
  measure_proxy: "secondary",
  ratio: "default",
  derived: "outline",
  expr: "destructive",
  cumulative: "secondary",
};

function formatParamValue(val: unknown): string {
  if (Array.isArray(val)) return val.join(", ");
  if (typeof val === "object" && val !== null) return JSON.stringify(val);
  return String(val ?? "");
}

function splitSearchText(text: string): string[] {
  return text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);
}

const copiedField = ref<string | null>(null);

async function copyToClipboard(text: string, fieldId: string) {
  try {
    await navigator.clipboard.writeText(text);
    copiedField.value = fieldId;
    setTimeout(() => { copiedField.value = null; }, 1500);
  } catch {
    // fallback
  }
}

function copyCardText(el: HTMLElement, fieldId: string) {
  const clone = el.cloneNode(true) as HTMLElement;
  clone.querySelectorAll("button").forEach((b) => b.remove());
  copyToClipboard(clone.innerText.trim(), fieldId);
}

// ─── State ───────────────────────────────────────────────────────────────────

const subjects = ref<SubjectNode[]>([]);
const loading = ref(false);
const selectedNode = ref<SubjectNode | null>(null);
const detailLoading = ref(false);

// Catalog tree state
const activeTree = ref<"subject" | "catalog">("subject");
const catalogEntries = ref<DatabaseInfo[]>([]);
const catalogLoading = ref(false);
const selectedTable = ref<string>("");
const tableDetail = ref<TableDetail | null>(null);
const semanticModelYaml = ref<string | null>(null);

// Bootstrap
const showBootstrap = ref(false);

// Detail data
const metricDetail = ref<MetricInfo | null>(null);
const sqlDetail = ref<ReferenceSQLInfo | null>(null);
const knowledgeDetail = ref<KnowledgeInfo | null>(null);

// Create/rename dialog
const showCreateDialog = ref(false);
const createType = ref<SubjectNodeType>("directory");
const createName = ref("");
const createParentPath = ref<string[]>([]);

// ─── Load tree ───────────────────────────────────────────────────────────────

async function loadSubjects() {
  loading.value = true;
  try {
    const { effectiveBase } = useConnection();
    const result = await subjectApi.list(effectiveBase());
    if (result) subjects.value = result.subjects ?? [];
  } catch (e) {
    console.error("Failed to load subjects:", e);
  } finally {
    loading.value = false;
  }
}

async function loadCatalog() {
  catalogLoading.value = true;
  try {
    const { effectiveBase } = useConnection();
    const result = await catalogApi.list(effectiveBase());
    if (result) catalogEntries.value = result.databases ?? [];
  } catch (e) {
    console.error("Failed to load catalog:", e);
  } finally {
    catalogLoading.value = false;
  }
}

// ─── Select node ─────────────────────────────────────────────────────────────

async function selectNode(node: SubjectNode) {
  selectedNode.value = node;
  selectedTable.value = "";
  tableDetail.value = null;
  semanticModelYaml.value = null;
  metricDetail.value = null;
  sqlDetail.value = null;
  knowledgeDetail.value = null;
  if (!node.type || node.type === "directory") return;

  detailLoading.value = true;
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    if (node.type === "metric") {
      metricDetail.value = await subjectApi.getMetric(base, node.subject_path);
    } else if (node.type === "reference_sql") {
      sqlDetail.value = await subjectApi.getReferenceSql(base, node.subject_path);
    } else if (node.type === "knowledge") {
      knowledgeDetail.value = await subjectApi.getKnowledge(base, node.subject_path);
    }
  } catch (e) {
    console.error("Failed to load detail:", e);
  } finally {
    detailLoading.value = false;
  }
}

async function selectTable(tableName: string) {
  selectedTable.value = tableName;
  selectedNode.value = null;
  metricDetail.value = null;
  sqlDetail.value = null;
  knowledgeDetail.value = null;
  tableDetail.value = null;
  semanticModelYaml.value = null;

  detailLoading.value = true;
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const [detailResult, smResult] = await Promise.all([
      tableApi.detail(base, tableName),
      tableApi.getSemanticModel(base, tableName),
    ]);
    if (detailResult) tableDetail.value = detailResult.table;
    semanticModelYaml.value = smResult?.yaml ?? null;
  } catch (e) {
    console.error("Failed to load table detail:", e);
  } finally {
    detailLoading.value = false;
  }
}

function switchTree(tree: "subject" | "catalog") {
  activeTree.value = tree;
  if (tree === "catalog" && catalogEntries.value.length === 0) {
    loadCatalog();
  }
}

// ─── CRUD operations ─────────────────────────────────────────────────────────

function openCreate(parentPath: string[], type: SubjectNodeType) {
  createParentPath.value = parentPath;
  createType.value = type;
  createName.value = "";
  showCreateDialog.value = true;
}

async function handleCreate() {
  if (!createName.value.trim()) return;
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  const path = [...createParentPath.value, createName.value.trim()];
  try {
    if (createType.value === "directory") {
      await subjectApi.create(base, path);
    } else if (createType.value === "metric") {
      await subjectApi.createMetric(base, path, createName.value.trim());
    } else if (createType.value === "knowledge") {
      await subjectApi.createKnowledge(base, path, createName.value.trim(), "", "");
    }
    showCreateDialog.value = false;
    await loadSubjects();
  } catch (e) {
    console.error("Create failed:", e);
  }
}

async function handleDelete(node: SubjectNode) {
  if (!confirm(`确定删除 "${node.name}"？`)) return;
  const { effectiveBase } = useConnection();
  try {
    await subjectApi.delete(effectiveBase(), node.type || "directory", node.subject_path);
    if (selectedNode.value?.subject_path.join("/") === node.subject_path.join("/")) {
      selectedNode.value = null;
    }
    await loadSubjects();
  } catch (e) {
    console.error("Delete failed:", e);
  }
}

// ─── Edit handlers ───────────────────────────────────────────────────────────

function handleEditKeydown(e: KeyboardEvent, saveFn: () => void, cancelFn?: () => void) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    saveFn();
  }
  if (e.key === "Escape") {
    e.preventDefault();
    (cancelFn ?? cancelEdit)();
  }
}

// Per-card editing state: tracks which card is being edited
const editingField = ref<string | null>(null);
const editingValue = ref("");

function startEdit(field: string, value?: string | null) {
  editingField.value = field;
  editingValue.value = value ?? "";
}

function cancelEdit() {
  editingField.value = null;
  editingValue.value = "";
}

function isEditing(field: string) {
  return editingField.value === field;
}

// ── Metric (YAML) ─────────────────────────────────────────────────────────

const editingMetric = ref(false);
const editingMetricYaml = ref("");

function startEditMetric() {
  if (!metricDetail.value) return;
  editingMetricYaml.value = metricDetail.value.yaml;
  editingMetric.value = true;
}

async function saveMetric() {
  if (!selectedNode.value) return;
  const { effectiveBase } = useConnection();
  try {
    await subjectApi.editMetric(effectiveBase(), selectedNode.value.subject_path, editingMetricYaml.value);
    metricDetail.value = { ...metricDetail.value!, yaml: editingMetricYaml.value };
    editingMetric.value = false;
  } catch (e) {
    console.error("Save metric failed:", e);
  }
}

// ── Reference SQL (per-card) ───────────────────────────────────────────────

async function saveSqlField(field: "summary" | "sql" | "search_text") {
  if (!selectedNode.value || !sqlDetail.value) return;
  const updated = { ...sqlDetail.value, [field]: editingValue.value };
  const { effectiveBase } = useConnection();
  try {
    await subjectApi.editReferenceSql(effectiveBase(), {
      name: updated.name,
      sql: updated.sql,
      summary: updated.summary,
      search_text: updated.search_text,
      subject_path: selectedNode.value.subject_path,
    });
    sqlDetail.value = updated;
    cancelEdit();
  } catch (e) {
    console.error("Save SQL field failed:", e);
  }
}

// ── Knowledge (per-card) ───────────────────────────────────────────────────

async function saveKnowledgeField(field: "explanation" | "search_text") {
  if (!selectedNode.value || !knowledgeDetail.value) return;
  const updated = { ...knowledgeDetail.value, [field]: editingValue.value };
  const { effectiveBase } = useConnection();
  try {
    await subjectApi.editKnowledge(effectiveBase(), selectedNode.value.subject_path, updated.search_text, updated.explanation);
    knowledgeDetail.value = updated;
    cancelEdit();
  } catch (e) {
    console.error("Save knowledge field failed:", e);
  }
}

// ── Semantic Model (per-card) ──────────────────────────────────────────────

const editingSm = ref(false);
const editingSmYaml = ref("");

function startEditSm() {
  editingSmYaml.value = semanticModelYaml.value ?? "";
  editingSm.value = true;
}

async function saveSm() {
  if (!selectedTable.value) return;
  const { effectiveBase } = useConnection();
  try {
    await tableApi.saveSemanticModel(effectiveBase(), selectedTable.value, editingSmYaml.value);
    semanticModelYaml.value = editingSmYaml.value;
    editingSm.value = false;
  } catch (e) {
    console.error("Save semantic model failed:", e);
  }
}

// ─── Init ────────────────────────────────────────────────────────────────────

onMounted(loadSubjects);
</script>

<template>
  <div class="knowledgeExplorer">
    <!-- Left: tree -->
    <div class="knowledgeTree">
      <!-- Tab bar -->
      <div class="treeTabBar">
        <button
          :class="['treeTab', { active: activeTree === 'subject' }]"
          @click="switchTree('subject')"
        >
          <BookOpen :size="14" />
          Subject
        </button>
        <button
          :class="['treeTab', { active: activeTree === 'catalog' }]"
          @click="switchTree('catalog')"
        >
          <Database :size="14" />
          Catalog
        </button>
      </div>

      <!-- Subject tree header -->
      <div v-if="activeTree === 'subject'" class="knowledgeTreeHeader">
        <div class="knowledgeTreeActions">
          <Button variant="ghost" size="icon" aria-label="Bootstrap" title="知识库构建" @click="showBootstrap = true">
            <Database :size="16" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="新建目录" @click="openCreate([], 'directory')">
            <FolderPlus :size="16" />
          </Button>
          <Button variant="ghost" size="icon" :disabled="loading" aria-label="刷新" @click="loadSubjects">
            <Loader2 v-if="loading" class="spin" :size="16" />
            <RotateCw v-else :size="16" />
          </Button>
        </div>
      </div>

      <!-- Catalog tree header -->
      <div v-if="activeTree === 'catalog'" class="knowledgeTreeHeader">
        <div class="knowledgeTreeActions">
          <Button variant="ghost" size="icon" :disabled="catalogLoading" aria-label="刷新" @click="loadCatalog">
            <Loader2 v-if="catalogLoading" class="spin" :size="16" />
            <RotateCw v-else :size="16" />
          </Button>
        </div>
      </div>

      <!-- Subject tree content -->
      <ScrollArea v-if="activeTree === 'subject'" class="knowledgeTreeContent">
        <div v-if="loading" class="knowledgeTreeLoading">
          <Loader2 class="spin" :size="20" />
        </div>
        <div v-else-if="subjects.length === 0" class="knowledgeTreeEmpty">
          <Folder :size="24" />
          <p>暂无 Subject</p>
        </div>
        <template v-else>
          <TreeNode
            v-for="node in subjects"
            :key="node.subject_path.join('/')"
            :node="node"
            :selected-path="selectedNode?.subject_path.join('/') ?? ''"
            :depth="0"
            @select="selectNode"
            @create="openCreate"
            @delete="handleDelete"
          />
        </template>
      </ScrollArea>

      <!-- Catalog tree content -->
      <ScrollArea v-if="activeTree === 'catalog'" class="knowledgeTreeContent">
        <div v-if="catalogLoading" class="knowledgeTreeLoading">
          <Loader2 class="spin" :size="20" />
        </div>
        <CatalogTree
          v-else
          :entries="catalogEntries"
          :selected-table="selectedTable"
          @select="selectTable"
        />
      </ScrollArea>
    </div>

    <!-- Right: detail -->
    <div class="knowledgeDetail">
      <div v-if="!selectedNode && !selectedTable" class="knowledgeDetailEmpty">
        <BookOpen :size="32" />
        <p>选择左侧节点查看详情</p>
      </div>
      <div v-else-if="detailLoading" class="knowledgeDetailLoading">
        <Loader2 class="spin" :size="24" />
      </div>
      <div v-else class="knowledgeDetailContent">
        <!-- Header for subject node -->
        <div v-if="selectedNode" class="knowledgeDetailHeader">
          <h3>{{ selectedNode.name }}</h3>
          <span class="knowledgeDetailType">{{ selectedNode.type || 'directory' }}</span>
        </div>
        <!-- Header for catalog table -->
        <div v-else-if="selectedTable && tableDetail" class="knowledgeDetailHeader">
          <h3>{{ tableDetail.name }}</h3>
          <span class="knowledgeDetailType">table</span>
        </div>

        <!-- Metric detail -->
        <div v-if="selectedNode?.type === 'metric' && metricDetail" class="knowledgeDetailBody">
          <div v-if="!editingMetric">
            <!-- Structured view -->
            <template v-if="parsedMetric">
              <div class="detailCard">
                <div class="detailCardHeader detailCardHeader--metric">
                  <span class="detailCardHeaderTitle">
                    <span class="metricCardName">{{ parsedMetric.name }}</span>
                    <Badge :variant="metricTypeColors[parsedMetric.type] ?? 'secondary'" style="margin-left: 6px;">
                      {{ parsedMetric.type }}
                    </Badge>
                  </span>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEditMetric">
                    <Pencil :size="14" />
                  </Button>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'metric-info')">
                    <Check v-if="copiedField === 'metric-info'" :size="14" class="copySuccess" />
                    <Copy v-else :size="14" />
                  </Button>
                </div>
                <div class="detailCardBody">
                  <p v-if="parsedMetric.description" class="metricDescription">{{ parsedMetric.description }}</p>
                  <div v-if="parsedMetric.tags.length" class="metricTags">
                    <span v-for="tag in parsedMetric.tags" :key="tag" class="metricTag">{{ tag }}</span>
                  </div>
                </div>
              </div>

              <!-- Ratio: numerator / denominator -->
              <div v-if="parsedMetric.type === 'ratio' && (parsedMetric.numerator || parsedMetric.denominator)" class="detailCard">
                <div class="detailCardHeader detailCardHeader--metric">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Ratio</h4></span>
                </div>
                <div class="detailCardBody">
                  <div class="metricParamsGrid">
                    <div v-if="parsedMetric.numerator" class="metricParamItem">
                      <span class="metricParamKey">Numerator</span>
                      <code class="metricParamVal">{{ parsedMetric.numerator }}</code>
                    </div>
                    <div v-if="parsedMetric.denominator" class="metricParamItem">
                      <span class="metricParamKey">Denominator</span>
                      <code class="metricParamVal">{{ parsedMetric.denominator }}</code>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Derived / Expr / Cumulative: expression + measures/metrics -->
              <div v-if="(parsedMetric.type === 'derived' || parsedMetric.type === 'expr' || parsedMetric.type === 'cumulative') && (parsedMetric.expr || parsedMetric.measures.length)" class="detailCard">
                <div class="detailCardHeader detailCardHeader--metric">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">{{ parsedMetric.type === 'derived' ? 'Derived From' : 'Expression' }}</h4></span>
                </div>
                <div class="detailCardBody">
                  <div class="metricParamsGrid">
                    <div v-if="parsedMetric.expr" class="metricParamItem">
                      <span class="metricParamKey">Formula</span>
                      <code class="metricParamVal">{{ parsedMetric.expr }}</code>
                    </div>
                    <div v-if="parsedMetric.measures.length" class="metricParamItem">
                      <span class="metricParamKey">{{ parsedMetric.type === 'derived' ? 'Metrics' : 'Measures' }}</span>
                      <span class="metricParamVal">
                        <span v-for="(m, i) in parsedMetric.measures" :key="m">
                          <code>{{ m }}</code><span v-if="i < parsedMetric.measures.length - 1">, </span>
                        </span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Simple / Measure Proxy: measure name(s) -->
              <div v-if="(parsedMetric.type === 'simple' || parsedMetric.type === 'measure_proxy') && parsedMetric.measures.length" class="detailCard">
                <div class="detailCardHeader detailCardHeader--metric">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">{{ parsedMetric.type === 'measure_proxy' ? 'Proxy Measure' : 'Measure' }}</h4></span>
                </div>
                <div class="detailCardBody">
                  <div class="metricParamsGrid">
                    <div class="metricParamItem">
                      <span class="metricParamKey">Name</span>
                      <span class="metricParamVal">
                        <span v-for="(m, i) in parsedMetric.measures" :key="m">
                          <code>{{ m }}</code><span v-if="i < parsedMetric.measures.length - 1">, </span>
                        </span>
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Fallback: generic type_params for unknown types -->
              <div v-if="!['ratio','derived','expr','cumulative','simple','measure_proxy'].includes(parsedMetric.type) && Object.keys(parsedMetric.typeParams).length" class="detailCard">
                <div class="detailCardHeader detailCardHeader--metric">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Type Parameters</h4></span>
                </div>
                <div class="detailCardBody">
                  <div class="metricParamsGrid">
                    <template v-for="(val, key) in parsedMetric.typeParams" :key="key">
                      <div class="metricParamItem">
                        <span class="metricParamKey">{{ key }}</span>
                        <span class="metricParamVal">{{ formatParamValue(val) }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
              <details class="detailCollapsible">
                <summary>Raw YAML</summary>
                <pre class="knowledgeYaml">{{ metricDetail.yaml }}</pre>
              </details>
            </template>
            <!-- Fallback: raw YAML if parse fails -->
            <template v-else>
              <div class="detailCard">
                <div class="detailCardHeader detailCardHeader--metric">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Raw YAML</h4></span>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEditMetric">
                    <Pencil :size="14" />
                  </Button>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'metric-yaml')">
                    <Check v-if="copiedField === 'metric-yaml'" :size="14" class="copySuccess" />
                    <Copy v-else :size="14" />
                  </Button>
                </div>
                <div class="detailCardBody">
                  <pre class="knowledgeYaml">{{ metricDetail.yaml }}</pre>
                </div>
              </div>
            </template>
          </div>
          <div v-else class="knowledgeEditForm" @keydown="handleEditKeydown($event, saveMetric, () => { editingMetric = false })">
            <div class="detailCard">
              <div class="detailCardHeader detailCardHeader--metric">
                <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">YAML</h4></span>
                <span class="cardEditMeta">{{ editingMetricYaml.split('\n').length }} lines</span>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="取消" @click="editingMetric = false">
                  <X :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn cardSaveBtn" title="保存 (Ctrl+Enter)" @click="saveMetric">
                  <Check :size="14" />
                </Button>
              </div>
              <div class="detailCardBody">
                <Textarea v-model="editingMetricYaml" class="editCodearea" :rows="14" placeholder="metric:\n  name: ...\n  description: ..." />
              </div>
            </div>
          </div>
        </div>

        <!-- Reference SQL detail -->
        <div v-if="selectedNode?.type === 'reference_sql' && sqlDetail" class="knowledgeDetailBody">
          <!-- Summary card -->
          <div class="detailCard">
            <div class="detailCardHeader">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Summary</h4></span>
              <template v-if="isEditing('sql-summary')">
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="取消" @click="cancelEdit">
                  <X :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn cardSaveBtn" title="保存 (Ctrl+Enter)" @click="saveSqlField('summary')">
                  <Check :size="14" />
                </Button>
              </template>
              <template v-else>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEdit('sql-summary', sqlDetail.summary ?? '')">
                  <Pencil :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'sql-summary')">
                  <Check v-if="copiedField === 'sql-summary'" :size="14" class="copySuccess" />
                  <Copy v-else :size="14" />
                </Button>
              </template>
            </div>
            <div class="detailCardBody" @keydown="handleEditKeydown($event, () => saveSqlField('summary'))">
              <Textarea v-if="isEditing('sql-summary')" v-model="editingValue" class="cardEditarea" :rows="3" placeholder="SQL 摘要描述" />
              <p v-else class="detailCardText">{{ sqlDetail.summary }}</p>
            </div>
          </div>
          <!-- SQL block with header -->
          <div class="detailCard">
            <div class="detailCardHeader">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">SQL</h4></span>
              <template v-if="isEditing('sql-code')">
                <span class="cardEditMeta">{{ editingValue.split('\n').length }} lines</span>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="取消" @click="cancelEdit">
                  <X :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn cardSaveBtn" title="保存 (Ctrl+Enter)" @click="saveSqlField('sql')">
                  <Check :size="14" />
                </Button>
              </template>
              <template v-else>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEdit('sql-code', sqlDetail.sql ?? '')">
                  <Pencil :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'sql-code')">
                  <Check v-if="copiedField === 'sql-code'" :size="14" class="copySuccess" />
                  <Copy v-else :size="14" />
                </Button>
              </template>
            </div>
            <div @keydown="handleEditKeydown($event, () => saveSqlField('sql'))">
              <Textarea v-if="isEditing('sql-code')" v-model="editingValue" class="editCodearea" :rows="10" placeholder="SELECT ..." style="margin: 0; border-radius: 0;" />
              <pre v-else class="sqlBlockCode">{{ sqlDetail.sql }}</pre>
            </div>
          </div>
          <!-- Search text card -->
          <div v-if="sqlDetail.search_text || isEditing('sql-search')" class="detailCard">
            <div class="detailCardHeader">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Search Text</h4></span>
              <template v-if="isEditing('sql-search')">
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="取消" @click="cancelEdit">
                  <X :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn cardSaveBtn" title="保存 (Ctrl+Enter)" @click="saveSqlField('search_text')">
                  <Check :size="14" />
                </Button>
              </template>
              <template v-else>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEdit('sql-search', sqlDetail.search_text ?? '')">
                  <Pencil :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'sql-search')">
                  <Check v-if="copiedField === 'sql-search'" :size="14" class="copySuccess" />
                  <Copy v-else :size="14" />
                </Button>
              </template>
            </div>
            <div class="detailCardBody" @keydown="handleEditKeydown($event, () => saveSqlField('search_text'))">
              <Textarea v-if="isEditing('sql-search')" v-model="editingValue" class="cardEditarea" :rows="3" placeholder="用于向量检索的文本" />
              <div v-else class="searchTextSegments">
                <p
                  v-for="(seg, i) in splitSearchText(sqlDetail.search_text ?? '')"
                  :key="i"
                  class="searchTextSegment"
                >
                  {{ seg }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Knowledge detail -->
        <div v-if="selectedNode?.type === 'knowledge' && knowledgeDetail" class="knowledgeDetailBody">
          <!-- Explanation rendered as markdown -->
          <div class="detailCard">
            <div class="detailCardHeader detailCardHeader--knowledge">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Explanation</h4></span>
              <template v-if="isEditing('knowledge-explanation')">
                <span class="cardEditMeta">支持 Markdown</span>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="取消" @click="cancelEdit">
                  <X :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn cardSaveBtn" title="保存 (Ctrl+Enter)" @click="saveKnowledgeField('explanation')">
                  <Check :size="14" />
                </Button>
              </template>
              <template v-else>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEdit('knowledge-explanation', knowledgeDetail.explanation ?? '')">
                  <Pencil :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'knowledge-explanation')">
                  <Check v-if="copiedField === 'knowledge-explanation'" :size="14" class="copySuccess" />
                  <Copy v-else :size="14" />
                </Button>
              </template>
            </div>
            <div class="detailCardBody" @keydown="handleEditKeydown($event, () => saveKnowledgeField('explanation'))">
              <Textarea v-if="isEditing('knowledge-explanation')" v-model="editingValue" class="cardEditarea" :rows="8" placeholder="知识条目的详细解释..." />
              <div v-else class="knowledgeMarkdown markdownBody" v-html="knowledgeHtml" />
            </div>
          </div>
          <!-- Search text card -->
          <div class="detailCard">
            <div class="detailCardHeader detailCardHeader--knowledge">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Search Text</h4></span>
              <template v-if="isEditing('knowledge-search')">
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="取消" @click="cancelEdit">
                  <X :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn cardSaveBtn" title="保存 (Ctrl+Enter)" @click="saveKnowledgeField('search_text')">
                  <Check :size="14" />
                </Button>
              </template>
              <template v-else>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEdit('knowledge-search', knowledgeDetail.search_text ?? '')">
                  <Pencil :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'knowledge-search')">
                  <Check v-if="copiedField === 'knowledge-search'" :size="14" class="copySuccess" />
                  <Copy v-else :size="14" />
                </Button>
              </template>
            </div>
            <div class="detailCardBody" @keydown="handleEditKeydown($event, () => saveKnowledgeField('search_text'))">
              <Textarea v-if="isEditing('knowledge-search')" v-model="editingValue" class="cardEditarea" :rows="3" placeholder="用于向量检索的文本" />
              <div v-else class="searchTextSegments">
                <p
                  v-for="(seg, i) in splitSearchText(knowledgeDetail.search_text ?? '')"
                  :key="i"
                  class="searchTextSegment"
                >
                  {{ seg }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Table detail (Catalog) -->
        <div v-if="selectedTable && tableDetail" class="knowledgeDetailBody">
          <!-- Row count -->
          <div v-if="tableDetail.rows != null" class="detailCard">
            <div class="detailCardHeader detailCardHeader--table">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Rows</h4></span>
              <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'table-rows')">
                <Check v-if="copiedField === 'table-rows'" :size="14" class="copySuccess" />
                <Copy v-else :size="14" />
              </Button>
            </div>
            <div class="detailCardBody">
              <p class="detailCardText">{{ tableDetail.rows.toLocaleString() }}</p>
            </div>
          </div>
          <!-- Columns table -->
          <div class="detailCard">
            <div class="detailCardHeader detailCardHeader--table">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Columns ({{ tableDetail.columns.length }})</h4></span>
              <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'table-columns')">
                <Check v-if="copiedField === 'table-columns'" :size="14" class="copySuccess" />
                <Copy v-else :size="14" />
              </Button>
            </div>
            <div class="detailCardBody">
              <table class="tableDetailTable">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Nullable</th>
                    <th>PK</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="col in tableDetail.columns" :key="col.name">
                    <td>{{ col.name }}</td>
                    <td><code>{{ col.type }}</code></td>
                    <td>{{ col.nullable ? '✓' : '' }}</td>
                    <td>{{ col.pk ? '✓' : '' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <!-- Indexes -->
          <div v-if="tableDetail.indexes.length" class="detailCard">
            <div class="detailCardHeader detailCardHeader--table">
              <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Indexes ({{ tableDetail.indexes.length }})</h4></span>
              <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyCardText(($event.currentTarget as HTMLElement).closest('.detailCard')!, 'table-indexes')">
                <Check v-if="copiedField === 'table-indexes'" :size="14" class="copySuccess" />
                <Copy v-else :size="14" />
              </Button>
            </div>
            <div class="detailCardBody">
              <div class="indexList">
                <div v-for="idx in tableDetail.indexes" :key="idx.name" class="indexItem">
                  <span class="indexName">{{ idx.name }}</span>
                  <Badge variant="secondary">{{ idx.type }}</Badge>
                  <span class="indexColumns">{{ idx.columns.join(', ') }}</span>
                </div>
              </div>
            </div>
          </div>
          <!-- Semantic Model -->
          <template v-if="selectedTable && semanticModelYaml !== null">
            <!-- Edit mode -->
            <div v-if="editingSm" class="detailCard" @keydown="handleEditKeydown($event, saveSm, () => { editingSm = false })">
              <div class="detailCardHeader detailCardHeader--table">
                <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Semantic Model — YAML</h4></span>
                <span class="cardEditMeta">{{ editingSmYaml.split('\n').length }} lines</span>
                <Button variant="ghost" size="icon" class="cardCopyBtn" title="取消" @click="editingSm = false">
                  <X :size="14" />
                </Button>
                <Button variant="ghost" size="icon" class="cardCopyBtn cardSaveBtn" title="保存 (Ctrl+Enter)" @click="saveSm">
                  <Check :size="14" />
                </Button>
              </div>
              <div class="detailCardBody">
                <Textarea v-model="editingSmYaml" class="editCodearea" :rows="18" />
              </div>
            </div>

            <!-- Structured view -->
            <template v-else-if="parsedSemanticModel">
              <!-- Data Source -->
              <div class="detailCard">
                <div class="detailCardHeader detailCardHeader--table">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Data Source</h4></span>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEditSm">
                    <Pencil :size="14" />
                  </Button>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyToClipboard(semanticModelYaml ?? '', 'sm-yaml')">
                    <Check v-if="copiedField === 'sm-yaml'" :size="14" class="copySuccess" />
                    <Copy v-else :size="14" />
                  </Button>
                </div>
                <div class="detailCardBody">
                  <div class="smFieldGrid">
                    <span class="smFieldKey">Name</span>
                    <span class="smFieldValue">{{ parsedSemanticModel.name }}</span>
                    <span class="smFieldKey">Description</span>
                    <span class="smFieldValue">{{ parsedSemanticModel.description }}</span>
                    <span class="smFieldKey">SQL</span>
                    <code class="smFieldValue smFieldSql">{{ parsedSemanticModel.sqlQuery }}</code>
                    <span v-if="parsedSemanticModel.mutability" class="smFieldKey">Mutability</span>
                    <Badge v-if="parsedSemanticModel.mutability" variant="secondary">{{ parsedSemanticModel.mutability }}</Badge>
                  </div>
                </div>
              </div>

              <!-- Identifiers -->
              <div v-if="parsedSemanticModel.identifiers.length" class="detailCard">
                <div class="detailCardHeader detailCardHeader--table">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Identifiers ({{ parsedSemanticModel.identifiers.length }})</h4></span>
                </div>
                <div class="detailCardBody">
                  <table class="tableDetailTable">
                    <thead>
                      <tr><th>Name</th><th>Description</th><th>Type</th><th>Expr</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="id in parsedSemanticModel.identifiers" :key="id.name">
                        <td>{{ id.name }}</td>
                        <td>{{ id.description }}</td>
                        <td><Badge variant="outline">{{ id.type }}</Badge></td>
                        <td><code>{{ id.expr }}</code></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Measures -->
              <div v-if="parsedSemanticModel.measures.length" class="detailCard">
                <div class="detailCardHeader detailCardHeader--table">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Measures ({{ parsedSemanticModel.measures.length }})</h4></span>
                </div>
                <div class="detailCardBody">
                  <table class="tableDetailTable">
                    <thead>
                      <tr><th>Name</th><th>Description</th><th>Agg</th><th>Expr</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="m in parsedSemanticModel.measures" :key="m.name">
                        <td>{{ m.name }}</td>
                        <td>{{ m.description }}</td>
                        <td><Badge variant="secondary">{{ m.agg }}</Badge></td>
                        <td><code>{{ m.expr }}</code></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Dimensions -->
              <div v-if="parsedSemanticModel.dimensions.length" class="detailCard">
                <div class="detailCardHeader detailCardHeader--table">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Dimensions ({{ parsedSemanticModel.dimensions.length }})</h4></span>
                </div>
                <div class="detailCardBody">
                  <table class="tableDetailTable">
                    <thead>
                      <tr><th>Name</th><th>Description</th><th>Type</th><th>Expr</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="d in parsedSemanticModel.dimensions" :key="d.name">
                        <td>{{ d.name }}</td>
                        <td>{{ d.description }}</td>
                        <td><Badge :variant="d.type === 'TIME' ? 'default' : 'outline'">{{ d.type }}</Badge></td>
                        <td><code>{{ d.expr }}</code></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Raw YAML (collapsible) -->
              <details class="detailCollapsible">
                <summary>Raw YAML</summary>
                <pre class="knowledgeYaml">{{ semanticModelYaml }}</pre>
              </details>
            </template>

            <!-- Fallback: raw YAML if parse fails -->
            <template v-else>
              <div class="detailCard">
                <div class="detailCardHeader detailCardHeader--table">
                  <span class="detailCardHeaderTitle"><h4 class="detailCardTitle">Semantic Model</h4></span>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" title="编辑" @click="startEditSm">
                    <Pencil :size="14" />
                  </Button>
                  <Button variant="ghost" size="icon" class="cardCopyBtn" @click="copyToClipboard(semanticModelYaml ?? '', 'sm-yaml')">
                    <Check v-if="copiedField === 'sm-yaml'" :size="14" class="copySuccess" />
                    <Copy v-else :size="14" />
                  </Button>
                </div>
                <div class="detailCardBody">
                  <pre class="knowledgeYaml">{{ semanticModelYaml }}</pre>
                </div>
              </div>
            </template>
          </template>
        </div>
      </div>
    </div>

    <!-- Create dialog -->
    <Sheet :open="showCreateDialog" @update:open="showCreateDialog = $event">
      <SheetContent class="settingsDrawer" side="right" aria-label="新建">
        <SheetHeader class="settingsHeader">
          <SheetTitle>新建 {{ createType }}</SheetTitle>
        </SheetHeader>
        <form class="agentForm" @submit.prevent="handleCreate">
          <Label>
            名称
            <Input :value="createName" @update:value="createName = $event" placeholder="名称" />
          </Label>
          <Button type="submit" :disabled="!createName.trim()">创建</Button>
        </form>
      </SheetContent>
    </Sheet>

    <BootstrapDialog :open="showBootstrap" @update:open="showBootstrap = $event" />
  </div>
</template>
