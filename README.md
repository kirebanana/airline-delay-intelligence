# Airline Delay Intelligence

Implementation repository for Airline Delay Intelligence. Currently initialized
for requirements and specification work only; no implementation or cloud
resources have been provisioned by this repository initialization.

## Planning workflow

1. `/grill-me`: conduct a thorough requirements interview.
2. Write and review a PRD.
3. `/to-spec`: turn the approved PRD into reviewed specifications.
4. `/to-tickets`: draft GitHub Issues and review them before publishing.
5. Implement approved tickets autonomously in reviewed batches.

Commit all approved PRDs, specifications, ADRs, and other documentation here.
Track implementation tickets in this repository's GitHub Issues.

## Documentation

- `docs/prds/`: product requirements documents.
- `docs/specifications/`: implementation specifications.
- `docs/adrs/`: architecture decision records.

## Repository boundary

This is an independent Git repository nested at `project/` inside the separate
`airline-warehouse/` research workspace. It is not a submodule. Research remains
in the parent repository; approved implementation planning belongs here.

Matt Pocock's skills are already installed globally; no local installation is
required. See `AGENTS.md` for approval gates and working boundaries.
