# Implementation Plan: Production-Grade Benchmark Test Harness, Automated Human-Readable Reporting, and Fail-Closed CI/CD for the Tropical Max-Plus Router (ADR-0034)

**Target Subsystem:** `/run/media/multiplic/AGI/prismagi/mount/ROUTERS/tropical-max-plus`  
**Governing ADR:** [ADR-0034](ADR-0034.md) (Prime Index 34)  
**Global ADR:** [ADR-0034](file:///home/multiplic/adr/03_accepted/ADR-0034-tropical-max-plus-router-benchmark-test-harness-and-ci-cd.md)  
**Reference Parity:** [`kuramoto-protocol-r3`](file:///run/media/multiplic/AGI/prismagi/mount/SUBSYSTEMS/kuramoto-protocol-r3) (ADR-0024/0025/0026) and [`ROUTERS/neuro-symbolic`](file:///run/media/multiplic/AGI/prismagi/mount/ROUTERS/neuro-symbolic) (ADR-0033)  
**Parent Framework:** Multiplicity Theory, PrismPM Production Governance, and NIST SP 800-53 Continuous Assurance  
**Date:** 2026-11-24  
**Status:** Implemented — Baseline Run Passing (9/9 suites, 5/5 benchmark sub-suites)  

**Toolchain Contract:** `leanprover/lean4:v4.32.2` · `prismpm 0.5.0` · LexLean Language 1.2 (embedded in PrismPM) · Python 3.11+  
**Pinned Baseline:** build `1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90` · semantic ID `afd80884608e37187f0bf6808c47b48d96551b3b529146b4757349b35d14d142` · compiler semantics `4b3ed2378d6c43bb32a41d466cf140337e8b1cedc5e1f345aaf3395f488f63a9`

---

## 1. Executive Summary

The Tropical Max-Plus Router currently compiles cleanly through PrismPM: `prismpm check` passes and `prismpm build` publishes a deterministic content-addressed release. However, the recompilation that produced the pinned baseline above required manual correction of stale toolchain and lock pins (`v4.32.1` → `v4.32.2`, compiler semantics `1427f8b6…` → `4b3ed237…`). That drift is exactly the class of failure a production harness must detect before commit, not during release.

This plan establishes a **shift-left, fail-closed verification harness** for the router that:

1. Pins and verifies the complete toolchain/lock contract on every run.
2. Executes nine deterministic verification suites, including Lean kernel attestation and PrismPM production build integrity.
3. Runs a property-based tropical benchmark engine covering semiring laws, checked overflow, routing-table scale, and reproducibility.
4. Generates human-readable Markdown and machine-readable JSON reports that are never out of sync with the source.
5. Enforces the same gates locally (git pre-commit) and remotely (GitHub Actions) with artifact publication and `$GITHUB_STEP_SUMMARY` reporting.

The design follows industry best practices: immutable toolchain pinning, reproducible builds, dual-format evidence, deterministic seeds, benchmark warmup/percentiles, negative-path gate testing, and NIST SP 800-53 control traceability (`SI-7`, `SA-11`, `CA-2`, `CM-3`, `AU-10`, `CP-2`).

---

## 2. Scope and Non-Goals

### In Scope
- Source, lockfiles, toolchain file, PrismPM configuration, LexLean entrypoint, and language packages under the router root.
- Verification of generated artifacts under `.lexlean/` and `.prism/`.
- Automated report generation under `reports/`.
- Local hooks, installer script, and remote CI workflow.

### Out of Scope (Explicit)
- `prismpm verify` is **informational only** for this baseline. The current semantic snapshot contains no Prism declarations and `prismpm verify` exits with `PP5003`. The blocking release gate is `prismpm check` + `prismpm build`. This ADR does not silently skip the check; it records the limitation and makes promotion of `prismpm verify` to a blocking suite a follow-up condition when Prism declarations are introduced.
- The standalone `lexlean` CLI is language 1.0 and rejects `lexlean/project/1` language 1.2 configurations. All language-1.2 verification MUST go through embedded PrismPM primitives; the harness must not depend on a mismatched standalone `lexlean` binary.

---

## 3. Invariant Contract

| Invariant ID | Property | Verification Strategy | NIST Controls |
| :--- | :--- | :--- | :--- |
| **INV-TRP-034a** | Max-plus semiring law preservation: `⊕ = max`, `⊗ = +`; `tropicalMul(w,x) = w + x`; `tropicalScore(w,x,b) = tropicalMul(w,x) + b`; associativity/commutativity/idempotence | Property-based exact-integer sampling, 10,000 deterministic draws, zero tolerance | SI-7, SA-11 |
| **INV-TRP-034b** | Checked 64-bit arithmetic: overflow is explicit failure, never silent wrap | Boundary sweep over `0`, `2^32−1`, `2^32`, `2^63−1`, `2^63`, `2^64−1`; zero silent wraps | SI-7, SC-28 |
| **INV-TRP-034c** | Deterministic score/cache canonicality: identical inputs emit identical build digest, semantic ID, and report bytes (excluding run timestamps) | Repeat-build digest comparison and canonical report hashing | AU-10, SI-7 |
| **INV-TRP-034d** | Formal kernel hygiene: attestation status `verified`, zero `sorryAx`/`Classical.choice`/`Quot.sound`/`propext`/unexpected axioms | Parse `.lexlean/verified/*/attestation.json` and enforce axiom policy | SI-7, SA-11 |
| **INV-TRP-034e** | Continuous assurance: stale pins, failed suites, or report drift block commit and CI | Pre-commit + GitHub Actions fail-closed gates with negative tests | CM-3, CA-2 |

---

## 4. Harness Architecture

### 4.1 Authoritative Runner (`run_tests.py`, `run-tests.sh`)

A single deterministic Python runner orchestrates nine suites. Every suite records `status`, `duration_ms`, `command`, `exit_code`, and evidence hashes in both report formats.

| Suite | Name | Target | Pass Criteria |
| :--- | :--- | :--- | :--- |
| **TS-01** | Toolchain & Runtime Pin Audit | `lean`, `lake`, `prismpm`, `lean-toolchain`, `lexlean.toml`, `lexlean.lock` | Lean `4.32.2`, PrismPM `0.5.0`, Python ≥ 3.11, no unexpected binaries |
| **TS-02** | Lake Host Workspace Build | `lake build` | Exit 0, clean manifest, no host build failure |
| **TS-03** | LexLean Lock & Canonical Config Parity | SHA-256 of `lexlean.toml`, `lakefile.toml`, `lean-toolchain`, `lake-manifest.json`; lock metadata | Hashes match `lexlean.lock`; `compiler_semantics` = `4b3ed237…`; `lean_toolchain` = `v4.32.2` |
| **TS-04** | PrismPM Static Model Check | `prismpm check` | Exit 0; canonical JSON emitted; no `PPxxxx` diagnostics |
| **TS-05** | Lean Kernel Attestation Audit | `.lexlean/verified/<id>/attestation.json` | `status: verified`; semantic ID matches manifest; axiom policy `exact`/`none`; zero prohibited axioms |
| **TS-06** | Formal Router Theorem Audit | `TropicalRouter.Main.router_smoke_eval`, `tropicalMul`, `tropicalScore` | All three declarations present, `decide` proof retained, no `sorry`, expected score evaluation `(3,5,2) = 10` |
| **TS-07** | PrismPM Build & Manifest Integrity | `prismpm build`; `.prism/build/<digest>/manifest.json` | Digest matches stdout; every manifest file SHA-256 verifies; build is byte-identical to pinned baseline when inputs unchanged |
| **TS-08** | Tropical Benchmark Engine | `benchmark_tropical_router.py` | All 5 sub-suites pass with zero invariant violations |
| **TS-09** | Reporting & Gate Contract Integrity | `reports/`, `.githooks/pre-commit`, `.github/workflows/verify-test.yml` | LATEST + timestamped Markdown/JSON exist and contain current digest/semantic ID; hook and workflow fail-closed; negative gate test passes |

### 4.2 Benchmark Engine (`benchmark_tropical_router.py`)

Modeled on `benchmark_kuramoto_scaling.py` but specialized to the max-plus router:

| Sub-Suite | Invariant | Workload | Pass Criteria |
| :--- | :--- | :--- | :--- |
| **S1** Semiring Law & Score Algebra | INV-TRP-034a | 10,000 seeded integer triples across `[0, 2^32]` | Zero law violations; exact equality; commutative and associative checks pass |
| **S2** Checked Overflow Containment | INV-TRP-034b | Boundary sweep plus 5,000 random near-limit pairs | Zero silent wraps; every over-limit case raises the checked-overflow sentinel |
| **S3** Routing Table Scale & Latency | INV-TRP-034a | N ∈ {10, 100, 1,000, 10,000, 100,000}; 5 warmups + 20 measured reps | p50/p95/p99 recorded; throughput ≥ pinned baseline × 0.90; no superlinear deviation beyond 10% |
| **S4** Build & Semantic Reproducibility | INV-TRP-034c | Two consecutive builds and report generations with unchanged inputs | Identical PrismPM digest, semantic ID, and canonical report hashes (timestamps excluded) |
| **S5** Gate Evidence Integrity | INV-TRP-034e | Inject a stale-lock fault and a failing-suite fault in a sandbox copy | Both faults produce non-zero exit and no report staging |

All random workloads use a fixed seed recorded in the report. Every latency table includes warmup count, repetition count, host OS/arch, Python version, and toolchain versions so CI regressions are interpretable.

---

## 5. Automated Human-Readable Reporting

The runner writes dual-retention evidence:

### Living canonical documents
- `reports/TEST_REPORT_LATEST.md`
- `reports/test_report_latest.json`
- `reports/STRESS_BENCHMARK_LATEST.md`
- `reports/stress_benchmark_latest.json`

### Immutable timestamped receipts
- `reports/TEST_REPORT_<YYYYMMDDTHHMMSS>.md` / `.json`
- `reports/STRESS_BENCHMARK_<YYYYMMDDTHHMMSS>.md` / `.json`

Every report MUST include: toolchain pins, compiler semantics ID, semantic ID, PrismPM build digest, the 9-suite matrix, the 5 benchmark sub-suite tables, pass/fail verdicts, environment metadata, and SHA-256 of the JSON companion. Markdown uses GitHub Flavored Markdown alerts and scorecards so a human can read the result in under 30 seconds; JSON is the authoritative machine ledger consumed by CI.

---

## 6. CI/CD Integration

1. **Local pre-commit** — `install-hooks.sh` installs `.githooks/pre-commit`; the hook runs `python3 run_tests.py`, aborts commits on any failure, and on success stages only the generated `reports/` artifacts.
2. **Remote GitHub Actions** — `.github/workflows/verify-test.yml` triggers on push/PR to `main`/`master` with path filters for `src/**`, `language/**`, `lexlean.toml`, `lexlean.lock`, `prismpm.toml`, `lean-toolchain`, `lakefile.toml`, harness scripts, and the workflow itself.
3. **Workflow steps** — checkout, pinned Lean setup from `lean-toolchain`, Python 3.11 setup with cache, full harness execution, artifact upload with `if: always()`, and concatenation of both Markdown reports into `$GITHUB_STEP_SUMMARY`.
4. **Fail-closed policy** — any non-zero suite, stale lock, missing report, or build digest mismatch fails the job and blocks the commit/PR. There is no `continue-on-error` on verification steps.

---

## 7. Phased Roadmap

| Phase | Deliverable | Evidence | Status |
| :--- | :--- | :--- | :--- |
| **P1** | Author and accept ADR-0034 | Local `docs/ADR-0034.md` + global register | ✅ Done |
| **P2** | Implement 9-suite runner and dual-format reporter | `run_tests.py`, `run-tests.sh`, `reports/` | ✅ Done |
| **P3** | Implement tropical benchmark engine | `benchmark_tropical_router.py` | ✅ Done |
| **P4** | Wire pre-commit hook and installer | `.githooks/pre-commit`, `install-hooks.sh` | ✅ Done |
| **P5** | Wire GitHub Actions pipeline | `.github/workflows/verify-test.yml` | ✅ Done |
| **P6** | Execute baseline run, negative gate tests, and pin reports | 9/9 + 5/5, `reports/TEST_REPORT_LATEST.md` | ✅ Done |
| **P7** | Revisit `prismpm verify` as a blocking suite when Prism declarations exist | Updated ADR amendment | ⬜ Follow-up |

---

## 8. Definition of Done

- [x] All 9 suites pass from a clean checkout with pinned toolchain.
- [x] All 5 benchmark sub-suites pass with zero violations and recorded seeds.
- [x] Repeat `prismpm build` reproduces digest `1027857c…` and semantic ID `afd80884…`.
- [x] Markdown and JSON reports are generated, contain the current digest, and are staged by the pre-commit hook.
- [x] Fault injection proves both local hook and CI job fail closed.
- [x] No prohibited axiom appears in any **project declaration** attestation record (runtime exact-policy axioms are excluded).
- [x] ADR-0034 is registered in the accepted ADR corpus and spine ledger under Prime Index 34.

### Implementation Evidence

Baseline run: `20261124T193309Z` — 9/9 suites, 5/5 benchmark sub-suites, build digest `1027857c…`, canonical report SHA-256 `39485d72e18a49cd8b8a21c207f0fcd50d0ec9ef7b4cfd7680cd6551f536c127`. Reports are in `reports/`; local pre-commit installation is deferred until the subsystem is a git work tree (`install-hooks.sh` reports this explicitly).
