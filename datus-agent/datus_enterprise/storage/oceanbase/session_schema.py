"""Additive OceanBase schema for enterprise chat session bodies."""

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise_session_bodies (
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, scope, session_id),
  INDEX idx_enterprise_session_bodies_updated (project_id, scope, updated_at)
);

CREATE TABLE IF NOT EXISTS enterprise_session_messages (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  message_data LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enterprise_session_messages_session (project_id, scope, session_id, id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_message_structure (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  message_id BIGINT NOT NULL,
  branch_id VARCHAR(255) NOT NULL DEFAULT 'main',
  message_type VARCHAR(64) NOT NULL,
  sequence_number INTEGER NOT NULL,
  user_turn_number INTEGER,
  branch_turn_number INTEGER,
  tool_name VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enterprise_session_structure_seq (project_id, scope, session_id, branch_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS enterprise_session_turn_usage (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  branch_id VARCHAR(255) NOT NULL DEFAULT 'main',
  user_turn_number INTEGER NOT NULL,
  requests INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  input_tokens_details LONGTEXT,
  output_tokens_details LONGTEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_enterprise_session_turn_usage (project_id, scope, session_id, branch_id, user_turn_number),
  INDEX idx_enterprise_session_usage_turn (project_id, scope, session_id, branch_id, user_turn_number)
);

CREATE TABLE IF NOT EXISTS enterprise_session_running_usage (
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  user_turn_number INTEGER,
  cumulative_json LONGTEXT,
  context_length INTEGER,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_system_prompts (
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  snapshot_json LONGTEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_terminal_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  event_id VARCHAR(255) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_enterprise_session_terminal_events_event (project_id, scope, session_id, event_id),
  INDEX idx_enterprise_session_terminal_events_session (project_id, scope, session_id, created_at, id)
);
"""
