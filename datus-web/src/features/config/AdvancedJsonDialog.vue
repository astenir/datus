<script setup lang="ts">
import { BracesIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"

defineProps<{
  title: string
  description: string
  fieldLabel: string
  fieldDescription: string
  textareaId: string
  canEdit: boolean
}>()

const emit = defineEmits<{
  apply: []
}>()

const open = defineModel<boolean>("open", { default: false })
const text = defineModel<string>("text", { required: true })
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <Button variant="outline" size="sm">
        <BracesIcon data-icon="inline-start" />
        高级 JSON
      </Button>
    </DialogTrigger>
    <DialogContent
      class="grid h-[min(44rem,calc(100dvh-2rem))] max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] sm:max-w-4xl"
    >
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
        <DialogDescription>{{ description }}</DialogDescription>
      </DialogHeader>

      <Field class="min-h-0 overflow-hidden">
        <FieldLabel :for="textareaId">{{ fieldLabel }}</FieldLabel>
        <Textarea
          :id="textareaId"
          v-model="text"
          class="h-full min-h-0 flex-1 overflow-y-auto overscroll-contain font-mono text-xs leading-6 [field-sizing:fixed]"
          :disabled="!canEdit"
          spellcheck="false"
        />
        <FieldDescription>{{ fieldDescription }}</FieldDescription>
      </Field>

      <DialogFooter>
        <Button variant="outline" @click="open = false">关闭</Button>
        <Button :disabled="!canEdit" @click="emit('apply')">应用 JSON</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
