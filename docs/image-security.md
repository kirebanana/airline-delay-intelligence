# Workload image security assessment

**Reviewed 2026-11-04.** This assessment preserves scanner findings; it is not a
claim of a clean image or proof that every transitive dependency is unreachable.

## Three HIGH findings

The ECR BASIC scan of candidate `sha256:81de082b00373c1c8258cb367648be7b78a1b53914185530a19821e577d7a3ef`
completed with 3 HIGH, 9 MEDIUM and 3 LOW findings. All three HIGH findings concern
Debian system libraries, not the Python dependency lock:

The subsequently GitHub-built/tested candidate
`sha256:b6e0db451e746e176fdfdd9a2ba04a686756e11254e542eb7a3aca4016cf5610`
has the same completed scan findings and measured processing contract. Its 128
container tests discovered 97 passes and 31 opt-in live skips. The assessed library
findings remain present; promotion must not be described as a vulnerability fix.

Protected-merge promotions also independently scanned
`sha256:e96b7ec58013830293151ba47ce449102b8fcf29d4d06b9acab10319be87dd43`
and `sha256:015ad69485677ea618e33dc26afc45bf257251274320e95c8d4ce310fea284e5`.
Both retain the same 3 HIGH / 9 MEDIUM / 3 LOW findings and measured processing
contract. The latter includes the strengthened saved-plan graph guard; that is a
deployment-safety fix, not a repair of the operating-system CVEs.

| Finding | Installed package | Assessment and disposition |
| --- | --- | --- |
| CVE-2026-5435 | glibc 2.41-12+deb13u4 | Deprecated DNS record-printing functions can overrun a supplied buffer. Debian classifies stable trixie as vulnerable, with no stable security update (`no-dsa`, minor issue); unstable is fixed at 2.43-3. Keep the finding. |
| CVE-2026-19499 | glibc 2.41-12+deb13u4 | `strfmon`/`strfmon_l` right-padding can overrun a supplied buffer. Debian classifies stable trixie as vulnerable, with no stable security update (`no-dsa`, minor issue); unstable is fixed at 2.43-5. Keep the finding. |
| CVE-2026-85091 | zlib 1:1.3.dfsg+really1.3.1-1+b1 | The published description identifies the later nonblocking gzip writer in 1.3.1.2–1.3.2, while the installed runtime reports 1.3.1. Debian still labels trixie vulnerable; its fixed unstable package is 1:1.3.dfsg+really1.3.2-4. Treat the version-range discrepancy as unresolved, not an accepted false positive. Keep the finding. |

An isolated, credential-free container refreshed the configured Debian indexes and
confirmed that installed `libc6` and `zlib1g` exactly equal their stable candidates.
There is **no supported stable package update to apply** for these findings at this
checkpoint (rechecked November 4 inside the exact deployed `015ad694…` digest).
Python's compile-time and runtime zlib versions both report **1.3.1**.
The Dockerfile already upgrades packages during build. Switching the
runtime to Debian unstable, hand-building glibc, suppressing findings or relabeling
the image is not a safe routine vulnerability fix and has not been done.

No application call to the affected glibc APIs is identified in project source.
A network-disabled, read-only ELF inventory of the exact deployed image examined
**616 ELF files**, with no unsupported ELF formats. It found no direct undefined
dynamic references to `ns_printrr`, `ns_printrrf`, `fp_nquery`, `strfmon`, `strfmon_l`,
`gzprintf` or `gzvprintf`; the only `gzwrite` reference was in `libapt-pkg.so.7.0.0`,
not the application processing path. Python `locale.currency` source also does not
call `strfmon`. These are useful negative observations, **not** a complete native
reachability proof: static/internal calls, `dlsym`, and runtime control/data flow
are outside that inventory.

Practical exposure requires the specific vulnerable paths: DNS TSIG record printing
for CVE-2026-5435; susceptible right-justified monetary formatting for
CVE-2026-19499; or nonblocking gzip writes that stall and then use formatted output
for CVE-2026-85091. No such workload path has been identified. Python gzip
usage alone does not establish use of zlib's nonblocking formatted writer. Existing
nonroot/read-only/capability-drop/no-ingress/finite-execution controls reduce exposure
but do not repair vulnerable library code or waive findings.

## Supported fixes and alternative bases

- **Current Debian trixie:** installed versions still equal the fresh stable
  candidates. Keep all HIGH findings visible; recheck supported vendor updates at
  the next build. Debian's `no-dsa`/minor classification is not a scanner override.
- **Debian bookworm:** not a demonstrated fix. The current Debian tracker also
  labels bookworm vulnerable for all three, including the disputed zlib range.
- **Alpine/musl:** avoids these glibc implementations, but does not automatically
  fix zlib. Native-wheel compatibility for the pinned Snowflake/dbt/PyArrow stack,
  image tests and the processing contract would need requalification. No compatible
  replacement image has been established; this is not a small verified patch.
- **A smaller/distroless glibc image:** removing tools reduces surface but does not
  establish that retained glibc/zlib code is fixed. A replacement needs exact-version
  vendor evidence, native-dependency checks, scan and workload qualification.
- **Unstable packages or hand-built libc:** not a supported stable upgrade; do not
  replace core libraries ad hoc or mix distributions to obtain a clean scan.

**Recommendation:** retain the qualified immutable image for the final walkthrough,
with the three unsuppressed HIGH findings explicitly disclosed and no proven
application exploit path. This is a residual-risk recommendation, not owner risk
acceptance or a claim of non-exploitability. No new image was built or promoted for
this assessment; a base migration would be a separate approved change.

## Promotion and follow-up

Before promotion, bind the exact image digest to container tests, its measured
processing contract and a completed ECR scan. Record remaining findings explicitly.
Do not infer that a newer application revision fixes the operating-system findings.
Recheck stable vendor updates at the next image build; rebuild and requalify if a
fix becomes available. Preserve previous images and releases for code rollback.

## Primary evidence and sources

- AWS ECR `DescribeImageScanFindings`, exact candidate digest, 2026-11-03.
- `apt-cache policy libc6 zlib1g`, `dpkg-query`, and Python zlib compile/runtime
  versions inside the exact deployed container after a fresh November 4 package-index download.
- November 4 exact-image dynamic-symbol inventory: 616 ELF files; limited as above.
- [Official Python image Alpine/musl caveat](https://github.com/docker-library/docs/blob/master/python/README.md#pythonversion-alpine).
- [Debian CVE-2026-5435](https://security-tracker.debian.org/tracker/CVE-2026-5435).
- [Debian CVE-2026-19499](https://security-tracker.debian.org/tracker/CVE-2026-19499).
- [Debian CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091).
- [Upstream zlib fix](https://github.com/madler/zlib/commit/df84af25dc1942490e1d1c899a07619152a46148).
