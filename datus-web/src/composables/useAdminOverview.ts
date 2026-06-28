import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import {
  adminArtifactApi,
  adminDatasourceApi,
  adminQuotaApi,
  adminSecretApi,
  adminSessionApi,
} from "@/lib/api";
import type {
  AdminArtifact,
  AdminDatasourceGrant,
  AdminOverviewData,
  AdminQuota,
  AdminSecret,
  AdminSession,
  AdminSessionDetail,
  ArtifactAclFormData,
  DatasourceGrantFormData,
  QuotaFormData,
  SecretFormData,
} from "@/types/admin";

type ArtifactAclTarget = {
  artifactType: AdminArtifact["artifact_type"];
  slug: string;
};

function cloneEmptyOverview(): AdminOverviewData {
  return {
    datasources: [],
    datasourceGrants: [],
    quotas: [],
    usage: [],
    secrets: [],
    sessions: [],
    artifacts: [],
  };
}

function scopeText(scope: Record<string, unknown> | undefined): string {
  if (!scope || Object.keys(scope).length === 0) return "{}";
  return JSON.stringify(scope, null, 2);
}

function parseScope(text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) return {};

  const parsed: unknown = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Scope 必须是 JSON 对象");
  }
  return parsed as Record<string, unknown>;
}

function commaList(value: string): string[] {
  return value
    .split(",")
    .map(item => item.trim())
    .filter(Boolean);
}

function artifactKey(artifact: AdminArtifact): string {
  return `${artifact.artifact_type}:${artifact.manifest.slug}`;
}

function artifactAclTargetKey(target: ArtifactAclTarget): string {
  return `${target.artifactType}:${target.slug}`;
}

