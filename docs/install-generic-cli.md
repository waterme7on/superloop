# Install for Generic CLI

Superloop can run directly from the source checkout:

```bash
./scripts/superloop_cli.sh resume --workspace /path/to/repo
```

To install a generic copy under `~/.superloop/superloop`:

```bash
./scripts/install.sh --host generic
```

Check the install:

```bash
./scripts/superloop_cli.sh doctor --host generic --source "$(pwd)"
./scripts/install.sh --host generic --source "$(pwd)" --check
```

Use the installed harness:

```bash
export SUPERLOOP_HOME="${SUPERLOOP_HOME:-$HOME/.superloop}"
export SUPERLOOP_HARNESS="$SUPERLOOP_HOME/superloop/scripts/superloop_cli.sh"
"$SUPERLOOP_HARNESS" resume --workspace /path/to/repo
```

Generic CLI state defaults to:

```text
$SUPERLOOP_HOME/state/<workspace-key>.json
```
