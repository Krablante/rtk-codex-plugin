# Stack Fit

`rtk-codex-plugin` is useful as a standalone Codex-compatible plugin, but it is
also designed to sit in a larger local-agent stack.

## Layers

| Layer | Responsibility |
| --- | --- |
| [Codez](https://github.com/Krablante/codez) or another compatible runtime | runs the model loop, shell tool, config, and plugin hooks |
| RTK Codex Plugin | keeps shell exploration compact and guards risky long-line output |
| Pitlane Codex Plugin | optionally compacts safe source reads, symbol lookups, and repo listings after RTK has passed them through |
| Telegram gateway / Teledex | coming next; will optionally install or sync the plugin on worker machines |

The plugin does not own sessions, chat delivery, host registries, or project
metadata. It only handles shell command rewrite and bounded output at the hook
layer.

## Upcoming Stack

This project is the first public piece of a planned stack:

- [Codez](https://github.com/Krablante/codez): core Codex-compatible runtime
  with token-aware context behavior, App Server v2, and plugin hook
  compatibility
- RTK Codex Plugin: optional shell token-safety and bounded output
- Pitlane Codex Plugin: optional code-navigation compaction hook, ordered after
  RTK when both are installed
- Teledex: a Telegram-facing gateway, coming next

The plugin does not require Codez or Teledex. Codez is linked now because it has
a clean public release; Teledex is intentionally not linked until its public
repo is ready.
