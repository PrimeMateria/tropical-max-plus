#!/usr/bin/env python3
"""Authoritative 9-suite verification runner for ADR-0034.

Produces dual-format living reports under reports/ and fails closed on any
verification, benchmark, or gate-contract failure.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
import time
import tomllib
from typing import Any, Callable

import benchmark_tropical_router as bench

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
REPORT_DIR = PROJECT_ROOT / "reports"

SCHEMA = "tropical-router/test-report/1"
EXPECTED_LEAN = "4.32.2"
EXPECTED_PRISM_VERSION = "prismpm 0.5.0"
PINNED_COMPILER_SEMANTICS = bench.PINNED_COMPILER_SEMANTICS
PINNED_BUILD_DIGEST = "1027857c266519abf79bcbd6d5dd95ed72f0d731ca7c66ecb3e250f3029dfa90"
PINNED_SOURCE_DIGEST = "45a96aa1d962573cd7ed66ef1b129a8aa4e861704a6fe315cfa59435240a7cd0"
PINNED_SEMANTIC_ID = "afd80884608e37187f0bf6808c47b48d96551b3b529146b4757349b35d14d142"
PROHIBITED_AXIOMS = {"sorryAx", "Classical.choice", "Quot.sound", "propext"}
PROJECT_NAMESPACE = "TropicalRouter."


def run_cmd(args: list[str], cwd: pathlib.Path = PROJECT_ROOT) -> dict[str, Any]:
    try:
        proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
        return {
            "command": " ".join(args),
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except OSError as exc:
        return {
            "command": " ".join(args),
            "exit_code": 127,
            "stdout": "",
            "stderr": str(exc),
        }


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(root: pathlib.Path = PROJECT_ROOT) -> str:
    """Deterministic digest of all compiler-relevant inputs."""
    paths = [
        pathlib.Path(rel)
        for rel in (
            "src/Main.lex.tex",
            "lexlean.toml",
            "lexlean.lock",
            "lakefile.toml",
            "lake-manifest.json",
            "lean-toolchain",
            "prismpm.toml",
        )
    ]
    paths.extend(p.relative_to(root) for p in (root / "language").rglob("*") if p.is_file())
    digest = hashlib.sha256()
    for rel in sorted(paths, key=str):
        digest.update(str(rel).encode() + b"\0")
        digest.update((root / rel).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def fail(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "FAIL", "message": message, **extra}


# ---------------------------------------------------------------------------
# TS-01 Toolchain & Runtime Pin Audit
# ---------------------------------------------------------------------------
def suite_ts01() -> dict[str, Any]:
    failures: list[str] = []
    lean = run_cmd(["lean", "--version"])
    lake = run_cmd(["lake", "--version"])
    prism = run_cmd(["prismpm", "--version"])
    toolchain_file = (PROJECT_ROOT / "lean-toolchain").read_text().strip()

    if lean["exit_code"] != 0 or f"version {EXPECTED_LEAN}" not in lean["stdout"]:
        failures.append("lean version mismatch")
    if lake["exit_code"] != 0 or "Lake version" not in lake["stdout"]:
        failures.append("lake unavailable")
    if prism["exit_code"] != 0 or EXPECTED_PRISM_VERSION not in prism["stdout"]:
        failures.append("prismpm version mismatch")
    if toolchain_file != f"leanprover/lean4:v{EXPECTED_LEAN}":
        failures.append("lean-toolchain pin mismatch")
    if platform.python_version_tuple()[:2] < ("3", "11"):
        failures.append("Python < 3.11")

    return {
        "status": "PASS" if not failures else "FAIL",
        "target": "lean --version; lake --version; prismpm --version; lean-toolchain",
        "details": {
            "lean": lean["stdout"],
            "lake": lake["stdout"],
            "prismpm": prism["stdout"],
            "python": platform.python_version(),
            "toolchain_file": toolchain_file,
            "standalone_lexlean_required": False,
        },
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# TS-02 Lake Host Workspace Build
# ---------------------------------------------------------------------------
def suite_ts02() -> dict[str, Any]:
    build = run_cmd(["lake", "build", "--allow-empty"])
    return {
        "status": "PASS" if build["exit_code"] == 0 else "FAIL",
        "target": "lake build --allow-empty",
        "details": build,
        "failures": [] if build["exit_code"] == 0 else ["lake build failed"],
    }


# ---------------------------------------------------------------------------
# TS-03 LexLean Lock & Canonical Configuration Parity
# ---------------------------------------------------------------------------
def suite_ts03() -> dict[str, Any]:
    lock_path = PROJECT_ROOT / "lexlean.lock"
    lock = tomllib.loads(lock_path.read_text())
    failures: list[str] = []

    if lock.get("spec") != "lexlean/lock/2":
        failures.append("unexpected lock spec")
    if lock.get("language") != "1.2":
        failures.append("unexpected language version")
    if lock.get("lean_toolchain") != f"leanprover/lean4:v{EXPECTED_LEAN}":
        failures.append("lock toolchain mismatch")
    if lock.get("compiler_semantics") != PINNED_COMPILER_SEMANTICS:
        failures.append("compiler semantics mismatch")
    if lock.get("project_config_sha256") != sha256_file(PROJECT_ROOT / "lexlean.toml"):
        failures.append("project_config_sha256 mismatch")

    workspace: list[dict[str, str]] = []
    for entry in lock.get("workspace_file", []):
        path = PROJECT_ROOT / entry["path"]
        actual = sha256_file(path) if path.is_file() else "missing"
        workspace.append({"path": entry["path"], "expected": entry["sha256"], "actual": actual})
        if actual != entry["sha256"]:
            failures.append(f"workspace hash mismatch: {entry['path']}")

    return {
        "status": "PASS" if not failures else "FAIL",
        "target": "lexlean.lock SHA-256 parity",
        "details": {
            "compiler_semantics": lock.get("compiler_semantics"),
            "lean_toolchain": lock.get("lean_toolchain"),
            "project_config_sha256": lock.get("project_config_sha256"),
            "workspace_file": workspace,
        },
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# TS-04 PrismPM Static Model Check
# ---------------------------------------------------------------------------
def suite_ts04() -> dict[str, Any]:
    check = run_cmd(["prismpm", "check", "--json"])
    failures: list[str] = []
    result: dict[str, Any] = {}
    if check["exit_code"] != 0:
        failures.append(f"prismpm check failed ({check['stderr'][:200]})")
    else:
        try:
            result = json.loads(check["stdout"])
        except json.JSONDecodeError:
            failures.append("prismpm check emitted non-JSON output")
    if result and result.get("schema") != "prismpm/check-result/1":
        failures.append("unexpected check result schema")
    if result and result.get("semantic_id") != PINNED_SEMANTIC_ID:
        failures.append("semantic ID drift")

    return {
        "status": "PASS" if not failures else "FAIL",
        "target": "prismpm check --json",
        "details": result or check,
        "failures": failures,
        "semantic_id": result.get("semantic_id"),
    }


# ---------------------------------------------------------------------------
# TS-05 Lean Kernel Attestation Audit
# ---------------------------------------------------------------------------
def suite_ts05(semantic_id: str | None) -> dict[str, Any]:
    failures: list[str] = []
    attestations = sorted((PROJECT_ROOT / ".lexlean" / "verified").glob("*/attestation.json"))
    if not attestations:
        return fail("no attestation records found", target=".lexlean/verified/*/attestation.json")

    matching = []
    for path in attestations:
        try:
            record = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if record.get("semantic_id") == semantic_id and record.get("status") == "verified":
            matching.append((path, record))

    if not matching:
        failures.append("no verified attestation matching current semantic ID")

    project_declarations: list[dict[str, Any]] = []
    for path, record in matching:
        for declaration in record.get("declarations", []):
            name = declaration.get("name", "")
            if not name.startswith(PROJECT_NAMESPACE):
                continue
            project_declarations.append(
                {
                    "attestation": path.parent.name,
                    "name": name,
                    "policy_kind": declaration.get("policy", {}).get("kind"),
                    "observed_axioms": declaration.get("observed", []),
                }
            )
            observed = set(declaration.get("observed", []))
            if observed & PROHIBITED_AXIOMS:
                failures.append(f"prohibited axiom in project declaration: {name}")

    expected_names = {
        f"{PROJECT_NAMESPACE}Main.tropicalMul",
        f"{PROJECT_NAMESPACE}Main.tropicalScore",
        f"{PROJECT_NAMESPACE}Main.router_smoke_eval",
    }
    observed_names = {item["name"] for item in project_declarations}
    missing = sorted(expected_names - observed_names)
    if missing:
        failures.append(f"missing attested project declarations: {missing}")

    return {
        "status": "PASS" if not failures else "FAIL",
        "target": ".lexlean/verified/*/attestation.json (project declarations only)",
        "details": {
            "attestation_count": len(attestations),
            "matching_attestations": [str(p.relative_to(PROJECT_ROOT)) for p, _ in matching],
            "project_declarations": project_declarations,
            "scope_note": "Runtime declarations with exact-policy axioms are excluded from the project axiom gate.",
        },
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# TS-06 Formal Router Theorem Audit
# ---------------------------------------------------------------------------
def suite_ts06() -> dict[str, Any]:
    source = (PROJECT_ROOT / "src" / "Main.lex.tex").read_text()
    required_tokens = [
        "name: tropicalMul",
        "name: tropicalScore",
        "name: router_smoke_eval",
        "statement: ((tropicalScore 3 5 2) = 10)",
        "proof: decide{}",
        "effects: [overflow]",
        "targets: [rust-core, rust-std]",
    ]
    failures = [f"missing token: {token}" for token in required_tokens if token not in source]
    return {
        "status": "PASS" if not failures else "FAIL",
        "target": "src/Main.lex.tex formal declaration audit",
        "details": {
            "tokens_checked": required_tokens,
            "source_sha256": sha256_file(PROJECT_ROOT / "src" / "Main.lex.tex"),
        },
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# TS-07 PrismPM Build & Manifest Integrity
# ---------------------------------------------------------------------------
def suite_ts07(semantic_id: str | None) -> dict[str, Any]:
    build = run_cmd(["prismpm", "build", "--json"])
    failures: list[str] = []
    result: dict[str, Any] = {}
    if build["exit_code"] != 0:
        failures.append(f"prismpm build failed ({build['stderr'][:200]})")
        return fail("prismpm build failed", target="prismpm build --json", details=build, failures=failures)

    try:
        result = json.loads(build["stdout"])
    except json.JSONDecodeError:
        return fail("prismpm build emitted non-JSON output", target="prismpm build --json", details=build)

    build_id = result.get("build_id", "")
    if result.get("semantic_id") != semantic_id:
        failures.append("build semantic ID differs from static check")
    if result.get("schema") != "prismpm/build-result/1":
        failures.append("unexpected build result schema")

    manifest_path = PROJECT_ROOT / result["manifest_path"]
    if not manifest_path.is_file():
        failures.append("build manifest missing")
        manifest_files: list[dict[str, Any]] = []
    else:
        manifest = json.loads(manifest_path.read_text())
        build_dir = manifest_path.parent
        manifest_files = []
        for entry in manifest.get("files", []):
            path = build_dir / entry["path"]
            actual_sha = sha256_file(path) if path.is_file() else "missing"
            actual_len = path.stat().st_size if path.is_file() else -1
            manifest_files.append(
                {
                    "path": entry["path"],
                    "expected_sha256": entry["sha256"],
                    "actual_sha256": actual_sha,
                    "expected_bytes": entry["byte_length"],
                    "actual_bytes": actual_len,
                }
            )
            if actual_sha != entry["sha256"] or actual_len != entry["byte_length"]:
                failures.append(f"manifest integrity failure: {entry['path']}")

    current_source = source_digest()
    baseline_applicable = current_source == PINNED_SOURCE_DIGEST
    baseline_note = "baseline applies"
    if baseline_applicable and build_id != PINNED_BUILD_DIGEST:
        failures.append(f"build digest drift: {build_id} != {PINNED_BUILD_DIGEST}")
    elif not baseline_applicable:
        baseline_note = "source inputs changed; re-accredit the pinned build digest"

    return {
        "status": "PASS" if not failures else "FAIL",
        "target": "prismpm build --json + manifest SHA-256 verification",
        "details": {
            "build_id": build_id,
            "manifest_path": result.get("manifest_path"),
            "semantic_id": result.get("semantic_id"),
            "source_digest": current_source,
            "pinned_source_digest": PINNED_SOURCE_DIGEST,
            "baseline_note": baseline_note,
            "manifest_files": manifest_files,
        },
        "failures": failures,
        "build_digest": build_id,
    }


# ---------------------------------------------------------------------------
# TS-08 Tropical Benchmark Engine
# ---------------------------------------------------------------------------
def suite_ts08() -> dict[str, Any]:
    result = bench.run_benchmarks(PROJECT_ROOT)
    failures = [
        f"{suite['suite_id']}: {suite['details'].get('failures')}"
        for suite in result["sub_suites"]
        if suite["status"] != "PASS"
    ]
    return {
        "status": result["status"],
        "target": "benchmark_tropical_router.py (S1-S5)",
        "details": result,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# TS-09 Reporting & Gate Contract Integrity
# ---------------------------------------------------------------------------
def suite_ts09(benchmark_result: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []

    sample = build_report_payload(
        suites=[{"id": "TS-TEST", "name": "sample", "target": "sample", "status": "PASS", "duration_ms": 0.0, "details": {}, "failures": []}],
        benchmark={"schema": bench.SCHEMA, "status": "PASS", "sub_suites": [], "environment": {}},
        generated_at="FIXED",
        build_digest=PINNED_BUILD_DIGEST,
        semantic_id=PINNED_SEMANTIC_ID,
    )
    required_keys = {
        "schema",
        "generated_at",
        "status",
        "toolchain",
        "build_digest",
        "semantic_id",
        "compiler_semantics",
        "suites",
        "benchmark",
        "canonical_sha256",
    }
    missing = sorted(required_keys - set(sample))
    if missing:
        failures.append(f"report payload missing keys: {missing}")

    hook = PROJECT_ROOT / ".githooks" / "pre-commit"
    if not hook.is_file():
        failures.append("pre-commit hook missing")
    else:
        hook_text = hook.read_text()
        for token in ("run_tests.py", "git add reports/", "exit"):
            if token not in hook_text:
                failures.append(f"pre-commit hook missing token: {token}")

    workflow = PROJECT_ROOT / ".github" / "workflows" / "verify-test.yml"
    if not workflow.is_file():
        failures.append("GitHub Actions workflow missing")
    else:
        workflow_text = workflow.read_text()
        for token in ("python3 run_tests.py", "GITHUB_STEP_SUMMARY", "upload-artifact", "fail"):
            if token not in workflow_text:
                failures.append(f"workflow missing token: {token}")

    s5 = next(
        (suite for suite in benchmark_result.get("sub_suites", []) if suite["suite_id"] == "S5"),
        None,
    )
    if not s5 or s5["status"] != "PASS":
        failures.append("S5 negative fault-injection suite did not pass")

    return {
        "status": "PASS" if not failures else "FAIL",
        "target": "reports schema, hook, workflow, and fault-injection contract",
        "details": {
            "required_report_keys": sorted(required_keys),
            "hook": str(hook.relative_to(PROJECT_ROOT)),
            "workflow": str(workflow.relative_to(PROJECT_ROOT)),
            "s5_status": s5["status"] if s5 else "missing",
        },
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def build_report_payload(
    suites: list[dict[str, Any]],
    benchmark: dict[str, Any],
    generated_at: str,
    build_digest: str,
    semantic_id: str,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "status": "PASS" if all(s["status"] == "PASS" for s in suites) and benchmark.get("status") == "PASS" else "FAIL",
        "toolchain": {
            "lean": f"leanprover/lean4:v{EXPECTED_LEAN}",
            "prismpm": EXPECTED_PRISM_VERSION,
            "language": "lexlean/project/1 (Language 1.2)",
            "python": platform.python_version(),
            "os": platform.system(),
            "arch": platform.machine(),
        },
        "build_digest": build_digest,
        "semantic_id": semantic_id,
        "compiler_semantics": PINNED_COMPILER_SEMANTICS,
        "source_digest": source_digest(),
        "suites": suites,
        "benchmark": benchmark,
        "deferred_gate": {
            "command": "prismpm verify",
            "status": "informational",
            "reason": "PP5003: snapshot contains no Prism declarations in ADR-0034 baseline",
        },
    }
    canonical = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    base["canonical_sha256"] = canonical
    return base


def _md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(payload: dict[str, Any], json_sha256: str) -> str:
    suites = payload["suites"]
    benchmark = payload["benchmark"]
    passed = sum(1 for suite in suites if suite["status"] == "PASS")
    verdict = "PASS" if payload["status"] == "PASS" else "FAIL"
    banner = "> [!NOTE]" if verdict == "PASS" else "> [!CAUTION]"
    banner_text = "All verification and benchmark gates passed." if verdict == "PASS" else "At least one verification or benchmark gate failed."

    lines: list[str] = [
        f"# Tropical Max-Plus Router — Test Report ({verdict})",
        "",
        banner,
        banner_text,
        "",
        f"**Generated (UTC):** `{payload['generated_at']}`  ",
        f"**Overall:** `{verdict}` ({passed}/{len(suites)} verification suites)  ",
        f"**PrismPM build:** `{payload['build_digest']}`  ",
        f"**Semantic ID:** `{payload['semantic_id']}`  ",
        f"**Compiler semantics:** `{payload['compiler_semantics']}`  ",
        f"**Source digest:** `{payload['source_digest']}`  ",
        f"**Canonical SHA-256:** `{payload['canonical_sha256']}`  ",
        f"**JSON companion SHA-256:** `{json_sha256}`",
        "",
        "## 1. Toolchain & Environment",
        "",
        "| Field | Value |",
        "| :--- | :--- |",
    ]
    for key, value in payload["toolchain"].items():
        lines.append(f"| {_md_escape(key)} | `{_md_escape(value)}` |")

    lines.extend(
        [
            "",
            "## 2. Nine-Suite Verification Matrix",
            "",
            "| Suite | Name | Target | Result | Duration (ms) | Failures |",
            "| :--- | :--- | :--- | :---: | ---: | :--- |",
        ]
    )
    for suite in suites:
        failures = "; ".join(suite.get("failures", [])) or "—"
        lines.append(
            f"| `{_md_escape(suite['id'])}` | {_md_escape(suite['name'])} | "
            f"`{_md_escape(suite['target'])}` | **{suite['status']}** | "
            f"{suite['duration_ms']:.3f} | {_md_escape(failures)} |"
        )

    lines.extend(
        [
            "",
            "## 3. Empirical Benchmark Engine",
            "",
            f"**Status:** `{benchmark.get('status')}` · **Seed:** `{benchmark.get('seed')}`",
            "",
            "| Sub-suite | Invariant | Name | Result | Summary |",
            "| :--- | :--- | :--- | :---: | :--- |",
        ]
    )
    for sub in benchmark.get("sub_suites", []):
        details = sub.get("details", {})
        summary_parts: list[str] = []
        for key in ("samples", "pairs_tested", "violation_count", "silent_wraps", "build_digests", "failures"):
            if key in details:
                summary_parts.append(f"{key}={_md_escape(details[key])}")
        summary = ", ".join(summary_parts) or "—"
        lines.append(
            f"| `{_md_escape(sub['suite_id'])}` | `{_md_escape(sub['invariant'])}` | "
            f"{_md_escape(sub['name'])} | **{sub['status']}** | {_md_escape(summary)} |"
        )

    throughput = next(
        (sub for sub in benchmark.get("sub_suites", []) if sub["suite_id"] == "S3"),
        None,
    )
    if throughput:
        lines.extend(
            [
                "",
                "### 3.1 Routing Table Scale & Latency",
                "",
                "| N | Median ops/s | Batch p50 (ms) | Batch p95 (ms) | Batch p99 (ms) |",
                "| ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in throughput["details"]["measurements"]:
            lines.append(
                f"| {row['table_size']} | {row['median_throughput_per_sec']:.0f} | "
                f"{row['batch_ms_p50']:.6f} | {row['batch_ms_p95']:.6f} | {row['batch_ms_p99']:.6f} |"
            )

    deferred = payload.get("deferred_gate", {})
    lines.extend(
        [
            "",
            "## 4. Gate Scope Note",
            "",
            f"`{deferred.get('command')}` is **{_md_escape(deferred.get('status'))}** for this baseline: "
            f"{_md_escape(deferred.get('reason'))}. The blocking release gate is `prismpm check` + `prismpm build`.",
            "",
            "---",
            "",
            "Generated automatically by `run_tests.py` under ADR-0034. Do not edit by hand.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_reports(payload: dict[str, Any]) -> tuple[pathlib.Path, pathlib.Path, str]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    json_sha256 = hashlib.sha256(json_text.encode()).hexdigest()
    md_text = render_markdown(payload, json_sha256)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    targets = {
        "json": [REPORT_DIR / "test_report_latest.json", REPORT_DIR / f"test_report_{stamp}.json"],
        "md": [REPORT_DIR / "TEST_REPORT_LATEST.md", REPORT_DIR / f"TEST_REPORT_{stamp}.md"],
        "benchmark_json": [REPORT_DIR / "stress_benchmark_latest.json", REPORT_DIR / f"stress_benchmark_{stamp}.json"],
        "benchmark_md": [REPORT_DIR / "STRESS_BENCHMARK_LATEST.md", REPORT_DIR / f"STRESS_BENCHMARK_{stamp}.md"],
    }

    benchmark_payload = {
        "schema": "tropical-router/stress-benchmark-report/1",
        "generated_at": payload["generated_at"],
        "status": payload["benchmark"].get("status"),
        "environment": payload["benchmark"].get("environment", {}),
        "seed": payload["benchmark"].get("seed"),
        "sub_suites": payload["benchmark"].get("sub_suites", []),
        "build_digest": payload["build_digest"],
        "semantic_id": payload["semantic_id"],
    }
    benchmark_json = json.dumps(benchmark_payload, indent=2, sort_keys=True) + "\n"
    benchmark_md = render_benchmark_markdown(benchmark_payload)

    for path in targets["json"]:
        path.write_text(json_text)
    for path in targets["md"]:
        path.write_text(md_text)
    for path in targets["benchmark_json"]:
        path.write_text(benchmark_json)
    for path in targets["benchmark_md"]:
        path.write_text(benchmark_md)

    return targets["md"][0], targets["benchmark_md"][0], json_sha256


def render_benchmark_markdown(payload: dict[str, Any]) -> str:
    verdict = "PASS" if payload.get("status") == "PASS" else "FAIL"
    banner = "> [!NOTE]" if verdict == "PASS" else "> [!CAUTION]"
    lines = [
        f"# Tropical Max-Plus Router — Stress Benchmark Report ({verdict})",
        "",
        banner,
        f"Benchmark suite result: `{verdict}`.",
        "",
        f"**Generated (UTC):** `{payload['generated_at']}`  ",
        f"**Build:** `{payload['build_digest']}`  ",
        f"**Semantic ID:** `{payload['semantic_id']}`  ",
        f"**Seed:** `{payload['seed']}`",
        "",
        "| Field | Value |",
        "| :--- | :--- |",
    ]
    for key, value in payload.get("environment", {}).items():
        lines.append(f"| {_md_escape(key)} | `{_md_escape(value)}` |")

    lines.extend(
        [
            "",
            "| Sub-suite | Invariant | Result | Detail |",
            "| :--- | :--- | :---: | :--- |",
        ]
    )
    for sub in payload.get("sub_suites", []):
        detail = _md_escape(json.dumps(sub.get("details", {}), sort_keys=True))[:600]
        lines.append(
            f"| `{_md_escape(sub['suite_id'])}` | `{_md_escape(sub['invariant'])}` | "
            f"**{sub['status']}** | `{detail}` |"
        )

    throughput = next((s for s in payload.get("sub_suites", []) if s["suite_id"] == "S3"), None)
    if throughput:
        lines.extend(
            [
                "",
                "## Throughput & Latency",
                "",
                "| N | Median ops/s | p50 batch ms | p95 batch ms | p99 batch ms |",
                "| ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in throughput["details"]["measurements"]:
            lines.append(
                f"| {row['table_size']} | {row['median_throughput_per_sec']:.0f} | "
                f"{row['batch_ms_p50']:.6f} | {row['batch_ms_p95']:.6f} | {row['batch_ms_p99']:.6f} |"
            )
    lines.extend(["", "---", "", "Generated automatically by `run_tests.py` under ADR-0034. Do not edit by hand."])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
SUITE_META: list[tuple[str, str, Callable[[], dict[str, Any]]]] = [
    ("TS-01", "Toolchain & Runtime Pin Audit", suite_ts01),
    ("TS-02", "Lake Host Workspace Build", suite_ts02),
    ("TS-03", "LexLean Lock & Canonical Config Parity", suite_ts03),
    ("TS-04", "PrismPM Static Model Check", suite_ts04),
]


def execute_suite(suite_id: str, name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - fail closed with diagnostic
        result = fail(f"unexpected exception: {type(exc).__name__}: {exc}", target=name)
    result["id"] = suite_id
    result["name"] = name
    result.setdefault("target", name)
    result.setdefault("details", {})
    result.setdefault("failures", [])
    result["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return result


def main(argv: list[str]) -> int:
    suites: list[dict[str, Any]] = []
    for suite_id, name, fn in SUITE_META:
        suites.append(execute_suite(suite_id, name, fn))

    ts04 = next(s for s in suites if s["id"] == "TS-04")
    semantic_id = ts04.get("semantic_id") or PINNED_SEMANTIC_ID

    suites.append(
        execute_suite("TS-05", "Lean Kernel Attestation Audit", lambda: suite_ts05(semantic_id))
    )
    suites.append(execute_suite("TS-06", "Formal Router Theorem Audit", suite_ts06))
    ts07 = execute_suite("TS-07", "PrismPM Build & Manifest Integrity", lambda: suite_ts07(semantic_id))
    suites.append(ts07)
    ts08 = execute_suite("TS-08", "Tropical Benchmark Engine", suite_ts08)
    suites.append(ts08)
    suites.append(
        execute_suite(
            "TS-09",
            "Reporting & Gate Contract Integrity",
            lambda: suite_ts09(ts08.get("details", {})),
        )
    )

    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    build_digest = ts07.get("build_digest") or PINNED_BUILD_DIGEST
    benchmark_result = ts08.get("details", {})
    payload = build_report_payload(suites, benchmark_result, generated_at, build_digest, semantic_id)
    md_path, benchmark_md_path, json_sha = write_reports(payload)

    for suite in suites:
        mark = "PASS" if suite["status"] == "PASS" else "FAIL"
        print(f"{suite['id']} {mark} {suite['name']} ({suite['duration_ms']:.3f} ms)")
        for failure in suite.get("failures", []):
            print(f"    - {failure}", file=sys.stderr)

    print(f"report: {md_path.relative_to(PROJECT_ROOT)}")
    print(f"benchmark report: {benchmark_md_path.relative_to(PROJECT_ROOT)}")
    print(f"report json sha256: {json_sha}")
    print(f"overall: {payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
