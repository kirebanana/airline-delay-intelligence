# Airline Delay Intelligence — Product Requirements Document

| Field | Value |
| --- | --- |
| Status | **Approved** |
| Version | 1.0 |
| Draft date | 2026-10-26 |
| Interview | Completed; shared-understanding checkpoint approved 2026-10-26 |
| PRD approval date | 2026-10-26 |
| Decision owner / acceptance | Project owner |
| Deliverables repository | `kirebanana/airline-delay-intelligence` |
| Approved-document path | `docs/prds/airline-delay-intelligence.md` in that repository |

The owner approved this PRD on 2026-10-26 with clarifications to MET-05 and INF-05.
This approval authorizes promotion of the PRD to the deliverables repository, not
implementation, account activation, provisioning, spending, or ticket creation.
Technical specification and ticket review follow separately.

## 1. Executive summary

Airline Delay Intelligence is a university data-warehousing project and an
infrastructure-focused engineering portfolio demonstration. It will turn official
historical U.S. airline operational records into a validated dimensional warehouse
and a locally presented analytical dashboard, with a small, quality-audited weather
integration.

The principal product is the **explainable engineering system**: infrastructure as
code, containerized batch execution, identity and networking boundaries, controlled
CI/CD, reproducible processing, source-to-result traceability, and safe publication
of validated results. The analytics demonstrate that the system produces correct,
meaningful outputs; this is not a commercial analytics service.

The required historical baseline is BTS Marketing Carrier On-Time Performance
for January 2023 through December 2025. The required secondary enrichment is NOAA
ISD weather for Denver-origin scheduled flights during **Denver-local January
2025**. Required analyses cover carriers, temporal patterns, airports, directional
routes, reported delay categories, and schedule-relative delay recovery.

The retained stack is Python, Docker, AWS S3, Snowflake, dbt Core, Streamlit,
Terraform, and GitHub Actions. ECS Fargate is the preferred batch execution
platform, conditional on remaining account-specific feasibility and credit checks.
All operation must remain within applicable free allowances or promotional/trial
credits, with **$0 out of pocket** and no unapproved paid-plan upgrade.

## 2. Goals, audience, and success

### 2.1 Priorities

1. **Platform/cloud engineering:** demonstrate intentional infrastructure,
   networking, IAM, container execution, delivery controls, and operational safety.
2. **Data engineering:** demonstrate acquisition, provenance, dimensional modeling,
   repeatable loading, corrections, quality gates, and reliable orchestration.
3. **Analytics engineering:** demonstrate accurate, documented transformations and
   defensible descriptive analysis.

Portfolio value and the owner's engineering understanding take priority over
merely satisfying the course. The course still needs a complete, viewable result
and demonstrable infrastructure. No additional formal rubric has been supplied;
this PRD does not invent course obligations.

Infrastructure depth means quality of decisions and implementation, not service
count, resource size, or a requirement to operate a cluster.

### 2.2 Audience and use

- **Owner/presenter:** runs the dashboard locally, reviews batches, and explains
  the entire system and its trade-offs.
- **Professor and portfolio reviewers:** assess the dashboard, architecture,
  infrastructure in service consoles, logs, validation evidence, and documentation
  through a presentation or preserved evidence.
- **Analytical persona:** someone exploring historical reported U.S. domestic
  airline operational performance, not a traveler seeking booking advice.

Independent public access to a live application is not required. The owner need
not author code, operate a manual deployment exercise, or independently rebuild
the system to meet the learning goal. Implementation and debugging are agent-led;
review and acceptance remain with the owner.

### 2.3 Success definition

The project succeeds when all eight acceptance outcomes in section 12 are met and
reviewed, the owner can explain the code and architecture, and the demonstration
has incurred no out-of-pocket charges. Finding that the smallest suitable
warehouse is sufficient is a valid engineering result. A large or statistically
significant weather association is not a success requirement.

There is no fixed finish date or owner-hours-based scope constraint. Trial
activation and provisioning must nevertheless be timed close to implementation
and demonstration, not performed during PRD/specification planning.

## 3. Scope boundaries

### 3.1 Required scope

- National reported coverage of the selected BTS marketing-carrier table for all
  36 baseline months, with both marketing and operating identifiers retained.
- A justified dimensional warehouse and dashboard-facing analytical results.
- Six analytical areas described in section 5, plus the bounded weather module.
- Local Streamlit presentation, relevant filters, methodology, and data-quality
  visibility.
- Terraform-managed agreed AWS/Snowflake infrastructure, containerized ingestion
  and dbt jobs, practical CI/CD, and a coordinated refresh pipeline.
- Withheld-month addition, idempotent reload, controlled correction/reprocessing,
  validation-failure safety, and traceable execution evidence.
- One cloud environment with isolated test data/resources.

### 3.2 Optional, separately evaluated extensions

