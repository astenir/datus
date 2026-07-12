import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const host = "127.0.0.1";
const port = "4187";
const baseUrl = `http://${host}:${port}`;
const viteCli = fileURLToPath(new URL("../node_modules/vite/bin/vite.js", import.meta.url));
const playwrightCli = fileURLToPath(new URL("../node_modules/playwright/cli.js", import.meta.url));

function waitForVite(server) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Timed out while starting the browser test server")), 30_000);
    let output = "";

    function finish(callback, value) {
      clearTimeout(timeout);
      server.stdout.off("data", handleOutput);
      server.stderr.off("data", handleOutput);
      server.off("exit", handleExit);
      callback(value);
    }

    function handleOutput(chunk) {
      output += chunk.toString();
      if (output.includes("Local:")) finish(resolve);
    }

    function handleExit(code) {
      finish(reject, new Error(`Browser test server exited before startup with code ${code ?? "unknown"}\n${output}`));
    }

    server.stdout.on("data", handleOutput);
    server.stderr.on("data", handleOutput);
    server.on("exit", handleExit);
  });
}

function waitForExit(child) {
  return new Promise(resolve => child.once("exit", code => resolve(code ?? 1)));
}

const server = spawn(process.execPath, [viteCli, "--host", host, "--port", port, "--strictPort"], {
  stdio: ["ignore", "pipe", "pipe"],
});

try {
  await waitForVite(server);
  const tests = spawn(process.execPath, [playwrightCli, "test"], {
    env: { ...process.env, DATUS_BROWSER_TEST_URL: baseUrl },
    stdio: "inherit",
  });
  process.exitCode = await waitForExit(tests);
} finally {
  server.kill("SIGTERM");
}
