# Portfolio Evidence Editor — Minimum Build

## Version shipped

The agent is implemented as a repeatable prompt workflow using the repository's identity kit, content map, and project notes as its reference files. It is intentionally a workflow, not an autonomous publishing agent.

## Run instructions

1. Provide the project notes and any public-safe supporting links.
2. Ask the editor to extract evidence before drafting.
3. Ask it to draft a five-part case: context, role, approach, evidence, next step.
4. Ask it to list unsupported claims and missing proof.
5. Human-review the result before adding it to the site.

## Test run

Input: the FlyRank search-discoverability capstone notes.  
Output: a structured summary, a source checklist, and a warning that the ranking result is decision support rather than a causal SEO claim.

## Failure modes and human check

It can over-compress nuance or make a source sound stronger than it is. The human must check every metric, privacy boundary, and publication decision.
