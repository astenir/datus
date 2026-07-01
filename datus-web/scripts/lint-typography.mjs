import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const SCAN_TARGETS = [
  "src/features",
  "src/App.vue",
];
const ALLOWED_TYPE_CLASSES = new Set([
  "text-xs",
  "text-sm",
  "text-base",
  "text-lg",
  "text-3xl",
  "text-4xl",
]);
const TYPOGRAPHY_CLASS_RE = /(?:^|[\s"'`])((?:[!a-zA-Z0-9_/-]+:)*!?text-(?:xs|sm|base|lg|xl|[2-9]xl|\[[^\]\s"'`]+]))/g;
const SCANNED_EXTENSIONS = new Set([".vue", ".ts", ".tsx", ".js", ".jsx"]);

async function collectFiles(target) {
  const entries = await readdir(target, { withFileTypes: true }).catch((error) => {
    if (error.code === "ENOTDIR") return null;
    throw error;
  });

  if (!entries) return [target];

  const files = [];
  for (const entry of entries) {
    const entryPath = path.join(target, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectFiles(entryPath));
    } else if (SCANNED_EXTENSIONS.has(path.extname(entry.name))) {
      files.push(entryPath);
    }
  }
  return files;
}

function normalizedTypeClass(token) {
  const lastSegment = token.split(":").at(-1) ?? token;
  return lastSegment.replace(/^!/, "");
}

function lineNumberAt(source, index) {
  return source.slice(0, index).split("\n").length;
}

function scanSource(filePath, source) {
  const errors = [];
  const warnings = [];

  for (const match of source.matchAll(TYPOGRAPHY_CLASS_RE)) {
    const token = match[1];
    const typeClass = normalizedTypeClass(token);
    const line = lineNumberAt(source, match.index ?? 0);
    const finding = { filePath, line, token };

    if (!ALLOWED_TYPE_CLASSES.has(typeClass)) {
      errors.push(finding);
    } else if (typeClass === "text-base") {
      warnings.push(finding);
    }
  }

  return { errors, warnings };
}

const files = (await Promise.all(SCAN_TARGETS.map(collectFiles))).flat().sort();
const results = await Promise.all(files.map(async (filePath) => {
  const source = await readFile(filePath, "utf8");
  return scanSource(filePath, source);
}));

const errors = results.flatMap((result) => result.errors);
const warnings = results.flatMap((result) => result.warnings);

if (warnings.length > 0) {
  console.log("Typography review: text-base exceptions found. Confirm each one matches AGENTS.md.");
  for (const warning of warnings) {
    console.log(`  ${warning.filePath}:${warning.line} ${warning.token}`);
  }
}

if (errors.length > 0) {
  console.error("Typography lint failed: unsupported font-size utilities in project-owned UI.");
  for (const error of errors) {
    console.error(`  ${error.filePath}:${error.line} ${error.token}`);
  }
  console.error("Allowed size utilities: text-xs, text-sm, text-base, text-lg, text-3xl, text-4xl.");
  process.exit(1);
}

console.log(`Typography lint passed: scanned ${files.length} files.`);
