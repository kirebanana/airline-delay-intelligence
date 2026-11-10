# Denver weather 2023–2025 — scope amendment

**Status:** Approved by owner, 2026-11-09.
**Parent:** [Airline Delay Intelligence PRD](airline-delay-intelligence.md).
**Technical contract:** [Denver extension](../specifications/den-weather-2023-2025.md).

Extend weather context from Denver-local January 2025 to DEN departures throughout
2023–2025, retaining all scheduled flights, cancellations and diversions. Reuse the
existing temperature, wind speed and visibility investigation and approved layout.
No additional airports, variables, predictions, causal claims or infrastructure.

NOAA ISD ends in August 2025 at the existing station. Owner approved the recommended
NOAA GHCNh replacement path after source assessment, retaining the original January
ISD artifact/release compatibility. This supersedes the parent's January/ISD-only
restriction for this extension, not other metric or security requirements.

Success requires validated full-period source coverage, preserved flight counts,
explicit unmatched weather and conservative unresolved-time handling. The one
observed ambiguous fall-back local clock stays counted with weather unavailable.

Owner approved implementation and a 50 MB total NOAA response-body ceiling,
including prior preflight, source documentation and boundary observations. Warehouse
writes, data build/publication and additional live spending remain separately gated.