- Marketing/operating composition as a contextual drilldown.
- Extra historical years or larger resources for a bounded, useful scale test.
- Partial 2026 or later analytical coverage, with matched-period labeling.
- Additional weather airports, periods, variables, or a future GHCNh adapter.
- Unattended scheduling with simple failure notifications.
- Another deployed environment or Kubernetes only if a concrete use case warrants
  its complexity and cost.

These are not necessary to complete the required release. They require explicit
scope/batch and cost approval before implementation; available credits alone do
not authorize expansion.

### 3.3 Non-goals

- Real-time operations, predictions, booking recommendations, causal attribution,
  passenger-level impact, fares/revenue, compensation, or missed connections.
- Fairness-adjusted rankings, mix-adjustment models, or an invented composite
  reliability score.
- National/multi-year weather enrichment or complex compound weather conditions.
- Generalized historical-name browsing or SCD Type 2 solely to demonstrate a
  technique.
- Public dashboard hosting, continuous availability, high availability, or a
  multiuser production load target.
- Automatic 2026 ingestion or continuous discovery of every historical correction.
- Required aggregate CSV exports, bulk raw-flight browsing/downloads, a custom
  design system, or elaborate cross-chart interaction.
- An offline replacement application or reliance on repeated trial eligibility.
- NAT Gateways, unnecessary always-on resources, or a complex monitoring stack.

## 4. Data coverage, identity, and history

| ID | Requirement |
| --- | --- |
| DATA-01 | Use official BTS Marketing Carrier On-Time Performance, January 2023–December 2025, at national reported coverage. Describe it as reported scheduled domestic nonstop operations within BTS coverage, not every U.S. flight or passenger itinerary. |
| DATA-02 | Preserve marketing and operating carrier identifiers, stable airport/carrier identifiers, source airport sequence identifiers, relevant source labels/attributes, outcome fields, and lineage. Do not equate marketing rows with guaranteed distinct physical aircraft movements. |
| DATA-03 | Aim for automated official-source acquisition. If reliable automation is unavailable, permit manually obtained official archives followed by automated downstream validation and processing. Disclose the fallback rather than claim fully unattended acquisition. |
| DATA-04 | Preserve raw source versions and manifests sufficient to trace published results and corrections: source table/month, retrieval, file identity, checksum, schema context, byte/row counts, and processing lineage. Retention and cleanup details belong in the specification and lifecycle plan. |
| DATA-05 | Publish the latest validated version of the selected months, including accepted corrections. Do not double-count multiple source versions, aliases, retries, or reruns. No historical-release comparison interface is required. |
| DATA-06 | Provide an explicit analytical fact grain and justified dimensional core. Validate identity across the chosen data before adopting a business-key contract; one sampled month is not proof of uniqueness. `Flights` and `Duplicate` must follow their source meanings, not substitute for validated identity controls. |
| DATA-07 | Use stable identifiers and consistent display labels while retaining historical source identifiers/attributes. Investigate meaningful historical airport/carrier changes before deciding the history strategy. Preserve flight-level marketer/operator assignments rather than overwrite them with current corporate/network affiliation. |
| DATA-08 | Use historically valid reference mappings wherever correctness depends on them, including weather/time/location interpretation. Determine source-native version joins versus scoped SCD handling in the specification; neither generalized SCD2 nor its blanket exclusion is approved here. |

The source `Duplicate` flag describes swapped-flight reporting, not a general
instruction to remove exact duplicate rows. Source `Flights` values, scheduled row
counts, completed-arrival counts, and distinct physical movements are separate
concepts even where observed values coincide. Reporting changes, code reuse,
mergers, and network transitions must not be hidden by display-label choices.

## 5. Analytical requirements and metric contracts

### 5.1 Shared population and presentation rules

For these definitions, **scheduled rows** means the selected published BTS
marketing-table rows after approved source-version and identity controls, not
unfiltered raw versions. Every metric applies its own eligibility rules within
the user's selected scope.

| ID | Requirement |
| --- | --- |
| MET-01 | Display metric meaning, eligible denominator/count, relevant unknown/excluded observations, period, filters, and marketing/operating perspective. Unknown outcomes must not silently become successful outcomes. Rates with zero denominator are N/A. |
| MET-02 | Recompute aggregate rates from aggregate numerators/denominators, not averages of subgroup percentages. Preserve stored precision and round presentation only. |
| MET-03 | Preserve signed delay values, including negative early arrivals/departures. Do not impute missing or cancelled actual outcomes as zero. Provide mean, median, p90, and eligible counts for delay summaries, emphasizing median/p90 in detailed comparisons. |
| MET-04 | Treat comparisons and rankings as descriptive. Show volume and operating/network/route/schedule-mix caveats. Small groups remain inspectable with warnings but are suppressed from rankings below 100 eligible observations for the selected metric and filters. Display the configurable threshold and date coverage. |

### 5.2 Approved primary KPIs

