<script setup lang="ts">
import { ref, onMounted } from "vue";
import { CheckCircle2, Loader2, Plug, Plus, RefreshCw, Trash2, Wrench, XCircle, Zap } from "@lucide/vue";

import Badge from "@/components/ui/Badge.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import ScrollArea from "@/components/ui/ScrollArea.vue";
import Sheet from "@/components/ui/Sheet.vue";
import SheetContent from "@/components/ui/SheetContent.vue";
import SheetHeader from "@/components/ui/SheetHeader.vue";
import SheetTitle from "@/components/ui/SheetTitle.vue";
import AppPopoverSelect from "@/components/AppPopoverSelect.vue";
import { mcpApi } from "@/lib/api";
import { useConnection } from "@/composables/useConnection";
import type { McpServerInfo, McpToolInfo } from "@/types";

// ─── State ───────────────────────────────────────────────────────────────────

const servers = ref<McpServerInfo[]>([]);
const loading = ref(false);

// Connectivity status per server
const connectivityMap = ref<Record<string, { ok: boolean; message?: string }>>({});
const testingServer = ref<string | null>(null);

// Tools per server
const toolsMap = ref<Record<string, McpToolInfo[]>>({});
const loadingTools = ref<string | null>(null);
const selectedServer = ref<string | null>(null);

// Tool test
const testToolName = ref("");
const testToolParams = ref("{}");
const testToolResult = ref<unknown>(null);
const testingTool = ref(false);

// Add server dialog
const showAddDialog = ref(false);
const newServer = ref<McpServerInfo>({ name: "", type: "stdio", command: "", args: [] });

// ─── Load servers ────────────────────────────────────────────────────────────

async function loadServers() {
  loading.value = true;
  try {
    const { effectiveBase } = useConnection();
    const result = await mcpApi.listServers(effectiveBase());
    if (result) servers.value = result.servers ?? [];
  } catch (e) {
    console.error("Failed to load MCP servers:", e);
  } finally {
    loading.value = false;
  }
}

// ─── Connectivity ────────────────────────────────────────────────────────────

async function testConnectivity(name: string) {
  testingServer.value = name;
  try {
    const { effectiveBase } = useConnection();
    const result = await mcpApi.connectivity(effectiveBase(), name);
    connectivityMap.value[name] = result ?? { ok: false, message: "No response" };
  } catch (e) {
    connectivityMap.value[name] = { ok: false, message: (e as Error).message };
  } finally {
    testingServer.value = null;
  }
}

// ─── Tools ───────────────────────────────────────────────────────────────────

async function loadTools(name: string) {
  loadingTools.value = name;
  try {
    const { effectiveBase } = useConnection();
    const result = await mcpApi.listTools(effectiveBase(), name);
    toolsMap.value[name] = result?.tools ?? [];
  } catch (e) {
    console.error("Failed to load tools:", e);
    toolsMap.value[name] = [];
  } finally {
    loadingTools.value = null;
  }
}

function selectServer(name: string) {
  selectedServer.value = selectedServer.value === name ? null : name;
  if (selectedServer.value && !toolsMap.value[name]) {
    loadTools(name);
  }
}

// ─── Tool test ───────────────────────────────────────────────────────────────

async function handleTestTool(serverName: string, toolName: string) {
  testingTool.value = true;
  testToolResult.value = null;
  try {
    const { effectiveBase } = useConnection();
    let params = {};
    try { params = JSON.parse(testToolParams.value); } catch { /* ignore */ }
    testToolResult.value = await mcpApi.callTool(effectiveBase(), serverName, toolName, params);
  } catch (e) {
    testToolResult.value = { error: (e as Error).message };
  } finally {
    testingTool.value = false;
  }
}

// ─── Add server ──────────────────────────────────────────────────────────────

async function handleAddServer() {
  if (!newServer.value.name.trim()) return;
  try {
    const { effectiveBase } = useConnection();
    await mcpApi.addServer(effectiveBase(), newServer.value);
    showAddDialog.value = false;
    newServer.value = { name: "", type: "stdio", command: "", args: [] };
    await loadServers();
  } catch (e) {
    console.error("Add server failed:", e);
  }
}

// ─── Remove server ───────────────────────────────────────────────────────────

async function handleRemoveServer(name: string) {
  if (!confirm(`确定删除 MCP 服务器 "${name}"？`)) return;
  try {
    const { effectiveBase } = useConnection();
    await mcpApi.removeServer(effectiveBase(), name);
    if (selectedServer.value === name) selectedServer.value = null;
    await loadServers();
  } catch (e) {
    console.error("Remove server failed:", e);
  }
}

