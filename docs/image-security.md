# Workload image security assessment

**Reviewed 2026-11-03.** This assessment preserves scanner findings; it is not a
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
checkpoint. The Dockerfile already upgrades packages during build. Switching the
runtime to Debian unstable, hand-building glibc, suppressing findings or relabeling
the image is not a safe routine vulnerability fix and has not been done.

No application call to the affected glibc APIs is identified in project source;
this is not a complete reachability proof for native dependencies. Python gzip
usage does not establish use of zlib's nonblocking `gzprintf` writer. Existing
nonroot/read-only/capability-drop/no-ingress/finite-execution controls reduce exposure
but do not repair vulnerable library code or waive findings.

## Promotion and follow-up

Before promotion, bind the exact image digest to container tests, its measured
processing contract and a completed ECR scan. Record remaining findings explicitly.
Do not infer that a newer application revision fixes the operating-system findings.
Recheck stable vendor updates at the next image build; rebuild and requalify if a
fix becomes available. Preserve previous images and releases for code rollback.

## Primary evidence and sources

- AWS ECR `DescribeImageScanFindings`, exact candidate digest, 2026-11-03.
- `apt-cache policy libc6 zlib1g`, `dpkg-query`, and Python zlib compile/runtime
  versions inside the candidate container after a fresh package-index download.
- [Debian CVE-2026-5435](https://security-tracker.debian.org/tracker/CVE-2026-5435).
- [Debian CVE-2026-19499](https://security-tracker.debian.org/tracker/CVE-2026-19499).
- [Debian CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091).
- [Upstream zlib fix](https://github.com/madler/zlib/commit/df84af25dc1942490e1d1c899a07619152a46148).
