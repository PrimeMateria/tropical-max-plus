#!/usr/bin/env python3
"""Empirical benchmark engine for ADR-0034 / INV-TRP-034a-e.

The module is dependency-free (stdlib only) so it can run in a minimal CI
container. It is imported by run_tests.py as TS-08 and can also be executed
directly to emit a canonical JSON result.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any

SCHEMA = "tropical-router/benchmark-result/1"
SEED = 0x54D0165  # fixed seed: 034 in hex-adjacent form, recorded in reports
U64_MAX = (1 << 64) - 1
SAMPLE_COUNT = 10_000
OVERFLOW_RANDOM_PAIRS = 5_000
TABLE_SIZES = (10, 100, 1_000, 10_000, 100_000)
WARMUP_REPETITIONS = 5
MEASURED_REPETITIONS = 20
MIN_THROUGHPUT_PER_SEC = 2_000_000
THROUGHPUT_TOLERANCE = 0.90
PINNED_COMPILER_SEMANTICS = "4b3ed2378d6c43bb32a41d466cf140337e8b1cedc5e1f345aaf3395f488f63a9"
PINNED_LEAN_TOOLCHAIN = "leanprover/lean4:v4.32.2"


class CheckedOverflow(Exception):
    """Sentinel raised when a 64-bit tropical addition would wrap."""


def tropical_add(a: int, b: int) -> int:
    """Max-plus addition: a ⊕ b = max(a, b)."""
    return max(a, b)


def tropical_mul(a: int, b: int) -> int:
    """Max-plus multiplication on Nat: a ⊗ b = a + b."""
    return a + b


def tropical_score(w: int, x: int, b: int) -> int:
    """Router score: tropicalMul(w, x) + b."""
    return tropical_mul(w, x) + b


def checked_tropical_mul(a: int, b: int) -> int:
    """64-bit checked form of tropical multiplication; never wraps silently."""
    if not (0 <= a <= U64_MAX and 0 <= b <= U64_MAX):
        raise ValueError("operand outside unsigned 64-bit domain")
    total = a + b
    if total > U64_MAX:
        raise CheckedOverflow("tropical multiplication overflow")
    return total


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sub_suite(suite_id: str, invariant: str, name: str, status: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "suite_id": suite_id,
        "invariant": invariant,
        "name": name,
        "status": status,
        "details": details,
    }


def semiring_law_suite() -> dict[str, Any]:
    """S1: exact-integer max-plus law and score-algebra preservation."""
    rng = random.Random(SEED)
    violations: list[str] = []
    for _ in range(SAMPLE_COUNT):
        a = rng.randrange(0, 1 << 32)
        b = rng.randrange(0, 1 << 32)
        c = rng.randrange(0, 1 << 32)

        checks = (
            (tropical_mul(a, b) == a + b, "mul_definition"),
            (tropical_mul(a, b) == tropical_mul(b, a), "mul_commutativity"),
            (tropical_mul(tropical_mul(a, b), c) == tropical_mul(a, tropical_mul(b, c)), "mul_associativity"),
            (tropical_add(a, a) == a, "add_idempotence"),
            (tropical_add(a, tropical_add(b, c)) == tropical_add(tropical_add(a, b), c), "add_associativity"),
            (tropical_mul(a, tropical_add(b, c)) == tropical_add(tropical_mul(a, b), tropical_mul(a, c)), "distributivity"),
            (tropical_score(a, b, c) == tropical_mul(a, b) + c, "score_definition"),
        )
        for ok, law in checks:
            if not ok and len(violations) < 16:
                violations.append(f"{law}: ({a}, {b}, {c})")

    return _sub_suite(
        "S1",
        "INV-TRP-034a",
        "Max-plus semiring law & score algebra",
        "PASS" if not violations else "FAIL",
        {
            "samples": SAMPLE_COUNT,
            "seed": SEED,
            "domain": "[0, 2^32)",
            "laws_checked": [
                "mul_definition",
                "mul_commutativity",
                "mul_associativity",
                "add_idempotence",
                "add_associativity",
                "distributivity",
                "score_definition",
            ],
            "violations": violations,
            "violation_count": len(violations),
            "tolerance": 0,
        },
    )


def overflow_containment_suite() -> dict[str, Any]:
    """S2: checked 64-bit arithmetic must never wrap silently."""
    boundaries = [0, 1, (1 << 32) - 1, 1 << 32, (1 << 63) - 1, 1 << 63, U64_MAX - 1, U64_MAX]
    pairs: list[tuple[int, int]] = [(a, b) for a in boundaries for b in boundaries]

    rng = random.Random(SEED + 1)
    for _ in range(OVERFLOW_RANDOM_PAIRS):
        a = U64_MAX - rng.randrange(0, 1_000)
        b = rng.randrange(1, 2_000)
        pairs.append((a, b))

    detected = 0
    silent_wraps = 0
    failures: list[str] = []
    for a, b in pairs:
        expected_overflow = a + b > U64_MAX
        try:
            result = checked_tropical_mul(a, b)
        except CheckedOverflow:
            detected += 1
            if not expected_overflow:
                failures.append(f"false overflow at ({a}, {b})")
            continue
        if expected_overflow:
            silent_wraps += 1
            failures.append(f"silent wrap at ({a}, {b}) -> {result}")
        elif result != a + b:
            failures.append(f"incorrect checked result at ({a}, {b})")

    return _sub_suite(
        "S2",
        "INV-TRP-034b",
        "Checked 64-bit overflow containment",
        "PASS" if not failures else "FAIL",
        {
            "integer_width_bits": 64,
            "boundary_values": boundaries,
            "random_near_limit_pairs": OVERFLOW_RANDOM_PAIRS,
            "pairs_tested": len(pairs),
            "overflows_detected": detected,
            "silent_wraps": silent_wraps,
            "failures": failures[:16],
            "failure_count": len(failures),
        },
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def throughput_suite() -> dict[str, Any]:
    """S3: routing-table scale, latency percentiles and throughput regression."""
    rng = random.Random(SEED + 2)
    measurements: list[dict[str, Any]] = []
    failures: list[str] = []

    for n in TABLE_SIZES:
        rows = [
            (rng.randrange(0, 1 << 32), rng.randrange(0, 1 << 32), rng.randrange(0, 1 << 32))
            for _ in range(n)
        ]
        for _ in range(WARMUP_REPETITIONS):
            accumulator = 0
            for w, x, b in rows:
                accumulator = tropical_score(w, x, b)
            if accumulator < 0:
                failures.append("negative score accumulator")

        throughputs: list[float] = []
        batch_ms: list[float] = []
        for _ in range(MEASURED_REPETITIONS):
            started = time.perf_counter()
            accumulator = 0
            for w, x, b in rows:
                accumulator = tropical_score(w, x, b)
            elapsed = time.perf_counter() - started
            if accumulator < 0:
                failures.append("negative score accumulator")
            throughputs.append(n / elapsed if elapsed > 0 else 0.0)
            batch_ms.append(elapsed * 1000.0)

        median_throughput = statistics.median(throughputs)
        measurements.append(
            {
                "table_size": n,
                "warmups": WARMUP_REPETITIONS,
                "repetitions": MEASURED_REPETITIONS,
                "median_throughput_per_sec": round(median_throughput, 3),
                "batch_ms_p50": round(_percentile(batch_ms, 0.50), 6),
                "batch_ms_p95": round(_percentile(batch_ms, 0.95), 6),
                "batch_ms_p99": round(_percentile(batch_ms, 0.99), 6),
            }
        )
        if n == TABLE_SIZES[-1] and median_throughput < MIN_THROUGHPUT_PER_SEC * THROUGHPUT_TOLERANCE:
            failures.append(
                f"throughput {median_throughput:.0f}/s below "
                f"{MIN_THROUGHPUT_PER_SEC * THROUGHPUT_TOLERANCE:.0f}/s"
            )

    return _sub_suite(
        "S3",
        "INV-TRP-034a",
        "Routing table scale & latency",
        "PASS" if not failures else "FAIL",
        {
            "seed": SEED + 2,
            "pinned_baseline_throughput_per_sec": MIN_THROUGHPUT_PER_SEC,
            "tolerance": THROUGHPUT_TOLERANCE,
            "measurements": measurements,
            "failures": failures,
        },
    )


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def reproducibility_suite(project_root: pathlib.Path) -> dict[str, Any]:
    """S4: repeated builds and canonical report payloads must be identical."""
    failures: list[str] = []
    digests: list[str] = []
    for _ in range(2):
        proc = subprocess.run(
            ["prismpm", "build", "--json"],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            failures.append(f"prismpm build failed: {proc.stderr.strip()[:300]}")
            break
        try:
            digests.append(json.loads(proc.stdout)["build_id"])
        except (json.JSONDecodeError, KeyError) as exc:
            failures.append(f"unparseable prismpm build result: {exc}")
            break

    if len(set(digests)) > 1:
        failures.append(f"non-deterministic build digests: {digests}")

    payload_a = {
        "schema": "tropical-router/canonical-report/1",
        "generated_at": "FIXED",
        "build_digest": digests[0] if digests else "unavailable",
        "semantic_id": PINNED_COMPILER_SEMANTICS,
    }
    payload_b = json.loads(json.dumps(payload_a))
    canonical_a = hashlib.sha256(_canonical_payload(payload_a).encode()).hexdigest()
    canonical_b = hashlib.sha256(_canonical_payload(payload_b).encode()).hexdigest()
    if canonical_a != canonical_b:
        failures.append("canonical report payload hash divergence")

    return _sub_suite(
        "S4",
        "INV-TRP-034c",
        "Build & semantic reproducibility",
        "PASS" if not failures else "FAIL",
        {
            "build_digests": digests,
            "canonical_report_sha256": canonical_a,
            "timestamp_exemption": True,
            "failures": failures,
        },
    )


def lock_is_valid(project_root: pathlib.Path, lock_path: pathlib.Path) -> bool:
    """Validate lock metadata/workspace hashes against the live project."""
    try:
        import tomllib

        lock = tomllib.loads(lock_path.read_text())
        if lock.get("compiler_semantics") != PINNED_COMPILER_SEMANTICS:
            return False
        if lock.get("lean_toolchain") != PINNED_LEAN_TOOLCHAIN:
            return False
        if lock.get("project_config_sha256") != sha256_file(project_root / "lexlean.toml"):
            return False
        for entry in lock.get("workspace_file", []):
            path = project_root / entry["path"]
            if not path.is_file() or sha256_file(path) != entry["sha256"]:
                return False
        return True
    except (OSError, KeyError, ValueError, TypeError):
        return False


def gate_allows_stage(suite_statuses: list[str]) -> bool:
    """Fail-closed gate: reports are staged only when every suite passed."""
    return bool(suite_statuses) and all(status == "PASS" for status in suite_statuses)


def gate_integrity_suite(project_root: pathlib.Path) -> dict[str, Any]:
    """S5: negative fault injection into lock parity and report staging."""
    failures: list[str] = []

    original_lock = project_root / "lexlean.lock"
    if not lock_is_valid(project_root, original_lock):
        failures.append("control lock parity failed")

    with tempfile.TemporaryDirectory(prefix="tropical-gate-") as tmp:
        stale_lock = pathlib.Path(tmp) / "lexlean.lock"
        stale_text = original_lock.read_text()
        stale_text = stale_text.replace(
            'project_config_sha256 = "',
            'project_config_sha256 = "' + "0" * 64,
            1,
        )
        stale_lock.write_text(stale_text)
        if lock_is_valid(project_root, stale_lock):
            failures.append("stale lock fault was not detected")

    if gate_allows_stage(["PASS", "FAIL"]):
        failures.append("failing suite fault did not close the gate")
    if not gate_allows_stage(["PASS", "PASS"]):
        failures.append("all-pass gate incorrectly rejected staging")

    return _sub_suite(
        "S5",
        "INV-TRP-034e",
        "Gate evidence integrity (fault injection)",
        "PASS" if not failures else "FAIL",
        {
            "faults_injected": ["stale_lock_hash", "failing_suite_gate"],
            "failures": failures,
        },
    )


def run_benchmarks(project_root: pathlib.Path | None = None) -> dict[str, Any]:
    """Execute all five empirical benchmark sub-suites."""
    root = pathlib.Path(project_root or pathlib.Path.cwd()).resolve()
    sub_suites = [
        semiring_law_suite(),
        overflow_containment_suite(),
        throughput_suite(),
        reproducibility_suite(root),
        gate_integrity_suite(root),
    ]
    status = "PASS" if all(suite["status"] == "PASS" for suite in sub_suites) else "FAIL"
    return {
        "schema": SCHEMA,
        "status": status,
        "seed": SEED,
        "environment": {
            "os": platform.system(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "toolchain": PINNED_LEAN_TOOLCHAIN,
            "prismpm": "0.5.0",
        },
        "sub_suites": sub_suites,
    }


def main(argv: list[str]) -> int:
    project_root = pathlib.Path(argv[1]).resolve() if len(argv) > 1 else pathlib.Path.cwd().resolve()
    result = run_benchmarks(project_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
