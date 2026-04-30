# Install for Codex

From the Superloop source checkout:

```bash
./scripts/install.sh --host codex
```

The installer syncs the source tree into:

```text
$CODEX_HOME/skills/superloop
```

If `CODEX_HOME` is unset, it defaults to `~/.codex`.

Check the install:

```bash
./scripts/superloop_cli.sh doctor --host codex --source "$(pwd)"
./scripts/install.sh --host codex --source "$(pwd)" --check
```

Use the installed harness:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export SUPERLOOP_HARNESS="$CODEX_HOME/skills/superloop/scripts/superloop_cli.sh"
"$SUPERLOOP_HARNESS" resume --workspace /path/to/repo
```

Codex state remains backwards compatible at:

```text
$CODEX_HOME/state/superloop/<workspace-key>.json
```
