<script setup lang="ts">
import AdminArtifactAclDialog from "@/features/admin/dialogs/AdminArtifactAclDialog.vue"
import AdminAuditDialog from "@/features/admin/dialogs/AdminAuditDialog.vue"
import AdminGrantDialog from "@/features/admin/dialogs/AdminGrantDialog.vue"
import AdminQuotaDialog from "@/features/admin/dialogs/AdminQuotaDialog.vue"
import AdminRoleDialogs from "@/features/admin/dialogs/AdminRoleDialogs.vue"
import AdminSecretDialog from "@/features/admin/dialogs/AdminSecretDialog.vue"
import AdminSessionDialogs from "@/features/admin/dialogs/AdminSessionDialogs.vue"
import AdminUserDialogs from "@/features/admin/dialogs/AdminUserDialogs.vue"
import type { AdminDialogProps } from "@/features/admin/types"

defineProps<AdminDialogProps>()
</script>

<template>
  <AdminUserDialogs
    :format-optional-date="formatOptionalDate"
    :format-scope="formatScope"
    :roles="roles"
    :set-user-detail-dialog-open="setUserDetailDialogOpen"
    :users="users"
  />
  <AdminRoleDialogs
    :format-optional-date="formatOptionalDate"
    :roles="roles"
    :set-role-detail-dialog-open="setRoleDetailDialogOpen"
  />
  <AdminSessionDialogs
    :format-optional-date="formatOptionalDate"
    :overview="overview"
    :set-session-detail-dialog-open="setSessionDetailDialogOpen"
  />
  <AdminAuditDialog
    :audits="audits"
    :format-optional-date="formatOptionalDate"
  />
  <AdminGrantDialog
    :format-scope="formatScope"
    :overview="overview"
    :save-grant-and-close-route="saveGrantAndCloseRoute"
    :set-grant-dialog-open="setGrantDialogOpen"
  />
  <AdminQuotaDialog
    :overview="overview"
    :roles="roles"
    :set-quota-limit="setQuotaLimit"
    :set-quota-window="setQuotaWindow"
    :users="users"
  />
  <AdminSecretDialog
    :overview="overview"
    :save-secret-and-close-route="saveSecretAndCloseRoute"
    :set-secret-dialog-open="setSecretDialogOpen"
  />
  <AdminArtifactAclDialog
    :overview="overview"
    :roles="roles"
    :save-artifact-acl-and-close-route="saveArtifactAclAndCloseRoute"
    :set-artifact-acl-dialog-open="setArtifactAclDialogOpen"
    :users="users"
  />
</template>
