# Skills & Permission Test Suite

Test coverage for AgentSkills system: skill discovery, loading, execution, permission enforcement, and agentic node integration.

## Test Structure

```
tests/
├── skills/                              # Unit tests (198 tests)
│   ├── test_skill_config.py             # SkillConfig & SkillMetadata models
│   ├── test_skill_registry.py           # Skill discovery from filesystem
│   ├── test_skill_bash_tool.py          # Restricted bash execution
│   ├── test_skill_func_tool.py          # LLM-callable load_skill / skill_execute_command
│   ├── test_skill_manager.py            # Skill coordination + XML generation
│   ├── test_permission_config.py        # PermissionLevel, PermissionRule, PermissionConfig
│   ├── test_permission_manager.py       # Permission evaluation & tool filtering
│   ├── test_permission_hooks.py         # Runtime permission enforcement hooks
│   └── test_agentic_node_skills.py      # AgenticNode base class skill integration
├── integration/
│   ├── conftest.py                      # Shared fixtures (AgentConfig, SkillManager, etc.)
│   └── test_integration_skill.py        # Integration tests (30 tests)
└── data/skills/                         # Test skill fixtures
    ├── sql-analysis/SKILL.md
    ├── sql-optimization/SKILL.md
    ├── report-generator/SKILL.md        # Has scripts/ for bash execution tests
    ├── data-profiler/SKILL.md           # Has scripts/ for bash execution tests
    └── admin-tools/SKILL.md
```

## Running Tests

```bash
# All skill unit tests (198 tests, ~3s)
pytest tests/skills/ -q

# All skill integration tests (30 tests, ~2min with LLM)
pytest tests/integration/test_integration_skill.py -q

# Acceptance tests only (6 tests, requires DEEPSEEK_API_KEY)
pytest tests/integration/test_integration_skill.py -m acceptance -q

# All skill + integration together
pytest tests/skills/ tests/integration/test_integration_skill.py -q
```

---

## Unit Tests (tests/skills/)

### test_skill_config.py — SkillConfig & SkillMetadata (17 tests)

Data model validation for the skills configuration layer.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestSkillConfig` | 7 | Default directories, custom dirs, from_dict, serialization |
| `TestSkillMetadata` | 10 | Required/optional fields, frontmatter parsing, lazy content loading, `has_scripts`, `is_model_invocable` |

### test_skill_registry.py — SkillRegistry (16 tests)

Filesystem scanning and skill discovery from `SKILL.md` files.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestSkillRegistryBasic` | 3 | Creation, empty dir scan, nonexistent dir handling |
| `TestSkillRegistryDiscovery` | 4 | Simple skill, skill with scripts, multiple skills, disabled model invocation |
| `TestSkillRegistryContentLoading` | 3 | Content loading, nonexistent skill, content caching |
| `TestSkillRegistryRefresh` | 1 | Dynamic skill addition via refresh() |
| `TestSkillRegistryEdgeCases` | 5 | Missing frontmatter, invalid YAML, missing required fields, duplicates, path validation |

### test_skill_bash_tool.py — SkillBashTool (27 tests)

Restricted bash execution with command pattern filtering.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestSkillBashToolBasic` | 5 | Creation, custom timeout, available tools with/without patterns, tool context |
| `TestSkillBashToolPatternMatching` | 7 | Exact match, args, wrong prefix/pattern, dangerous commands, wildcards, multi-pattern |
| `TestSkillBashToolExecution` | 6 | Allowed/denied commands, empty command, JSON output, failure handling |
| `TestSkillBashToolWorkspaceIsolation` | 2 | Workspace root, skill directory isolation |
| `TestSkillBashToolEnvironment` | 1 | Environment variables (SKILL_NAME, SKILL_DIR, WORKSPACE_ROOT) |
| `TestSkillBashToolEdgeCases` | 5 | Quotes, special chars, whitespace-only, no patterns → empty tools/deny all |
| `TestSkillBashToolTimeout` | 1 | Command timeout enforcement |

### test_skill_func_tool.py — SkillFuncTool (18 tests)

LLM-callable function tools: `load_skill()` and `skill_execute_command()`.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestSkillFuncToolBasic` | 3 | Creation, available_tools (load_skill + skill_execute_command), tool context |
| `TestSkillFuncToolLoadSkill` | 4 | Success, not found, denied, with scripts (creates bash tool) |
| `TestSkillFuncToolBashToolManagement` | 5 | Get before/after load, get all, get loaded tools, no-scripts → no bash tool |
| `TestSkillFuncToolPermissionCallback` | 1 | Setting async permission callback |
| `TestSkillFuncToolEdgeCases` | 3 | Empty name, duplicate load, multiple script skills |
| `TestSkillExecuteCommand` | 5 | Before load, not found, no scripts, after load, not allowed |

