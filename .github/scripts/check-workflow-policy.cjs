const fs = require("node:fs");
const path = require("node:path");

const READ_ONLY_PERMISSIONS = { contents: "read", "pull-requests": "read" };
// title-check 需要给 PR 打 label 和评论，是白名单中唯一允许 write 的 workflow。
const TITLE_CHECK_PERMISSIONS = { contents: "read", "pull-requests": "write" };
const WORKFLOW_PERMISSION_POLICIES = {
  "agent-artifact-renderer.yml": READ_ONLY_PERMISSIONS,
  "python-quality.yml": READ_ONLY_PERMISSIONS,
  "title-check.yml": TITLE_CHECK_PERMISSIONS,
  "web-quality.yml": READ_ONLY_PERMISSIONS,
};

function unquote(value) {
  if (
    value.length >= 2 &&
    ((value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'")))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function validateWorkflow(name, source, allowedPermissions) {
  const violations = [];
  const lines = source.split(/\r?\n/);

  for (const [index, line] of lines.entries()) {
    const usesMatch = line.match(/^(?: {4}uses:| {8}uses:| {6}- uses:)\s*(.+?)\s*$/);
    if (usesMatch) {
      const reference = unquote(usesMatch[1].replace(/\s+#.*$/, "").trim());
      if (!reference.startsWith("./") && !/^[^@\s]+@[0-9a-f]{40}$/.test(reference)) {
        violations.push(`${name}:${index + 1}: remote action must use a full 40-character SHA: ${reference}`);
      }
    }

    if (/^ {4}permissions\s*:/.test(line)) {
      violations.push(`${name}:${index + 1}: job-level permissions are not allowed`);
    }
  }

  const permissionsIndex = lines.findIndex((line) => /^permissions\s*:/.test(line));
  if (permissionsIndex === -1) {
    violations.push(`${name}: missing top-level permissions`);
    return violations;
  }

  if (!/^permissions\s*:\s*(?:#.*)?$/.test(lines[permissionsIndex])) {
    violations.push(`${name}:${permissionsIndex + 1}: permissions must use an explicit mapping`);
    return violations;
  }

  const actualPermissions = {};
  for (let index = permissionsIndex + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line.trim() || /^\s*#/.test(line)) {
      continue;
    }
    if (!/^\s/.test(line)) {
      break;
    }

    const permissionMatch = line.match(/^ {2}([a-z-]+)\s*:\s*([a-z-]+)\s*(?:#.*)?$/);
    if (!permissionMatch) {
      violations.push(`${name}:${index + 1}: invalid top-level permission entry`);
      continue;
    }
    const [, permission, access] = permissionMatch;
    if (permission in actualPermissions) {
      violations.push(`${name}:${index + 1}: duplicate top-level permission: ${permission}`);
    }
    actualPermissions[permission] = access;
  }

  const sortedPermissions = (permissions) =>
    Object.fromEntries(Object.entries(permissions).sort(([left], [right]) => left.localeCompare(right)));
  if (
    JSON.stringify(sortedPermissions(actualPermissions)) !==
    JSON.stringify(sortedPermissions(allowedPermissions))
  ) {
    violations.push(
      `${name}: permissions must be ${JSON.stringify(allowedPermissions)}, got ${JSON.stringify(actualPermissions)}`,
    );
  }

  return violations;
}

function validateWorkflowFiles(workflows, policies = WORKFLOW_PERMISSION_POLICIES) {
  const violations = [];
  const workflowNames = Object.keys(workflows).sort();

  for (const name of workflowNames) {
    if (!policies[name]) {
      violations.push(`${name}: missing explicit permission policy`);
      continue;
    }
    violations.push(...validateWorkflow(name, workflows[name], policies[name]));
  }

  for (const name of Object.keys(policies).sort()) {
    if (!(name in workflows)) {
      violations.push(`${name}: permission policy references a missing workflow`);
    }
  }

  return violations;
}

function loadWorkflowFiles(workflowDirectory) {
  return Object.fromEntries(
    fs
      .readdirSync(workflowDirectory)
      .filter((name) => name.endsWith(".yml") || name.endsWith(".yaml"))
      .sort()
      .map((name) => [name, fs.readFileSync(path.join(workflowDirectory, name), "utf8")]),
  );
}

function validateWorkflowDirectory(workflowDirectory) {
  return validateWorkflowFiles(loadWorkflowFiles(workflowDirectory));
}

if (require.main === module) {
  const workflowDirectory = path.resolve(__dirname, "../workflows");
  const violations = validateWorkflowDirectory(workflowDirectory);
  if (violations.length) {
    console.error(violations.join("\n"));
    process.exitCode = 1;
  } else {
    console.log("Workflow action pins and permissions are valid");
  }
}

module.exports = {
  validateWorkflow,
  validateWorkflowDirectory,
  validateWorkflowFiles,
};
