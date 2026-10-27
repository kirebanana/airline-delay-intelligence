# Airline Delay Intelligence

Project deliverables for Airline Delay Intelligence. **Status: PRD and technical
specification v0.4 approved; tickets 01–04 implementation batch ready for review.**
The [approved PRD](docs/prds/airline-delay-intelligence.md) defines product scope and
acceptance; the [approved specification](docs/specifications/airline-delay-intelligence.md)
defines architecture and phase-specific feasibility gates. The owner authorized
the revised data-first 01–04 batch on 2026-10-27; later work remains gated.
Prior research is reference material, not additional approved requirements.

## Planning workflow

1. Thorough requirements interview.
2. Reviewed and approved PRD.
3. Reviewed and approved technical specification.
4. Reviewed tickets, then publication to this repository's GitHub Issues.
5. Mostly autonomous implementation within approved batches, with batch reviews.

Commit all approved PRDs, specifications, ADRs, and other documentation here.
Track implementation tickets in this repository's GitHub Issues.
Link issues to approved document revisions and acceptance criteria.

## Documentation

- [Airline Delay Intelligence PRD](docs/prds/airline-delay-intelligence.md): approved 2026-10-26.
- [Airline Delay Intelligence technical specification](docs/specifications/airline-delay-intelligence.md): v0.4, approved 2026-10-26.
- `docs/adrs/`: approved architecture decision records.

ADRs may be added when separate decision records are needed. The revised path is
Snowflake safeguards → BTS preparation → private S3/external stage → raw COPY →
dbt → development Streamlit → safe publication. No internal-stage fallback was built.
January preparation and real S3 → external stage → raw COPY ingestion are now verified:
599,013 source rows,24,732 DEN departures, exact lineage/fingerprints and replay reuse.
Tickets01–04 are ready for batch review; ticket05 and later work have not started.

## Preparation and ingestion

See [the ingestion runbook](docs/ingestion.md) for deterministic preparation,
tests, infrastructure controls, load commands and the live-validation hold points.
No datasets, credentials or Terraform state belong in Git.

## Repository boundary

This is an independent Git repository nested at `project/` inside the separate
`airline-warehouse/` research workspace. It is not a submodule. Research remains
in the parent repository; approved project deliverables belong here.

Agent instructions, skill configuration, scratch files, and environment notes
are maintained in the outer workspace, not this deliverables repository. When
working from that workspace, consult its root `AGENTS.md` and `docs/workflow.md`.
This repository remains usable independently; those local operating instructions
are not part of the project's product documentation.
