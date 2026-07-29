import { describe, expect, it } from "vitest";

import {
  groupTodoQueueItems,
  todoQueueFromToolResult,
} from "./todo-queue";

describe("todoQueueFromToolResult", () => {
  it("normalizes the unwrapped todo_write payload used by chat blocks", () => {
    expect(todoQueueFromToolResult("tools.todo_write", {
      message: "Appended 2 items",
      items: [
        { id: 1, title: "盘点数据库结构", status: "pending" },
        { id: 2, title: "分析基金持仓", status: "completed" },
      ],
    })).toEqual({
      toolName: "todo_write",
      variant: "snapshot",
      title: "执行队列已更新",
      actionLabel: "已写入",
      total: 2,
      completed: 1,
      items: [
        { id: "1", title: "盘点数据库结构", status: "pending" },
        { id: "2", title: "分析基金持仓", status: "completed" },
      ],
    });
  });

  it("preserves updated_item when todo_update also contains a message", () => {
    expect(todoQueueFromToolResult("todo_update", {
      message: "Successfully updated todo item to 'in_progress' status",
      updated_item: {
        id: 4,
        title: "汇总分析结论",
        status: "in_progress",
        content: "整理关键发现并说明风险。",
      },
    })).toEqual({
      toolName: "todo_update",
      variant: "item",
      title: "任务状态已更新",
      actionLabel: "进行中",
      total: 1,
      completed: 0,
      items: [{
        id: "4",
        title: "汇总分析结论",
        status: "in_progress",
        content: "整理关键发现并说明风险。",
      }],
    });
  });

  it("normalizes todo_read details and still accepts a transport envelope", () => {
    expect(todoQueueFromToolResult("todo_read", {
      success: 1,
      result: {
        id: 5,
        title: "检查数据质量",
        status: "failed",
        content: "确认缺失值和异常日期。",
      },
    })).toMatchObject({
      toolName: "todo_read",
      variant: "item",
      actionLabel: "执行失败",
      items: [{ id: "5", status: "failed" }],
    });
  });

  it("keeps an empty todo_list as a valid queue state", () => {
    expect(todoQueueFromToolResult("todo_list", {
      items: [],
      total: 0,
      completed: 0,
    })).toMatchObject({
      title: "执行队列",
      variant: "snapshot",
      total: 0,
      completed: 0,
      items: [],
    });
  });

  it("falls back for unrelated tools and malformed todo payloads", () => {
    expect(todoQueueFromToolResult("read_query", { items: [] })).toBeNull();
    expect(todoQueueFromToolResult("todo_update", { updated_item: {} })).toBeNull();
    expect(todoQueueFromToolResult("todo_write", { message: "missing items" })).toBeNull();
  });
});

describe("groupTodoQueueItems", () => {
  it("puts active work first and terminal states last", () => {
    expect(groupTodoQueueItems([
      { id: "1", title: "待执行", status: "pending" },
      { id: "2", title: "已完成", status: "completed" },
      { id: "3", title: "进行中", status: "in_progress" },
      { id: "4", title: "未知", status: "unknown" },
    ]).map((group) => group.status)).toEqual([
      "in_progress",
      "pending",
      "completed",
      "unknown",
    ]);
  });
});
