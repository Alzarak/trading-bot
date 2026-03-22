---
phase: 06-distribution-and-observability
plan: 02
subsystem: plugin-manifest
tags: [distribution, marketplace, plugin, versioning]
dependency_graph:
  requires: []
  provides: [plugin-manifest-v1, marketplace-listing]
  affects: [distribution]
tech_stack:
  added: []
  patterns: [tdd, json-validation, plugin-manifest]
key_files:
  created:
    - .claude-plugin/marketplace.json
    - tests/test_plugin_manifest.py
  modified:
    - .claude-plugin/plugin.json
    - commands/initialize.md
decisions:
  - Plugin manifest bumped to 1.0.0 with full marketplace metadata (commands, dependencies, hooks, agents, skills)
  - marketplace.json uses placeholder GitHub URL — user must update before publishing
  - Installation comment added to initialize.md as HTML comment above frontmatter (non-intrusive)
metrics:
  duration: 8m
  completed: "2026-03-22"
  tasks_completed: 2
  files_modified: 4
requirements_satisfied: [DIST-01, DIST-02, DIST-03]
---

# Phase 06 Plan 02: Plugin Manifest and Marketplace Publishing Summary

Plugin.json bumped to v1.0.0 with full marketplace metadata; marketplace.json created for GitHub-hosted distribution; 18 manifest validation tests confirm both files are well-formed and consistent.

## What Was Built

### .claude-plugin/plugin.json (updated)
Bumped from v0.1.0 to v1.0.0. Added fields required for marketplace distribution:
- `commands`: ["initialize", "build", "run"]
- `dependencies`: {"python": ">=3.12"}
- `hooks`: ["SessionStart"]
- `agents`: ["market-analyst", "risk-manager", "trade-executor"]
- `skills`: ["trading-rules"]
- Expanded `description` to describe the plugin's three commands

### .claude-plugin/marketplace.json (new)
Marketplace listing file for GitHub-hosted plugin distribution. Contains:
- `source: "github"` — required field for `claude plugin install`
- `repository` pointing to placeholder GitHub URL (user must update before publishing)
- Matching name/version/description from plugin.json
- `min_claude_code_version: "1.0.0"`

### tests/test_plugin_manifest.py (new)
18 tests covering:
- Both files parse as valid JSON
- plugin.json: version is semver, version is 1.0.0, name, description, author, license, keywords, commands, dependencies
- marketplace.json: source is "github", name/version match plugin.json, repository is GitHub URL, description present

### commands/initialize.md (minor)
Added HTML comment at line 1:
`<!-- Plugin: trading-bot v1.0.0 | Install: claude plugin install <github-url> -->`

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing manifest tests | 1646556 | tests/test_plugin_manifest.py |
| 1 (GREEN) | Update plugin.json, create marketplace.json | 0c3be1f | .claude-plugin/plugin.json, .claude-plugin/marketplace.json |
| 2 | Verify plugin structure, add installation note | 9625b96 | commands/initialize.md |

## Verification Results

- `python -m pytest tests/test_plugin_manifest.py -v` — 18/18 passed
- `python -m pytest tests/ -v` (excluding parallel-plan files) — 266/266 passed
- All declared plugin components verified on disk: commands (initialize, build, run), hooks (hooks.json), agents (market-analyst, risk-manager, trade-executor), skills (trading-rules/)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- `marketplace.json` `repository` field uses placeholder URL `https://github.com/trading-bot/trading-bot-plugin`. This is intentional — the user must update it to their actual GitHub repository URL before publishing to the marketplace. Documented in test comments.

## Self-Check: PASSED

Files:
- FOUND: /home/parz/projects/trading-bot/.claude-plugin/plugin.json
- FOUND: /home/parz/projects/trading-bot/.claude-plugin/marketplace.json
- FOUND: /home/parz/projects/trading-bot/tests/test_plugin_manifest.py
- FOUND: /home/parz/projects/trading-bot/commands/initialize.md

Commits:
- FOUND: 1646556 (test: add failing tests)
- FOUND: 0c3be1f (feat: update plugin.json and create marketplace.json)
- FOUND: 9625b96 (chore: verify structure and add installation note)
