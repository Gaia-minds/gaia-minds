#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const launcherPath = path.join(repoRoot, "tools", "gaia-assistant.py");

if (!fs.existsSync(launcherPath)) {
  console.error(`Gaia launcher not found at: ${launcherPath}`);
  process.exit(1);
}

const passthroughArgs = process.argv.slice(2);
const candidates = [];
if (process.env.GAIA_PYTHON_BIN && process.env.GAIA_PYTHON_BIN.trim()) {
  candidates.push({ cmd: process.env.GAIA_PYTHON_BIN.trim(), prefixArgs: [] });
}
candidates.push(
  { cmd: "python3", prefixArgs: [] },
  { cmd: "python", prefixArgs: [] },
  { cmd: "py", prefixArgs: ["-3"] }
);

let lastError = null;
for (const candidate of candidates) {
  const result = spawnSync(
    candidate.cmd,
    [...candidate.prefixArgs, launcherPath, ...passthroughArgs],
    {
      cwd: repoRoot,
      env: { ...process.env, GAIA_ASSISTANT_CLI_HINT: "gaia" },
      stdio: "inherit",
    }
  );

  if (result.error) {
    if (result.error.code === "ENOENT") {
      continue;
    }
    lastError = result.error;
    break;
  }

  if (typeof result.status === "number") {
    process.exit(result.status);
  }

  if (result.signal) {
    process.kill(process.pid, result.signal);
    process.exit(1);
  }

  process.exit(1);
}

if (lastError) {
  console.error(`Failed to launch Gaia assistant: ${lastError.message}`);
  process.exit(1);
}

console.error(
  "Python 3 is required. Install Python or set GAIA_PYTHON_BIN to a valid interpreter."
);
process.exit(1);