// ─── Init ────────────────────────────────────────────────────────────────────

onMounted(loadServers);
</script>

<template>
  <div class="mcpManager">
    <div class="mcpHeader">
      <h2>MCP 服务器</h2>
      <div class="mcpHeaderActions">
        <Button variant="outline" size="sm" @click="showAddDialog = true">
          <Plus :size="14" />
          添加
        </Button>
        <Button variant="ghost" size="icon" :disabled="loading" @click="loadServers">
          <Loader2 v-if="loading" class="spin" :size="16" />
          <RefreshCw v-else :size="16" />
        </Button>
      </div>
    </div>

    <ScrollArea class="mcpServerList">
      <div v-if="servers.length === 0" class="mcpEmpty">
        <Plug :size="32" />
        <p>暂无 MCP 服务器</p>
      </div>

      <div v-for="server in servers" :key="server.name" class="mcpServerCard">
        <div class="mcpServerInfo" @click="selectServer(server.name)">
          <div class="mcpServerName">
            <Wrench :size="14" />
            <strong>{{ server.name }}</strong>
            <Badge variant="secondary">{{ server.type }}</Badge>
            <Badge v-if="connectivityMap[server.name]" :variant="connectivityMap[server.name].ok ? 'success' : 'destructive'">
              <CheckCircle2 v-if="connectivityMap[server.name].ok" :size="10" />
              <XCircle v-else :size="10" />
            </Badge>
          </div>
          <p v-if="server.command" class="mcpServerMeta">{{ server.command }}</p>
          <p v-if="server.url" class="mcpServerMeta">{{ server.url }}</p>
        </div>
        <div class="mcpServerActions">
          <Button
            class="iconButton"
            variant="ghost"
            size="icon"
            :disabled="testingServer === server.name"
            aria-label="测试连接"
            @click="testConnectivity(server.name)"
          >
            <Loader2 v-if="testingServer === server.name" class="spin" :size="14" />
            <Zap v-else :size="14" />
          </Button>
          <Button class="iconButton" variant="ghost" size="icon" aria-label="删除" @click="handleRemoveServer(server.name)">
            <Trash2 :size="14" />
          </Button>
        </div>

        <!-- Tools list (expanded) -->
        <div v-if="selectedServer === server.name" class="mcpToolsList">
          <div v-if="loadingTools === server.name" class="mcpToolsLoading">
            <Loader2 class="spin" :size="16" />
          </div>
          <div v-else-if="(toolsMap[server.name] ?? []).length === 0" class="mcpToolsEmpty">
            暂无工具
          </div>
          <div v-for="tool in toolsMap[server.name] ?? []" :key="tool.name" class="mcpToolItem">
            <div class="mcpToolInfo">
              <strong>{{ tool.name }}</strong>
              <p v-if="tool.description">{{ tool.description }}</p>
            </div>
            <Button variant="ghost" size="sm" @click="testToolName = tool.name; handleTestTool(server.name, tool.name)">
              测试
            </Button>
          </div>
          <div v-if="testToolResult" class="mcpToolResult">
            <pre>{{ JSON.stringify(testToolResult, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </ScrollArea>

    <!-- Add server dialog -->
    <Sheet :open="showAddDialog" @update:open="showAddDialog = $event">
      <SheetContent class="settingsDrawer" side="right" aria-label="添加 MCP 服务器">
        <SheetHeader class="settingsHeader">
          <SheetTitle>添加 MCP 服务器</SheetTitle>
        </SheetHeader>
        <form class="agentForm" @submit.prevent="handleAddServer">
          <Label>
            名称 *
            <Input v-model="newServer.name" placeholder="服务器名称" />
          </Label>
          <Label>
            类型
            <AppPopoverSelect
              :value="newServer.type"
              :options="[{ value: 'stdio', label: 'stdio' }, { value: 'sse', label: 'sse' }, { value: 'http', label: 'http' }]"
              @update:value="newServer.type = $event"
            />
          </Label>
          <Label v-if="newServer.type === 'stdio'">
            命令
            <Input v-model="newServer.command" placeholder="如: npx @modelcontextprotocol/server-..." />
          </Label>
          <Label v-if="newServer.type === 'sse' || newServer.type === 'http'">
            URL
            <Input v-model="newServer.url" placeholder="http://..." />
          </Label>
          <Button type="submit" :disabled="!newServer.name.trim()">添加</Button>
        </form>
      </SheetContent>
    </Sheet>
  </div>
</template>