### test_skill_manager.py — SkillManager (25 tests)

High-level coordinator: registry + permissions + pattern filtering + XML generation.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestSkillManagerBasic` | 5 | Creation, with permissions, skill count, get skill, list all |
| `TestSkillManagerAvailableSkills` | 5 | No permissions, with permissions (DENY hidden, ASK visible), patterns, multiple patterns, wildcard |
| `TestSkillManagerLoadSkill` | 5 | Success, not found, denied, ASK permission, skip permission check |
| `TestSkillManagerXMLGeneration` | 6 | Basic XML, with permissions, with patterns, empty, includes description, includes tags |
| `TestSkillManagerPermissionCheck` | 4 | ALLOW, DENY, ASK, no manager → default ALLOW |
| `TestSkillManagerPatternParsing` | 4 | Empty, single, multiple, whitespace handling |
| `TestSkillManagerRefresh` | 1 | Dynamic skill addition |

### test_permission_config.py — PermissionConfig (19 tests)

Permission rule matching and configuration models.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestPermissionLevel` | 4 | Values (ALLOW/DENY/ASK), from_string, invalid value, string repr |
| `TestPermissionRule` | 8 | Creation, wildcard pattern, string permission, all wildcards, matches (basic, wildcard, tool wildcard, all wildcards) |
| `TestPermissionConfig` | 7 | Default config, with rules, from_dict (full, empty, partial, only default/rules), serialization, merge |

### test_permission_manager.py — PermissionManager (15 tests)

Permission evaluation engine: rule matching, tool filtering, node overrides.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestPermissionManagerBasic` | 2 | Creation with defaults, with overrides |
| `TestPermissionManagerCheckPermission` | 5 | Default allow/deny, matching rule, wildcard, last-match-wins, node override (dict + config) |
| `TestPermissionManagerFilterTools` | 4 | No deny, with deny, all denied, ASK included |
| `TestPermissionManagerFilterSkills` | 3 | No deny, with deny, node-specific |
| `TestPermissionManagerEdgeCases` | 4 | Empty tool name, empty node name, special chars, None overrides |

### test_permission_hooks.py — PermissionHooks (14 tests)

Runtime hook that intercepts tool calls for permission checks.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestPermissionDeniedException` | 2 | Exception creation, with category/name |
| `TestCompositeHooks` | 2 | Filters None hooks, calls all hooks |
| `TestPermissionHooks` | 7 | Init, register tools, category extraction (native/MCP/skill/unknown), parse args (JSON/invalid/dict), on_tool_start (allow/deny/ask) |
| `TestPermissionHooksIntegration` | 3 | MCP tool name parsing, skill name extraction, multi-category registration |

### test_agentic_node_skills.py — AgenticNode Skill Integration (25 tests)

