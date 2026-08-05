"""PostgreSQL enterprise metadata bootstrap schema definition.

The bootstrap remains additive and idempotent. Production migration tooling,
versioning, and rollback are separate operations concerns.
"""

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise_users (
    user_id text PRIMARY KEY,
    display_name text,
    email text,
    enabled boolean NOT NULL DEFAULT true,
    external_user_id text,
    department text,
    title text,
    last_seen_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE enterprise_users
ADD COLUMN IF NOT EXISTS external_user_id text;

ALTER TABLE enterprise_users
ADD COLUMN IF NOT EXISTS department text;

ALTER TABLE enterprise_users
ADD COLUMN IF NOT EXISTS title text;

ALTER TABLE enterprise_users
ADD COLUMN IF NOT EXISTS last_seen_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_enterprise_users_enabled
ON enterprise_users (enabled, user_id);

CREATE TABLE IF NOT EXISTS enterprise_user_chat_preferences (
    user_id text PRIMARY KEY,
    default_agent_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_roles (
    role_id text PRIMARY KEY,
    name text NOT NULL,
    description text,
    built_in boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_role_permissions (
    role_id text NOT NULL REFERENCES enterprise_roles(role_id) ON DELETE CASCADE,
    permission text NOT NULL,
    PRIMARY KEY (role_id, permission)
);

CREATE TABLE IF NOT EXISTS enterprise_user_roles (
    user_id text NOT NULL,
    role_id text NOT NULL REFERENCES enterprise_roles(role_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_user_roles_role
ON enterprise_user_roles (role_id, user_id);

CREATE TABLE IF NOT EXISTS enterprise_datasource_grants (
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    datasource_key text NOT NULL,
    effect text NOT NULL,
    scope_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_type, subject_id, datasource_key)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_datasource_grants_datasource
ON enterprise_datasource_grants (datasource_key, subject_type, subject_id);

CREATE TABLE IF NOT EXISTS enterprise_agents (
    agent_id text PRIMARY KEY,
    name text NOT NULL,
    description text,
    node_class text NOT NULL,
    status text NOT NULL,
    owner_user_id text,
    datasource_id text,
    artifact_slug text,
    prompt_template text,
    prompt_language text NOT NULL DEFAULT 'en',
    prompt_version text NOT NULL DEFAULT '1.0',
    tools text[] NOT NULL DEFAULT ARRAY[]::text[],
    mcp text[] NOT NULL DEFAULT ARRAY[]::text[],
    skills text[] NOT NULL DEFAULT ARRAY[]::text[],
    scoped_context_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    rules text[] NOT NULL DEFAULT ARRAY[]::text[],
    max_turns integer NOT NULL DEFAULT 30,
    acl_json jsonb NOT NULL DEFAULT '{"visibility":"private","allowed_roles":[],"allowed_user_ids":[]}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_enterprise_agents_status
ON enterprise_agents (status, agent_id);

CREATE INDEX IF NOT EXISTS idx_enterprise_agents_owner
ON enterprise_agents (owner_user_id, agent_id);

CREATE TABLE IF NOT EXISTS enterprise_agent_prompt_versions (
    version_id text PRIMARY KEY,
    agent_id text NOT NULL,
    version_label text NOT NULL,
    prompt_template text NOT NULL,
    prompt_language text NOT NULL DEFAULT 'en',
    content_sha256 text NOT NULL,
    change_note text,
    based_on_version_id text,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (agent_id, version_label)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_agent_prompt_versions_agent
ON enterprise_agent_prompt_versions (agent_id, created_at DESC, version_id);

CREATE TABLE IF NOT EXISTS enterprise_agent_active_prompt_versions (
    agent_id text PRIMARY KEY,
    version_id text NOT NULL,
    activated_by text,
    activated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_owners (
    project_id text NOT NULL,
    session_id text NOT NULL,
    user_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_session_owners_user
ON session_owners (project_id, user_id, updated_at);

CREATE TABLE IF NOT EXISTS enterprise_artifact_acls (
    artifact_type text NOT NULL,
    slug text NOT NULL,
    acl_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (artifact_type, slug)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_artifact_acls_type_updated
ON enterprise_artifact_acls (artifact_type, updated_at);

CREATE TABLE IF NOT EXISTS enterprise_audit_logs (
    id bigserial PRIMARY KEY,
    user_id text,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text,
    decision text NOT NULL,
    reason text,
    request_id text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_created_at
ON enterprise_audit_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_user_id
ON enterprise_audit_logs (user_id);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_action
ON enterprise_audit_logs (action);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_resource_type
ON enterprise_audit_logs (resource_type);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_decision
ON enterprise_audit_logs (decision);

CREATE INDEX IF NOT EXISTS idx_enterprise_audit_logs_request_id
ON enterprise_audit_logs (request_id);

CREATE TABLE IF NOT EXISTS enterprise_quotas (
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    resource text NOT NULL,
    limit_value integer NOT NULL,
    window_seconds integer NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_type, subject_id, resource)
);

CREATE TABLE IF NOT EXISTS enterprise_quota_usage (
    subject_type text NOT NULL,
    subject_id text NOT NULL,
    resource text NOT NULL,
    window_start timestamptz NOT NULL,
    used integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_type, subject_id, resource, window_start)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_quota_usage_filter
ON enterprise_quota_usage (subject_type, subject_id, resource, window_start DESC);

CREATE TABLE IF NOT EXISTS enterprise_secrets (
    name text PRIMARY KEY,
    provider text NOT NULL,
    reference text NOT NULL,
    description text,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_model_credentials (
    user_id text NOT NULL,
    credential_id text NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    api_key_blob text NOT NULL,
    api_key_hint text NOT NULL,
    base_url text,
    display_name text,
    enabled boolean NOT NULL DEFAULT true,
    last_used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, credential_id)
);

ALTER TABLE user_model_credentials
ADD COLUMN IF NOT EXISTS base_url text;

CREATE INDEX IF NOT EXISTS idx_user_model_credentials_user_enabled
ON user_model_credentials (user_id, enabled, created_at);

CREATE TABLE IF NOT EXISTS user_model_preferences (
    user_id text PRIMARY KEY,
    default_credential_id text,
    default_model text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_datasources (
    user_id text NOT NULL,
    datasource_id text NOT NULL,
    datasource_type text NOT NULL,
    host text NOT NULL,
    port text NOT NULL,
    username text NOT NULL,
    password_blob text NOT NULL,
    password_hint text NOT NULL,
    database_name text NOT NULL,
    schema_name text,
    catalog_name text,
    display_name text,
    enabled boolean NOT NULL DEFAULT true,
    last_used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, datasource_id)
);

CREATE INDEX IF NOT EXISTS idx_user_datasources_user_enabled
ON user_datasources (user_id, enabled, created_at);
"""
