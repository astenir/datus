"""OceanBase MySQL enterprise metadata bootstrap schema definition.

The bootstrap remains additive and idempotent. Production migration tooling,
versioning, and rollback are separate operations concerns.
"""

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise_users (
  user_id VARCHAR(255) NOT NULL,
  display_name VARCHAR(255),
  email VARCHAR(255),
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  external_user_id VARCHAR(255),
  department VARCHAR(255),
  title VARCHAR(255),
  last_seen_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  INDEX idx_enterprise_users_enabled (enabled, user_id)
);

CREATE TABLE IF NOT EXISTS enterprise_user_chat_preferences (
  user_id VARCHAR(255) NOT NULL,
  default_agent_id VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS enterprise_roles (
  role_id VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description LONGTEXT,
  built_in TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role_id)
);

CREATE TABLE IF NOT EXISTS enterprise_role_permissions (
  role_id VARCHAR(255) NOT NULL,
  permission VARCHAR(255) NOT NULL,
  PRIMARY KEY (role_id, permission)
);

CREATE TABLE IF NOT EXISTS enterprise_user_roles (
  user_id VARCHAR(255) NOT NULL,
  role_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, role_id),
  INDEX idx_enterprise_user_roles_role (role_id, user_id)
);

CREATE TABLE IF NOT EXISTS enterprise_datasource_grants (
  subject_type VARCHAR(64) NOT NULL,
  subject_id VARCHAR(255) NOT NULL,
  datasource_key VARCHAR(255) NOT NULL,
  effect VARCHAR(16) NOT NULL,
  scope_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (subject_type, subject_id, datasource_key),
  INDEX idx_enterprise_datasource_grants_datasource (datasource_key, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS enterprise_agents (
  agent_id VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description LONGTEXT,
  node_class VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL,
  owner_user_id VARCHAR(255),
  datasource_id VARCHAR(255),
  artifact_slug VARCHAR(255),
  prompt_template LONGTEXT,
  prompt_language VARCHAR(32) NOT NULL DEFAULT 'en',
  prompt_version VARCHAR(64) NOT NULL DEFAULT '1.0',
  tools_json LONGTEXT NOT NULL,
  mcp_json LONGTEXT NOT NULL,
  skills_json LONGTEXT NOT NULL,
  scoped_context_json LONGTEXT NOT NULL,
  rules_json LONGTEXT NOT NULL,
  max_turns INTEGER NOT NULL DEFAULT 30,
  acl_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (agent_id),
  INDEX idx_enterprise_agents_status (status, agent_id),
  INDEX idx_enterprise_agents_owner (owner_user_id, agent_id)
);

CREATE TABLE IF NOT EXISTS enterprise_agent_prompt_versions (
  version_id VARCHAR(64) NOT NULL,
  agent_id VARCHAR(255) NOT NULL,
  version_label VARCHAR(64) NOT NULL,
  prompt_template LONGTEXT NOT NULL,
  prompt_language VARCHAR(32) NOT NULL DEFAULT 'en',
  content_sha256 CHAR(64) NOT NULL,
  change_note VARCHAR(500),
  based_on_version_id VARCHAR(64),
  created_by VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (version_id),
  UNIQUE KEY uq_enterprise_agent_prompt_version_label (agent_id, version_label),
  INDEX idx_enterprise_agent_prompt_versions_agent (agent_id, created_at, version_id)
);

CREATE TABLE IF NOT EXISTS enterprise_agent_active_prompt_versions (
  agent_id VARCHAR(255) NOT NULL,
  version_id VARCHAR(64) NOT NULL,
  activated_by VARCHAR(255),
  activated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (agent_id)
);

CREATE TABLE IF NOT EXISTS session_owners (
  project_id VARCHAR(255) NOT NULL,
  session_id VARCHAR(255) NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, session_id),
  INDEX idx_session_owners_user (project_id, user_id, updated_at)
);

CREATE TABLE IF NOT EXISTS enterprise_artifact_acls (
  artifact_type VARCHAR(64) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  acl_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (artifact_type, slug)
);

CREATE TABLE IF NOT EXISTS enterprise_audit_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id VARCHAR(255),
  action VARCHAR(255) NOT NULL,
  resource_type VARCHAR(128) NOT NULL,
  resource_id VARCHAR(255),
  decision VARCHAR(64) NOT NULL,
  reason LONGTEXT,
  request_id VARCHAR(255),
  metadata_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enterprise_audit_created (id, created_at),
  INDEX idx_enterprise_audit_user_action (user_id, action, id),
  INDEX idx_enterprise_audit_request (request_id, id),
  INDEX idx_enterprise_audit_created_at (created_at, id)
);

CREATE TABLE IF NOT EXISTS enterprise_quotas (
  subject_type VARCHAR(64) NOT NULL,
  subject_id VARCHAR(255) NOT NULL,
  resource VARCHAR(255) NOT NULL,
  limit_value BIGINT NOT NULL,
  window_seconds BIGINT NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (subject_type, subject_id, resource)
);

CREATE TABLE IF NOT EXISTS enterprise_quota_usage (
  subject_type VARCHAR(64) NOT NULL,
  subject_id VARCHAR(255) NOT NULL,
  resource VARCHAR(255) NOT NULL,
  window_start TIMESTAMP NOT NULL,
  used BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (subject_type, subject_id, resource, window_start),
  INDEX idx_enterprise_quota_usage_resource (resource, subject_type, subject_id)
);

CREATE TABLE IF NOT EXISTS enterprise_secrets (
  name VARCHAR(255) NOT NULL,
  provider VARCHAR(128) NOT NULL,
  reference LONGTEXT NOT NULL,
  description LONGTEXT,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (name),
  INDEX idx_enterprise_secrets_enabled (enabled, name)
);

CREATE TABLE IF NOT EXISTS user_model_credentials (
  user_id VARCHAR(255) NOT NULL,
  credential_id VARCHAR(255) NOT NULL,
  provider VARCHAR(128) NOT NULL,
  model VARCHAR(255) NOT NULL,
  api_key_blob LONGTEXT NOT NULL,
  api_key_hint VARCHAR(32) NOT NULL,
  base_url VARCHAR(512),
  display_name VARCHAR(255),
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  last_used_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, credential_id),
  INDEX idx_user_model_credentials_user_enabled (user_id, enabled, created_at)
);

CREATE TABLE IF NOT EXISTS user_model_preferences (
  user_id VARCHAR(255) NOT NULL,
  default_credential_id VARCHAR(255),
  default_model VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS user_datasources (
  user_id VARCHAR(255) NOT NULL,
  datasource_id VARCHAR(255) NOT NULL,
  datasource_type VARCHAR(128) NOT NULL,
  host VARCHAR(255) NOT NULL,
  port VARCHAR(32) NOT NULL,
  username VARCHAR(255) NOT NULL,
  password_blob LONGTEXT NOT NULL,
  password_hint VARCHAR(32) NOT NULL,
  database_name VARCHAR(255) NOT NULL,
  schema_name VARCHAR(255),
  catalog_name VARCHAR(255),
  display_name VARCHAR(255),
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  last_used_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, datasource_id),
  INDEX idx_user_datasources_user_enabled (user_id, enabled, created_at)
);
"""