Base class skill support: `_finalize_system_prompt()`, `_ensure_skill_tools_in_tools()`, `_setup_skill_func_tools()`.

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestFinalizeSystemPrompt` | 4 | No skill_func_tool → unchanged, with skill_func_tool → XML appended, empty XML → unchanged, calls ensure_skill_tools |
| `TestEnsureSkillToolsInTools` | 5 | No skill_func_tool → noop, adds when missing, idempotent (no duplicates), handles None tools, preserves existing tools |
| `TestSetupSkillFuncTools` | 4 | No skills config → noop, creates SkillManager when None, uses existing SkillManager, creates SkillFuncTool |
| `TestAgenticNodeSkillDefaults` | 2 | No config → skill_func_tool is None, with config → skill_func_tool activated |
| `TestGetAvailableSkillsContext` | 4 | No skill_manager → empty, with manager → XML, respects patterns, no pattern → all skills |
| `TestSkillManagerSetup` | 3 | No agent_config → noop, no skills_config → noop, with config → creates manager |
| `TestSkillIntegrationEdgeCases` | 3 | Multiple patterns, preserves existing tools, exception handling |

---

## Integration Tests (tests/integration/test_integration_skill.py)

### Config & Fixtures

- **agent.yml**: `tests/conf/agent.yml` with `skills:`, `permissions:`, `agentic_nodes:` sections
- **agent_llm_skill.yml**: Real LLM config for acceptance tests (DeepSeek + california_schools)
- **Test skills**: `tests/data/skills/` (5 skills: sql-analysis, sql-optimization, report-generator, data-profiler, admin-tools)
- **conftest.py**: Shared fixtures — AgentConfig, SkillConfig, PermissionManager, SkillManager, SkillFuncTool

### TestSkillDiscoveryIntegration (5 tests)

Real filesystem discovery using `tests/data/skills/`.

| Test | Description |
|------|-------------|
| `test_discovers_all_skills_from_data_dir` | All 5 skills discovered (acceptance) |
| `test_multi_directory_discovery` | Skills from multiple directories merged |
| `test_refresh_picks_up_new_skills` | Dynamic skill addition at runtime |
| `test_nonexistent_directory_gracefully_skipped` | Mixed valid + invalid dirs works |
| `test_duplicate_skill_first_directory_wins` | First discovered wins, count stays same |

### TestSkillLoadAndExecuteIntegration (6 tests)

Full load → execute → result pipeline with real Python scripts.

| Test | Description |
|------|-------------|
| `test_workflow_skill_loads_content_no_bash_tool` | Workflow skill returns content, no bash tool |
| `test_script_skill_loads_and_executes` | Script skill creates bash tool, executes, returns JSON (acceptance) |
| `test_chained_workflow_then_execute` | Load workflow → load script → execute script |
| `test_script_execution_error_propagates` | Nonexistent skill → error |
| `test_denied_command_rejected` | `rm -rf /` rejected by pattern filter (acceptance) |
| `test_skill_execute_command_before_load` | Helpful error before load_skill |

### TestPermissionIntegration (6 tests)

Permission enforcement across SkillManager + PermissionManager layers.

| Test | Description |
|------|-------------|
| `test_deny_hides_skill_from_available_and_xml` | DENY hides from list and XML |
| `test_deny_blocks_load` | DENY blocks load_skill (acceptance) |
| `test_ask_keeps_skill_visible_but_blocks_load` | ASK visible but returns ASK_PERMISSION |
| `test_node_override_grants_access_to_denied_skill` | Global DENY + node ALLOW → accessible |
| `test_permission_with_pattern_filtering_combined` | Pattern + permission filters work together |
| `test_disable_model_invocation_hides_from_available` | `disable_model_invocation: true` hides skill |

### TestAgenticNodeSkillFiltering (7 tests)

Skill filtering based on `agentic_nodes` config in agent.yml.

| Test | Description |
|------|-------------|
| `test_agent_config_loads_skills_config` | AgentConfig parses skills section |
| `test_agent_config_loads_permissions_config` | AgentConfig parses permissions section |
| `test_agent_config_has_skill_nodes` | school_sql, school_report, school_all nodes exist |
| `test_school_sql_node_sees_only_sql_skills` | `skills: "sql-*"` → only sql-analysis, sql-optimization (acceptance) |
| `test_school_report_node_sees_report_and_data_skills` | `skills: "report-*, data-*"` → report-generator, data-profiler |
| `test_school_all_node_sees_all_including_admin` | `skills: "*"` + admin override → all 5 skills |
| `test_xml_generation_respects_node_patterns` | Different nodes generate different XML |

### TestSkillToolsAccumulationIntegration (5 tests)

Multi-skill loading lifecycle and tool management.

| Test | Description |
|------|-------------|
| `test_loaded_tools_accumulate_across_skills` | Loading 2 script skills → 2 bash tools (acceptance) |
| `test_workflow_skill_does_not_add_to_bash_tools` | Workflow-only skills → 0 bash tools |
| `test_mixed_skills_only_script_ones_get_bash_tools` | 2 workflow + 2 script → 2 bash tools |
| `test_duplicate_load_does_not_double_bash_tool` | Same skill twice → 1 bash tool |
| `test_loaded_skill_tools_returns_tool_objects` | get_loaded_skill_tools returns Tool objects |

### TestRealLLMSkillIntegration (1 test, acceptance)

End-to-end with real LLM (DeepSeek) + california_schools database.

| Test | Description |
|------|-------------|
| `test_skill_invocation_in_chat` | ChatAgenticNode queries DB → `load_skill("report-generator")` → `skill_execute_command()` |

Prerequisites: `DEEPSEEK_API_KEY`, `~/.datus/benchmark/california_schools/california_schools.sqlite`, `~/.datus/skills/report-generator/`

---

## Architecture Coverage

```
agent.yml                    test_skill_config, test_integration (section 4)
  ├── skills:                  SkillConfig defaults, directories, from_dict
  │     └── directories        SkillRegistry scan, multi-dir, refresh
  ├── permissions:             PermissionConfig rules, merge_with
  │     ├── rules              PermissionRule matching, wildcards, last-match-wins
  │     └── node overrides     PermissionManager node-specific overrides
  └── agentic_nodes:
        └── skills: "pattern"  AgenticNode _setup_skill_func_tools, _finalize_system_prompt

