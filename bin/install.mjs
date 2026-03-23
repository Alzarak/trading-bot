#!/usr/bin/env node

import { createInterface } from "readline";
import { execSync } from "child_process";
import { existsSync, mkdirSync, cpSync, writeFileSync, readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { homedir } from "os";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PACKAGE_ROOT = join(__dirname, "..");
const CLAUDE_DIR = join(homedir(), ".claude");
const TRADING_BOT_DIR = join(CLAUDE_DIR, "trading-bot");
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

  // Step 3: Copy files to ~/.claude/
  // Commands
  copyDir(
    join(PACKAGE_ROOT, "commands", "trading-bot"),
    join(CLAUDE_DIR, "commands", "trading-bot")
  );
  success("Commands  -> ~/.claude/commands/trading-bot/");

  // Skills
  copyDir(
    join(PACKAGE_ROOT, "skills"),
    join(CLAUDE_DIR, "skills", "trading-bot")
  );
  success("Skills    -> ~/.claude/skills/trading-bot/");

  // Agents — copy individual files with trading-bot- prefix
  const agentsSrc = join(PACKAGE_ROOT, "agents");
  const agentsDest = join(CLAUDE_DIR, "agents");
  mkdirSync(agentsDest, { recursive: true });
  for (const file of ["market-analyst.md", "risk-manager.md", "trade-executor.md"]) {
    if (existsSync(join(agentsSrc, file))) {
      cpSync(join(agentsSrc, file), join(agentsDest, `trading-bot-${file}`));
    }
  }
  success("Agents    -> ~/.claude/agents/trading-bot-*.md");

  // Scripts, hooks, references, requirements.txt -> ~/.claude/trading-bot/
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
  success("Scripts   -> ~/.claude/trading-bot/scripts/");
  success("Hooks     -> ~/.claude/trading-bot/hooks/");
  success("References-> ~/.claude/trading-bot/references/");

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
  console.log("  Next steps:");
  console.log("  1. Start Claude Code in this project directory");
  console.log("  2. Run \x1b[1m/trading-bot:initialize\x1b[0m to configure trading preferences");
  console.log("  3. Run \x1b[1m/trading-bot:build\x1b[0m to generate trading scripts");
  console.log("  4. Run \x1b[1m/trading-bot:run\x1b[0m to start autonomous trading");
  console.log("");
  if (useMcp) {
    console.log("  MCP server is configured. Run \x1b[1m/mcp\x1b[0m in Claude Code to verify.");
  }
  console.log("");

  rl.close();
}

main().catch((err) => {
  console.error(err);
  rl.close();
  process.exit(1);
});
