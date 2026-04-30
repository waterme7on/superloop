# Install for Claude Code

From the Superloop source checkout:

```bash
./scripts/install.sh --host claude-code
```

The installer syncs the source tree into:

```text
$CLAUDE_HOME/skills/superloop
```

If `CLAUDE_HOME` is unset, it defaults to `~/.claude`.

Check the install:

```bash
./scripts/superloop_cli.sh doctor --host claude-code --source "$(pwd)"
./scripts/install.sh --host claude-code --source "$(pwd)" --check
```

Use the installed harness:

```bash
export CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
export SUPERLOOP_HARNESS="$CLAUDE_HOME/skills/superloop/scripts/superloop_cli.sh"
"$SUPERLOOP_HARNESS" resume --workspace /path/to/repo
```

Claude Code state is host-specific:

```text
$CLAUDE_HOME/state/superloop/<workspace-key>.json
```

The same `SKILL.md`, `docs/`, `references/`, `src/`, and `scripts/` are used.
The Claude adapter does not depend on Codex-specific `agents/openai.yaml`
metadata.
