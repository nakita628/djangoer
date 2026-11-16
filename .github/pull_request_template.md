<!--
Title: `type(scope): summary` — imperative mood, no trailing period. Write it for the
person reading the release notes, not for the diff.

  type   feat | fix | perf | refactor | docs | test | build | ci | chore
  scope  schema | data | sql | orm | docs | server | cli | studio | examples | ci

  fix(orm): complete the lookups of a field reached through a reverse relation
  feat(cli): open the browser with --open
-->

## Why

<!-- The bug, the missing capability or the request behind this change. Link the issue: `Closes #123`. -->

## What

<!-- What changed, as someone using Studio sees it. One to three sentences. -->

## Where

<!-- Scope: the server (schema, rows, SQL analysis, ORM playground, docs), the CLI, the Studio client, the example. Name what is deliberately left out. -->

## Who

<!-- Who notices: every user, users of one database or one Django version, contributors only. Breaking for anyone? -->

## When

<!-- Release impact: `none` | `next release` | `version bumped to x.y.z`. The title is what the generated release notes say. -->

## How

<!--
The approach in a sentence, then the evidence: the test that covers it, or a screenshot of the
page for a change to the client. Tick only what you ran; paste the output of anything that failed.
-->

- [ ] `uv run just lint`
- [ ] `uv run just typecheck`
- [ ] `uv run just test` and `uv run just test-client`
- [ ] `uv run just test-e2e`, when Studio changed
