# FlyRank Capstone: Social Media Studio

Status: implementation in progress. This public repository is dedicated to the Social Studio capstone.

The service will turn one stored Markdown post into platform-specific variants, validate each variant before review, and publish approved variants through interchangeable publisher adapters. A SQLite-backed scheduler and publish history will make retries observable and safe.

## Design

See [`DESIGN.md`](DESIGN.md) for the data model, API surface, adapter seam, and non-goals. No real post is published by default; the demo adapter is `mock_x`.

## Learning checkpoints

- A **constraint profile** turns a platform's text limits into executable validation.
- An **adapter** lets business logic call one interface while platform-specific code changes independently.
- An **idempotency key** makes a repeated request for the same variant and slot safe.
- A durable schedule stores due work in SQLite so a restarted worker can resume it.

Run steps and acceptance evidence will be added with the implementation.
