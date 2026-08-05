"""Additive PostgreSQL schema for enterprise chat session bodies."""

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise_session_bodies (
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_messages (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  message_data TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_session_message_structure (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  message_id BIGINT NOT NULL,
  branch_id TEXT NOT NULL DEFAULT 'main',
  message_type TEXT NOT NULL,
  sequence_number INTEGER NOT NULL,
  user_turn_number INTEGER,
  branch_turn_number INTEGER,
  tool_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_session_turn_usage (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  branch_id TEXT NOT NULL DEFAULT 'main',
  user_turn_number INTEGER NOT NULL,
  requests INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  input_tokens_details TEXT,
  output_tokens_details TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(project_id, scope, session_id, branch_id, user_turn_number)
);

CREATE TABLE IF NOT EXISTS enterprise_session_running_usage (
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  user_turn_number INTEGER,
  cumulative_json TEXT,
  context_length INTEGER,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_system_prompts (
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_terminal_events (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, scope, session_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_session_bodies_updated
  ON enterprise_session_bodies (project_id, scope, updated_at);
CREATE INDEX IF NOT EXISTS idx_enterprise_session_messages_session
  ON enterprise_session_messages (project_id, scope, session_id, id);
CREATE INDEX IF NOT EXISTS idx_enterprise_session_structure_seq
  ON enterprise_session_message_structure (project_id, scope, session_id, branch_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_enterprise_session_usage_turn
  ON enterprise_session_turn_usage (project_id, scope, session_id, branch_id, user_turn_number);
CREATE INDEX IF NOT EXISTS idx_enterprise_session_terminal_events_session
  ON enterprise_session_terminal_events (project_id, scope, session_id, created_at, id);
"""