export function useAdminOverview() {
  const loading = shallowRef(false);
  const savingGrant = shallowRef(false);
  const savingQuota = shallowRef(false);
  const savingSecret = shallowRef(false);
  const savingArtifactAcl = shallowRef(false);
  const actingSessionId = shallowRef<string | null>(null);
  const deletingGrantKey = shallowRef<string | null>(null);
  const deletingSecretName = shallowRef<string | null>(null);
  const loadingGrantDetail = shallowRef(false);
  const selectedGrantRouteKey = shallowRef<string | null>(null);
  const grantDetailError = shallowRef<string | null>(null);
  const loadingSecretDetail = shallowRef(false);
  const selectedSecretName = shallowRef<string | null>(null);
  const secretDetailError = shallowRef<string | null>(null);
  const loadingArtifactAcl = shallowRef(false);
  const selectedArtifactAclKey = shallowRef<string | null>(null);
  const artifactAclError = shallowRef<string | null>(null);
  const loadingSessionDetail = shallowRef(false);
  const showSessionDetailDialog = shallowRef(false);
  const selectedSessionDetailId = shallowRef<string | null>(null);
  const selectedSessionDetail = shallowRef<AdminSessionDetail | null>(null);
  const sessionDetailError = shallowRef<string | null>(null);
  let grantDetailRequestId = 0;
  let secretDetailRequestId = 0;
  let artifactAclRequestId = 0;
  let sessionDetailRequestId = 0;

  const data = ref<AdminOverviewData>(cloneEmptyOverview());

  const showGrantDialog = shallowRef(false);
  const editingGrant = shallowRef<AdminDatasourceGrant | null>(null);
  const grantForm = ref<DatasourceGrantFormData>({
    subject_type: "user",
    subject_id: "",
    datasource_key: "",
    effect: "allow",
    scope_text: "{}",
  });

  const showQuotaDialog = shallowRef(false);
  const editingQuota = shallowRef<AdminQuota | null>(null);
  const quotaForm = ref<QuotaFormData>({
    subject_type: "user",
    subject_id: "",
    resource: "chat_tokens",
    limit: 100000,
    window_seconds: 86400,
    enabled: true,
  });

  const showSecretDialog = shallowRef(false);
  const editingSecret = shallowRef<AdminSecret | null>(null);
  const secretForm = ref<SecretFormData>({
    name: "",
    provider: "env",
    reference: "",
    description: "",
    enabled: true,
  });

  const showArtifactAclDialog = shallowRef(false);
  const editingArtifact = shallowRef<AdminArtifact | null>(null);
  const editingArtifactAclTarget = shallowRef<ArtifactAclTarget | null>(null);
  const artifactAclForm = ref<ArtifactAclFormData>({
    owner_user_id: "",
    visibility: "private",
    allowed_roles_text: "",
    datasources_text: "",
  });

  const defaultDatasourceName = computed(() => data.value.datasources.find(item => item.is_default)?.name ?? "");
  const runningSessionCount = computed(() => data.value.sessions.filter(session => session.is_running).length);
  const grantCount = computed(() => data.value.datasourceGrants.length);
  const quotaCount = computed(() => data.value.quotas.length);
  const secretCount = computed(() => data.value.secrets.length);

  function grantRouteKey(subjectType: string, subjectId: string, datasourceKey: string): string {
    return `${subjectType}:${subjectId}:${datasourceKey}`;
  }

  function setGrantFormFromGrant(grant: AdminDatasourceGrant) {
    editingGrant.value = grant;
    grantForm.value = {
      subject_type: grant.subject_type,
      subject_id: grant.subject_id,
      datasource_key: grant.datasource_key,
      effect: grant.effect === "deny" ? "deny" : "allow",
      scope_text: scopeText(grant.scope),
    };
  }

  function setSecretFormFromSecret(secret: AdminSecret) {
    editingSecret.value = secret;
    secretForm.value = {
      name: secret.name,
      provider: secret.provider,
      reference: secret.ref_hint,
      description: secret.description ?? "",
      enabled: secret.enabled,
    };
  }

  async function loadOverview() {
    loading.value = true;
    try {
      const [
        datasourceResult,
        grantResult,
        quotaResult,
        usageResult,
        secretResult,
        sessionResult,
        artifactResult,
      ] = await Promise.all([
        adminDatasourceApi.listDatasources(),
        adminDatasourceApi.listGrants(),
        adminQuotaApi.listQuotas(),
        adminQuotaApi.listUsage(),
        adminSecretApi.listSecrets(),
        adminSessionApi.listSessions(),
        adminArtifactApi.listArtifacts(),
      ]);

      data.value = {
        datasources: datasourceResult.data ?? [],
        datasourceGrants: grantResult.data ?? [],
        quotas: quotaResult.data ?? [],
        usage: usageResult.data ?? [],
        secrets: secretResult.data ?? [],
        sessions: sessionResult.data ?? [],
        artifacts: artifactResult.data ?? [],
      };
    } catch (err) {
      console.error("加载管理概览失败:", err);
      data.value = cloneEmptyOverview();
      toast.error("加载管理概览失败");
    } finally {
      loading.value = false;
    }
  }

  function openCreateGrantDialog() {
    grantDetailRequestId += 1;
    selectedGrantRouteKey.value = null;
    grantDetailError.value = null;
    loadingGrantDetail.value = false;
    editingGrant.value = null;
    grantForm.value = {
      subject_type: "user",
      subject_id: "",
      datasource_key: defaultDatasourceName.value || data.value.datasources[0]?.name || "",
      effect: "allow",
      scope_text: "{}",
    };
    showGrantDialog.value = true;
  }

  function openEditGrantDialog(grant: AdminDatasourceGrant) {
    grantDetailRequestId += 1;
    selectedGrantRouteKey.value = grantRouteKey(grant.subject_type, grant.subject_id, grant.datasource_key);
    grantDetailError.value = null;
    loadingGrantDetail.value = false;
    setGrantFormFromGrant(grant);
    showGrantDialog.value = true;
  }

  async function openGrantDetail(subjectType: string, subjectId: string, datasourceKey: string) {
    const normalizedSubjectType = subjectType.trim();
    const normalizedSubjectId = subjectId.trim();
    const normalizedDatasourceKey = datasourceKey.trim();
    if (!normalizedSubjectType || !normalizedSubjectId || !normalizedDatasourceKey) return;

    const requestId = grantDetailRequestId + 1;
    grantDetailRequestId = requestId;
    selectedGrantRouteKey.value = grantRouteKey(normalizedSubjectType, normalizedSubjectId, normalizedDatasourceKey);
    editingGrant.value = null;
    grantDetailError.value = null;
    loadingGrantDetail.value = true;
    grantForm.value = {
      subject_type: normalizedSubjectType,
      subject_id: normalizedSubjectId,
      datasource_key: normalizedDatasourceKey,
      effect: "allow",
      scope_text: "{}",
    };
    showGrantDialog.value = true;

    try {
      const result = await adminDatasourceApi.getGrant(
        normalizedSubjectType,
        normalizedSubjectId,
        normalizedDatasourceKey,
      );
      if (requestId !== grantDetailRequestId) return;

      if (result.data) {
        setGrantFormFromGrant(result.data);
      } else {
        grantDetailError.value = "未找到数据授权详情";
      }
    } catch (err) {
      if (requestId !== grantDetailRequestId) return;
      console.error("加载数据授权详情失败:", err);
      grantDetailError.value = "加载数据授权详情失败";
      toast.error("加载数据授权详情失败");
    } finally {
      if (requestId === grantDetailRequestId) {
        loadingGrantDetail.value = false;
      }
    }
  }

  function closeGrantDialog() {
    grantDetailRequestId += 1;
    showGrantDialog.value = false;
    selectedGrantRouteKey.value = null;
    editingGrant.value = null;
    grantDetailError.value = null;
    loadingGrantDetail.value = false;
  }

  async function saveGrant() {
    const subjectType = grantForm.value.subject_type.trim();
    const subjectId = grantForm.value.subject_id.trim();
    const datasourceKey = grantForm.value.datasource_key.trim();
    if (!subjectType || !subjectId || !datasourceKey) {
      toast.error("请填写授权主体和数据源");
      return;
    }

    let scope: Record<string, unknown>;
    try {
      scope = parseScope(grantForm.value.scope_text);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Scope JSON 无效");
      return;
    }

    savingGrant.value = true;
    try {
      await adminDatasourceApi.upsertGrant(subjectType, subjectId, datasourceKey, {
        effect: grantForm.value.effect,
        scope,
      });
      closeGrantDialog();
      await loadOverview();
    } catch (err) {
      console.error("保存数据授权失败:", err);
      toast.error("保存数据授权失败");
    } finally {
      savingGrant.value = false;
    }
  }

  async function deleteGrant(grant: AdminDatasourceGrant) {
    const key = `${grant.subject_type}:${grant.subject_id}:${grant.datasource_key}`;
    deletingGrantKey.value = key;
    try {
      await adminDatasourceApi.deleteGrant(grant.subject_type, grant.subject_id, grant.datasource_key);
      await loadOverview();
    } catch (err) {
      console.error("删除数据授权失败:", err);
      toast.error("删除数据授权失败");
    } finally {
      deletingGrantKey.value = null;
    }
  }

  function openCreateQuotaDialog() {
    editingQuota.value = null;
    quotaForm.value = {
      subject_type: "user",
      subject_id: "",
      resource: "chat_tokens",
      limit: 100000,
      window_seconds: 86400,
      enabled: true,
    };
    showQuotaDialog.value = true;
  }

  function openEditQuotaDialog(quota: AdminQuota) {
    editingQuota.value = quota;
    quotaForm.value = {
      subject_type: quota.subject_type,
      subject_id: quota.subject_id,
      resource: quota.resource,
      limit: quota.limit,
      window_seconds: quota.window_seconds,
      enabled: quota.enabled,
    };
    showQuotaDialog.value = true;
  }

  async function saveQuota() {
    const subjectType = quotaForm.value.subject_type.trim();
    const resource = quotaForm.value.resource.trim();
    if (!subjectType || !resource || quotaForm.value.limit < 0 || quotaForm.value.window_seconds <= 0) {
      toast.error("请填写有效的额度主体、资源、限制和窗口");
      return;
    }

    savingQuota.value = true;
    try {
      await adminQuotaApi.upsertQuota({
        subject_type: subjectType,
        subject_id: quotaForm.value.subject_id.trim() || null,
        resource,
        limit: Number(quotaForm.value.limit),
        window_seconds: Number(quotaForm.value.window_seconds),
        enabled: quotaForm.value.enabled,
      });
      showQuotaDialog.value = false;
      await loadOverview();
    } catch (err) {
      console.error("保存额度失败:", err);
      toast.error("保存额度失败");
    } finally {
      savingQuota.value = false;
    }
  }

  function openCreateSecretDialog() {
    secretDetailRequestId += 1;
    selectedSecretName.value = null;
    secretDetailError.value = null;
    loadingSecretDetail.value = false;
    editingSecret.value = null;
    secretForm.value = {
      name: "",
      provider: "env",
      reference: "",
      description: "",
      enabled: true,
    };
    showSecretDialog.value = true;
  }

  function openEditSecretDialog(secret: AdminSecret) {
    secretDetailRequestId += 1;
    selectedSecretName.value = secret.name;
    secretDetailError.value = null;
    loadingSecretDetail.value = false;
    setSecretFormFromSecret(secret);
    showSecretDialog.value = true;
  }

  async function openSecretDetail(name: string) {
    const normalizedName = name.trim();
    if (!normalizedName) return;

    const requestId = secretDetailRequestId + 1;
    secretDetailRequestId = requestId;
    selectedSecretName.value = normalizedName;
    editingSecret.value = null;
    secretDetailError.value = null;
    loadingSecretDetail.value = true;
    secretForm.value = {
      name: normalizedName,
      provider: "",
      reference: "",
      description: "",
      enabled: true,
    };
    showSecretDialog.value = true;

    try {
      const result = await adminSecretApi.getSecret(normalizedName);
      if (requestId !== secretDetailRequestId) return;

      if (result.data) {
        setSecretFormFromSecret(result.data);
      } else {
        secretDetailError.value = "未找到密钥引用详情";
      }
    } catch (err) {
      if (requestId !== secretDetailRequestId) return;
      console.error("加载密钥引用详情失败:", err);
      secretDetailError.value = "加载密钥引用详情失败";
      toast.error("加载密钥引用详情失败");
    } finally {
      if (requestId === secretDetailRequestId) {
        loadingSecretDetail.value = false;
      }
    }
  }

  function closeSecretDialog() {
    secretDetailRequestId += 1;
    showSecretDialog.value = false;
    selectedSecretName.value = null;
    editingSecret.value = null;
    secretDetailError.value = null;
    loadingSecretDetail.value = false;
  }

  async function saveSecret() {
    const name = secretForm.value.name.trim();
    const provider = secretForm.value.provider.trim();
    const reference = secretForm.value.reference.trim();
    if (!name || !provider || !reference) {
      toast.error("请填写密钥名称、Provider 和引用");
      return;
    }

    savingSecret.value = true;
    try {
      await adminSecretApi.upsertSecret(name, {
        provider,
        reference,
        description: secretForm.value.description.trim() || null,
        enabled: secretForm.value.enabled,
      });
      closeSecretDialog();
      await loadOverview();
    } catch (err) {
      console.error("保存密钥引用失败:", err);
      toast.error("保存密钥引用失败");
    } finally {
      savingSecret.value = false;
    }
  }

  async function deleteSecret(secret: AdminSecret) {
    deletingSecretName.value = secret.name;
    try {
      await adminSecretApi.deleteSecret(secret.name);
      await loadOverview();
    } catch (err) {
      console.error("删除密钥引用失败:", err);
      toast.error("删除密钥引用失败");
    } finally {
      deletingSecretName.value = null;
    }
  }

  function setArtifactAclTarget(target: ArtifactAclTarget) {
    editingArtifactAclTarget.value = target;
    selectedArtifactAclKey.value = artifactAclTargetKey(target);
    editingArtifact.value = data.value.artifacts.find(item =>
      item.artifact_type === target.artifactType && item.manifest.slug === target.slug
    ) ?? null;
  }

  async function openArtifactAclTarget(target: ArtifactAclTarget) {
    const requestId = artifactAclRequestId + 1;
    artifactAclRequestId = requestId;
    setArtifactAclTarget(target);
    artifactAclError.value = null;
    loadingArtifactAcl.value = true;
    artifactAclForm.value = {
      owner_user_id: "",
      visibility: "private",
      allowed_roles_text: "",
      datasources_text: editingArtifact.value?.manifest.datasources?.join(", ") ?? "",
    };
    showArtifactAclDialog.value = true;

    try {
      const result = await adminArtifactApi.getAcl(target.artifactType, target.slug);
      if (requestId !== artifactAclRequestId) return;

      const acl = result.data;
      if (acl) {
        artifactAclForm.value = {
          owner_user_id: acl.owner_user_id,
          visibility: acl.visibility,
          allowed_roles_text: acl.allowed_roles?.join(", ") ?? "",
          datasources_text: acl.datasources?.join(", ") ?? "",
        };
      } else {
        artifactAclError.value = "未找到产物 ACL";
      }
    } catch (err) {
      if (requestId !== artifactAclRequestId) return;
      console.error("加载产物 ACL 失败:", err);
      artifactAclError.value = "加载产物 ACL 失败";
      toast.error("加载产物 ACL 失败");
    } finally {
      if (requestId === artifactAclRequestId) {
        loadingArtifactAcl.value = false;
      }
    }
  }

  async function openArtifactAclDialog(artifact: AdminArtifact) {
    await openArtifactAclTarget({
      artifactType: artifact.artifact_type,
      slug: artifact.manifest.slug,
    });
  }

  async function openArtifactAclDetail(artifactType: AdminArtifact["artifact_type"], slug: string) {
    const normalizedSlug = slug.trim();
    if (!normalizedSlug) return;

    await openArtifactAclTarget({
      artifactType,
      slug: normalizedSlug,
    });
  }

  function closeArtifactAclDialog() {
    artifactAclRequestId += 1;
    showArtifactAclDialog.value = false;
    selectedArtifactAclKey.value = null;
    editingArtifact.value = null;
    editingArtifactAclTarget.value = null;
    artifactAclError.value = null;
    loadingArtifactAcl.value = false;
  }

  async function saveArtifactAcl() {
    if (!editingArtifactAclTarget.value) return;

    const ownerUserId = artifactAclForm.value.owner_user_id.trim();
    if (!ownerUserId) {
      toast.error("请填写产物所有者");
      return;
    }

    savingArtifactAcl.value = true;
    try {
      await adminArtifactApi.putAcl(editingArtifactAclTarget.value.artifactType, editingArtifactAclTarget.value.slug, {
        owner_user_id: ownerUserId,
        visibility: artifactAclForm.value.visibility,
        allowed_roles: commaList(artifactAclForm.value.allowed_roles_text),
        datasources: commaList(artifactAclForm.value.datasources_text),
      });
      closeArtifactAclDialog();
      await loadOverview();
    } catch (err) {
      console.error("保存产物 ACL 失败:", err);
      toast.error("保存产物 ACL 失败");
    } finally {
      savingArtifactAcl.value = false;
    }
  }

  async function openSessionDetail(sessionId: string) {
    const normalizedSessionId = sessionId.trim();
    if (!normalizedSessionId) return;

    const requestId = sessionDetailRequestId + 1;
    sessionDetailRequestId = requestId;
    showSessionDetailDialog.value = true;
    selectedSessionDetailId.value = normalizedSessionId;
    selectedSessionDetail.value = null;
    sessionDetailError.value = null;
    loadingSessionDetail.value = true;

    try {
      const result = await adminSessionApi.getSession(normalizedSessionId);
      if (requestId !== sessionDetailRequestId) return;
      selectedSessionDetail.value = result.data ?? null;
      if (!selectedSessionDetail.value) {
        sessionDetailError.value = "未找到会话详情";
      }
    } catch (err) {
      if (requestId !== sessionDetailRequestId) return;
      console.error("加载会话详情失败:", err);
      sessionDetailError.value = "加载会话详情失败";
      toast.error("加载会话详情失败");
    } finally {
      if (requestId === sessionDetailRequestId) {
        loadingSessionDetail.value = false;
      }
    }
  }

  function closeSessionDetail() {
    sessionDetailRequestId += 1;
    showSessionDetailDialog.value = false;
    selectedSessionDetailId.value = null;
    selectedSessionDetail.value = null;
    sessionDetailError.value = null;
    loadingSessionDetail.value = false;
  }

  async function stopSession(session: AdminSession) {
    actingSessionId.value = session.session_id;
    try {
      await adminSessionApi.stopSession(session.session_id);
      await loadOverview();
    } catch (err) {
      console.error("停止会话失败:", err);
      toast.error("停止会话失败");
    } finally {
      actingSessionId.value = null;
    }
  }

  async function deleteSession(session: AdminSession) {
    actingSessionId.value = session.session_id;
    try {
      await adminSessionApi.deleteSession(session.session_id);
      await loadOverview();
    } catch (err) {
      console.error("删除会话失败:", err);
      toast.error("删除会话失败");
    } finally {
      actingSessionId.value = null;
    }
  }

  return {
    loading,
    savingGrant,
    savingQuota,
    savingSecret,
    savingArtifactAcl,
    actingSessionId,
    deletingGrantKey,
    deletingSecretName,
    loadingGrantDetail,
    selectedGrantRouteKey,
    grantDetailError,
    loadingSecretDetail,
    selectedSecretName,
    secretDetailError,
    loadingArtifactAcl,
    selectedArtifactAclKey,
    artifactAclError,
    loadingSessionDetail,
    data,
    showGrantDialog,
    editingGrant,
    grantForm,
    showQuotaDialog,
    editingQuota,
    quotaForm,
    showSecretDialog,
    editingSecret,
    secretForm,
    showArtifactAclDialog,
    editingArtifact,
    editingArtifactAclTarget,
    artifactAclForm,
    showSessionDetailDialog,
    selectedSessionDetailId,
    selectedSessionDetail,
    sessionDetailError,
    defaultDatasourceName,
    runningSessionCount,
    grantCount,
    quotaCount,
    secretCount,
    loadOverview,
    openCreateGrantDialog,
    openEditGrantDialog,
    openGrantDetail,
    closeGrantDialog,
    saveGrant,
    deleteGrant,
    openCreateQuotaDialog,
    openEditQuotaDialog,
    saveQuota,
    openCreateSecretDialog,
    openEditSecretDialog,
    openSecretDetail,
    closeSecretDialog,
    saveSecret,
    deleteSecret,
    openArtifactAclDialog,
    openArtifactAclDetail,
    closeArtifactAclDialog,
    saveArtifactAcl,
    openSessionDetail,
    closeSessionDetail,
    stopSession,
    deleteSession,
    artifactKey,
    artifactAclTargetKey,
  };
}
