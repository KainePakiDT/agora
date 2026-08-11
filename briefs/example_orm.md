# Brief: ORM vs Raw SQL

## Topic
Should we adopt an ORM (e.g. SQLAlchemy) for our database layer, replacing hand-written SQL?

## Context
The codebase has approximately 50,000 lines of hand-written SQL across 200+ query files.
The team consists of 8 engineers — 5 backend generalists and 3 with strong PostgreSQL expertise.
The database is PostgreSQL 15 with several stored procedures and custom index strategies.
The product is a multi-tenant SaaS application with varying query complexity — some are trivial
CRUD, others are complex analytical queries with CTEs and window functions.

## Constraints
- Full rewrite is not on the table — any migration must be incremental
- Migration effort must be completable within 3 months part-time
- No regression in p95 query latency for the top 20 critical paths

## Personas
- For: Backend Architect — focuses on developer velocity, onboarding, and long-term maintainability
- Against: Database Specialist — focuses on query performance, control, and operational risk
- Neutral: Engineering Manager — balances team capacity, risk, and delivery timelines

## Rounds
2
