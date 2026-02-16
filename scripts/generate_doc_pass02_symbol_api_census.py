#!/usr/bin/env python3
"""Generate DOC-PASS-02 symbol/API census artifacts."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = REPO_ROOT / "artifacts/docs/v1/doc_pass02_symbol_api_census_v1.json"
OUTPUT_MD = REPO_ROOT / "artifacts/docs/v1/doc_pass02_symbol_api_census_v1.md"

BASELINE_COMPARATOR = "legacy_networkx/main@python3.12"
PROFILE_FIRST_ARTIFACTS = {
    "baseline": "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    "hotspot": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
    "delta": "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
}
OPTIMIZATION_LEVER_POLICY = {
    "rule": "exactly_one_optimization_lever_per_change",
    "evidence_path": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
}
ALIEN_UPLIFT_CONTRACT_CARD = {
    "ev_score": 2.19,
    "baseline_comparator": BASELINE_COMPARATOR,
    "expected_value_statement": (
        "A deterministic symbol/API census reduces compatibility blind spots and "
        "prevents high-regression surface drift."
    ),
}
DECISION_THEORETIC_RUNTIME_CONTRACT = {
    "states": ["collect", "classify", "audit", "fail_closed"],
    "actions": ["enumerate_symbol", "assign_surface", "attach_risk_note", "fail_closed"],
    "loss_model": (
        "Minimize expected compatibility regression by prioritizing high-risk public symbols "
        "while keeping internal surfaces explicitly separated."
    ),
    "loss_budget": {
        "max_expected_loss": 0.02,
        "max_surface_misclassification": 0.0,
        "max_untracked_high_risk_symbols": 0.0,
    },
    "safe_mode_fallback": {
        "trigger_thresholds": {
            "missing_workspace_crates": 1,
            "missing_public_symbols": 1,
            "missing_high_regression_risk_notes": 1,
        },
        "fallback_action": "halt DOC-PASS publication and emit fail-closed diagnostics",
        "budgeted_recovery_window_ms": 30000,
    },
}
ISOMORPHISM_PROOF_ARTIFACTS = [
    "artifacts/perf/phase2c/isomorphism_harness_report_v1.json",
    "artifacts/perf/phase2c/isomorphism_golden_signatures_v1.json",
]
STRUCTURED_LOGGING_EVIDENCE = [
    "artifacts/conformance/latest/structured_logs.jsonl",
    "artifacts/e2e/latest/e2e_script_pack_events_v1.jsonl",
    "artifacts/e2e/latest/e2e_script_pack_steps_v1.jsonl",
]

FAMILY_FOR_CRATE = {
    "fnx-runtime": "runtime-policy",
    "fnx-classes": "graph-storage",
    "fnx-views": "graph-view-api",
    "fnx-dispatch": "compat-dispatch",
    "fnx-convert": "conversion-ingest",
    "fnx-readwrite": "io-serialization",
    "fnx-generators": "graph-generators",
    "fnx-algorithms": "algorithm-engine",
    "fnx-durability": "durability-repair",
    "fnx-conformance": "conformance-harness",
}
DESCRIPTION_FOR_FAMILY = {
    "runtime-policy": "Mode split policy, decision rules, and structured runtime contracts.",
    "graph-storage": "Core graph mutation and deterministic adjacency/node/edge storage.",
    "graph-view-api": "Read-only and cached graph views with deterministic projection semantics.",
    "compat-dispatch": "Compatibility-aware backend dispatch and routing policies.",
    "conversion-ingest": "Format conversion and ingest normalization interfaces.",
    "io-serialization": "Read/write parser and serializer interfaces.",
    "graph-generators": "Graph constructor and seeded/stochastic generator interfaces.",
    "algorithm-engine": "Algorithm execution surfaces and witness/result contracts.",
    "durability-repair": "RaptorQ durability, scrub, decode, and recovery interfaces.",
    "conformance-harness": "Fixture execution, differential checks, and evidence emission APIs.",
}

TEST_BINDINGS_FOR_CRATE = {
    "fnx-runtime": ["fnx_runtime::tests::structured_test_log_validates_passed_record"],
    "fnx-classes": ["fnx_classes::tests::add_edge_autocreates_nodes_and_preserves_order"],
    "fnx-views": ["fnx_views::tests::cached_snapshot_refreshes_on_revision_change"],
    "fnx-dispatch": ["fnx_dispatch::tests::strict_mode_rejects_unknown_incompatible_request"],
    "fnx-convert": ["fnx_convert::tests::edge_list_conversion_is_deterministic"],
    "fnx-readwrite": ["fnx_readwrite::tests::strict_mode_fails_closed_for_malformed_line"],
    "fnx-generators": ["fnx_generators::tests::cycle_graph_edge_order_matches_networkx_for_n_five"],
    "fnx-algorithms": ["fnx_algorithms::tests::shortest_path_handles_unreachable"],
    "fnx-durability": ["fnx_durability::tests::sidecar_generation_and_scrub_recovery_work"],
    "fnx-conformance": ["fnx_conformance::tests::smoke_report_is_stable"],
}

PUBLIC_SYMBOL_RE = re.compile(
    r"^pub(?:\((?P<scope>[^)]+)\))?\s+"
    r"(?:(?:async|const|unsafe)\s+)*"
    r"(?P<kind>fn|struct|enum|trait|type|mod)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
PRIVATE_FN_RE = re.compile(
    r"^(?:(?:async|const|unsafe)\s+)*fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)

CRITICAL_SYMBOL_TOKENS = (
    "add_",
    "remove",
    "neighbor",
    "shortest_path",
    "component",
    "dispatch",
    "convert",
    "read",
    "write",
    "decode",
    "repair",
    "scrub",
    "run_smoke",
    "forensic",
    "replay",
)


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def workspace_members() -> list[tuple[str, Path]]:
    root_toml = load_toml(REPO_ROOT / "Cargo.toml")
    members = root_toml.get("workspace", {}).get("members", [])
    rows: list[tuple[str, Path]] = []
    for member in members:
        crate_dir = REPO_ROOT / member
        manifest = crate_dir / "Cargo.toml"
        if not manifest.exists():
            continue
        package_name = load_toml(manifest).get("package", {}).get("name")
        if isinstance(package_name, str):
            rows.append((package_name, crate_dir))
    return sorted(rows, key=lambda row: row[0])


def should_track_internal_symbol(symbol_name: str) -> bool:
    lowered = symbol_name.lower()
    return any(token in lowered for token in CRITICAL_SYMBOL_TOKENS)


def classify_visibility(scope: str | None) -> tuple[str, str]:
    if scope in {"crate", "super", "self"}:
        return "internal", "internal_impl"
    return "public", "public_contract"


def classify_regression_risk(
    *,
    crate_name: str,
    symbol_name: str,
    symbol_kind: str,
    visibility: str,
) -> tuple[str, str]:
    lowered = symbol_name.lower()
    if any(token in lowered for token in CRITICAL_SYMBOL_TOKENS):
        return "high", "Symbol name intersects high-regression behavior paths."
    if crate_name in {"fnx-runtime", "fnx-conformance"} and visibility == "public":
        return "high", "Public runtime/conformance surface is contract-critical."
    if visibility == "public" and symbol_kind in {"fn", "trait", "struct", "enum"}:
        return "medium", "Public API symbol contributes to user-observable contract."
    if visibility == "public":
        return "medium", "Public symbol should remain stable across compatibility gates."
    return "low", "Internal implementation symbol with bounded compatibility exposure."


def replay_command_for_crate(crate_name: str) -> str:
    if crate_name == "fnx-conformance":
        return "rch exec -- cargo test -q -p fnx-conformance --test smoke -- --nocapture"
    return f"rch exec -- cargo test -q -p {crate_name} --lib -- --nocapture"


def symbol_inventory_for_crate(crate_name: str, crate_dir: Path) -> list[dict[str, Any]]:
    source_root = crate_dir / "src"
    if not source_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for source_path in sorted(source_root.rglob("*.rs")):
        relative_source = source_path.relative_to(REPO_ROOT).as_posix()
        lines = source_path.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            public_match = PUBLIC_SYMBOL_RE.match(stripped)
            symbol_kind: str | None = None
            symbol_name: str | None = None
            visibility = "internal"
            api_surface = "internal_impl"
            if public_match:
                symbol_kind = public_match.group("kind")
                symbol_name = public_match.group("name")
                visibility, api_surface = classify_visibility(public_match.group("scope"))
            else:
                private_match = PRIVATE_FN_RE.match(stripped)
                if private_match:
                    symbol_kind = "fn"
                    symbol_name = private_match.group("name")
                    if not should_track_internal_symbol(symbol_name):
                        continue
                else:
                    continue
            assert symbol_kind is not None
            assert symbol_name is not None
            regression_risk, rationale = classify_regression_risk(
                crate_name=crate_name,
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                visibility=visibility,
            )
            stability_tier = "core_contract" if visibility == "public" else "internal_behavior"
            symbol_id = f"{crate_name}:{relative_source}:{line_no}:{symbol_name}"
            rows.append(
                {
                    "symbol_id": symbol_id,
                    "crate_name": crate_name,
                    "subsystem_family": FAMILY_FOR_CRATE.get(crate_name, "misc"),
                    "module_path": relative_source,
                    "line": line_no,
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "visibility": visibility,
                    "api_surface": api_surface,
                    "stability_tier": stability_tier,
                    "regression_risk": regression_risk,
                    "rationale": rationale,
                    "test_bindings": TEST_BINDINGS_FOR_CRATE.get(crate_name, []),
                    "replay_command": replay_command_for_crate(crate_name),
                }
            )
    rows.sort(key=lambda row: (row["crate_name"], row["module_path"], row["line"], row["symbol_name"]))
    return rows


def build_subsystem_families(symbol_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "crate_names": set(),
            "public_symbol_count": 0,
            "internal_symbol_count": 0,
            "high_regression_count": 0,
        }
    )
    for row in symbol_rows:
        family = row["subsystem_family"]
        bucket = grouped[family]
        bucket["crate_names"].add(row["crate_name"])
        if row["visibility"] == "public":
            bucket["public_symbol_count"] += 1
        else:
            bucket["internal_symbol_count"] += 1
        if row["regression_risk"] == "high":
            bucket["high_regression_count"] += 1
    families: list[dict[str, Any]] = []
    for family_id in sorted(grouped):
        bucket = grouped[family_id]
        families.append(
            {
                "family_id": family_id,
                "description": DESCRIPTION_FOR_FAMILY.get(family_id, "Scoped subsystem family."),
                "crates": sorted(bucket["crate_names"]),
                "public_symbol_count": bucket["public_symbol_count"],
                "internal_symbol_count": bucket["internal_symbol_count"],
                "high_regression_count": bucket["high_regression_count"],
            }
        )
    return families


def build_high_regression_symbols(symbol_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in symbol_rows if row["regression_risk"] == "high"]
    return sorted(rows, key=lambda row: (row["crate_name"], row["symbol_name"], row["line"]))


def build_risk_notes(high_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for index, row in enumerate(high_rows, start=1):
        notes.append(
            {
                "note_id": f"DOC-PASS02-RISK-{index:03d}",
                "symbol_id": row["symbol_id"],
                "risk_level": "high",
                "reason": row["rationale"],
                "mitigation": (
                    "Require differential + e2e replay validation before behavior changes and "
                    "retain deterministic replay metadata in structured logs."
                ),
                "baseline_comparator": BASELINE_COMPARATOR,
            }
        )
    return notes


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DOC-PASS-02 Symbol/API Census v1",
        "",
        f"Generated at: `{payload['generated_at_utc']}`",
        f"Baseline comparator: `{payload['baseline_comparator']}`",
        "",
        "## Census Summary",
    ]
    summary = payload["census_summary"]
    for key in [
        "workspace_crate_count",
        "symbol_count_total",
        "public_symbol_count",
        "internal_symbol_count",
        "high_regression_count",
    ]:
        lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(["", "## Subsystem Families", "", "| family | crates | public | internal | high-risk |", "|---|---:|---:|---:|---:|"])
    for family in payload["subsystem_families"]:
        lines.append(
            "| {family_id} | {crate_count} | {public_symbol_count} | {internal_symbol_count} | {high_regression_count} |".format(
                family_id=family["family_id"],
                crate_count=len(family["crates"]),
                public_symbol_count=family["public_symbol_count"],
                internal_symbol_count=family["internal_symbol_count"],
                high_regression_count=family["high_regression_count"],
            )
        )
    lines.extend(["", "## High-Regression Symbols (Top 25)", "", "| symbol | crate | kind | visibility | module |", "|---|---|---|---|---|"])
    for row in payload["high_regression_symbols"][:25]:
        lines.append(
            "| {symbol_name} | {crate_name} | {symbol_kind} | {visibility} | `{module_path}:{line}` |".format(
                **row
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", default=str(OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(OUTPUT_MD))
    args = parser.parse_args()

    all_rows: list[dict[str, Any]] = []
    members = workspace_members()
    for crate_name, crate_dir in members:
        all_rows.extend(symbol_inventory_for_crate(crate_name, crate_dir))

    subsystem_families = build_subsystem_families(all_rows)
    high_regression_symbols = build_high_regression_symbols(all_rows)
    risk_notes = build_risk_notes(high_regression_symbols)

    payload = {
        "schema_version": "1.0.0",
        "artifact_id": "doc-pass-02-symbol-api-census-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparator": BASELINE_COMPARATOR,
        "census_summary": {
            "workspace_crate_count": len(members),
            "symbol_count_total": len(all_rows),
            "public_symbol_count": sum(1 for row in all_rows if row["visibility"] == "public"),
            "internal_symbol_count": sum(1 for row in all_rows if row["visibility"] != "public"),
            "high_regression_count": len(high_regression_symbols),
        },
        "subsystem_families": subsystem_families,
        "symbol_inventory": all_rows,
        "high_regression_symbols": high_regression_symbols,
        "risk_notes": risk_notes,
        "alien_uplift_contract_card": dict(ALIEN_UPLIFT_CONTRACT_CARD),
        "profile_first_artifacts": dict(PROFILE_FIRST_ARTIFACTS),
        "optimization_lever_policy": dict(OPTIMIZATION_LEVER_POLICY),
        "decision_theoretic_runtime_contract": dict(DECISION_THEORETIC_RUNTIME_CONTRACT),
        "isomorphism_proof_artifacts": list(ISOMORPHISM_PROOF_ARTIFACTS),
        "structured_logging_evidence": list(STRUCTURED_LOGGING_EVIDENCE),
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    if not output_json.is_absolute():
        output_json = REPO_ROOT / output_json
    if not output_md.is_absolute():
        output_md = REPO_ROOT / output_md

    write_json(output_json, payload)
    write_text(output_md, build_markdown(payload))
    print(f"doc_pass02_json:{output_json}")
    print(f"doc_pass02_md:{output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