| KPI | Numerator | Denominator / population |
| --- | --- | --- |
| Arrival on-time rate | Known arrival indicator indicates delay below 15 minutes | Noncancelled, nondiverted scheduled rows with a known ordinary arrival-delay indicator |
| Cancellation rate | Source cancellation flag = 1 | All scheduled rows in scope |
| Diversion rate | Source diversion flag = 1 | All scheduled rows in scope |
| Departure-delay rate | Known departure indicator indicates delay of at least 15 minutes | Noncancelled scheduled rows with a known departure-delay indicator; diversions included |

**MET-05:** Implement these four definitions consistently across dashboard views.
Exactly 15 minutes is delayed; 14 minutes is below the threshold. A cancellation
remains outside departure-performance calculations even if departure information
exists. Ordinary arrival-performance metrics exclude diversions rather than
silently mixing specialized diversion-arrival fields into the denominator.
Unknown cancellation/diversion flags and delay indicators must follow an explicit
data-quality policy and be reported. Unknown cancellation/diversion flags must
never be silently treated as false; rows with unknown flags must not silently
enter populations requiring a known noncancelled or nondiverted outcome.

Punctuality, cancellation, and diversion measures must remain separately visible:
on-time performance among eligible arrivals is not the same as schedule success
among all scheduled rows. Counts are operation-row weighted, not passenger
weighted. The corresponding known signed-arrival-delay population is used for
arrival-delay summaries, with its own eligible count if it differs from indicator
coverage.

### 5.3 Required analytical areas

| ID | Area | Required capability |
| --- | --- | --- |
| ANA-01 | Carrier reliability | Compare marketing carriers on arrival punctuality alongside cancellations/diversions, with counts and temporal context. Operating-carrier comparisons, if included, are explicitly within the marketing dataset's coverage. |
| ANA-02 | Temporal patterns | Explore month, weekday, and scheduled local departure-hour differences in appropriate delay/cancellation metrics. Label local hours; compare equivalent periods and identify missing/incomplete coverage. Do not shift delayed flights into actual-departure-hour cohorts. |
| ANA-03 | Airport reliability | Explore origin departure delays/cancellations with carrier and volume context. Airport grouping is location context, not proof of airport responsibility. |
| ANA-04 | Directional routes | Explore reliability and delay variability for ordered origin/destination pairs with volume eligibility and filters. A→B and B→A are distinct. Do not imply round trips or passenger connections. |
| ANA-05 | Reported delay categories | Provide category-minute totals/shares and affected-flight rates for eligible late arrivals, plus separately presented cancellation reasons, under section 5.4. |
| ANA-06 | Delay recovery | Provide signed improvement, distributions/summaries, and share recovering below the arrival-delay threshold under section 5.5. |

Categories and recovery are secondary in presentation but **required**, not optional.
Exact chart types, layout, and page count remain flexible; six areas do not require
six separate pages. Calendar patterns and local-time patterns are descriptive, not
evidence of causation or simultaneous national conditions.

### 5.4 Reported delay categories

The eligible late-arrival population is ordinary noncancelled/nondiverted arrivals
with a known arrival indicator showing at least 15 minutes of delay. Category
completeness and inconsistencies must be checked within that population.

- Show minutes for carrier, weather, NAS, security, and late-aircraft categories.
- A **share of reported category minutes** divides a category's reported minutes
  by total reported category minutes on an explicitly defined eligible subset.
- An affected-flight rate divides eligible flights with a positive allocation for
  that category by the stated eligible late-arrival population/subset. Explain
  any exclusion and missingness; do not switch to all-arrival denominators silently.
- A share relative to **total eligible arrival-delay minutes**, if displayed, is a
  different measure and must be labeled with that denominator. It must not be
  presented as interchangeable with a share of reported category minutes.
- Positive category counts can overlap. Their affected-flight rates need not sum
  to 100%. Minute shares can sum to 100% of reported minutes despite unallocated
  arrival delay elsewhere; disclose that discrepancy.
- Present cancellation-reason counts/shares separately using cancelled rows and
  disclose unknown reasons. Do not combine cancellation counts with delay minutes.

**MET-06:** Preserve and report missing, inconsistent, unallocated, and excluded
observations/minutes; use compatible numerator/denominator subsets. Never invent
an allocation. BTS intends category allocation to reconcile for eligible late
flights; exceptions are diagnostics, not justification to assume reconciliation
is irrelevant. These are reported attribution categories, not experimentally
established causes. `WeatherDelay` is not every weather-associated disruption.

### 5.5 Schedule-relative recovery

**MET-07:** The primary population is ordinary noncancelled/nondiverted flights
departing at least 15 minutes late, with both signed departure and arrival delays
known.

```text
signed improvement = departure delay − arrival delay
recovered below threshold = arrival delay < 15 minutes
recovery share = recovered below threshold / eligible late departures
```

