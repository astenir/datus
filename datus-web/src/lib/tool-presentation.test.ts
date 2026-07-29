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
  });

  it("builds a completed SQL presentation with summary and duration", () => {
    expect(toolPresentation({
      type: "tool-execution",
      callToolId: "sql-1",
      toolName: "db_tools.execute_sql",
      params: { sql: "select * from fund_positions" },
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
