# Airline Delay Intelligence

Project deliverables for Airline Delay Intelligence. **Status: pre-PRD.** No
approved product requirements, technical specification, implementation, or
architecture decisions exist yet. The technology stack and dataset scope remain
open; prior research is reference material, not finalized requirements.

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

- `docs/prds/`: product requirements documents.
- `docs/specifications/`: implementation specifications.
- `docs/adrs/`: approved architecture decision records.

These directories are placeholders until reviewed deliverables exist. Later,
source code and tests will be added according to the approved specification;
no implementation structure is prescribed yet.

## Repository boundary

This is an independent Git repository nested at `project/` inside the separate
`airline-warehouse/` research workspace. It is not a submodule. Research remains
in the parent repository; approved project deliverables belong here.

Agent instructions, skill configuration, scratch files, and environment notes
are maintained in the outer workspace, not this deliverables repository. When
working from that workspace, consult its root `AGENTS.md` and `docs/workflow.md`.
This repository remains usable independently; those local operating instructions
are not part of the project's product documentation.
