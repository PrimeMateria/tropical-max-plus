# Tropical Max-Plus Router — Stress Benchmark Report (PASS)

> [!NOTE]
Benchmark suite result: `PASS`.

**Generated (UTC):** `20261124T193936Z`  
**Build:** `1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90`  
**Semantic ID:** `afd80884608e37187f0bf6808c47b48d96551b3b529146b4757349b35d14d142`  
**Seed:** `88932709`

| Field | Value |
| :--- | :--- |
| os | `Linux` |
| arch | `x86_64` |
| python | `3.15.2` |
| toolchain | `leanprover/lean4:v4.32.2` |
| prismpm | `0.5.0` |

| Sub-suite | Invariant | Result | Detail |
| :--- | :--- | :---: | :--- |
| `S1` | `INV-TRP-034a` | **PASS** | `{"domain": "[0, 2^32)", "laws_checked": ["mul_definition", "mul_commutativity", "mul_associativity", "add_idempotence", "add_associativity", "distributivity", "score_definition"], "samples": 10000, "seed": 88932709, "tolerance": 0, "violation_count": 0, "violations": []}` |
| `S2` | `INV-TRP-034b` | **PASS** | `{"boundary_values": [0, 1, 4294967295, 4294967296, 9223372036854775807, 9223372036854775808, 18446744073709551614, 18446744073709551615], "failure_count": 0, "failures": [], "integer_width_bits": 64, "overflows_detected": 3809, "pairs_tested": 5064, "random_near_limit_pairs": 5000, "silent_wraps": 0}` |
| `S3` | `INV-TRP-034a` | **PASS** | `{"failures": [], "measurements": [{"batch_ms_p50": 0.001487, "batch_ms_p95": 0.001903, "batch_ms_p99": 0.002223, "median_throughput_per_sec": 6727185.493, "repetitions": 20, "table_size": 10, "warmups": 5}, {"batch_ms_p50": 0.014535, "batch_ms_p95": 0.014691, "batch_ms_p99": 0.014948, "median_throughput_per_sec": 6879942.166, "repetitions": 20, "table_size": 100, "warmups": 5}, {"batch_ms_p50": 0.167952, "batch_ms_p95": 0.254856, "batch_ms_p99": 0.26929, "median_throughput_per_sec": 5955572.91, "repetitions": 20, "table_size": 1000, "warmups": 5}, {"batch_ms_p50": 1.695702, "batch_ms_p95": 2.3` |
| `S4` | `INV-TRP-034c` | **PASS** | `{"build_digests": ["1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90", "1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90"], "canonical_report_sha256": "a61767d14420732e21c858f729e9f4c487bcf6cdad18a235d726acf228432b55", "failures": [], "timestamp_exemption": true}` |
| `S5` | `INV-TRP-034e` | **PASS** | `{"failures": [], "faults_injected": ["stale_lock_hash", "failing_suite_gate"]}` |

## Throughput & Latency

| N | Median ops/s | p50 batch ms | p95 batch ms | p99 batch ms |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 6727185 | 0.001487 | 0.001903 | 0.002223 |
| 100 | 6879942 | 0.014535 | 0.014691 | 0.014948 |
| 1000 | 5955573 | 0.167952 | 0.254856 | 0.269290 |
| 10000 | 5897364 | 1.695702 | 2.311861 | 2.375462 |
| 100000 | 5721080 | 17.480811 | 28.292912 | 33.331942 |

---

Generated automatically by `run_tests.py` under ADR-0034. Do not edit by hand.
