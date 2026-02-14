#!/usr/bin/env python3
"""Generate DOC-PASS-01 module/package cartography artifacts."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = REPO_ROOT / "artifacts/docs/v1/doc_pass01_module_cartography_v1.json"
DEFAULT_OUTPUT_MD = REPO_ROOT / "artifacts/docs/v1/doc_pass01_module_cartography_v1.md"

LAYER_ORDER = {
    "runtime-policy": 0,
    "graph-storage": 1,
    "graph-view-api": 2,
    "compat-dispatch": 2,
    "conversion-ingest": 3,
    "io-serialization": 3,
    "graph-generators": 3,
    "algorithm-engine": 3,
    "durability-repair": 4,
    "conformance-harness": 5,
}

LAYER_FOR_CRATE = {
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

PURPOSE_FOR_CRATE = {
    "fnx-runtime": "Mode split types, decision-theoretic guards, evidence ledger, structured test logs.",
    "fnx-classes": "Deterministic graph storage and mutation contracts with revisioned snapshots.",
    "fnx-views": "Live and cached graph view semantics with deterministic ordering preservation.",
    "fnx-dispatch": "Backend selection and fail-closed compatibility routing.",
    "fnx-convert": "Ingestion/conversion entrypoints from edge-list and adjacency payloads.",
    "fnx-readwrite": "Edgelist/JSON graph parsers and serializers with strict/hardened behaviors.",
    "fnx-generators": "Deterministic/seeded graph generators with bounded hardened recovery.",
    "fnx-algorithms": "Shortest path, components, and centrality operations plus complexity witnesses.",
    "fnx-durability": "RaptorQ sidecar generation, scrub, and decode-drill proof lifecycle.",
    "fnx-conformance": "Fixture-driven differential harness and structured telemetry/artifact emission.",
}

LEGACY_ANCHORS_FOR_CRATE = {
    "fnx-runtime": ["networkx/utils/backends.py", "networkx/lazy_imports.py"],
    "fnx-classes": ["networkx/classes/graph.py", "networkx/classes/digraph.py"],
    "fnx-views": [
        "networkx/classes/coreviews.py",
        "networkx/classes/graphviews.py",
        "networkx/classes/reportviews.py",
    ],
    "fnx-dispatch": ["networkx/utils/backends.py"],
    "fnx-convert": ["networkx/convert.py", "networkx/convert_matrix.py", "networkx/relabel.py"],
    "fnx-readwrite": ["networkx/readwrite/edgelist.py", "networkx/readwrite/json_graph"],
    "fnx-generators": ["networkx/generators/classic.py", "networkx/generators/random_graphs.py"],
    "fnx-algorithms": [
        "networkx/algorithms/shortest_paths/unweighted.py",
        "networkx/algorithms/components/connected.py",
        "networkx/algorithms/centrality",
    ],
    "fnx-durability": ["project durability contract (RaptorQ sidecar doctrine)"],
    "fnx-conformance": ["networkx/tests/*", "networkx/classes/tests/*", "networkx/algorithms/tests/*"],
}

OWNERSHIP_BOUNDARIES_FOR_CRATE = {
    "fnx-runtime": [
        "Defines canonical `CompatibilityMode` and `DecisionAction` semantics.",
        "Owns structured log schema and validation requirements.",
    ],
    "fnx-classes": [
        "Owns adjacency/node/edge mutation model and deterministic iteration order.",
        "Must not encode serializer or fixture-routing policy.",
    ],
    "fnx-views": [
        "Owns read-only projection and cache staleness semantics.",
        "Must not mutate graph storage directly.",
    ],
    "fnx-dispatch": [
        "Owns backend compatibility filtering and tie-break policy.",
        "Must not implement conversion/readwrite parsing logic.",
    ],
    "fnx-convert": [
        "Owns payload normalization and conversion warnings contract.",
        "Must delegate backend policy decisions to `fnx-dispatch`.",
    ],
    "fnx-readwrite": [
        "Owns parser/serializer correctness and strict/hardened malformed-input behavior.",
        "Must not alter graph algorithm semantics.",
    ],
    "fnx-generators": [
        "Owns deterministic graph construction and seeded stochastic generation.",
        "Must not route through conformance harness internals.",
    ],
    "fnx-algorithms": [
        "Owns algorithm result semantics and witness accounting.",
        "Must remain independent of fixture storage and artifact writes.",
    ],
    "fnx-durability": [
        "Owns sidecar/scrub/decode proof artifact lifecycle.",
        "Must stay generic and not embed algorithm-specific policy.",
    ],
    "fnx-conformance": [
        "Owns fixture execution orchestration, mismatch taxonomy, and telemetry artifacts.",
        "Depends on lower layers, but must not become a source crate for them.",
    ],
}

STRICT_HARDENED_POLICY_FOR_CRATE = {
    "fnx-runtime": {
        "strict_mode": "Fail closed for unknown incompatible features or unsupported schema.",
        "hardened_mode": "Bounded diagnostics with fail-closed terminal action when compatibility is uncertain.",
    },
    "fnx-dispatch": {
        "strict_mode": "Reject unknown incompatible features and unavailable requested backends.",
        "hardened_mode": "Validation action allowed for moderate risk, but unknown incompatibilities still fail closed.",
    },
    "fnx-convert": {
        "strict_mode": "Malformed node/edge payload rows are terminal failures.",
        "hardened_mode": "Skip malformed entries with warning ledger until bounded recovery budget is exhausted.",
    },
    "fnx-readwrite": {
        "strict_mode": "Malformed parse rows/JSON decode failures fail closed.",
        "hardened_mode": "Return warnings and bounded recovery outputs; escalate to fail closed when required invariants break.",
    },
}

VERIFICATION_HOOKS_FOR_CRATE = {
    "fnx-runtime": {
        "unit": ["fnx_runtime::tests::structured_test_log_validates_passed_record"],
        "property": ["property::fnx_runtime::environment_fingerprint_stability"],
        "differential": ["fixture::generated/runtime_config_optional_strict"],
        "e2e": ["scripts/run_phase2c_readiness_e2e.sh"],
    },
    "fnx-classes": {
        "unit": ["fnx_classes::tests::add_edge_autocreates_nodes_and_preserves_order"],
        "property": ["property::fnx_classes::mutation_invariants"],
        "differential": ["fixture::graph_core_shortest_path_strict"],
        "e2e": ["cargo test -p fnx-conformance --test smoke"],
    },
    "fnx-views": {
        "unit": ["fnx_views::tests::cached_snapshot_refreshes_on_revision_change"],
        "property": ["property::fnx_views::cache_coherence"],
        "differential": ["fixture::generated/view_neighbors_strict"],
        "e2e": ["cargo test -p fnx-conformance --test smoke"],
    },
    "fnx-dispatch": {
        "unit": ["fnx_dispatch::tests::strict_mode_rejects_unknown_incompatible_request"],
        "property": ["property::fnx_dispatch::deterministic_selection"],
        "differential": ["fixture::generated/dispatch_route_strict"],
        "e2e": ["cargo test -p fnx-conformance --test smoke"],
    },
    "fnx-convert": {
        "unit": ["fnx_convert::tests::edge_list_conversion_is_deterministic"],
        "property": ["property::fnx_convert::normalized_payload_stability"],
        "differential": ["fixture::generated/convert_edge_list_strict"],
        "e2e": ["cargo test -p fnx-conformance --test smoke"],
    },
    "fnx-readwrite": {
        "unit": ["fnx_readwrite::tests::strict_mode_fails_closed_for_malformed_line"],
        "property": ["property::fnx_readwrite::roundtrip_stability"],
        "differential": ["fixture::generated/readwrite_roundtrip_strict"],
        "e2e": ["cargo test -p fnx-conformance --test smoke"],
    },
    "fnx-generators": {
        "unit": ["fnx_generators::tests::cycle_graph_edge_order_matches_networkx_for_n_five"],
        "property": ["property::fnx_generators::seed_reproducibility"],
        "differential": ["fixture::generated/generators_cycle_strict"],
        "e2e": ["cargo test -p fnx-conformance --test smoke"],
    },
    "fnx-algorithms": {
        "unit": ["fnx_algorithms::tests::shortest_path_handles_unreachable"],
        "property": ["property::fnx_algorithms::component_partition_invariants"],
        "differential": ["fixture::generated/components_connected_strict"],
        "e2e": ["cargo test -p fnx-conformance --test smoke"],
    },
    "fnx-durability": {
        "unit": ["fnx_durability::tests::sidecar_generation_and_scrub_recovery_work"],
        "property": ["property::fnx_durability::decode_hash_preservation"],
        "differential": ["artifact::conformance/latest/*.raptorq.json"],
        "e2e": ["scripts/run_conformance_with_durability.sh"],
    },
    "fnx-conformance": {
        "unit": ["fnx_conformance::tests::smoke_report_is_stable"],
        "property": ["property::fnx_conformance::fixture_path_stability"],
        "differential": ["cargo run -p fnx-conformance --bin run_smoke"],
        "e2e": ["scripts/run_phase2c_readiness_e2e.sh"],
    },
}

HIDDEN_COUPLINGS = [
    {
        "coupling_id": "HC-001",
        "crates_involved": ["fnx-convert", "fnx-readwrite", "fnx-conformance", "fnx-dispatch"],
        "description": "Backend capability strings are duplicated across dispatch defaults and callsites, so feature-name drift can silently break route compatibility.",
        "risk_level": "high",
        "mitigation": "Generate capability constants from a single registry contract and assert parity in conformance gates.",
    },
    {
        "coupling_id": "HC-002",
        "crates_involved": ["fnx-runtime", "fnx-conformance"],
        "description": "Independent stable-hash implementations exist in both crates; accidental algorithm drift would fork artifact identity semantics.",
        "risk_level": "medium",
        "mitigation": "Centralize stable hash helper in `fnx-runtime` and consume from conformance crate.",
    },
    {
        "coupling_id": "HC-003",
        "crates_involved": ["fnx-conformance", "fnx-algorithms", "fnx-readwrite", "fnx-generators"],
        "description": "Packet routing relies on fixture filename heuristics (`packet_id_for_fixture`), coupling test naming conventions to release-gate accounting.",
        "risk_level": "high",
        "mitigation": "Move packet IDs into fixture schema fields and fail closed when absent.",
    },
    {
        "coupling_id": "HC-004",
        "crates_involved": ["fnx-classes", "fnx-views", "fnx-algorithms"],
        "description": "Deterministic ordering depends on `IndexMap` insertion order assumptions propagated across view and algorithm callers.",
        "risk_level": "medium",
        "mitigation": "Keep explicit deterministic ordering invariants and differential fixture checks for every ordering-sensitive API.",
    },
    {
        "coupling_id": "HC-005",
        "crates_involved": ["fnx-durability", "fnx-conformance"],
        "description": "Durability sidecar/decode-proof lifecycle is tied to conformance artifact naming conventions, creating drift risk between payload and recovery metadata.",
        "risk_level": "high",
        "mitigation": "Define shared durability envelope schema in a single contract crate and validate conformance artifact names against it.",
    },
]


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def discover_workspace_members() -> list[Path]:
    root_toml = load_toml(REPO_ROOT / "Cargo.toml")
    members = root_toml.get("workspace", {}).get("members", [])
    out = []
    for member in members:
        manifest = REPO_ROOT / member / "Cargo.toml"
        if manifest.exists():
            out.append(manifest)
    return sorted(out)


def extract_public_contracts(lib_rs: Path) -> list[str]:
    if not lib_rs.exists():
        return []
    rows = []
    pattern = re.compile(r"^pub\s+(?:fn|struct|enum|trait|type|const)\s+[A-Za-z0-9_]+")
    for line in lib_rs.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if pattern.match(stripped):
            rows.append(stripped.rstrip("{").strip())
    return rows[:16]


def normalize_external_dependency(dep_name: str, dep_spec: Any) -> str:
    if isinstance(dep_spec, str):
        return f"{dep_name}={dep_spec}"
    if isinstance(dep_spec, dict):
        if isinstance(dep_spec.get("version"), str):
            return f"{dep_name}={dep_spec['version']}"
        if dep_spec.get("optional") is True:
            return f"{dep_name}=optional"
        if isinstance(dep_spec.get("path"), str):
            return f"{dep_name}@path:{dep_spec['path']}"
    return dep_name


def build_payload() -> dict[str, Any]:
    manifests = discover_workspace_members()
    by_manifest: dict[Path, str] = {}
    by_crate: dict[str, dict[str, Any]] = {}

    for manifest in manifests:
        cargo = load_toml(manifest)
        crate_name = cargo.get("package", {}).get("name")
        if not isinstance(crate_name, str):
            continue
        by_manifest[manifest.resolve()] = crate_name
        by_crate[crate_name] = {
            "crate_name": crate_name,
            "manifest_path": manifest.relative_to(REPO_ROOT).as_posix(),
            "source_root": (manifest.parent / "src").relative_to(REPO_ROOT).as_posix(),
        }

    module_rows = []
    dependency_edges = []

    for manifest in manifests:
        cargo = load_toml(manifest)
        crate_name = cargo.get("package", {}).get("name")
        if crate_name not in by_crate:
            continue

        deps = cargo.get("dependencies", {})
        workspace_deps = set()
        external_deps = set()
        for dep_name, dep_spec in deps.items():
            dep_path = dep_spec.get("path") if isinstance(dep_spec, dict) else None
            if isinstance(dep_path, str):
                resolved_dep_manifest = (manifest.parent / dep_path / "Cargo.toml").resolve()
                target_crate = by_manifest.get(resolved_dep_manifest)
                if target_crate:
                    workspace_deps.add(target_crate)
                    continue
            external_deps.add(normalize_external_dependency(dep_name, dep_spec))

        for dep_crate in sorted(workspace_deps):
            dependency_edges.append(
                {
                    "from_crate": crate_name,
                    "to_crate": dep_crate,
                    "edge_type": "compile_time_dependency",
                    "justification": f"{crate_name} Cargo dependency on {dep_crate}",
                }
            )

        lib_rs = manifest.parent / "src/lib.rs"
        layer = LAYER_FOR_CRATE.get(crate_name, "unclassified")
        hidden_ids = sorted(
            coupling["coupling_id"]
            for coupling in HIDDEN_COUPLINGS
            if crate_name in coupling["crates_involved"]
        )
        policy = STRICT_HARDENED_POLICY_FOR_CRATE.get(
            crate_name,
            {
                "strict_mode": "Fail closed for incompatible/unknown behavior.",
                "hardened_mode": "Bounded defensive recovery with deterministic diagnostics.",
            },
        )

        module_rows.append(
            {
                "crate_name": crate_name,
                "manifest_path": by_crate[crate_name]["manifest_path"],
                "source_root": by_crate[crate_name]["source_root"],
                "layer": layer,
                "purpose": PURPOSE_FOR_CRATE.get(crate_name, "TBD"),
                "legacy_scope_paths": LEGACY_ANCHORS_FOR_CRATE.get(crate_name, []),
                "depends_on": sorted(workspace_deps),
                "external_dependencies": sorted(external_deps),
                "public_contract_surface": extract_public_contracts(lib_rs),
                "ownership_boundaries": OWNERSHIP_BOUNDARIES_FOR_CRATE.get(crate_name, []),
                "strict_hardened_policy": policy,
                "verification_hooks": VERIFICATION_HOOKS_FOR_CRATE.get(
                    crate_name,
                    {"unit": [], "property": [], "differential": [], "e2e": []},
                ),
                "known_hidden_couplings": hidden_ids,
            }
        )

    module_rows.sort(key=lambda row: (LAYER_ORDER.get(row["layer"], 99), row["crate_name"]))
    dependency_edges.sort(key=lambda row: (row["from_crate"], row["to_crate"]))

    layering_constraints = [
        {
            "constraint_id": "LC-001",
            "description": "Runtime policy layer is foundational and must not depend on higher layers.",
            "source_layer": "runtime-policy",
            "allowed_target_layers": ["runtime-policy"],
            "fail_closed_on_violation": True,
        },
        {
            "constraint_id": "LC-002",
            "description": "Storage/view/dispatch layers may depend only on runtime and same-layer support crates.",
            "source_layer": "graph-storage|graph-view-api|compat-dispatch",
            "allowed_target_layers": ["runtime-policy", "graph-storage", "graph-view-api", "compat-dispatch"],
            "fail_closed_on_violation": True,
        },
        {
            "constraint_id": "LC-003",
            "description": "Conversion/readwrite/generator/algorithm layers may depend on lower layers but not conformance.",
            "source_layer": "conversion-ingest|io-serialization|graph-generators|algorithm-engine",
            "allowed_target_layers": [
                "runtime-policy",
                "graph-storage",
                "graph-view-api",
                "compat-dispatch",
                "conversion-ingest",
                "io-serialization",
                "graph-generators",
                "algorithm-engine",
            ],
            "fail_closed_on_violation": True,
        },
        {
            "constraint_id": "LC-004",
            "description": "Durability is support infrastructure and must not depend on conformance or algorithm internals.",
            "source_layer": "durability-repair",
            "allowed_target_layers": ["durability-repair", "runtime-policy"],
            "fail_closed_on_violation": True,
        },
        {
            "constraint_id": "LC-005",
            "description": "Conformance harness may depend downward on implementation layers.",
            "source_layer": "conformance-harness",
            "allowed_target_layers": list(LAYER_ORDER.keys()),
            "fail_closed_on_violation": True,
        },
    ]

    layer_by_crate = {row["crate_name"]: row["layer"] for row in module_rows}
    layering_violations = []
    for edge in dependency_edges:
        source_layer = layer_by_crate.get(edge["from_crate"], "unclassified")
        target_layer = layer_by_crate.get(edge["to_crate"], "unclassified")
        if LAYER_ORDER.get(source_layer, 99) < LAYER_ORDER.get(target_layer, 99):
            layering_violations.append(
                {
                    "from_crate": edge["from_crate"],
                    "to_crate": edge["to_crate"],
                    "source_layer": source_layer,
                    "target_layer": target_layer,
                    "reason": "upward dependency violates layer directionality",
                }
            )

    layer_count = {}
    for row in module_rows:
        layer_count[row["layer"]] = layer_count.get(row["layer"], 0) + 1

    return {
        "schema_version": "1.0.0",
        "artifact_id": "doc-pass-01-module-cartography-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_comparator": "legacy_networkx/main@python3.12",
        "workspace_summary": {
            "crate_count": len(module_rows),
            "layer_count": layer_count,
            "dependency_edge_count": len(dependency_edges),
            "hidden_coupling_count": len(HIDDEN_COUPLINGS),
            "layering_violation_count": len(layering_violations),
        },
        "module_cartography": module_rows,
        "cross_module_dependency_map": dependency_edges,
        "layering_constraints": layering_constraints,
        "layering_violations": layering_violations,
        "hidden_coupling_hotspots": HIDDEN_COUPLINGS,
        "alien_uplift_contract_card": {
            "ev_score": 2.61,
            "baseline_comparator": "legacy_networkx/main@python3.12",
            "optimization_lever": "workspace-cartography first to reduce integration rework probability",
            "decision_hypothesis": "Explicit ownership and dependency graph lowers parity-drift incidence in downstream packet execution.",
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/BASELINE_BFS_V1.md",
            "hotspot": "artifacts/perf/OPPORTUNITY_MATRIX.md",
            "delta": "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
        },
        "decision_theoretic_runtime_contract": {
            "states": ["unmapped", "mapped", "validated", "blocked"],
            "actions": ["record_edge", "flag_hidden_coupling", "defer", "fail_closed"],
            "loss_model": "Minimize architecture ambiguity and downstream integration churn while preserving deterministic parity contracts.",
            "safe_mode_fallback": "fail_closed",
            "fallback_thresholds": {
                "max_layering_violations": 0,
                "min_hidden_coupling_inventory": 3,
            },
        },
        "isomorphism_proof_artifacts": [
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_009_V1.md",
        ],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DOC-PASS-01 Module/Package Cartography (V1)",
        "",
        f"- generated_at_utc: {payload['generated_at_utc']}",
        f"- baseline_comparator: {payload['baseline_comparator']}",
        f"- crate_count: {payload['workspace_summary']['crate_count']}",
        f"- dependency_edge_count: {payload['workspace_summary']['dependency_edge_count']}",
        f"- hidden_coupling_count: {payload['workspace_summary']['hidden_coupling_count']}",
        f"- layering_violation_count: {payload['workspace_summary']['layering_violation_count']}",
        "",
        "## Crate Topology",
        "",
        "| Crate | Layer | Depends On | Public Surface Count | Legacy Anchors |",
        "|---|---|---|---:|---:|",
    ]

    for row in payload["module_cartography"]:
        lines.append(
            f"| `{row['crate_name']}` | `{row['layer']}` | "
            f"{', '.join(f'`{dep}`' for dep in row['depends_on']) or '-'} | "
            f"{len(row['public_contract_surface'])} | {len(row['legacy_scope_paths'])} |"
        )

    lines.extend(
        [
            "",
            "## Hidden Coupling Hotspots",
            "",
            "| Coupling ID | Crates Involved | Risk | Mitigation |",
            "|---|---|---|---|",
        ]
    )
    for coupling in payload["hidden_coupling_hotspots"]:
        lines.append(
            f"| `{coupling['coupling_id']}` | "
            f"{', '.join(f'`{crate}`' for crate in coupling['crates_involved'])} | "
            f"{coupling['risk_level']} | {coupling['mitigation']} |"
        )

    if payload["layering_violations"]:
        lines.extend(
            [
                "",
                "## Layering Violations",
                "",
                "| From | To | Source Layer | Target Layer | Reason |",
                "|---|---|---|---|---|",
            ]
        )
        for violation in payload["layering_violations"]:
            lines.append(
                f"| `{violation['from_crate']}` | `{violation['to_crate']}` | "
                f"`{violation['source_layer']}` | `{violation['target_layer']}` | "
                f"{violation['reason']} |"
            )
    else:
        lines.extend(
            [
                "",
                "## Layering Violations",
                "",
                "- none (all compile-time dependencies respect declared layering order).",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-json",
        default=DEFAULT_OUTPUT_JSON.as_posix(),
        help="Output path for machine-auditable JSON artifact",
    )
    parser.add_argument(
        "--output-md",
        default=DEFAULT_OUTPUT_MD.as_posix(),
        help="Output path for human-readable markdown summary",
    )
    args = parser.parse_args()

    payload = build_payload()
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(render_markdown(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "output_json": output_json.as_posix(),
                "output_md": output_md.as_posix(),
                "crate_count": payload["workspace_summary"]["crate_count"],
                "dependency_edge_count": payload["workspace_summary"]["dependency_edge_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
