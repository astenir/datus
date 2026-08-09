<script setup lang="ts">
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import type { AdminSecretDialogProps } from "@/features/admin/types"

defineProps<AdminSecretDialogProps>()
</script>
<template>
  <Dialog
    :open="overview.showSecretDialog.value"
    @update:open="setSecretDialogOpen"
  >
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{{ overview.editingSecret.value ? "编辑密钥引用" : "新增密钥引用" }}</DialogTitle>
        <DialogDescription>只保存密钥引用元数据，不在前端保存真实密钥。</DialogDescription>
      </DialogHeader>
      <div
        v-if="overview.loadingSecretDetail.value"
        class="rounded-md border p-4 text-sm text-muted-foreground"
      >
        正在加载密钥引用详情...
      </div>
      <div
        v-else-if="overview.secretDetailError.value"
        class="rounded-md border p-4 text-sm text-muted-foreground"
      >
        {{ overview.secretDetailError.value }}
      </div>
      <FieldGroup class="gap-4">
        <Field>
          <FieldLabel for="secret-name">名称</FieldLabel>
          <Input
            id="secret-name"
            v-model="overview.secretForm.value.name"
            :disabled="Boolean(overview.editingSecret.value)"
          />
        </Field>
        <Field>
          <FieldLabel for="secret-provider">Provider</FieldLabel>
          <Input
            id="secret-provider"
            v-model="overview.secretForm.value.provider"
          />
        </Field>
        <Field>
          <FieldLabel for="secret-reference">引用</FieldLabel>
          <Input
            id="secret-reference"
            v-model="overview.secretForm.value.reference"
            :placeholder="overview.editingSecret.value ? '输入新的完整引用' : '例如环境变量名或外部密钥路径'"
          />
          <FieldDescription v-if="overview.editingSecret.value">
            当前引用提示：{{ overview.editingSecret.value.ref_hint }}。后端不会返回真实引用，保存时需要重新输入完整引用。
          </FieldDescription>
          <FieldDescription v-else>
            后端返回列表和详情时只展示脱敏后的引用提示。
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel for="secret-description">说明</FieldLabel>
          <Textarea
            id="secret-description"
            v-model="overview.secretForm.value.description"
          />
        </Field>
        <Field
          orientation="horizontal"
          class="items-center justify-between"
        >
          <FieldLabel>启用密钥引用</FieldLabel>
          <Switch v-model="overview.secretForm.value.enabled" />
        </Field>
      </FieldGroup>
      <DialogFooter>
        <Button
          variant="outline"
          @click="setSecretDialogOpen(false)"
        >
          取消
        </Button>
        <Button
          :disabled="overview.savingSecret.value || overview.loadingSecretDetail.value"
          @click="saveSecretAndCloseRoute"
        >
          保存
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
