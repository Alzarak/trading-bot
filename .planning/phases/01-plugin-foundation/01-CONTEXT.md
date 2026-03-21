# Phase 1: Plugin Foundation - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the complete Claude Code plugin scaffold and an interactive `/initialize` setup wizard. Users can install the plugin, run `/initialize`, answer adaptive questions based on their experience level, and receive a valid `config.json` that all downstream commands consume. The Alpaca MCP server is wired in and Python dependencies install automatically on session start.

</domain>

<decisions>
## Implementation Decisions

### Wizard Interaction Flow
- Wizard uses Claude Code's native AskUserQuestion prompts — no external UI dependencies
- 5-6 grouped steps: experience level → risk tolerance → budget/mode → strategies → market hours → watchlist
- Smart defaults pre-filled based on experience level — beginners get conservative defaults, experts get neutral starting points
- Invalid input handled by re-prompting with explanation of valid options

### Configuration Schema
- Config stored as JSON (`config.json`) in `${CLAUDE_PLUGIN_DATA}` directory
- Strategies stored as array of strategy objects with per-strategy params: `[{"name": "momentum", "weight": 0.5, "params": {...}}]`
- API keys stored in `.env` file in plugin data dir, loaded by pydantic-settings — never stored in config.json
- Config file format matches REQUIREMENTS STATE-03

### Beginner vs Expert Adaptation
- First question asks directly: "What's your trading experience?" with 3 options (beginner/intermediate/expert)
- Beginners: fewer questions, conservative defaults auto-applied, explanatory descriptions on each option
- Experts: all parameters exposed, no defaults pre-selected, technical terminology used
- Default trading mode for beginners is paper trading only — live requires explicit opt-in

### Plugin Bootstrap & Dependencies
- SessionStart hook installs deps via `uv pip install` into `${CLAUDE_PLUGIN_DATA}/venv`
- Dep reinstall triggered by diffing `requirements.txt` hash against cached hash in plugin data dir
- Static `.mcp.json` referencing `uvx alpaca-mcp-server` with env var placeholders for API keys

### Claude's Discretion
No items deferred to Claude's discretion — all areas resolved.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing codebase — greenfield plugin project
- CLAUDE.md contains full technology stack reference and plugin directory structure conventions

### Established Patterns
- Plugin structure: commands/, agents/, skills/, hooks/, references/ directories
- YAML frontmatter for agent and skill definitions
- hooks.json for hook definitions
- plugin.json for manifest
- .mcp.json for MCP server configuration

### Integration Points
- `${CLAUDE_PLUGIN_DATA}` for persistent plugin storage (config, venv, logs)
- Alpaca MCP server via .mcp.json
- Requirements.txt for Python dependency management
- .env file for API key management

</code_context>

<specifics>
## Specific Ideas

- 3 reference files: `trading-strategies.md`, `risk-rules.md`, `alpaca-api-patterns.md`
- Trading-rules skill provides domain context to all agents automatically
- Plugin manifest follows semver for marketplace cache invalidation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