Show eligible/excluded counts, mean/median/p90, and a distribution. Preserve zero
and negative improvement. Positive improvement means less schedule-relative delay
on arrival; it does not prove faster flying, crew effectiveness, or a causal
intervention. A broader all-completed-flight comparison is not required and must
not silently replace the primary population if added.

## 6. Required Denver weather pilot

| ID | Requirement |
| --- | --- |
| WX-01 | Use official NOAA ISD observations for Denver-origin scheduled rows throughout Denver-local January 2025, including cancellations and diversions. Acquire only the necessary adjacent UTC boundary observations to cover that local period and matching lookback. No national or multi-year weather scope is required. |
| WX-02 | Match each variable to its latest quality-accepted observation at or before scheduled departure, no more than 60 minutes old. Preserve original local source fields, interpreted UTC anchor, station/crosswalk provenance, observation time, age, and match status. No future matches, invented cancellation event times, or flight-row multiplication. |
| WX-03 | Require at least 95% valid coverage **for each of temperature, wind speed, and visibility**, with all scheduled Denver pilot rows—including cancellations—in each coverage denominator. Disclose missing, malformed, rejected-QC, stale, mapping/time, and boundary issues and sample sizes. Do not improve apparent coverage by dropping unmatched flights. |
| WX-04 | Report per-variable coverage/ages, cancellation/noncancellation coverage, and descriptive scheduled-weather context/comparisons. Use separate-variable analyses; do not silently combine different observation times into compound conditions. Show date/episode support as well as flight counts. No significant association, prediction, or causal conclusion is required. |

If acceptance fails, investigate and request an explicit decision; do not silently
relax quality rules, age limits, thresholds, or denominators. Technical details of
field-level QC decoding, units, band selection, tie handling, and time conversion
must be specified and tested before implementation. A newer rejected measurement
may be distinguished from an older accepted match; reporting must make such
fallbacks understandable.

Station observations describe scheduled-time context, not necessarily conditions
when a cancellation decision was made or all conditions affecting a flight. NOAA
observation timestamps do not establish when corrected observations were available
in real time. Episode clustering, carrier/route/hour mix, cancellation selection,
and missingness limit interpretation. No statistical adjustment model is required.

The pilot's January evidence does not validate DST transitions, all-airport time
reconstruction, national station mappings, precipitation/ceiling semantics, or
GHCNh acquisition. Those are not claims the delivered pilot may make.

## 7. Dashboard and presentation

| ID | Requirement |
| --- | --- |
| DASH-01 | Run Streamlit locally for one presenter. Expose the required analytical areas without prescribing page count or exact chart types. Keep presentation understandable and proportional to a university/portfolio demonstration. |
| DASH-02 | Provide useful baseline date, marketing-carrier, origin, destination/directional-route filters; clear reset behavior and applied-filter summary. Weather controls and labels must make its fixed DEN/January-2025 scope explicit rather than imply national baseline coverage. |
| DASH-03 | Provide methodology/data-quality information: source scope, grain/perspective, KPI definitions, counts/exclusions, warnings, ranking threshold, coverage, and refresh/release status. Distinguish data coverage dates from acquisition/processing/refresh timestamps and identify the active validated release. |
| DASH-04 | Present empty/insufficient data honestly, including N/A denominators and low-volume warnings. A failed refresh must not replace the validated results with incomplete data or falsely imply that the failed attempt refreshed the active data. |

The dashboard is an accessible demonstration of correct results, not a new product
requiring exports, exhaustive interactivity, or a production availability SLA.
Specific responsiveness expectations, query/caching design, and quantile methods
belong in the specification, using measured workload evidence rather than invented
multiuser performance requirements.

## 8. Refresh, quality, and publication behavior

The required logical flow is:

```text
deliberate trigger → acquire → validate/preserve raw and provenance
                  → load → transform/enrich → validate results
                  → atomically publish a compatible validated release
```

This describes dependencies and outcomes, not a chosen orchestrator or transaction
mechanism.

| ID | Requirement |
| --- | --- |
| PIPE-01 | Once triggered, run automatically through required dependencies without manual handoffs between successful stages. Support independently rerunnable stages and reuse of compatible validated artifacts, including unchanged fixed weather data. |
| PIPE-02 | Support any selected month being reprocessed and future months without redesign. Required demonstrations use adding a withheld baseline month and revision-safe reprocessing; rolling future data and global correction discovery are not required. Clearly label controlled revision fixtures rather than claim they are observed BTS revisions. |
| PIPE-03 | Repeating identical accepted inputs must not double-count results. Reprocessing a replacement source version must produce the expected validated result and preserve traceability of the change. Exact equivalence rules and implementation belong in the specification. |
| PIPE-04 | Block publication on critical schema, identity, reconciliation, or metric-integrity failures. Document noncritical warnings and approved source exceptions. Preserve raw evidence and diagnostics; do not silently repair source values. |
| PIPE-05 | Publication must be atomic from the dashboard's perspective. A failed required stage retains the **entire previous validated release**; do not publish new BTS results alongside incompatible old weather or partially replaced tables. If no validated release exists, show an explicit unavailable/not-yet-validated state. |
| PIPE-06 | Provide durable run/stage status, useful secret-free errors/logs, timeouts, and bounded retries for transient failures. Do not endlessly retry deterministic validation/configuration errors. Initial deliberate runs need clear status, not a complex alerting stack; unattended scheduling, if later approved, requires simple inexpensive failure notifications. |

