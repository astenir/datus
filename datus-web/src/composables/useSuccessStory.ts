import { readonly, shallowRef } from "vue"
import { toast } from "vue-sonner"

import { useConnection } from "@/composables/useConnection"
import { successStoryApi } from "@/lib/api"
import { ApiResultError } from "@/lib/chat"
import type { SuccessStorySource } from "@/types"

function sourceKey(source: SuccessStorySource) {
  return `${source.sessionId}:${source.callToolId}`
}

function withKey(current: ReadonlySet<string>, key: string) {
  const next = new Set(current)
  next.add(key)
  return next
}

function withoutKey(current: ReadonlySet<string>, key: string) {
  const next = new Set(current)
  next.delete(key)
  return next
}

function errorMessage(error: unknown) {
  if (!(error instanceof ApiResultError)) return "保存失败，请稍后重试"

  if (error.errorCode === "SUCCESS_STORY_NOT_SUCCESSFUL") return "仅支持保存已成功执行的 SQL"
  if (error.errorCode === "SUCCESS_STORY_SQL_NOT_READ_ONLY") return "仅支持保存只读 SQL"
  if (error.errorCode === "SUCCESS_STORY_SESSION_FORBIDDEN") return "无权保存此会话中的 SQL"
  if (error.errorCode === "SUCCESS_STORY_SOURCE_NOT_FOUND") return "未找到对应的 SQL 执行记录"
  if (error.errorCode === "SUCCESS_STORY_DATASOURCE_NOT_FOUND") return "未找到该 SQL 实际使用的数据源"
  if (error.errorCode === "SUCCESS_STORY_DATASOURCE_CONFLICT") return "SQL 执行记录中的数据源不一致，无法保存"
  return "保存失败，请稍后重试"
}

export function useSuccessStory() {
  const connection = useConnection()
  const savingKeys = shallowRef<ReadonlySet<string>>(new Set())
  const savedKeys = shallowRef<ReadonlySet<string>>(new Set())
  const version = shallowRef(0)

  function isSaving(source: SuccessStorySource) {
    return savingKeys.value.has(sourceKey(source))
  }

  function isSaved(source: SuccessStorySource) {
    return savedKeys.value.has(sourceKey(source))
  }

  async function save(source: SuccessStorySource) {
    const key = sourceKey(source)
    if (savingKeys.value.has(key) || savedKeys.value.has(key)) return false

    savingKeys.value = withKey(savingKeys.value, key)
    version.value += 1
    try {
      const result = await successStoryApi.save(connection.effectiveBase(), {
        session_id: source.sessionId,
        call_tool_id: source.callToolId,
        ...(source.sessionLink ? { session_link: source.sessionLink } : {}),
      })
      if (!result) throw new Error("Empty success-story response")

      savedKeys.value = withKey(savedKeys.value, key)
      version.value += 1
      toast.success(result.created ? "已保存为成功案例" : "该 SQL 已保存")
      return true
    } catch (error) {
      console.error("Failed to save success story:", error)
      toast.error(errorMessage(error))
      return false
    } finally {
      savingKeys.value = withoutKey(savingKeys.value, key)
      version.value += 1
    }
  }

  return {
    savingKeys: readonly(savingKeys),
    savedKeys: readonly(savedKeys),
    version: readonly(version),
    isSaving,
    isSaved,
    save,
  }
}
