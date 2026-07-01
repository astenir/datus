import { describe, expect, it } from "vitest";

import { buildSubjectTree } from "./subject-tree";
import type { SubjectNode } from "@/types";

describe("buildSubjectTree", () => {
  it("builds file-tree nodes with expanded folders and path lookup", () => {
    const subjects: SubjectNode[] = [
      {
        name: "基金",
        type: "directory",
        subject_path: ["基金"],
        children: [
          {
            name: "规模",
            type: "metric",
            subject_path: ["基金", "规模"],
            children: [],
          },
          {
            name: "净值 SQL",
            type: "reference_sql",
            subject_path: ["基金", "净值 SQL"],
            children: [],
          },
        ],
      },
    ];

    const tree = buildSubjectTree(subjects);

    expect(tree.nodes).toHaveLength(1);
    expect(tree.nodes[0]).toMatchObject({
      key: "directory:基金",
      path: "基金",
      name: "基金",
      type: "directory",
      subjectPath: ["基金"],
    });
    expect(tree.nodes[0]?.children).toHaveLength(2);
    expect(tree.nodes[0]?.children[0]).toMatchObject({
      key: "metric:基金/规模",
      path: "基金/规模",
      type: "metric",
      subjectPath: ["基金", "规模"],
    });
    expect(tree.expandedPaths.has("基金")).toBe(true);
    expect(tree.nodeByPath.get("基金/净值 SQL")?.type).toBe("reference_sql");
  });

  it("falls back to the node name when subject_path is empty", () => {
    const tree = buildSubjectTree([
      {
        name: "未归类",
        type: "directory",
        subject_path: [],
        children: [],
      },
    ]);

    expect(tree.nodes[0]).toMatchObject({
      path: "未归类",
      subjectPath: ["未归类"],
    });
    expect(tree.nodeByPath.get("未归类")?.name).toBe("未归类");
  });
});
