# Portfolio Evidence Editor evaluation harness

## Problem

The Portfolio Evidence Editor already demonstrated five hand-reviewed v2 cases,
but that small check did not make the test set, failure taxonomy, or comparison
scorecard inspectable. A public case needed to show how the editor behaves when
evidence is missing, language is too absolute, numbers need checking, or input is
empty.

## What I did

I published a 12-case synthetic test set and a dependency-free evaluator for the
deterministic rules in the [live editor](../../../agent/). The cases use only
public-safe notes; they contain no client names, URLs, credentials, raw queries,
or private exports.

The harness compares the current v2 rules with a formatter-only baseline:

- `missing-section`: a labeled section is absent, such as Evidence or Limitation.
- `risky-language`: the small audit list catches terms such as `guarantee`, `best`,
  or `caused`.
- `numeric-claim`: number-like tokens are surfaced for human checking.
- `empty-input`: the editor refuses to draft when there are no notes.
- `complete-input`: case-insensitive labels still produce a complete structured draft.

## What came of it

The v2 rules preserve complete-input parsing while making the review signals
observable: 3/3 missing-section cases, 3/3 risky-language cases, 5/5 numeric-audit
cases, and 1/1 empty-input case matched their expected behavior. The full comparison
is in the [scorecard](scorecard.md), and the public fixtures are in the [test set](test-set.json).

## Evidence

- [Run the evaluator](evaluate.py)
- [Read the scorecard](scorecard.md)
- [Inspect the current editor documentation](../../week-08/agent-readme.md)
- [Try the live editor](../../../agent/)

## Honest limitation

This harness tests deterministic line labels, substring matching, and numeric-token
extraction. It cannot decide whether a claim is true, whether an artifact is private,
or whether a measured result generalizes. A passing case is evidence that a guardrail
fired on a fixture—not permission to publish automatically. A human still verifies
every metric, privacy boundary, and publication decision.

Published 14 August 2026.