Testing, fixtures, and failed refreshes must not affect the validated dashboard
data. Atomic publication covers the complete required result set, not necessarily
one database transaction; the actual strategy remains open. Compatible artifact
reuse must be dependency-aware, not a license to ignore changed inputs.

### 8.1 Known source exceptions to preserve

The January 2024 research sample contains a late flight with 1,345 arrival-delay
minutes and zero allocation in all five categories, and one noncancelled row with
a diversion-related cancellation sentinel. Preserve the records unchanged,
document the exceptions, and retain them in calculations whose relevant fields
remain valid. Exclude or flag only affected secondary calculations and disclose
unallocated/excluded observations and minutes. Never override the cancellation
flag solely from the sentinel.

These cases refine error classification; they do not waive critical gates or
authorize blanket suppression of new anomalies. The specification must define
the exact validation rules, severities, reviewed exception handling, and tests
using broader retained-data evidence where necessary.

## 9. Infrastructure, security, and CI/CD

### 9.1 Platform constraints

| ID | Requirement |
| --- | --- |
| INF-01 | Retain Python acquisition, Docker packaging, private S3 raw storage, Snowflake warehousing, containerized dbt Core, and local Streamlit. ECS Fargate is preferred for finite batch jobs, conditional on effective access, entitlement, and cost verification before deployment commitment. A failed feasibility gate requires an owner decision, not a silent platform substitution or paid upgrade. |
| INF-02 | Use Terraform for agreed AWS and Snowflake infrastructure. Reproducibility may have documented account/authentication/bootstrap exceptions; data loading and transformations are separate concerns. Parameterize infrastructure for possible later environments without deploying duplicates by default. |
| INF-03 | Use one cloud environment with isolated test data/resources, including separate Snowflake schemas and S3 prefixes where appropriate. Isolation must protect published results, not just provide different names. |
| INF-04 | Make IAM and networking meaningful: private storage, least-privilege workload access, separate workload responsibilities, protected credentials, and explainable connectivity boundaries. Do not use the existing broad administrative access as routine workload access. Keep secrets out of code, images, task arguments, logs, and Git; keep Terraform state and sensitive operational artifacts out of Git. |
| INF-05 | Evaluate short-lived Fargate tasks using dedicated networking, temporary public IPs for necessary outbound connectivity, and zero inbound rules as the **preferred option**, not a fixed implementation. The specification must compare feasible networking choices against connectivity, security, and the no-NAT/$0 constraints before selecting the design. If selected, explain that this option is not private-only networking or a strict outbound domain allowlist; no listening application, load balancer, or unnecessary public exposure is required. Exact routes, endpoints, policies, and authentication remain specification decisions. |
| INF-06 | Use AWS project region `eu-north-1`; verify Snowflake region compatibility, external connectivity, and transfer consequences before setup. Prefer the smallest suitable resources, measure before resizing, and avoid unnecessary always-on components. |

A bounded sizing comparison should evaluate correctness, elapsed time, and credit
consumption where feasible within approved allowances. Larger resources are not
a final-state requirement. Returning to the smallest suitable configuration—or
showing that it is sufficient—is acceptable. Extra benchmark years remain an
optional separately approved extension, not a reason to expand required analytics.

### 9.2 CI/CD

| ID | Requirement |
| --- | --- |
| CI-01 | GitHub Actions runs tests, linting, and container build checks for PRs, with an understandable result for review. Keep the approach practical rather than construct an elaborate delivery platform. |
| CI-02 | After approved merges within the approved scope/batch, automate building/publishing tested versioned images to private ECR and updating the relevant ECS job task definitions. Promote identifiable immutable versions; do not depend on an ambiguous mutable image to identify a release. |
| CI-03 | Keep data execution separate from deployment. A code merge/image publication must not itself automatically run ingestion/dbt or incur an unapproved data workload. Existing running/validated data must not be replaced simply because code was deployed. |
| CI-04 | Protect deployment credentials and permissions, test/published data separation, and approved promotion boundaries. Exact identity federation, Terraform plan/apply controls, state access, CI trust conditions, and recovery workflow belong in the specification. |

The owner reviews PRs, failures, deployments, and results at batch level. Artificial
failures and manual deployment exercises are not learning requirements. Controlled
automated failure tests remain necessary to demonstrate publication safety; they
are not a requirement to make the owner manually break or repair infrastructure.

