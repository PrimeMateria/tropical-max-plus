# Tropical Max-Plus Router

[![Verification](https://img.shields.io/badge/ADR--0034-9%2F9%20PASS-success.svg)](#current-test-results)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-Pre--Commit%20%2B%20GHA-success.svg)](#cicd-and-governance)
[![Toolchain](https://img.shields.io/badge/Lean-4.32.2-blue.svg)](#current-state)
[![PrismPM](https://img.shields.io/badge/PrismPM-0.5.0-blue.svg)](#current-state)

Formal LexLean Language 1.2 model of tropical max-plus routing arithmetic, compiled and published through PrismPM, with a production-grade benchmark harness, automated human-readable reporting, and fail-closed CI/CD gates governed by [ADR-0034](docs/ADR-0034.md).

---

## Executive Summary

This subsystem formalizes the tropical router core:

- `tropicalMul(w, x) = w + x` — max-plus multiplication on `Nat`
- `tropicalScore(w, x, b) = tropicalMul(w, x) + b` — router score
- `router_smoke_eval : tropicalScore 3 5 2 = 10` — kernel-certified smoke theorem via `decide`

It is built with `leanprover/lean4:v4.32.2`, verified through the language-1.2 compiler embedded in `prismpm 0.5.0`, and published as a content-addressed release. A prior release was blocked by stale toolchain and lock pins (`v4.32.1` → `v4.32.2`, compiler semantics `1427f8b6…` → `4b3ed237…`). ADR-0034 was created in direct response: the harness now detects exactly that class of drift **before commit**, not during release.

The current baseline is green: **9/9 verification suites** and **5/5 benchmark sub-suites** pass, with reproducible build digest `1027857c…`, semantic ID `afd80884…`, and dual Markdown/JSON reports generated from execution receipts.

---

## Current State

| Area | Status | Evidence |
| :--- | :--- | :--- |
| Formal model | Implemented | [`src/Main.lex.tex`](src/Main.lex.tex) — 2 executable definitions + 1 `decide` theorem |
| Language | LexLean `project/1`, Language 1.2 | [`lexlean.toml`](lexlean.toml) |
| Toolchain | Lean `4.32.2`, Lake `5.0.0`, PrismPM `0.5.0` | [`lean-toolchain`](lean-toolchain), [`lexlean.lock`](lexlean.lock) |
| Static verification | Passing | `prismpm check --json` |
| Kernel attestation | `verified`, zero prohibited axioms in `TropicalRouter.*` declarations | `.lexlean/verified/*/attestation.json` |
| Production release | Published | `.prism/build/1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90/` |
| Verification harness | Implemented and passing | [`run_tests.py`](run_tests.py), 9 suites |
| Benchmark engine | Implemented and passing | [`benchmark_tropical_router.py`](benchmark_tropical_router.py), 5 sub-suites |
| Living reports | Generated and tracked | [`reports/TEST_REPORT_LATEST.md`](reports/TEST_REPORT_LATEST.md), [`reports/STRESS_BENCHMARK_LATEST.md`](reports/STRESS_BENCHMARK_LATEST.md) |
| Git working tree | Initialized on `main`, clean at `fbaeee2c40e57616e51dd1fa8c02618ce8016a2f` | `.git/` |
| Pre-commit hook | Installed | `.git/hooks/pre-commit` |
| GitHub Actions | Configured | [`.github/workflows/verify-test.yml`](.github/workflows/verify-test.yml) |
| Git remote | Not configured | `git remote -v` is empty |

**Important scope note:** `prismpm verify` is informational for this baseline. The snapshot contains no Prism declarations, so it exits `PP5003`. The blocking release gate is intentionally `prismpm check` + `prismpm build`. Promotion of `prismpm verify` to a blocking suite requires an ADR amendment; see [ADR-0034 §7](docs/ADR-0034.md).

The standalone `lexlean` CLI in this environment is language 1.0 and rejects `lexlean/project/1` language-1.2 configurations. All language-1.2 verification is therefore driven through PrismPM's embedded compiler rather than the standalone CLI.

---

## Current Test Results

Latest baseline run: `20261124T193936Z` · **overall PASS** · total suite time ≈ **13.53 s**.

### Verification Matrix

| Suite | Name | Result | Duration (ms) |
| :--- | :--- | :---: | ---: |
| `TS-01` | Toolchain & Runtime Pin Audit | **PASS** | 145.607 |
| `TS-02` | Lake Host Workspace Build | **PASS** | 166.690 |
| `TS-03` | LexLean Lock & Canonical Config Parity | **PASS** | 0.818 |
| `TS-04` | PrismPM Static Model Check | **PASS** | 2912.444 |
| `TS-05` | Lean Kernel Attestation Audit | **PASS** | 11.475 |
| `TS-06` | Formal Router Theorem Audit | **PASS** | 0.262 |
| `TS-07` | PrismPM Build & Manifest Integrity | **PASS** | 3213.656 |
| `TS-08` | Tropical Benchmark Engine | **PASS** | 7063.210 |
| `TS-09` | Reporting & Gate Contract Integrity | **PASS** | 13.374 |

### Benchmark Sub-Suites

| Sub-suite | Invariant | Result | Key measurement |
| :--- | :--- | :---: | :--- |
| `S1` Semiring law & score algebra | `INV-TRP-034a` | **PASS** | 10,000 seeded samples, 7 laws, 0 violations |
| `S2` Checked 64-bit overflow | `INV-TRP-034b` | **PASS** | 5,064 pairs, 3,809 overflows detected, 0 silent wraps |
| `S3` Routing table scale & latency | `INV-TRP-034a` | **PASS** | N = 10…100,000; see table below |
| `S4` Build & semantic reproducibility | `INV-TRP-034c` | **PASS** | Two builds produced identical digest `1027857c…` |
| `S5` Gate evidence integrity | `INV-TRP-034e` | **PASS** | Stale-lock and failing-suite faults both rejected |

### Throughput & Latency (Python reference harness, fixed seed `88932709`)

| N | Median ops/s | Batch p50 (ms) | Batch p95 (ms) | Batch p99 (ms) |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 6,727,185 | 0.001487 | 0.001903 | 0.002223 |
| 100 | 6,879,942 | 0.014535 | 0.014691 | 0.014948 |
| 1,000 | 5,955,573 | 0.167952 | 0.254856 | 0.269290 |
| 10,000 | 5,897,364 | 1.695702 | 2.311861 | 2.375462 |
| 100,000 | 5,721,080 | 17.480811 | 28.292912 | 33.331942 |

These are reference-harness numbers, not Rust production-target SLAs. The gate enforces a conservative floor of `2,000,000 ops/s × 0.90` at N = 100,000 so CI machine variance does not produce false failures while still catching order-of-magnitude regressions.

### Evidence Hashes

| Artifact | SHA-256 |
| :--- | :--- |
| PrismPM build | `1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90` |
| LexLean semantic ID | `afd80884608e37187f0bf6808c47b48d96551b3b529146b4757349b35d14d142` |
| Compiler semantics | `4b3ed2378d6c43bb32a41d466cf140337e8b1cedc5e1f345aaf3395f488f63a9` |
| Source input digest | `45a96aa1d962573cd7ed66ef1b129a8aa4e861704a6fe315cfa59435240a7cd0` |
| Canonical report | `fe32675e5a146e91e276467b3142503e7babbf8a80885e6ff01ccc9c586d2021` |
| JSON companion | `5b9689c9e4c5a359b243352b8faaffcce56ede4e3b776d1043cea0de14194adb` |

---

## Quick Start

```bash
cd /run/media/multiplic/AGI/prismagi/mount/ROUTERS/tropical-max-plus

# Full authoritative verification (9 suites + 5 benchmarks), regenerates reports
./run-tests.sh

# Static check and production build directly
prismpm check --json
prismpm build --json

# Benchmark engine standalone (JSON to stdout)
python3 benchmark_tropical_router.py .

# Install the pre-commit gate (already installed in the current working tree)
./install-hooks.sh
```

`run_tests.py` exits non-zero on any suite failure and still writes diagnostic reports. The pre-commit hook runs the same runner and stages only `reports/TEST_REPORT_LATEST.md`, `reports/test_report_latest.json`, `reports/STRESS_BENCHMARK_LATEST.md`, and `reports/stress_benchmark_latest.json` when everything passes.

A negative test on an isolated copy with a corrupted `compiler_semantics` pin confirmed fail-closed behavior: the stale-lock, static-check, build, benchmark, and gate-contract suites all failed and the runner exited `1`.

---

## Repository Layout

```text
tropical-max-plus/
├── src/Main.lex.tex                 # Formal max-plus model and decide theorem
├── language/                        # prism.arch / prism.qual / prism.sec lexicons
├── docs/
│   ├── PLAN-ADR-0034.md              # Implementation plan
│   └── ADR-0034.md                   # Accepted architecture decision
├── reports/
│   ├── TEST_REPORT_LATEST.md         # Human-readable verification report
│   ├── test_report_latest.json       # Machine-readable verification ledger
│   ├── STRESS_BENCHMARK_LATEST.md    # Human-readable benchmark report
│   ├── stress_benchmark_latest.json  # Machine-readable benchmark ledger
│   └── *_20*.md / *_20*.json         # Timestamped immutable receipts (git-ignored)
├── run_tests.py / run-tests.sh       # Authoritative harness
├── benchmark_tropical_router.py      # Empirical benchmark + fault injection
├── .githooks/pre-commit              # Fail-closed local gate
├── install-hooks.sh                  # Hook installer
├── .github/workflows/verify-test.yml # Remote CI gate
└── .prism/build/<digest>/            # Content-addressed PrismPM release
```

---

## CI/CD and Governance

- **Local:** `.githooks/pre-commit` runs the full harness for code/config changes, blocks the commit on failure, and auto-stages fresh reports on success. Documentation-only commits (`README.md`, `docs/`, `reports/`, `LICENSE`) skip the harness to avoid regenerating evidence without changing behavior.
- **Remote:** `.github/workflows/verify-test.yml` triggers on push/PR to `main`/`master`, pins Lean from `lean-toolchain`, runs `python3 run_tests.py`, uploads `reports/` with `if: always()`, and publishes both Markdown reports to `$GITHUB_STEP_SUMMARY`. Verification steps set `continue-on-error: false`.
- **Plan:** [`docs/PLAN-ADR-0034.md`](docs/PLAN-ADR-0034.md) · [global planning copy](file:///home/multiplic/adr/01_planning/PLAN-ADR-0034.md)
- **ADR:** [`docs/ADR-0034.md`](docs/ADR-0034.md) · [global accepted record](file:///home/multiplic/adr/03_accepted/ADR-0034-tropical-max-plus-router-benchmark-test-harness-and-ci-cd.md)
- **Spine ledger:** Prime Index 34 in `/home/multiplic/adr/spine-ledger.jsonl`

Reference parity: [`kuramoto-protocol-r3`](file:///run/media/multiplic/AGI/prismagi/mount/SUBSYSTEMS/kuramoto-protocol-r3) (ADR-0024/0025/0026) and the router lineage in ADR-0033.

---

## Next Actions

1. Add a GitHub `origin` remote when the repository URL is available:
   ```bash
   git remote add origin <url>
   git push -u origin main
   ```
2. Add Prism declarations to the semantic snapshot, then amend ADR-0034 to promote `prismpm verify` from informational to a blocking suite.
3. Re-accredit the pinned build digest whenever source, lockfile, toolchain, or compiler-semantics inputs change; TS-07 enforces this via the pinned source-digest baseline.
