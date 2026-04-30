# Status Cards

Status cards are the operator-facing summary for plan, build, test, deploy, and
external-service transitions.

Use them when a round changes deployment state, hits a CI or service failure, or
needs a PR/Issue comment that explains what happened without requiring the user
to open the CI provider.

```bash
"$SUPERLOOP_HARNESS" status-card \
  --stage deploy \
  --platform cloudflare \
  --migration-from vercel \
  --migration-to cloudflare \
  --require-env CLOUDFLARE_API_TOKEN \
  --github-repo owner/repo \
  --github-issue 4
```

The command renders stable JSON by default. Use `--format markdown` for direct
terminal output, or pass `--github-issue` / `--github-pr` to post the markdown
through `gh`.

CI defaults:

- `GITHUB_REPOSITORY`: default GitHub repo target
- `SUPERLOOP_GITHUB_ISSUE`: default issue comment target
- `SUPERLOOP_GITHUB_PR`: default PR comment target

## Classification Codes

- `ready`
- `config-missing-required`
- `config-missing-optional`
- `permissions`
- `workflow-syntax`
- `external-service`
- `environment`
- `contract-boundary`
- `code-regression`
- `unknown`

`status-card` can infer the code from `--require-env`, `--optional-env`, or
`--failure-text`. Prefer explicit `--classification` when CI already knows the
failure class.

## Locale

Use `--locale en` or `--locale zh`. JSON keys stay stable in English; the
operator-facing markdown labels and default action copy use the selected locale.
