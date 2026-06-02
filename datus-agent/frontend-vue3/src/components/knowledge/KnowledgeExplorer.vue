<script setup lang="ts">
import { ref, onMounted } from "vue";
import { BookOpen, ChevronRight, Database, Folder, FolderPlus, Loader2, Pencil, Trash2 } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import ScrollArea from "@/components/ui/ScrollArea.vue";
import Input from "@/components/ui/Input.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Label from "@/components/ui/Label.vue";
import Sheet from "@/components/ui/Sheet.vue";
import SheetContent from "@/components/ui/SheetContent.vue";
import SheetHeader from "@/components/ui/SheetHeader.vue";
import SheetTitle from "@/components/ui/SheetTitle.vue";
import { subjectApi } from "@/lib/api";
import BootstrapDialog from "./BootstrapDialog.vue";
import { useConnection } from "@/composables/useConnection";
import type { SubjectNode, MetricInfo, ReferenceSQLInfo, KnowledgeInfo, SubjectNodeType } from "@/types";

// ─── State ───────────────────────────────────────────────────────────────────

const subjects = ref<SubjectNode[]>([]);
const loading = ref(false);
const selectedNode = ref<SubjectNode | null>(null);
const detailLoading = ref(false);

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

// ─── Select node ─────────────────────────────────────────────────────────────

async function selectNode(node: SubjectNode) {
  selectedNode.value = node;
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

// ─── Icons ───────────────────────────────────────────────────────────────────

const typeIconMap: Record<string, typeof Folder> = {
  directory: Folder,
  metric: BookOpen,
  reference_sql: BookOpen,
  knowledge: BookOpen,
};

// ─── Init ────────────────────────────────────────────────────────────────────

onMounted(loadSubjects);
</script>

<template>
  <div class="knowledgeExplorer">
    <!-- Left: tree -->
    <div class="knowledgeTree">
      <div class="knowledgeTreeHeader">
        <h3>Subject 树</h3>
        <div class="knowledgeTreeActions">
          <Button variant="ghost" size="icon" aria-label="Bootstrap" title="知识库构建" @click="showBootstrap = true">
            <Database :size="16" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="新建目录" @click="openCreate([], 'directory')">
            <FolderPlus :size="16" />
          </Button>
          <Button variant="ghost" size="icon" :disabled="loading" aria-label="刷新" @click="loadSubjects">
            <Loader2 v-if="loading" class="spin" :size="16" />
            <ChevronRight v-else :size="16" />
          </Button>
        </div>
      </div>

      <ScrollArea class="knowledgeTreeContent">
        <div v-if="loading" class="knowledgeTreeLoading">
          <Loader2 class="spin" :size="20" />
        </div>
        <div v-else-if="subjects.length === 0" class="knowledgeTreeEmpty">
          <Folder :size="24" />
          <p>暂无 Subject</p>
        </div>
        <template v-else>
          <div
            v-for="node in subjects"
            :key="node.subject_path.join('/')"
            :class="`knowledgeTreeNode ${selectedNode?.subject_path.join('/') === node.subject_path.join('/') ? 'selected' : ''}`"
            @click="selectNode(node)"
          >
            <component :is="typeIconMap[node.type || 'directory'] || Folder" :size="14" />
            <span>{{ node.name }}</span>
            <div class="knowledgeTreeNodeActions">
              <button v-if="node.type === 'directory'" type="button" title="新建" @click.stop="openCreate(node.subject_path, 'metric')">
                <FolderPlus :size="12" />
              </button>
              <button type="button" title="删除" @click.stop="handleDelete(node)">
                <Trash2 :size="12" />
              </button>
            </div>
          </div>
        </template>
      </ScrollArea>
    </div>

    <!-- Right: detail -->
    <div class="knowledgeDetail">
      <div v-if="!selectedNode" class="knowledgeDetailEmpty">
        <BookOpen :size="32" />
        <p>选择左侧节点查看详情</p>
      </div>
      <div v-else-if="detailLoading" class="knowledgeDetailLoading">
        <Loader2 class="spin" :size="24" />
      </div>
      <div v-else class="knowledgeDetailContent">
        <div class="knowledgeDetailHeader">
          <h3>{{ selectedNode.name }}</h3>
          <span class="knowledgeDetailType">{{ selectedNode.type || 'directory' }}</span>
        </div>

        <!-- Metric detail -->
        <div v-if="selectedNode.type === 'metric' && metricDetail" class="knowledgeDetailBody">
          <div v-if="!editingMetric">
            <pre class="knowledgeYaml">{{ metricDetail.yaml }}</pre>
            <Button variant="outline" size="sm" @click="startEditMetric">
              <Pencil :size="14" />
              编辑
            </Button>
          </div>
          <div v-else class="knowledgeEditForm">
            <Label>
              YAML
              <Textarea v-model="editingMetricYaml" :rows="12" />
            </Label>
            <div class="knowledgeEditActions">
              <Button variant="outline" size="sm" @click="editingMetric = false">取消</Button>
              <Button size="sm" @click="saveMetric">保存</Button>
            </div>
          </div>
        </div>

        <!-- Reference SQL detail -->
        <div v-if="selectedNode.type === 'reference_sql' && sqlDetail" class="knowledgeDetailBody">
          <div v-if="!editingSql">
            <div class="knowledgeField">
              <strong>Summary:</strong>
              <p>{{ sqlDetail.summary }}</p>
            </div>
            <pre class="knowledgeYaml">{{ sqlDetail.sql }}</pre>
            <Button variant="outline" size="sm" @click="startEditSql">
              <Pencil :size="14" />
              编辑
            </Button>
          </div>
          <div v-else class="knowledgeEditForm">
            <Label>
              Summary
              <Input v-model="editingSqlData.summary" />
            </Label>
            <Label>
              SQL
              <Textarea v-model="editingSqlData.sql" :rows="10" />
            </Label>
            <Label>
              Search Text
              <Input v-model="editingSqlData.search_text" />
            </Label>
            <div class="knowledgeEditActions">
              <Button variant="outline" size="sm" @click="editingSql = false">取消</Button>
              <Button size="sm" @click="saveSql">保存</Button>
            </div>
          </div>
        </div>

        <!-- Knowledge detail -->
        <div v-if="selectedNode.type === 'knowledge' && knowledgeDetail" class="knowledgeDetailBody">
          <div v-if="!editingKnowledge">
            <div class="knowledgeField">
              <strong>Search Text:</strong>
              <p>{{ knowledgeDetail.search_text }}</p>
            </div>
            <div class="knowledgeField">
              <strong>Explanation:</strong>
              <p>{{ knowledgeDetail.explanation }}</p>
            </div>
            <Button variant="outline" size="sm" @click="startEditKnowledge">
              <Pencil :size="14" />
              编辑
            </Button>
          </div>
          <div v-else class="knowledgeEditForm">
            <Label>
              Search Text
              <Input v-model="editingKnowledgeData.search_text" />
            </Label>
            <Label>
              Explanation
              <Textarea v-model="editingKnowledgeData.explanation" :rows="6" />
            </Label>
            <div class="knowledgeEditActions">
              <Button variant="outline" size="sm" @click="editingKnowledge = false">取消</Button>
              <Button size="sm" @click="saveKnowledge">保存</Button>
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
