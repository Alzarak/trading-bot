#!/usr/bin/env node

import { createInterface } from "readline";
import { execSync } from "child_process";
import { existsSync, mkdirSync, cpSync, writeFileSync, readFileSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { homedir } from "os";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PACKAGE_ROOT = join(__dirname, "..");
const PROJECT_DIR = process.cwd();

const rl = createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((resolve) => rl.question(q, resolve));

function log(msg) {
  console.log(`\x1b[36m[trading-bot]\x1b[0m ${msg}`);
}

function success(msg) {
  console.log(`\x1b[32m[trading-bot]\x1b[0m ${msg}`);
}

function warn(msg) {
  console.log(`\x1b[33m[trading-bot]\x1b[0m ${msg}`);
}

function copyDir(src, dest) {
  if (existsSync(src)) {
    mkdirSync(dest, { recursive: true });
    cpSync(src, dest, { recursive: true });
  }
}

async function main() {
  console.log("");
  console.log("\x1b[1m  Autonomous Trading Bot for Claude Code\x1b[0m");
  console.log("  Alpaca Markets API | Paper & Live Trading");
  console.log("");

  // Step 0: Install scope
  const scopeAnswer = await ask(
    "  Install commands/skills globally or for this project only?\n" +
    "  1. Global  — available in all projects (~/.claude/)\n" +
    "  2. Project — only this project (./.claude/)\n" +
    "  Choice (1/2): "
  );
  const installGlobal = scopeAnswer.trim() !== "2";
  const CLAUDE_DIR = installGlobal
    ? join(homedir(), ".claude")
    : join(PROJECT_DIR, ".claude");
  const TRADING_BOT_DIR = join(
    installGlobal ? join(homedir(), ".claude") : join(PROJECT_DIR, ".claude"),
    "trading-bot"
  );

  console.log("");
  log(installGlobal ? "Installing globally to ~/.claude/" : "Installing locally to ./.claude/");
  console.log("");

  // Step 1: Alpaca API credentials
  log("Alpaca API credentials (get free keys at https://app.alpaca.markets/)");
  console.log("");

  const apiKey = await ask("  Alpaca API Key: ");
  if (!apiKey.trim()) {
    warn("API key is required. Re-run the installer when you have your keys.");
    rl.close();
    process.exit(1);
  }

  const secretKey = await ask("  Alpaca Secret Key: ");
  if (!secretKey.trim()) {
    warn("Secret key is required. Re-run the installer when you have your keys.");
    rl.close();
    process.exit(1);
  }

  // Validate API credentials
  log("Verifying API credentials...");
  try {
    const resp = await fetch("https://paper-api.alpaca.markets/v2/account", {
      headers: {
        "APCA-API-KEY-ID": apiKey.trim(),
        "APCA-API-SECRET-KEY": secretKey.trim(),
      },
    });
    if (resp.ok) {
      const account = await resp.json();
      success(`Credentials valid — account ${account.account_number} (${account.status})`);
    } else if (resp.status === 401 || resp.status === 403) {
      warn("Invalid API credentials. Double-check your key and secret.");
      const cont = await ask("  Continue anyway? (y/N): ");
      if (cont.trim().toLowerCase() !== "y") {
        rl.close();
        process.exit(1);
      }
    } else {
      warn(`Alpaca API returned status ${resp.status}. Skipping validation.`);
    }
  } catch {
    warn("Could not reach Alpaca API. Skipping validation.");
  }

  console.log("");

  // Step 2: MCP server
  const mcpAnswer = await ask(
    "  Enable Alpaca MCP server? Gives Claude 44 real-time API tools. (Y/n): "
  );
  const useMcp = mcpAnswer.trim().toLowerCase() !== "n";

  if (useMcp) {
    // Check uvx
    try {
      execSync("command -v uvx", { stdio: "ignore" });
    } catch {
      console.log("");
      const installUv = await ask(
        "  uvx is required for MCP but not installed. Install uv now? (Y/n): "
      );
      if (installUv.trim().toLowerCase() !== "n") {
        log("Installing uv...");
        try {
          execSync("curl -LsSf https://astral.sh/uv/install.sh | sh", {
            stdio: "inherit",
          });
        } catch {
          warn("uv installation failed. MCP server will be skipped.");
        }
      }
    }
  }

  console.log("");
  log("Installing files...");
  console.log("");

  const prefix = installGlobal ? "~/.claude" : "./.claude";

  // Step 3: Copy files to CLAUDE_DIR
  // Commands
  copyDir(
    join(PACKAGE_ROOT, "commands", "trading-bot"),
    join(CLAUDE_DIR, "commands", "trading-bot")
  );
  success(`Commands  -> ${prefix}/commands/trading-bot/`);

  // Skills
  copyDir(
    join(PACKAGE_ROOT, "skills"),
    join(CLAUDE_DIR, "skills", "trading-bot")
  );
  success(`Skills    -> ${prefix}/skills/trading-bot/`);

  // For local installs, rewrite ~/.claude/ paths to ./.claude/ in all .md files
  if (!installGlobal) {
    const rewritePaths = (dir) => {
      if (!existsSync(dir)) return;
      const entries = readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = join(dir, entry.name);
        if (entry.isDirectory()) {
          rewritePaths(fullPath);
        } else if (entry.name.endsWith(".md") || entry.name.endsWith(".sh")) {
          let content = readFileSync(fullPath, "utf8");
          const updated = content.replace(/~\/\.claude\//g, "./.claude/")
                                 .replace(/\$HOME\/\.claude\//g, "./.claude/");
          if (updated !== content) writeFileSync(fullPath, updated);
        }
      }
    };
    rewritePaths(join(CLAUDE_DIR, "commands"));
    rewritePaths(join(CLAUDE_DIR, "skills"));
    rewritePaths(join(CLAUDE_DIR, "agents"));
    rewritePaths(TRADING_BOT_DIR);
  }

  // Agents — copy individual files with trading-bot- prefix
  const agentsSrc = join(PACKAGE_ROOT, "agents");
  const agentsDest = join(CLAUDE_DIR, "agents");
  mkdirSync(agentsDest, { recursive: true });
  for (const file of ["market-analyst.md", "risk-manager.md", "trade-executor.md"]) {
    if (existsSync(join(agentsSrc, file))) {
      cpSync(join(agentsSrc, file), join(agentsDest, `trading-bot-${file}`));
    }
  }
  success(`Agents    -> ${prefix}/agents/trading-bot-*.md`);

  // Scripts, hooks, references, requirements.txt -> trading-bot dir
  mkdirSync(TRADING_BOT_DIR, { recursive: true });
  copyDir(join(PACKAGE_ROOT, "scripts"), join(TRADING_BOT_DIR, "scripts"));
  copyDir(join(PACKAGE_ROOT, "hooks"), join(TRADING_BOT_DIR, "hooks"));
  copyDir(join(PACKAGE_ROOT, "references"), join(TRADING_BOT_DIR, "references"));
  if (existsSync(join(PACKAGE_ROOT, "requirements.txt"))) {
    cpSync(
      join(PACKAGE_ROOT, "requirements.txt"),
      join(TRADING_BOT_DIR, "requirements.txt")
    );
  }
  success(`Scripts   -> ${prefix}/trading-bot/scripts/`);
  success(`Hooks     -> ${prefix}/trading-bot/hooks/`);
  success(`References-> ${prefix}/trading-bot/references/`);

  // Step 4: Project-level files
  const botDataDir = join(PROJECT_DIR, "trading-bot");
  mkdirSync(botDataDir, { recursive: true });

  // Write .env
  const envContent = `# Alpaca API Credentials
ALPACA_API_KEY=${apiKey.trim()}
ALPACA_SECRET_KEY=${secretKey.trim()}

# Paper trading mode (true = simulated, false = real money)
# Change this in config.json via /trading-bot:initialize
ALPACA_PAPER=true
`;
  writeFileSync(join(botDataDir, ".env"), envContent);
  success(".env      -> ./trading-bot/.env");

  // Seed config.json if not exists
  if (!existsSync(join(botDataDir, "config.json")) || readFileSync(join(botDataDir, "config.json"), "utf8").trim() === "{}") {
    writeFileSync(join(botDataDir, "config.json"), "{}\n");
  }
  success("config    -> ./trading-bot/config.json");

  // Step 5: .mcp.json with API keys injected
  if (useMcp) {
    const mcpConfig = {
      mcpServers: {
        alpaca: {
          type: "stdio",
          command: "bash",
          args: [join(TRADING_BOT_DIR, "scripts", "start-mcp.sh")],
          env: {
            ALPACA_API_KEY: apiKey.trim(),
            ALPACA_SECRET_KEY: secretKey.trim(),
            ALPACA_PAPER_TRADE: "true",
          },
        },
      },
    };
    writeFileSync(
      join(PROJECT_DIR, ".mcp.json"),
      JSON.stringify(mcpConfig, null, 2) + "\n"
    );
    success("MCP       -> ./.mcp.json (keys injected)");
  }

  // Step 6: Project-level hooks in .claude/settings.local.json
  const settingsDir = join(PROJECT_DIR, ".claude");
  mkdirSync(settingsDir, { recursive: true });
  const settingsPath = join(settingsDir, "settings.local.json");

  const hooksConfig = {
    hooks: {
      SessionStart: [
        {
          hooks: [
            {
              type: "command",
              command: `bash "${join(TRADING_BOT_DIR, "hooks", "install-deps.sh")}"`,
              timeout: 120,
            },
          ],
        },
      ],
      PreToolUse: [
        {
          matcher: "Bash",
          hooks: [
            {
              type: "command",
              command: `bash "${join(TRADING_BOT_DIR, "hooks", "validate-order.sh")}"`,
              timeout: 10,
            },
          ],
        },
      ],
      Stop: [
        {
          hooks: [
            {
              type: "command",
              command: `bash "${join(TRADING_BOT_DIR, "hooks", "check-session.sh")}"`,
              timeout: 10,
            },
          ],
        },
      ],
    },
  };

  // Merge with existing settings if present
  let existingSettings = {};
  if (existsSync(settingsPath)) {
    try {
      existingSettings = JSON.parse(readFileSync(settingsPath, "utf8"));
    } catch {
      // corrupted file, overwrite
    }
  }
  existingSettings.hooks = hooksConfig.hooks;
  writeFileSync(settingsPath, JSON.stringify(existingSettings, null, 2) + "\n");
  success("Hooks     -> ./.claude/settings.local.json");

  // Step 7: .gitignore entries
  const gitignorePath = join(PROJECT_DIR, ".gitignore");
  const gitignoreEntries = [
    "trading-bot/.env",
    "trading-bot/venv/",
    "trading-bot/*.db",
    "trading-bot/audit/",
    "trading-bot/circuit_breaker.flag",
    ".mcp.json",
  ];
  let gitignore = existsSync(gitignorePath)
    ? readFileSync(gitignorePath, "utf8")
    : "";
  const newEntries = gitignoreEntries.filter((e) => !gitignore.includes(e));
  if (newEntries.length > 0) {
    gitignore += "\n# Trading bot\n" + newEntries.join("\n") + "\n";
    writeFileSync(gitignorePath, gitignore);
    success(".gitignore updated");
  }

  // Step 8: Install Python dependencies
  console.log("");
  log("Installing Python dependencies...");
  try {
    const venvDir = join(botDataDir, "venv");
    execSync(`uv venv "${venvDir}" --python python3 --quiet 2>/dev/null || uv venv "${venvDir}" --quiet`, {
      stdio: "inherit",
      shell: true,
    });
    execSync(
      `uv pip install -r "${join(TRADING_BOT_DIR, "requirements.txt")}" --python "${join(venvDir, "bin", "python")}" --quiet`,
      { stdio: "inherit", shell: true }
    );
    success("Python dependencies installed");
  } catch {
    warn("Python dependency install failed. The SessionStart hook will retry automatically.");
  }

  // Done
  console.log("");
  console.log("\x1b[1m  Installation complete!\x1b[0m");
  console.log("");
  console.log("  To configure your trading preferences, run:");
  console.log("");
  console.log("    \x1b[1mclaude /trading-bot:initialize\x1b[0m");
  console.log("");

  rl.close();
}

main().catch((err) => {
  console.error(err);
  rl.close();
  process.exit(1);
});