## 10. Financial constraints and finite lifecycle

| ID | Requirement |
| --- | --- |
| COST-01 | **$0 out of pocket** across the project. AWS usage must fit confirmed applicable promotional credits/free allowances, Snowflake its confirmed trial credits, and CI/artifact/dependency usage its own applicable free allowance. AWS credits cannot be assumed to cover unrelated providers. No paid-plan upgrade, overage, or paid-only activation without a new explicit owner decision. |
| COST-02 | Before approved deployment/runs, verify current plan/credit eligibility, applicable services, expiry, effective permissions, relevant quotas, and a conservative workload/lifecycle estimate. Include Fargate compute, image storage, logs, public IPv4, storage/requests, secrets if used, and data transfer—not just headline compute. Unknown coverage is not permission to proceed. |
| COST-03 | Use bounded workloads, timeouts/retries/concurrency, credit/usage visibility, and an approved stop/cleanup plan. Alerts are not a guaranteed hard spending cap; stopping compute does not eliminate retained storage/log/image costs. Do not automatically upgrade, increase quotas, or scale to overcome a denial/failure. |
| COST-04 | Delay Snowflake trial activation and cloud provisioning until closer to implementation, preserving the trial/demonstration window. Preserve screenshots, relevant results/logs, architecture and reproducibility evidence **before** access/credits expire. Stop cloud operation when continued eligibility cannot be established; no indefinite live service or repeated-trial availability guarantee is required. |

Published Free Plan/Fargate evidence and a read-only account snapshot support a
conditional candidate, not a guarantee of future account state or complete credit
applicability. The snapshot, balance, and quotas are environment context rather
than durable PRD configuration. Revalidate them before authorized work.

The specification must address retained raw versions, ECR/log storage, credential
material, export costs, credit reserve, expiry, and scoped cleanup. Expiry is not
a backup plan. Deletion, IAM/trust changes, public exposure, and account actions
still require the established bounded approval; this PRD authorizes none of them.

## 11. Evidence, explainability, and portfolio handoff

| ID | Requirement |
| --- | --- |
| EVID-01 | Provide architecture/data-flow and security-boundary diagrams, infrastructure/bootstrap/reproduction documentation, metric/methodology documentation, and an operational walkthrough covering trigger, status, rerun, validation, publication, and failure recovery. |
| EVID-02 | Preserve reviewable evidence: infrastructure/service-console views, CI/CD results, job/stage logs and status, source/KPI reconciliation, replay/correction/failure-safety results, resource-sizing reasoning, and dashboard screenshots/results. Capture necessary evidence while access remains available; sanitize secrets and sensitive operational details. |
| EVID-03 | Support the owner's ability to explain code, infrastructure, decisions, alternatives, limitations, and cost/security trade-offs. Aim for an eventually sanitized public source repository and concise portfolio case study, subject to separate explicit visibility/publication approval. |

No particular diagram tool, document generator, page count, or presentation length
is mandated. An explanation should distinguish observed results, controlled test
fixtures, estimates, and unverified assumptions rather than rely on screenshots
alone as proof of correctness.

## 12. Acceptance outcomes and evidence

These eight outcomes are the completion backbone approved in the interview.
Detailed executable checks and test fixtures will be specified later; the
requirements below must not be weakened to fit an implementation.

| ID | Outcome | Linked requirements | Required acceptance evidence |
| --- | --- | --- | --- |
| AC-01 | Reproducible managed infrastructure | INF-01–06; COST-01–04 | Reviewed Terraform definitions/validation and deployment evidence for the agreed resources; documented bootstrap exceptions, one-environment isolation, region/network boundaries, and eligibility/cost gates. No requirement that the owner manually rebuild it. |
| AC-02 | Controlled CI/CD | CI-01–04 | PR tests/lint/container build checks; an approved promotion with identifiable image version and updated job definition; evidence that promotion does not automatically execute a data refresh. |
| AC-03 | Coordinated observable refresh | DATA-01–04; PIPE-01–02,06 | A deliberately triggered end-to-end run proceeds through dependencies, exposes durable stage/run results and useful logs, and adds a withheld baseline month to reach complete 2023–2025 coverage. |
| AC-04 | Idempotence and correction safety | DATA-05–06; PIPE-02–03 | Repeated identical input does not duplicate results; a clearly labeled controlled correction produces the expected results, is traceable, and agrees with independently expected/rebuilt output for that scenario. Future-month support is demonstrated through the design/contracts without requiring automatic 2026 operation. |
| AC-05 | Failed runs cannot replace validated data | PIPE-04–06; INF-03; DASH-03–04 | Controlled automated tests show critical/required-stage failures leave the complete prior validated release and its coverage unchanged. Test data is isolated; compatible artifact reuse does not mix incompatible versions. Failure status differs from active-release freshness. |
| AC-06 | Correct analytical and weather results | DATA-06–08; MET-01–07; ANA-01–06; WX-01–04; DASH-01–04 | All six analytical areas and the weather module are viewable locally. Independently checked source/population/KPI reconciliations, boundary/unknown tests, disclosed exceptions, signed summaries, and ranking behavior agree with contracts. Full-local-month weather achieves ≥95% per-variable coverage on all scheduled DEN rows, ≤60-minute backward matches, zero future matches and zero multiplication. |
| AC-07 | Explainable secure and credit-bounded operation | INF-04–06; CI-04; COST-01–04 | Reviewed identity/network/secret boundaries, isolated test access, sizing/credit-consumption evidence and reasoning, current eligibility checks and approved lifecycle/stop controls. No out-of-pocket charges or unapproved upgrades. Larger resources or a significant weather effect are not required. |
| AC-08 | Complete demonstrable handoff | EVID-01–03; DASH-03; COST-04 | Architecture, methodology, operational walkthrough, sanitized screenshots/results and supporting logs/tests are preserved for presentation; owner reviews the explanation and outcomes. Public repository publication remains a separate gate. |

