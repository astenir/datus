import type { SubjectNode } from "@/types";

export type SubjectTreeNode = {
  key: string;
  path: string;
  name: string;
  type: SubjectNode["type"];
  subjectPath: string[];
  children: SubjectTreeNode[];
};

export type SubjectTreeData = {
  nodes: SubjectTreeNode[];
  expandedPaths: Set<string>;
  nodeByPath: Map<string, SubjectTreeNode>;
};

function subjectNodePath(node: SubjectNode) {
  const path = node.subject_path.length > 0 ? node.subject_path : [node.name];
  return path.join("/");
}

function toTreeNode(node: SubjectNode, expandedPaths: Set<string>, nodeByPath: Map<string, SubjectTreeNode>): SubjectTreeNode {
  const path = subjectNodePath(node);
  const children = (node.children ?? []).map((child) => toTreeNode(child, expandedPaths, nodeByPath));
  const treeNode: SubjectTreeNode = {
    key: `${node.type ?? "directory"}:${path}`,
    path,
    name: node.name || path,
    type: node.type ?? "directory",
    subjectPath: node.subject_path.length > 0 ? node.subject_path : [node.name].filter(Boolean),
    children,
  };

  if (children.length > 0) {
    expandedPaths.add(path);
  }

  nodeByPath.set(path, treeNode);
  return treeNode;
}

export function buildSubjectTree(subjects: readonly SubjectNode[]): SubjectTreeData {
  const expandedPaths = new Set<string>();
  const nodeByPath = new Map<string, SubjectTreeNode>();
  const nodes = subjects.map((node) => toTreeNode(node, expandedPaths, nodeByPath));

  return {
    nodes,
    expandedPaths,
    nodeByPath,
  };
}
