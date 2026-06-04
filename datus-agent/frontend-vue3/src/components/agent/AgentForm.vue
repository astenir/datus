<script setup lang="ts">
import { ref, watch } from "vue";
import { Loader2, Save } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Sheet from "@/components/ui/Sheet.vue";
import SheetContent from "@/components/ui/SheetContent.vue";
import SheetHeader from "@/components/ui/SheetHeader.vue";
import SheetTitle from "@/components/ui/SheetTitle.vue";
import AppPopoverSelect from "@/components/AppPopoverSelect.vue";
import { useAgents } from "@/composables/useAgents";
import type { AgentInfo } from "@/types";

const props = defineProps<{
  open: boolean;
  agent: AgentInfo | null;
}>();

const emit = defineEmits<{
  close: [];
}>();

const { createAgent, editAgent } = useAgents();

const name = ref("");
const type = ref("gen_sql");
const description = ref("");
const promptTemplate = ref("");
const saving = ref(false);
const error = ref("");

const isEdit = ref(false);

const agentTypeOptions = [
  { value: "gen_sql", label: "gen_sql" },
  { value: "gen_report", label: "gen_report" },
  { value: "gen_dashboard", label: "gen_dashboard" },
];

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    if (props.agent) {
      isEdit.value = true;
      name.value = props.agent.name;
      type.value = props.agent.type || "gen_sql";
      description.value = "";
      promptTemplate.value = props.agent.system_prompt || "";
    } else {
      isEdit.value = false;
      name.value = "";
      type.value = "gen_sql";
      description.value = "";
      promptTemplate.value = "";
    }
    error.value = "";
  }
});

async function handleSubmit() {
  if (!name.value.trim()) {
    error.value = "名称不能为空";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    if (isEdit.value && props.agent) {
      await editAgent({
        id: props.agent.name,
        name: name.value,
        description: description.value || undefined,
        prompt_template: promptTemplate.value || undefined,
      });
    } else {
      await createAgent({
        name: name.value,
        type: type.value,
        description: description.value || undefined,
        prompt_template: promptTemplate.value || undefined,
      });
    }
    emit("close");
  } catch (e) {
    error.value = (e as Error).message || "操作失败";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Sheet :open="open" @update:open="(v) => { if (!v) emit('close') }">
    <SheetContent class="settingsDrawer" side="right" aria-label="Agent 表单">
      <SheetHeader class="settingsHeader">
        <SheetTitle>{{ isEdit ? '编辑 Agent' : '新建 Agent' }}</SheetTitle>
      </SheetHeader>

      <form class="agentForm" @submit.prevent="handleSubmit">
        <label>
          名称 *
          <Input v-model="name" placeholder="Agent 名称" :disabled="isEdit" />
        </label>

        <label>
          类型
          <AppPopoverSelect :value="type" :options="agentTypeOptions" @update:value="type = $event" />
        </label>

        <label>
          描述
          <Input v-model="description" placeholder="可选描述" />
        </label>

        <label>
          系统提示词
          <Textarea v-model="promptTemplate" placeholder="Agent 系统提示词..." :rows="6" />
        </label>

        <p v-if="error" class="agentFormError">{{ error }}</p>

        <Button type="submit" :disabled="saving || !name.trim()">
          <Loader2 v-if="saving" class="spin" :size="16" />
          <Save v-else :size="16" />
          {{ isEdit ? '保存' : '创建' }}
        </Button>
      </form>
    </SheetContent>
  </Sheet>
</template>