SkillRegistry                test_skill_registry
  └── scan_directories()       SKILL.md parsing, frontmatter, lazy content

SkillManager                 test_skill_manager
  ├── get_available_skills()   Pattern filtering + permission filtering
  ├── load_skill()             Permission check → content loading
  └── generate_xml()           <available_skills> XML generation

SkillFuncTool                test_skill_func_tool
  ├── load_skill()             LLM tool: discover + load + create bash tool
  └── skill_execute_command()  LLM tool: route to correct SkillBashTool

SkillBashTool                test_skill_bash_tool
  └── execute_command()        Pattern matching, workspace isolation, timeout

PermissionManager            test_permission_manager
  ├── check_permission()       Rule evaluation, last-match-wins
  ├── filter_tools()           Hide DENY tools from LLM
  └── filter_skills()          Hide DENY skills from available list

PermissionHooks              test_permission_hooks
  └── on_tool_start()          Runtime interception: ALLOW/DENY/ASK

AgenticNode (base)           test_agentic_node_skills
  ├── _setup_skill_func_tools()    Auto-create SkillManager, create SkillFuncTool
  ├── _ensure_skill_tools_in_tools()  Lazy tool injection, idempotent
  ├── _finalize_system_prompt()       Skills XML injection (all subclasses)
  └── _get_available_skills_context() Pattern-filtered XML generation
```

## Key Design Decisions Tested

1. **ChatAgenticNode loads ALL skills by default** — no explicit `skills:` config needed
2. **Other AgenticNodes load NO skills by default** — must set `skills:` in `agentic_nodes.{name}`
3. **`_finalize_system_prompt()`** — called by all subclass `_get_system_prompt()` overrides, ensures consistent skills XML injection regardless of how the template is rendered
4. **`_ensure_skill_tools_in_tools()`** — lazy injection solves the timing issue where subclass `setup_tools()` resets `self.tools = []` after base `__init__`
5. **Auto-create SkillManager** — when no global `skills:` section in agent.yml, `_setup_skill_func_tools()` creates a default SkillManager (same default directories as ChatAgenticNode)
6. **`skill_execute_command` default permission is ASK** — prepended as lowest-priority rule, user config can override
