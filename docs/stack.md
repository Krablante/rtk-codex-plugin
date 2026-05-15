# Stack Fit

`rtk-codex-plugin` is useful as a standalone Codex-compatible plugin, but it is
also designed to sit in a larger local-agent stack.

## Layers

| Layer | Responsibility |
| --- | --- |
| Codex-compatible runtime | runs the model loop, shell tool, config, and plugin hooks |
| RTK Codex Plugin | keeps shell exploration compact and guards risky long-line output |
| gateway or remote-worker UI | optionally installs the plugin on worker machines |

The plugin does not own sessions, chat delivery, host registries, or project
metadata. It only handles shell command rewrite and bounded output at the hook
layer.

## Upcoming Stack

This project is the first public piece of a planned stack:

- Codez: a Codex-compatible runtime layer
- RTK Codex Plugin: shell token-safety and bounded output
- Teledex: a Telegram-facing gateway

The plugin does not require Codez or Teledex. Public links for those projects
will be added only after they have clean public releases.
