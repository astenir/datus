<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { BookOpen, ChevronRight, Copy, Database, Folder, FolderPlus, Loader2, Pencil, Check, Table2, RotateCw } from "@lucide/vue";
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
}

const parsedMetric = computed<ParsedMetric | null>(() => {
  if (!metricDetail.value?.yaml) return null;
  try {
    const doc = yaml.load(metricDetail.value.yaml) as Record<string, unknown>;
    const m = doc?.metric as Record<string, unknown> | undefined;
    if (!m) return null;
    const locked = m.locked_metadata as Record<string, unknown> | undefined;
    const tags = (locked?.tags as string[]) ?? [];
    return {
      name: String(m.name ?? ""),
      description: String(m.description ?? ""),
      type: String(m.type ?? ""),
      typeParams: (m.type_params as Record<string, unknown>) ?? {},
      tags,
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

  detailLoading.value = true;
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const result = await tableApi.detail(base, tableName);
    if (result) tableDetail.value = result.table;
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

function handleEditKeydown(e: KeyboardEvent, saveFn: () => void) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    saveFn();
  }
}

const editingSql = ref(false);
const editingSqlData = ref({ sql: "", summary: "", search_text: "" });

function startEditSql() {
  if (!sqlDetail.value) return;
  editingSqlData.value = { sql: sqlDetail.value.sql, summary: sqlDetail.value.summary, search_text: sqlDetail.value.search_text };
  editingSql.value = true;
}

async function saveSql() {
  if (!selectedNode.value || !sqlDetail.value) return;
  const { effectiveBase } = useConnection();
  try {
    await subjectApi.editReferenceSql(effectiveBase(), {
      name: sqlDetail.value.name,
      ...editingSqlData.value,
      subject_path: selectedNode.value.subject_path,
    });
    sqlDetail.value = { ...sqlDetail.value, ...editingSqlData.value };
    editingSql.value = false;
  } catch (e) {
    console.error("Save SQL failed:", e);
  }
}

const editingKnowledge = ref(false);
const editingKnowledgeData = ref({ search_text: "", explanation: "" });

function startEditKnowledge() {
  if (!knowledgeDetail.value) return;
  editingKnowledgeData.value = { search_text: knowledgeDetail.value.search_text, explanation: knowledgeDetail.value.explanation };
  editingKnowledge.value = true;
}

async function saveKnowledge() {
  if (!selectedNode.value) return;
  const { effectiveBase } = useConnection();
  try {
    await subjectApi.editKnowledge(effectiveBase(), selectedNode.value.subject_path, editingKnowledgeData.value.search_text, editingKnowledgeData.value.explanation);
    knowledgeDetail.value = { ...knowledgeDetail.value!, ...editingKnowledgeData.value };
    editingKnowledge.value = false;
  } catch (e) {
    console.error("Save knowledge failed:", e);
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
                <div class="metricCardHeader">
                  <span class="metricCardName">{{ parsedMetric.name }}</span>
                  <Badge :variant="metricTypeColors[parsedMetric.type] ?? 'secondary'">
                    {{ parsedMetric.type }}
                  </Badge>
                </div>
                <p v-if="parsedMetric.description" class="metricDescription">{{ parsedMetric.description }}</p>
                <div v-if="parsedMetric.tags.length" class="metricTags">
                  <span v-for="tag in parsedMetric.tags" :key="tag" class="metricTag">{{ tag }}</span>
                </div>
              </div>
              <div v-if="Object.keys(parsedMetric.typeParams).length" class="detailCard">
                <h4 class="detailCardTitle">Type Parameters</h4>
                <div class="metricParamsGrid">
                  <template v-for="(val, key) in parsedMetric.typeParams" :key="key">
                    <div class="metricParamItem">
                      <span class="metricParamKey">{{ key }}</span>
                      <span class="metricParamVal">{{ formatParamValue(val) }}</span>
                    </div>
                  </template>
                </div>
              </div>
              <details class="detailCollapsible">
                <summary>Raw YAML</summary>
                <pre class="knowledgeYaml">{{ metricDetail.yaml }}</pre>
              </details>
            </template>
            <!-- Fallback: raw YAML if parse fails -->
            <template v-else>
              <pre class="knowledgeYaml">{{ metricDetail.yaml }}</pre>
            </template>
            <div class="knowledgeDetailActions">
              <Button variant="outline" size="sm" @click="startEditMetric">
                <Pencil :size="14" />
                编辑
              </Button>
            </div>
          </div>
          <div v-else class="knowledgeEditForm" @keydown="handleEditKeydown($event, saveMetric)">
            <div class="editSection">
              <div class="editSectionHeader">
                <span class="editSectionTitle">YAML</span>
                <span class="editSectionMeta">{{ editingMetricYaml.split('\n').length }} lines</span>
              </div>
              <Textarea v-model="editingMetricYaml" class="editCodearea" :rows="14" placeholder="metric:\n  name: ...\n  description: ..." />
            </div>
            <div class="editFooter">
              <span class="editHint">Ctrl + Enter 保存</span>
              <div class="editFooterActions">
                <Button variant="outline" size="sm" @click="editingMetric = false">取消</Button>
                <Button size="sm" @click="saveMetric">保存</Button>
              </div>
            </div>
          </div>
        </div>

        <!-- Reference SQL detail -->
        <div v-if="selectedNode?.type === 'reference_sql' && sqlDetail" class="knowledgeDetailBody">
          <div v-if="!editingSql">
            <!-- Summary card -->
            <div class="detailCard">
              <h4 class="detailCardTitle">Summary</h4>
              <p class="detailCardText">{{ sqlDetail.summary }}</p>
            </div>
            <!-- SQL block with header -->
            <div class="sqlBlock">
              <div class="sqlBlockHeader">
                <span>SQL</span>
                <Button
                  variant="ghost"
                  size="icon"
                  class="sqlCopyBtn"
                  @click="copyToClipboard(sqlDetail.sql, 'sql')"
                >
                  <Check v-if="copiedField === 'sql'" :size="14" class="copySuccess" />
                  <Copy v-else :size="14" />
                </Button>
              </div>
              <pre class="sqlBlockCode">{{ sqlDetail.sql }}</pre>
            </div>
            <!-- Search text card -->
            <div v-if="sqlDetail.search_text" class="detailCard">
              <h4 class="detailCardTitle">Search Text（向量检索文本）</h4>
              <div class="searchTextSegments">
                <p
                  v-for="(seg, i) in splitSearchText(sqlDetail.search_text)"
                  :key="i"
                  class="searchTextSegment"
                >
                  {{ seg }}
                </p>
              </div>
            </div>
            <div class="knowledgeDetailActions">
              <Button variant="outline" size="sm" @click="startEditSql">
                <Pencil :size="14" />
                编辑
              </Button>
            </div>
          </div>
          <div v-else class="knowledgeEditForm" @keydown="handleEditKeydown($event, saveSql)">
            <div class="editSection">
              <div class="editSectionHeader">
                <span class="editSectionTitle">Summary</span>
              </div>
              <Input v-model="editingSqlData.summary" placeholder="SQL 摘要描述" />
            </div>
            <div class="editSection">
              <div class="editSectionHeader">
                <span class="editSectionTitle">SQL</span>
                <span class="editSectionMeta">{{ editingSqlData.sql.split('\n').length }} lines</span>
              </div>
              <Textarea v-model="editingSqlData.sql" class="editCodearea" :rows="10" placeholder="SELECT ..." />
            </div>
            <details class="editSection editCollapsible">
              <summary class="editSectionHeader editCollapsibleSummary">
                <span class="editSectionTitle">Search Text</span>
                <span class="editSectionMeta">向量检索文本</span>
              </summary>
              <Input v-model="editingSqlData.search_text" class="editCollapsibleInput" placeholder="用于向量检索的文本" />
            </details>
            <div class="editFooter">
              <span class="editHint">Ctrl + Enter 保存</span>
              <div class="editFooterActions">
                <Button variant="outline" size="sm" @click="editingSql = false">取消</Button>
                <Button size="sm" @click="saveSql">保存</Button>
              </div>
            </div>
          </div>
        </div>

        <!-- Knowledge detail -->
        <div v-if="selectedNode?.type === 'knowledge' && knowledgeDetail" class="knowledgeDetailBody">
          <div v-if="!editingKnowledge">
            <!-- Explanation rendered as markdown -->
            <div class="detailCard">
              <h4 class="detailCardTitle">Explanation</h4>
              <div class="knowledgeMarkdown markdownBody" v-html="knowledgeHtml" />
            </div>
            <!-- Search text card -->
            <div class="detailCard">
              <h4 class="detailCardTitle">Search Text（向量检索文本）</h4>
              <div class="searchTextSegments">
                <p
                  v-for="(seg, i) in splitSearchText(knowledgeDetail.search_text)"
                  :key="i"
                  class="searchTextSegment"
                >
                  {{ seg }}
                </p>
              </div>
            </div>
            <div class="knowledgeDetailActions">
              <Button variant="outline" size="sm" @click="startEditKnowledge">
                <Pencil :size="14" />
                编辑
              </Button>
            </div>
          </div>
          <div v-else class="knowledgeEditForm" @keydown="handleEditKeydown($event, saveKnowledge)">
            <div class="editSection">
              <div class="editSectionHeader">
                <span class="editSectionTitle">Explanation</span>
                <span class="editSectionMeta">支持 Markdown</span>
              </div>
              <Textarea v-model="editingKnowledgeData.explanation" class="editCodearea" :rows="8" placeholder="知识条目的详细解释..." />
            </div>
            <details class="editSection editCollapsible">
              <summary class="editSectionHeader editCollapsibleSummary">
                <span class="editSectionTitle">Search Text</span>
                <span class="editSectionMeta">向量检索文本</span>
              </summary>
              <Input v-model="editingKnowledgeData.search_text" class="editCollapsibleInput" placeholder="用于向量检索的文本" />
            </details>
            <div class="editFooter">
              <span class="editHint">Ctrl + Enter 保存</span>
              <div class="editFooterActions">
                <Button variant="outline" size="sm" @click="editingKnowledge = false">取消</Button>
                <Button size="sm" @click="saveKnowledge">保存</Button>
              </div>
            </div>
          </div>
        </div>

        <!-- Table detail (Catalog) -->
        <div v-if="selectedTable && tableDetail" class="knowledgeDetailBody">
          <!-- Row count -->
          <div v-if="tableDetail.rows != null" class="detailCard">
            <h4 class="detailCardTitle">Rows</h4>
            <p class="detailCardText">{{ tableDetail.rows.toLocaleString() }}</p>
          </div>
          <!-- Columns table -->
          <div class="detailCard">
            <h4 class="detailCardTitle">Columns ({{ tableDetail.columns.length }})</h4>
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
          <!-- Indexes -->
          <div v-if="tableDetail.indexes.length" class="detailCard">
            <h4 class="detailCardTitle">Indexes ({{ tableDetail.indexes.length }})</h4>
            <div class="indexList">
              <div v-for="idx in tableDetail.indexes" :key="idx.name" class="indexItem">
                <span class="indexName">{{ idx.name }}</span>
                <Badge variant="secondary">{{ idx.type }}</Badge>
                <span class="indexColumns">{{ idx.columns.join(', ') }}</span>
              </div>
            </div>
          </div>
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
            <Input v-model="createName" placeholder="名称" />
          </Label>
          <Button type="submit" :disabled="!createName.trim()">创建</Button>
        </form>
      </SheetContent>
    </Sheet>

    <BootstrapDialog :open="showBootstrap" @update:open="showBootstrap = $event" />
  </div>
</template>
