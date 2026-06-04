<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Edit2, Loader2, Plus, Trash2, Bot } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import Badge from "@/components/ui/Badge.vue";
import ScrollArea from "@/components/ui/ScrollArea.vue";
import { useAgents } from "@/composables/useAgents";
import type { AgentInfo } from "@/types";
import AgentForm from "./AgentForm.vue";

const { agents, loadAgents, deleteAgent } = useAgents();

const showForm = ref(false);
const editingAgent = ref<AgentInfo | null>(null);
const deletingAgent = ref<string | null>(null);

onMounted(loadAgents);

function openCreate() {
  editingAgent.value = null;
  showForm.value = true;
}

function openEdit(agent: AgentInfo) {
  editingAgent.value = agent;
  showForm.value = true;
}

async function handleDelete(name: string) {
  if (!confirm(`确定删除 Agent "${name}"？`)) return;
  deletingAgent.value = name;
  try {
    await deleteAgent(name);
  } catch (e) {
    console.error("Delete failed:", e);
  } finally {
    deletingAgent.value = null;
  }
}

function handleFormClose() {
  showForm.value = false;
  editingAgent.value = null;
  loadAgents();
}
</script>

<template>
  <div class="agentManager">
    <div class="agentManagerHeader">
      <h2>Agent 管理</h2>
      <Button variant="outline" size="sm" @click="openCreate">
        <Plus :size="14" />
        新建 Agent
      </Button>
    </div>

    <ScrollArea class="agentList">
      <div v-if="agents.length === 0" class="agentEmpty">
        <Bot :size="32" />
        <p>暂无自定义 Agent</p>
      </div>
      <div v-for="agent in agents" :key="agent.name" class="agentCard">
        <div class="agentCardInfo">
          <div class="agentCardName">
            <Bot :size="16" />
            <strong>{{ agent.name }}</strong>
            <Badge v-if="agent.type" variant="secondary">{{ agent.type }}</Badge>
          </div>
          <p v-if="agent.created_at" class="agentCardMeta">创建于 {{ agent.created_at }}</p>
        </div>
        <div class="agentCardActions">
          <Button class="iconButton" variant="ghost" size="icon" aria-label="编辑" @click="openEdit(agent)">
            <Edit2 :size="14" />
          </Button>
          <Button
            class="iconButton"
            variant="ghost"
            size="icon"
            aria-label="删除"
            :disabled="deletingAgent === agent.name"
            @click="handleDelete(agent.name)"
          >
            <Loader2 v-if="deletingAgent === agent.name" class="spin" :size="14" />
            <Trash2 v-else :size="14" />
          </Button>
        </div>
      </div>
    </ScrollArea>

    <AgentForm
      :open="showForm"
      :agent="editingAgent"
      @close="handleFormClose"
    />
  </div>
</template>
