# Tropical Max-Plus Router — Test Report (PASS)

> [!NOTE]
All verification and benchmark gates passed.

**Generated (UTC):** `20261124T193936Z`  
**Overall:** `PASS` (9/9 verification suites)  
**PrismPM build:** `1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90`  
**Semantic ID:** `afd80884608e37187f0bf6808c47b48d96551b3b529146b4757349b35d14d142`  
**Compiler semantics:** `4b3ed2378d6c43bb32a41d466cf140337e8b1cedc5e1f345aaf3395f488f63a9`  
**Source digest:** `45a96aa1d962573cd7ed66ef1b129a8aa4e861704a6fe315cfa59435240a7cd0`  
**Canonical SHA-256:** `fe32675e5a146e91e276467b3142503e7babbf8a80885e6ff01ccc9c586d2021`  
**JSON companion SHA-256:** `5b9689c9e4c5a359b243352b8faaffcce56ede4e3b776d1043cea0de14194adb`

## 1. Toolchain & Environment

| Field | Value |
| :--- | :--- |
| lean | `leanprover/lean4:v4.32.2` |
| prismpm | `prismpm 0.5.0` |
| language | `lexlean/project/1 (Language 1.2)` |
| python | `3.15.2` |
| os | `Linux` |
| arch | `x86_64` |

## 2. Nine-Suite Verification Matrix

| Suite | Name | Target | Result | Duration (ms) | Failures |
| :--- | :--- | :--- | :---: | ---: | :--- |
| `TS-01` | Toolchain & Runtime Pin Audit | `lean --version; lake --version; prismpm --version; lean-toolchain` | **PASS** | 145.607 | — |
| `TS-02` | Lake Host Workspace Build | `lake build --allow-empty` | **PASS** | 166.690 | — |
| `TS-03` | LexLean Lock & Canonical Config Parity | `lexlean.lock SHA-256 parity` | **PASS** | 0.818 | — |
| `TS-04` | PrismPM Static Model Check | `prismpm check --json` | **PASS** | 2912.444 | — |
| `TS-05` | Lean Kernel Attestation Audit | `.lexlean/verified/*/attestation.json (project declarations only)` | **PASS** | 11.475 | — |
| `TS-06` | Formal Router Theorem Audit | `src/Main.lex.tex formal declaration audit` | **PASS** | 0.262 | — |
| `TS-07` | PrismPM Build & Manifest Integrity | `prismpm build --json + manifest SHA-256 verification` | **PASS** | 3213.656 | — |
| `TS-08` | Tropical Benchmark Engine | `benchmark_tropical_router.py (S1-S5)` | **PASS** | 7063.210 | — |
| `TS-09` | Reporting & Gate Contract Integrity | `reports schema, hook, workflow, and fault-injection contract` | **PASS** | 13.374 | — |

## 3. Empirical Benchmark Engine

**Status:** `PASS` · **Seed:** `88932709`

| Sub-suite | Invariant | Name | Result | Summary |
| :--- | :--- | :--- | :---: | :--- |
| `S1` | `INV-TRP-034a` | Max-plus semiring law & score algebra | **PASS** | samples=10000, violation_count=0 |
| `S2` | `INV-TRP-034b` | Checked 64-bit overflow containment | **PASS** | pairs_tested=5064, silent_wraps=0, failures=[] |
| `S3` | `INV-TRP-034a` | Routing table scale & latency | **PASS** | failures=[] |
| `S4` | `INV-TRP-034c` | Build & semantic reproducibility | **PASS** | build_digests=['1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90', '1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90'], failures=[] |
| `S5` | `INV-TRP-034e` | Gate evidence integrity (fault injection) | **PASS** | failures=[] |

### 3.1 Routing Table Scale & Latency

| N | Median ops/s | Batch p50 (ms) | Batch p95 (ms) | Batch p99 (ms) |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 6727185 | 0.001487 | 0.001903 | 0.002223 |
| 100 | 6879942 | 0.014535 | 0.014691 | 0.014948 |
| 1000 | 5955573 | 0.167952 | 0.254856 | 0.269290 |
| 10000 | 5897364 | 1.695702 | 2.311861 | 2.375462 |
| 100000 | 5721080 | 17.480811 | 28.292912 | 33.331942 |

## 4. Gate Scope Note

`prismpm verify` is **informational** for this baseline: PP5003: snapshot contains no Prism declarations in ADR-0034 baseline. The blocking release gate is `prismpm check` + `prismpm build`.

---

Generated automatically by `run_tests.py` under ADR-0034. Do not edit by hand.
