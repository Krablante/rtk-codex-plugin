# Compatibility

The plugin is intended for Codex-compatible runtimes that support:

- plugin manifests via `.codex-plugin/plugin.json`;
- hook declarations via `hooks/hooks.json`;
- `PreToolUse` hooks for shell/Bash tool calls;
- `${PLUGIN_ROOT}` expansion in hook commands.

Known integration layers:

- [Codez](https://github.com/Krablante/codez) is the recommended public runtime
  layer when you want plugin hooks plus token-aware context behavior.
- Other Codez/Codex-compatible runtimes can execute the hook directly if they
  support plugin-loaded `PreToolUse` shell hooks.
- Telegram or remote-worker gateways can sync the plugin to worker machines,
  but no gateway is required for local usage. Teledex is the planned Telegram
  gateway layer and is intentionally not linked until it has a public release.

`rtk` command rewrite requires the `rtk` binary in `PATH`. Output guarding does
not require `rtk`.

## Pass-Through Policy

The hook avoids rewriting commands where exact output is expected:

- tests and package-manager check commands
- build commands
- direct `rg`/`grep` searches, including regex-like patterns
- Docker commands
- machine-readable modes such as JSON, porcelain, counts, and file lists
- interactive commands
- binary-ish output commands
- Pitlane-owned code-navigation reads and recursive listings, so a later
  Pitlane hook can compact source reads instead of RTK rewriting them first
- shell-control forms that are not recognized risky inspection pipelines

Recognized JSONL, log, and prompt-input inspection shapes are guarded before
execution so a single long line cannot dominate the context window.

## Pitlane Coexistence

If you use a Pitlane Codex hook in the same runtime, configure RTK before
Pitlane. RTK keeps its exact-output and risky-output guard behavior, then passes
safe source reads such as `cat src/app.py`, `head -n 20 src/app.py`,
`sed -n '1,20p' src/app.py`, `ls -R src`, and `tree src` through unchanged so
the later Pitlane hook can decide whether to rewrite them.