Agent-reported success alone is not acceptance. Reviews must identify met/unmet
criteria, evidence, deviations, limitations, and any decision needed before the
next approved batch.

## 13. Supporting evidence, not additional requirements

Research performed 2026-10-25 sampled two official BTS marketing archives and one
NOAA station/month. It did not validate all 36 months or establish long-term
source stability. The September research is proposal context; newer primary
documentation and sample evidence take precedence where they correct it.

| Observed evidence | What it supports | What it does not establish |
| --- | --- | --- |
| January 2024 marketing archive: 582,425 rows; 119 named fields plus trailing empty CSV field | Concrete KPI populations, null/outcome behavior, parsing and test examples | Whole-period identity uniqueness, future schemas, or distinct physical-flight identity |
| Zero observed candidate identity collisions; `Flights=1` and `Duplicate=N` throughout that sample | Useful diagnostics for candidate contracts | Universal keys or a validated policy for swapped-flight cases |
| Category sums reconcile on 134,574 of 134,575 ordinary late arrivals; one 1,345-minute exception | Reconciliation is meaningful and explicit anomaly handling is necessary | Authority to fabricate allocation or ignore all future mismatches |
| Cancellations with departure information; diversions lacking ordinary arrival-delay fields; actual clocks containing 2400 | Outcome-specific eligibility and careful local-time handling | A general actual-event UTC/DST reconstruction algorithm |
| January 2025 BTS archive: 599,013 rows, including 24,732 DEN-origin rows and 313 DEN cancellations | Aligned flight/weather sample | National weather coverage or multi-year mapping stability |
| DEN January sample: temperature 98.35%, wind 98.75%, visibility 97.52% fresh accepted matches; no future matches/multiplication | Feasibility of the selected small ISD integration | Complete local-month delivered coverage: 261 research-boundary rows were deliberately unavailable |
| OAK renamings, Alaska/Hawaiian integration and Mesa network-transition documentation | Historical attributes, reporting changes and flight-level affiliations deserve investigation | Exact BTS reference-version transitions or an automatic need for generalized SCD2 |

January 2024 archive SHA-256:
`7a96466f2165b93ac1a064422c960e9b3089c2cc8a70c2cbabc8fde1c8b0af31`.
January 2025 archive SHA-256:
`0feaabdbc9e4bd851ef717f342678cdcc5ea0822dd706359aab030bb1a5d1c24`.
The NOAA station was `72565003017` / KDEN; the observation sample covered January
2025 UTC, not all of Denver-local January.

Directory metadata suggested roughly 1.11 GiB compressed for 36 baseline monthly
archives, with an alias ambiguity for December 2023. That is not measured loaded
storage, row volume, credit consumption, or proof all files are equivalent.

### 13.1 Primary references

Sources were reviewed during the October research; mutable service availability,
terms, pricing, and source behavior must be revalidated before specification/setup
depends on them.

