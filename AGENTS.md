# Working agreements

## Scope

Work inside this independent implementation repository. Treat the parent
`airline-warehouse/` repository as read-only research context. Read the approved
documents relevant to the task before changing code or proposing decisions.

## Approval gates

Follow the planning workflow in `README.md`, using the globally installed skills
as appropriate. Complete the requirements interview before drafting the PRD;
obtain approval of the PRD and specifications before deriving implementation
tickets. Review ticket drafts with the user before publishing GitHub Issues.

Commit approved PRDs, specifications, ADRs, and other documentation to this
repository. Use GitHub Issues as the ticket tracker, with links to the approved
documents and acceptance criteria. Start implementation only after the user
approves the tickets and batch scope; present each completed batch for review
before proceeding to the next batch.

Record agreed architecture decisions in `docs/adrs/`. Separate open questions
and proposals from approved requirements; research is not implicit approval.

## Cloud and credentials

Cloud provisioning, IAM changes, billing changes, and other cloud mutations
require explicit authorization for the task. Available AWS CLI and MCP access
does not itself authorize cloud changes. Keep credentials, authentication caches,
and generated secrets outside Git; examples must use placeholders.

## Current phase

Repository initialization only. Wait for the user to start the planning
interview; no implementation code or cloud resources are authorized yet.
