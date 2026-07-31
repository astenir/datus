import { describe, expect, it } from "vitest";

import {
  isInteractionToolName,
  subagentDisplayName,
  toolDisplayName,
  toolPresentation,
  visibleToolChildMessages,
} from "@/lib/tool-presentation";

describe("tool presentation", () => {
  it("turns common internal tool names into user-facing actions", () => {
    expect(toolDisplayName("db_tools.list_tables")).toBe("列出数据表");
    expect(toolDisplayName("execute_sql")).toBe("执行 SQL");
    expect(toolDisplayName("custom_server.lookup_fund")).toBe("lookup fund");
    expect(toolDisplayName("semantic_tools.attribution_analyze")).toBe("执行归因分析");
    expect(toolDisplayName("artifact_tools.validate_render")).toBe("校验产物渲染");
    expect(toolDisplayName("db_tools.list_database")).toBe("列出数据库");
    expect(toolDisplayName("db_tools.search_tables")).toBe("搜索数据表");
  });

  it("builds a completed SQL presentation with summary and duration", () => {
    expect(toolPresentation({
      type: "tool-execution",
      callToolId: "sql-1",
      toolName: "db_tools.execute_sql",
      params: { sql: "select * from fund_positions" },
      shortDesc: "select * from fund_positions",
      duration: 1.25,
      resultStatus: "success",
      result: {
        columns: ["fund_id"],
        rows: [["F001"], ["F002"]],
      },
    })).toEqual({
      title: "执行 SQL",
      technicalName: "db_tools.execute_sql",
      state: "completed",
      statusLabel: "已完成",
      summary: "select * from fund_positions",
      metadata: ["1.25 秒", "2 行"],
      isSubagent: false,
    });
  });

  it("uses the delegated agent as the primary task title", () => {
    const presentation = toolPresentation({
      type: "tool-execution",
      callToolId: "task-1",
      toolName: "task",
      params: { type: "explore", prompt: "探索基金持仓相关表" },
      result: { session_id: "explore-1" },
      childMessages: [
        {
          id: "progress-1",
          role: "assistant",
          content: "正在列出数据表",
          blocks: [{ type: "markdown", content: "正在列出数据表" }],
        },
        {
          id: "complete-1",
          role: "assistant",
          content: "已完成",
          blocks: [{
            type: "subagent-complete",
            subagent: "explore",
            toolCount: 4,
            duration: 3.2,
          }],
        },
      ],
    });

    expect(presentation).toEqual({
      title: "探索数据结构",
      technicalName: "task · explore",
      state: "completed",
      statusLabel: "已完成",
      summary: "探索基金持仓相关表",
      metadata: ["4 次工具调用", "3.20 秒"],
      isSubagent: true,
    });
  });

  it("adds meaningful scope summaries to database discovery tools", () => {
    expect(toolPresentation({
      type: "tool-execution",
      callToolId: "databases-1",
      toolName: "list_databases",
      params: { datasource: "datus_enterprise" },
      duration: 0.25,
      result: ["postgres"],
    })).toMatchObject({
      summary: "数据源 datus_enterprise",
      metadata: ["0.25 秒", "1 项"],
    });

    expect(toolPresentation({
      type: "tool-execution",
      callToolId: "schemas-1",
      toolName: "list_schemas",
      params: { database: "datus_enterprise" },
      result: ["public", "semantic"],
    })).toMatchObject({ summary: "数据库 datus_enterprise" });

    expect(toolPresentation({
      type: "tool-execution",
      callToolId: "tables-1",
      toolName: "list_tables",
      params: { database: "datus_enterprise", schema_name: "public" },
      result: [],
    })).toMatchObject({ summary: "datus_enterprise.public" });
  });

  it("supports table-search aliases and leaves parameterless discovery summaries optional", () => {
    expect(toolPresentation({
      type: "tool-call",
      callToolId: "search-table-1",
      toolName: "search_table",
      params: {
        query_text: "基金持仓和投资组合相关的数据表",
        database: "datus_enterprise",
        schema_name: "public",
      },
    })).toMatchObject({
      title: "搜索数据表",
      summary: "基金持仓和投资组合相关的数据表",
    });

    expect(toolPresentation({
      type: "tool-call",
      callToolId: "search-1",
      toolName: "search_tables",
      params: { keywords: ["基金", "持仓"] },
    })).toMatchObject({
      title: "搜索数据表",
      summary: "基金、持仓",
    });

    expect(toolPresentation({
      type: "tool-execution",
      callToolId: "subject-tree-1",
      toolName: "list_subject_tree",
      params: {},
      duration: 0.4,
      result: {},
    })).not.toHaveProperty("summary");
  });

  it("uses the pattern instead of the search path for file discovery tools", () => {
    expect(toolPresentation({
      type: "tool-call",
      callToolId: "glob-1",
      toolName: "glob",
      params: { pattern: "**/*.sql", path: "subject" },
    })).toMatchObject({
      title: "查找文件",
      summary: "**/*.sql",
    });

    expect(toolPresentation({
      type: "tool-call",
      callToolId: "grep-1",
      toolName: "grep",
      params: { pattern: "fund_positions", path: "src" },
    })).toMatchObject({
      title: "搜索文件内容",
      summary: "fund_positions",
    });
  });

  it("uses the canonical backend summary while a tool is running", () => {
    expect(toolPresentation({
      type: "tool-call",
      callToolId: "grep-running",
      toolName: "grep",
      params: { pattern: "fund_positions", path: "src", include: "*.py" },
      shortDesc: "fund_positions · src · *.py",
    })).toMatchObject({
      state: "running",
      summary: "fund_positions · src · *.py",
    });
  });

  it("marks a delegated task without a result as interrupted after execution stops", () => {
    const block = {
      type: "tool-call" as const,
      callToolId: "task-stopped",
      toolName: "task",
      params: { type: "explore", prompt: "探索基金持仓相关表" },
      childMessages: [{
        id: "progress-before-stop",
        role: "assistant" as const,
        content: "正在列出数据表",
        blocks: [{ type: "markdown" as const, content: "正在列出数据表" }],
      }],
    };

    expect(toolPresentation(block)).toMatchObject({
      state: "running",
      statusLabel: "执行中",
    });
    expect(toolPresentation(block, { isActive: false })).toMatchObject({
      title: "探索数据结构",
      state: "interrupted",
      statusLabel: "已中断",
      summary: "探索基金持仓相关表",
      metadata: ["1 条执行进展"],
    });
  });

  it("promotes a child sub-agent failure to the parent task state", () => {
    const presentation = toolPresentation({
      type: "tool-execution",
      callToolId: "task-2",
      toolName: "task",
      params: { type: "gen_report" },
      result: { session_id: "report-1" },
      childMessages: [{
        id: "complete-2",
        role: "assistant",
        content: "失败",
        blocks: [{
          type: "subagent-complete",
          subagent: "gen_report",
          toolCount: 2,
          duration: 2,
          errorText: "报表渲染失败",
        }],
      }],
    });

    expect(presentation.state).toBe("error");
    expect(presentation.statusLabel).toBe("执行失败");
    expect(presentation.summary).toBe("报表渲染失败");
  });

  it("uses a friendly error before the tool context in failed cards", () => {
    const presentation = toolPresentation({
      type: "tool-execution",
      callToolId: "sql-error",
      toolName: "execute_sql",
      params: { sql: "drop table fund_positions" },
      shortDesc: "drop table fund_positions",
      resultStatus: "error",
      errorText: "只读模式不允许执行写操作",
      result: null,
    });

    expect(presentation.summary).toBe("只读模式不允许执行写操作");
  });

  it("removes completion-only child messages from the expanded progress list", () => {
    const progress = {
      id: "progress",
      role: "assistant" as const,
      content: "正在执行",
      blocks: [{ type: "markdown" as const, content: "正在执行" }],
    };
    const completion = {
      id: "completion",
      role: "assistant" as const,
      content: "已完成",
      blocks: [{ type: "subagent-complete" as const, subagent: "explore", toolCount: 1 }],
    };

    expect(visibleToolChildMessages([progress, completion])).toEqual([progress]);
  });

  it("recognizes interaction tools independently of namespace", () => {
    expect(isInteractionToolName("tools.ask_user")).toBe(true);
    expect(isInteractionToolName("confirm_plan")).toBe(true);
    expect(isInteractionToolName("execute_sql")).toBe(false);
    expect(subagentDisplayName("gen_visual_report")).toBe("生成可视化报表");
  });
});
