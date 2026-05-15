# Compatibility

The plugin is intended for Codex-compatible runtimes that support:

- plugin manifests via `.codex-plugin/plugin.json`;
- hook declarations via `hooks/hooks.json`;
- `PreToolUse` hooks for shell/Bash tool calls;
- `${PLUGIN_ROOT}` expansion in hook commands.

Known integration layers:

- Codez-compatible runtimes can execute the hook directly.
- Telegram or remote-worker gateways can sync the plugin to worker machines,
  but no gateway is required for local usage.

`rtk` command rewrite requires the `rtk` binary in `PATH`. Output guarding does
not require `rtk`.

## Pass-Through Policy

The hook avoids rewriting commands where exact output is expected:

- tests and package-manager check commands
- machine-readable modes such as JSON, porcelain, counts, and file lists
- interactive commands
- binary-ish output commands
- shell-control forms that are not recognized risky inspection pipelines

Recognized JSONL, log, and prompt-input inspection shapes are guarded before
execution so a single long line cannot dominate the context window.
