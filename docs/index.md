# Superloop Docs

Start here when editing or operating Superloop.

## Operator Path

1. Install the host adapter:
   - [Codex](install-codex.md)
   - [Claude Code](install-claude-code.md)
   - [Generic CLI](install-generic-cli.md)
2. Read the core model: [core.md](core.md)
3. Use the CLI reference: [reference/cli.md](reference/cli.md)
4. Check host paths and metadata: [host-adapters.md](host-adapters.md)

## Repo Map

- `SKILL.md`: short operational contract loaded by agent hosts
- `src/superloop/`: importable harness implementation
- `scripts/superloop_harness.py`: compatibility wrapper for older commands
- `scripts/superloop_cli.sh`: stable shell entrypoint
- `scripts/install.sh`: host-aware install/sync wrapper
- `agents/openai.yaml`: Codex/OpenAI host metadata
- `docs/`: maintained docs entrypoint, install notes, and CLI reference
- `references/`: deeper operating-model notes that are linked from `SKILL.md`
- `tests/`: focused harness regression tests

## Maintainer Rules

- Keep host-specific behavior in host adapter helpers or docs, not in the loop contract.
- Keep `SKILL.md` operational; move long command detail to [reference/cli.md](reference/cli.md).
- Preserve `scripts/superloop_harness.py` as a backwards-compatible wrapper.
- When adding a failure path, expose the classification in JSON and markdown status cards.