1. [BTS marketing table profile](https://www.transtats.bts.gov/TableInfo.asp?QO_fu146_anzr=b0-gvzr&V0s1_b0yB=D&gnoyr_VQ=FGK), [field definitions](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FGK), and [official archive directory](https://www.transtats.bts.gov/PREZIP/).
2. [BTS Technical Directive 31](https://www.bts.gov/topics/airlines-and-airports/number-31-technical-directive-time-reporting-effective-jan-1-2019) and [Directive 39 for 2025](https://www.bts.gov/explore-topics-and-geography/modes/aviation/number-39-technical-directive-reporting-time): timing, outcomes, and reporting/allocation rules.
3. [BTS historical Master Coordinate fields](https://www.transtats.bts.gov/Fields.asp?gnoyr_VQ=FLL) and [on-time notes](https://www.transtats.bts.gov/ONTIME/): identity/history and reporting cautions.
4. [NOAA ISD](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database), [format manual](https://www.ncei.noaa.gov/data/global-hourly/doc/isd-format-document.pdf), and [Access Data Service API](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation): observation format, QC, and bounded access. The manual's direct live retrieval was unreliable; the research records that limitation rather than claiming otherwise.
5. [FAA DEN airport display](https://nfdc.faa.gov/nfdcApps/services/ajv5/airportDisplay.jsp?airportId=DEN): current mapping/timezone context, not independently verified historical mapping intervals.
6. [AWS supported Free Plan services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html), [Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/), [Fargate regions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate-Regions.html), and [Fargate pricing](https://aws.amazon.com/fargate/pricing/): conditional feasibility, not account-specific permanent free operation.
7. [Fargate networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html) and [VPC pricing](https://aws.amazon.com/vpc/pricing/): no-NAT connectivity choices and billed dependencies.
8. [Snowflake trial accounts](https://docs.snowflake.com/en/user-guide/admin-trial-account): finite trial and access lifecycle; terms must be checked at activation.

Detailed working evidence remains in the outer workspace, not as a required
dependency of the future standalone deliverables repository: `interview-notes.md`,
`bts-research/findings.md`, `bts-research/den-weather-join.md`,
`weather-research/findings.md`, `reference-history/findings.md`, and
`fargate-feasibility.md`, all under `.scratch/airline-delay-intelligence/`.
Approved product requirements come from owner decisions, not from these reports
automatically promoting suggestions into scope.

## 14. Risks, deferred decisions, and specification obligations

The following are intentionally unresolved technical decisions or evidence gates,
not permission to choose silently or to alter the product contracts.

| Area | Required specification resolution / gate |
| --- | --- |
| Batch platform and entitlement | Confirm effective Fargate/ECR/IAM access, regional limits, per-service credit applicability/expiry, and conservative workload/dependency costs. Stop for owner decision if strict $0 cannot be sustained. |
| Acquisition contract | Define discovery, archive aliases, schema handling, version manifests and acquisition failure/fallback behavior. A working historical URL is not a stable API guarantee. |
| Fact identity and revisions | Validate broader retained-data keys, swapped-flight behavior, replacement semantics and reproducibility. Select a key/source-version policy only with evidence. |
| Reference history | Perform a bounded targeted reference check with appropriate authorization; inspect real airport/carrier changes and relevant source-version intervals. Decide current labels, source-native history and any scoped SCD2 from analytical correctness, not pattern-count goals. |
| Model design | Define dimensions, fact keys, unknown members, temporal attributes and aggregates. A route dimension, snapshots, actual-event UTC reconstruction and specific materializations are not predetermined. |
| Orchestration and publication | Choose a simple mechanism with dependency control, durable status, independent reruns, compatible artifact reuse, bounded retry/timeout/stop behavior and atomic complete-release publication. No orchestrator or table-swap technique is selected by this PRD. |
| Weather details | Define QC/report types/units, station mapping validity, full-local-month boundary acquisition, timezone/HHMM interpretation, deterministic matching, rejection reasons and descriptive bands. Validate rules without reducing the approved acceptance denominator. |
| CI and security | Define trusted events, identity federation/authentication, roles, private artifact access, image promotion, Terraform plan/apply and bootstrap/state protection. Demonstrate test isolation and no secret leakage. |
| Testing and performance | Specify executable metric and pipeline tests, exception severities, reconciliation checks, independent reference calculations, quantile definitions, responsiveness targets and measured resource sizing. No production uptime/concurrency target is implied. |
| Lifecycle | Define limits, credit reserve/stop conditions, safe evidence capture, retained-version/log/image policies and bounded cleanup/rollback before resources or trials are activated. |

If evidence changes requirements, financial exposure, security boundaries, or
acceptance feasibility, pause affected work and obtain an explicit owner decision.
Do not rewrite the requirements to match an implementation limitation.

## 15. Review and next gates

1. **Completed:** owner approved scope, contracts, exclusions, and acceptance on
   2026-10-26 with the MET-05 and INF-05 clarifications incorporated in version 1.0.
2. Maintain this approved document in the deliverables repository at the recorded
   path through the established repository review/commit workflow. Subsequent
   changes require review rather than silently changing approved scope.
3. Draft and review the technical specification, resolving section 14 decisions
   and linking its requirements to this PRD's stable IDs.
4. Draft, review, and obtain publication approval for tickets and dependency-aware
   batches in the inner repository only.
5. Activate the Snowflake trial/provision cloud resources closer to implementation,
   only under a separately approved bounded plan, then execute reviewed batches.

No fixed implementation phase schedule, service expansion, cloud mutation,
repository visibility change, or specification/ticket publication is authorized
by this PRD approval.
