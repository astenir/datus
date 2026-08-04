# Customized Subagents

## Overview

Both `/agent` and `/subagent` open the **unified agent management TUI**. The TUI has two tabs:

- **Built-in** — list the system subagents from `SYS_SUB_AGENTS`. Press `Enter` on a row to set it as the current agent, or `e` to open a single-field form that overrides `max_turns` (persisted under `agent.agentic_nodes.<name>`). `model` is intentionally not editable here — use the global `/model` picker or edit `agent.yml` directly if you really need a per-node model override.
- **Custom** — list user-defined subagents stored under `agent.agentic_nodes` in `agent.yml`. Press `Enter` on a row to set it as the current agent, `e` to edit it in the wizard, `a` to add a new one, or `d d` (twice) to delete.

The legacy `/subagent add|list|remove|update` text subcommands have been removed — all operations now live inside the TUI.

`/agent <name>` still works as a non-TUI shortcut to switch the default directly.

## What the Wizard Creates

The wizard writes two things:

1. A new entry under `agent.agentic_nodes`
2. A prompt template file named like `{agent_name}_system_{prompt_version}.j2`

The wizard currently supports two custom node styles:

- `gen_sql` (default)
- `gen_report`

If you want advanced aliases such as `explore`, `gen_table`, `gen_skill`, `gen_dashboard`, or `scheduler`, edit `agent.yml` manually.

## Wizard Fields

### Step 1: Basic Info

- `system_prompt`: the subagent name and config key
- `node_class`: `gen_sql` or `gen_report`
- `agent_description`: short description shown in previews and task-tool descriptions

### Step 2: Tools and MCP

You must select at least one native tool or one MCP tool.

- Native tools are stored as comma-separated category or method patterns such as `db_tools`, `semantic_tools.*`, or `context_search_tools.list_subject_tree`
- MCP selections are stored as comma-separated server or `server.tool` entries

### Step 3: Scoped Context

The wizard supports scoped values for:

- `tables`
- `metrics`
- `sqls`

When the wizard saves the config, it also records the current database as `scoped_context.datasource`.

### Step 4: Rules

Rules are stored as a string list under `rules` and appended to the final system prompt.

## TUI Reference

Open the manager with `/agent` (lands on the Built-in tab) or `/subagent` (lands on the Custom tab).

Keyboard shortcuts (agent list view):

| Key | Action |
|-----|--------|
| ↑ ↓ / PageUp / PageDown | Navigate |
| `Tab` or ← → | Switch Built-in ↔ Custom |
| `Enter` | Set the highlighted agent as the current agent (the Custom tab's trailing `+ Add agent…` row opens the wizard instead) |
| `e` | Built-in: open the model / max_turns override form. Custom: open the wizard for the selected agent. |
| `a` | (Custom tab) Start the wizard to create a new custom subagent |
| `d` twice | (Custom tab) Delete the highlighted custom subagent (two presses to confirm) |
| `Esc` / `Ctrl+C` | Cancel |

Built-in edit form:

| Key | Action |
|-----|--------|
| Type integer | Edit `max_turns` directly in the input |
| `Enter` / `Ctrl+S` | Save override |
| `Esc` | Back to the agent list |

Overrides write only `max_turns` into `agent.agentic_nodes.<name>`; sibling keys such as `scoped_context`, `rules`, or `tools` (if present) are preserved, and any hand-edited `model` override stays intact. Clearing the input (empty `max_turns`) removes the override; if the node has no other override fields, its entry is dropped from the YAML entirely.

## Example Output

A generated config typically looks like this:

```yaml
agent:
  agentic_nodes:
    finance_report:
      system_prompt: finance_report
      node_class: gen_report
      prompt_version: "1.0"
      prompt_language: en
      agent_description: "Finance reporting assistant"
      tools: semantic_tools.*, db_tools.*, context_search_tools.list_subject_tree
      mcp: ""
      rules:
        - Prefer existing finance metrics before generating new SQL
      scoped_context:
        datasource: finance
        tables: mart.finance_daily
        metrics: finance.revenue.daily_revenue
        sqls: finance.revenue.region_rollup
```

## Scoped Context Semantics

Current code no longer builds a separate scoped knowledge-base directory for each subagent.

Instead:

- scoped context is stored in `agentic_nodes.<name>.scoped_context`
- Datus applies filters against the shared global storage at query time
- database tools may also narrow their visible table surface based on the active subagent

That means:

- there is no `/subagent bootstrap` command in the current CLI
- `scoped_kb_path` is deprecated and not persisted for newly saved configs
- global knowledge still needs to be populated separately with `datus-agent bootstrap-kb`

## Prompt Sources, Updates, and Verification

An Agent's base system prompt resolves in this order:

1. A non-empty enterprise `prompt_template` projected into the request-scoped
   `agent_config.agentic_nodes`
2. A user template at
   `{agent.home}/template/{template_name}_{version}.j2`
3. A bundled template under `datus/prompts/prompt_templates/`

`system_prompt` selects `template_name`; most nodes append `_system`. An explicit
`prompt_version` pins that version. Only an unpinned template selects the highest
numeric version across the user and bundled directories. In other words,
"latest" means the current effective source selected by configuration, not an
unconditional switch to the highest filename while a version is pinned.

The finalized system prompt can also append runtime context, datasource
capabilities, plugin context, `AGENTS.md`, Skills, Memory, and response-language
rules. These non-template inputs follow session snapshot semantics and do not
drift on every turn merely because template auto-invalidation is enabled.

Each session persists one system-prompt snapshot. Local sessions use:

```text
{sessions_dir}/{scope}/{session_id}.sysprompt.json
```

With an enterprise `session_body_store`, the snapshot is stored in
`enterprise_session_system_prompts.snapshot_json`. Snapshot schema v2 records
safe provenance fields including:

- `agent_id`, `prompt_version`, and `prompt_pipeline_version`
- `prompt_template_name`, `resolved_prompt_version`, and `prompt_template_source`
- `prompt_template_sha256` and `prompt_template_revision_sha256`
- `prompt_revision_sha256` and `final_prompt_sha256`
- `prompt_templates`, containing every template identity read while assembling
  the final prompt

Whenever a session continues, Datus re-resolves those identities. A change to
the main template, a static Jinja `include`/`import`, a user override, a
request-scoped enterprise custom prompt, the effective version, or the Agent
definition invalidates and atomically replaces the old snapshot. No API restart
or manual database deletion is required. A v1 snapshot is lazily rebuilt as v2
on its next use. A change cannot alter an in-flight turn that has already been
sent to the model; it applies at the next prompt lookup.

Verify provenance and hashes without printing the `prompt` field. The
`System prompt snapshot rebuilt` log includes the Agent, session, template,
resolved version, revision hash, and final hash. If no rebuild is logged,
compare the snapshot's `prompt_templates` with the intended source. Adding a
higher version does not switch an explicitly pinned Agent.

## Advanced Manual Configuration

The wizard covers the common `gen_sql` and `gen_report` cases. For more advanced setups, edit `agent.yml` directly.

Example:

```yaml
agent:
  agentic_nodes:
    sales_dashboard:
      node_class: gen_dashboard
      model: claude
      bi_platform: superset
      max_turns: 30

    etl_scheduler:
      node_class: scheduler
      model: claude
      max_turns: 30
```

See [Subagent Guide](./introduction.md) and [Built-in subagents](./builtin_subagents.md) for the supported node classes and runtime behavior.
