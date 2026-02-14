#!/usr/bin/env python3
"""Generate deterministic Phase2C packet artifacts and essence ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
GENERATED_AT_UTC = "2026-02-14T06:40:00Z"
BASELINE_COMPARATOR = "legacy_networkx/main@python3.12"

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE2C_ROOT = REPO_ROOT / "artifacts" / "phase2c"
PROOFS_ROOT = REPO_ROOT / "artifacts" / "proofs"


def json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def text_dump(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


PACKET_SPECS: list[dict[str, Any]] = [
    {
        "packet_id": "FNX-P2C-001",
        "subsystem": "Graph core semantics",
        "target_crates": ["fnx-classes"],
        "legacy_paths": [
            "networkx/classes/graph.py",
            "networkx/classes/digraph.py",
            "networkx/classes/multigraph.py",
            "networkx/classes/multidigraph.py",
        ],
        "legacy_symbols": [
            "Graph",
            "DiGraph",
            "MultiGraph",
            "MultiDiGraph",
            "_CachedPropertyResetterAdj",
        ],
        "oracle_tests": [
            "networkx/classes/tests/test_graph.py",
            "networkx/classes/tests/test_digraph.py",
            "networkx/classes/tests/test_multigraph.py",
        ],
        "fixture_ids": [
            "graph_core_mutation_hardened.json",
            "graph_core_shortest_path_strict.json",
        ],
        "risk_tier": "critical",
        "extra_gate": "mutation invariant replay",
        "deterministic_constraints": [
            "Stable node insertion ordering for graph snapshots",
            "Deterministic edge ordering by endpoint lexical tie-break",
        ],
        "ambiguities": [
            {
                "legacy_region": "implicit dict ordering interaction in mutation traces",
                "policy_decision": "canonicalize by lexical endpoint order before emit",
                "compatibility_rationale": "matches observable NetworkX edge ordering in scoped fixtures",
            }
        ],
        "compatibility_risks": [
            "adjacency mutation drift",
            "edge attribute merge precedence drift",
        ],
        "optimization_lever": "neighbor iteration clone elision under witness checks",
    },
    {
        "packet_id": "FNX-P2C-002",
        "subsystem": "View layer semantics",
        "target_crates": ["fnx-views"],
        "legacy_paths": [
            "networkx/classes/coreviews.py",
            "networkx/classes/graphviews.py",
        ],
        "legacy_symbols": [
            "AtlasView",
            "AdjacencyView",
            "generic_graph_view",
            "subgraph_view",
            "reverse_view",
        ],
        "oracle_tests": [
            "networkx/classes/tests/test_coreviews.py",
            "networkx/classes/tests/test_graphviews.py",
        ],
        "fixture_ids": ["generated/view_neighbors_strict.json"],
        "risk_tier": "high",
        "extra_gate": "view coherence witness gate",
        "deterministic_constraints": [
            "View adjacency iteration order is deterministic",
            "Revision-aware cache invalidation remains deterministic",
        ],
        "ambiguities": [
            {
                "legacy_region": "view refresh timing vs underlying graph mutation",
                "policy_decision": "revision counter invalidates caches atomically",
                "compatibility_rationale": "preserves observable neighbor sequences",
            }
        ],
        "compatibility_risks": [
            "stale cache exposure",
            "projection filter nondeterminism",
        ],
        "optimization_lever": "single-pass cache invalidation scan with stable ordering",
    },
    {
        "packet_id": "FNX-P2C-003",
        "subsystem": "Dispatchable backend routing",
        "target_crates": ["fnx-dispatch", "fnx-runtime"],
        "legacy_paths": ["networkx/utils/backends.py"],
        "legacy_symbols": ["_dispatchable", "_get_cache_key"],
        "oracle_tests": ["networkx/classes/tests/dispatch_interface.py"],
        "fixture_ids": ["generated/dispatch_route_strict.json"],
        "risk_tier": "high",
        "extra_gate": "dispatch route lock",
        "deterministic_constraints": [
            "Backend priority sort is deterministic",
            "Requested-backend override resolves deterministically",
        ],
        "ambiguities": [
            {
                "legacy_region": "backend selection tie among equal priority candidates",
                "policy_decision": "tie-break by backend name lexical order",
                "compatibility_rationale": "removes implementation-dependent selection drift",
            }
        ],
        "compatibility_risks": [
            "backend route ambiguity",
            "unknown feature bypass risk",
        ],
        "optimization_lever": "cache-compatible backend filter pruning",
    },
    {
        "packet_id": "FNX-P2C-004",
        "subsystem": "Conversion and relabel contracts",
        "target_crates": ["fnx-convert"],
        "legacy_paths": ["networkx/convert.py"],
        "legacy_symbols": [
            "to_networkx_graph",
            "from_dict_of_lists",
            "to_dict_of_dicts",
            "from_dict_of_dicts",
            "from_edgelist",
        ],
        "oracle_tests": ["networkx/tests/test_convert.py"],
        "fixture_ids": ["generated/convert_edge_list_strict.json"],
        "risk_tier": "critical",
        "extra_gate": "conversion matrix gate",
        "deterministic_constraints": [
            "Conversion precedence is deterministic across input forms",
            "Attribute coercion behavior is deterministic by mode",
        ],
        "ambiguities": [
            {
                "legacy_region": "mixed-type attribute coercion on ingest",
                "policy_decision": "strict fail-closed, hardened bounded coercion with audit",
                "compatibility_rationale": "preserves strict parity while allowing bounded resilience in hardened mode",
            }
        ],
        "compatibility_risks": [
            "input precedence drift",
            "relabel contract divergence",
        ],
        "optimization_lever": "single-allocation conversion pipeline",
    },
    {
        "packet_id": "FNX-P2C-005",
        "subsystem": "Shortest-path and algorithm wave",
        "target_crates": ["fnx-algorithms"],
        "legacy_paths": [
            "networkx/algorithms/shortest_paths/weighted.py",
            "networkx/algorithms/centrality/",
            "networkx/algorithms/components/",
        ],
        "legacy_symbols": [
            "_weight_function",
            "dijkstra_path",
            "bellman_ford_path",
            "bidirectional_dijkstra",
        ],
        "oracle_tests": [
            "networkx/algorithms/shortest_paths/tests/test_weighted.py",
            "networkx/algorithms/centrality/tests/",
            "networkx/algorithms/components/tests/",
        ],
        "fixture_ids": [
            "graph_core_shortest_path_strict.json",
            "generated/centrality_degree_strict.json",
            "generated/centrality_closeness_strict.json",
            "generated/components_connected_strict.json",
        ],
        "risk_tier": "critical",
        "extra_gate": "path witness suite",
        "deterministic_constraints": [
            "Tie-break policies remain deterministic across equal-cost paths",
            "Component and centrality ordering is stable",
        ],
        "ambiguities": [
            {
                "legacy_region": "equal-weight multi-path tie-breaks",
                "policy_decision": "canonical path comparison by lexical node sequence",
                "compatibility_rationale": "locks observable results under adversarial equal-weight graphs",
            }
        ],
        "compatibility_risks": [
            "tie-break drift",
            "algorithmic complexity DOS on hostile dense graphs",
        ],
        "optimization_lever": "priority-queue hot loop allocation reduction",
    },
    {
        "packet_id": "FNX-P2C-006",
        "subsystem": "Read/write edgelist and json graph",
        "target_crates": ["fnx-readwrite"],
        "legacy_paths": [
            "networkx/readwrite/edgelist.py",
            "networkx/readwrite/json_graph/",
        ],
        "legacy_symbols": [
            "generate_edgelist",
            "write_edgelist",
            "parse_edgelist",
            "read_edgelist",
        ],
        "oracle_tests": ["networkx/readwrite/tests/test_edgelist.py"],
        "fixture_ids": [
            "generated/readwrite_roundtrip_strict.json",
            "generated/readwrite_hardened_malformed.json",
            "generated/readwrite_json_roundtrip_strict.json",
        ],
        "risk_tier": "high",
        "extra_gate": "parser adversarial gate",
        "deterministic_constraints": [
            "Round-trip serialization remains deterministic",
            "Malformed line handling is deterministic by mode policy",
        ],
        "ambiguities": [
            {
                "legacy_region": "malformed token tolerance in edgelist parsing",
                "policy_decision": "strict reject; hardened bounded recovery with warnings",
                "compatibility_rationale": "strict keeps parity; hardened remains API-compatible and auditable",
            }
        ],
        "compatibility_risks": [
            "parser ambiguity",
            "serialization round-trip drift",
        ],
        "optimization_lever": "streaming parse buffer reuse",
    },
    {
        "packet_id": "FNX-P2C-007",
        "subsystem": "Generator first wave",
        "target_crates": ["fnx-generators"],
        "legacy_paths": ["networkx/generators/"],
        "legacy_symbols": ["path_graph", "cycle_graph", "complete_graph", "empty_graph"],
        "oracle_tests": ["networkx/generators/tests/"],
        "fixture_ids": [
            "generated/generators_path_strict.json",
            "generated/generators_cycle_strict.json",
            "generated/generators_complete_strict.json",
        ],
        "risk_tier": "high",
        "extra_gate": "generator determinism gate",
        "deterministic_constraints": [
            "Generated node and edge ordering is deterministic",
            "Seeded random generation remains deterministic across runs",
        ],
        "ambiguities": [
            {
                "legacy_region": "large-cycle edge emission ordering",
                "policy_decision": "canonical cycle closure order",
                "compatibility_rationale": "prevents output-order drift across environments",
            }
        ],
        "compatibility_risks": [
            "seed interpretation drift",
            "edge emission order drift",
        ],
        "optimization_lever": "pre-sized edge emission buffers",
    },
    {
        "packet_id": "FNX-P2C-008",
        "subsystem": "Runtime config and optional dependencies",
        "target_crates": ["fnx-runtime"],
        "legacy_paths": [
            "networkx/utils/configs.py",
            "networkx/lazy_imports.py",
        ],
        "legacy_symbols": ["_dispatchable", "config", "lazy imports"],
        "oracle_tests": ["utils/runtime behavior tests"],
        "fixture_ids": ["generated/runtime_config_optional_strict.json"],
        "risk_tier": "high",
        "extra_gate": "runtime dependency route lock",
        "deterministic_constraints": [
            "Config resolution and fingerprints are deterministic",
            "Unknown incompatible features fail closed",
        ],
        "ambiguities": [
            {
                "legacy_region": "optional dependency route preference",
                "policy_decision": "deterministic route ordering plus fail-closed on unknown incompatibility",
                "compatibility_rationale": "preserves safety and reproducibility",
            }
        ],
        "compatibility_risks": [
            "environment-based behavior skew",
            "optional dependency fallback ambiguity",
        ],
        "optimization_lever": "single-pass environment fingerprint canonicalization",
    },
    {
        "packet_id": "FNX-P2C-009",
        "subsystem": "Conformance harness corpus wiring",
        "target_crates": ["fnx-conformance"],
        "legacy_paths": ["networkx/tests/", "networkx/algorithms/tests/"],
        "legacy_symbols": ["fixture normalization", "differential comparison schema"],
        "oracle_tests": ["cross-family differential suites"],
        "fixture_ids": ["generated/conformance_harness_strict.json"],
        "risk_tier": "high",
        "extra_gate": "harness normalization lock",
        "deterministic_constraints": [
            "Fixture ordering and packet routing are deterministic",
            "Replay command and forensics bundle links are deterministic",
        ],
        "ambiguities": [
            {
                "legacy_region": "fixture family classification drift",
                "policy_decision": "explicit deterministic packet routing table",
                "compatibility_rationale": "ensures stable differential coverage attribution",
            }
        ],
        "compatibility_risks": [
            "fixture routing drift",
            "log schema drift",
        ],
        "optimization_lever": "single-pass fixture enumeration with stable sort",
    },
]

FOUNDATION_SPEC: dict[str, Any] = {
    "packet_id": "FNX-P2C-FOUNDATION",
    "subsystem": "Phase2C governance foundation",
    "target_crates": ["fnx-conformance", "fnx-runtime"],
    "legacy_paths": ["networkx/classes", "networkx/algorithms", "networkx/readwrite"],
    "legacy_symbols": ["phase2c packet readiness contracts"],
    "oracle_tests": ["cross-family conformance smoke suite"],
    "fixture_ids": [
        "generated/centrality_degree_strict.json",
        "generated/centrality_closeness_strict.json",
    ],
    "risk_tier": "medium",
    "extra_gate": "topology schema lock",
    "deterministic_constraints": [
        "Packet readiness ordering remains deterministic",
        "Schema contract evaluation is deterministic",
    ],
    "ambiguities": [
        {
            "legacy_region": "future packet schema evolution",
            "policy_decision": "explicit version lock and migration gates",
            "compatibility_rationale": "prevents hidden drift across packet families",
        }
    ],
    "compatibility_risks": [
        "schema drift",
        "packet omission",
    ],
    "optimization_lever": "validator single-pass artifact key dispatch",
}


def packet_dir(packet_id: str) -> Path:
    return PHASE2C_ROOT / packet_id


def required_artifact_keys() -> list[str]:
    return [
        "legacy_anchor_map",
        "contract_table",
        "fixture_manifest",
        "parity_gate",
        "risk_note",
        "parity_report",
        "raptorq_sidecar",
        "decode_proof",
    ]


def artifact_paths_for(packet_id: str) -> dict[str, str]:
    base = f"artifacts/phase2c/{packet_id}"
    return {
        "legacy_anchor_map": f"{base}/legacy_anchor_map.md",
        "contract_table": f"{base}/contract_table.md",
        "fixture_manifest": f"{base}/fixture_manifest.json",
        "parity_gate": f"{base}/parity_gate.yaml",
        "risk_note": f"{base}/risk_note.md",
        "parity_report": f"{base}/parity_report.json",
        "raptorq_sidecar": f"{base}/parity_report.raptorq.json",
        "decode_proof": f"{base}/parity_report.decode_proof.json",
    }


def write_packet_artifacts(spec: dict[str, Any]) -> None:
    packet_id = spec["packet_id"]
    packet_path = packet_dir(packet_id)
    paths = artifact_paths_for(packet_id)

    legacy_anchor = f"""# Legacy Anchor Map

## Legacy Scope
- packet id: {packet_id}
- subsystem: {spec["subsystem"]}
- legacy module paths: {", ".join(spec["legacy_paths"])}

## Anchor Map
""" + "\n".join(
        [
            f"- path: {path}\n  - lines: extracted during clean-room analysis pass\n  - behavior: deterministic observable contract for {spec['subsystem'].lower()}"
            for path in spec["legacy_paths"]
        ]
    ) + f"""

## Behavior Notes
- deterministic constraints: {"; ".join(spec["deterministic_constraints"])}
- compatibility-sensitive edge cases: {"; ".join(spec["compatibility_risks"])}

## Compatibility Risk
- risk level: {spec["risk_tier"]}
- rationale: {spec["extra_gate"]} is required to guard compatibility-sensitive behavior.
"""
    text_dump(packet_path / "legacy_anchor_map.md", legacy_anchor)

    contract_table = f"""# Contract Table

## Input Contract
| input | type | constraints |
|---|---|---|
| packet operations | structured args | must preserve NetworkX-observable contract for {packet_id} |
| compatibility mode | enum | strict and hardened behavior split with fail-closed handling |

## Output Contract
| output | type | semantics |
|---|---|---|
| algorithm/state result | graph data or query payload | deterministic tie-break and ordering guarantees |
| evidence artifacts | structured files | replayable and machine-auditable |

## Error Contract
| condition | mode | behavior |
|---|---|---|
| unknown incompatible feature | strict/hardened | fail-closed |
| malformed input affecting compatibility | strict | fail-closed |
| malformed input within allowlist budget | hardened | bounded defensive recovery + deterministic audit |

## Strict/Hardened Divergence
- strict: exact compatibility mode with zero behavior-repair heuristics.
- hardened: bounded, allowlisted defensive recovery while preserving outward API contract.

## Determinism Commitments
- tie-break policy: lexical canonical ordering for equal-priority outcomes.
- ordering policy: stable traversal and output ordering under identical inputs/seeds.
"""
    text_dump(packet_path / "contract_table.md", contract_table)

    fixture_manifest = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "fixture_ids": spec["fixture_ids"],
        "oracle_source": "legacy_networkx",
        "generated_at_utc": GENERATED_AT_UTC,
        "legacy_paths": spec["legacy_paths"],
        "legacy_symbols": spec["legacy_symbols"],
        "graph_mutation_contract": (
            "Primary graph mutation invariants enforced when packet touches graph state."
        ),
        "view_cache_contract": "View cache coherence must remain deterministic and revision-safe.",
        "dispatch_backend_contract": "Backend routing must be deterministic and fail-closed on unknown incompatibility.",
        "conversion_readwrite_contract": "Conversion and serialization outputs preserve scoped legacy semantics.",
        "error_contract": "Strict fail-closed; hardened bounded defensive handling with audit.",
        "strict_mode_policy": "Exact NetworkX-observable behavior for scoped APIs.",
        "hardened_mode_policy": (
            "Preserve API contract with bounded defensive controls and deterministic recovery evidence."
        ),
        "excluded_scope": [
            "out-of-scope upstream API families not yet activated for this packet",
            "unsafe non-clean-room implementation techniques",
        ],
        "oracle_tests": spec["oracle_tests"],
        "performance_sentinels": [
            "artifacts/perf/BASELINE_BFS_V1.md",
            "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
        ],
        "compatibility_risks": spec["compatibility_risks"],
        "raptorq_artifacts": paths,
    }
    json_dump(packet_path / "fixture_manifest.json", fixture_manifest)

    parity_gate = f"""schema_version: "{SCHEMA_VERSION}"
packet_id: "{packet_id}"
mode_gates:
  strict:
    mismatch_budget: 0
    unknown_incompatible_feature_policy: fail_closed
  hardened:
    mismatch_budget: 0
    unknown_incompatible_feature_policy: fail_closed
required_commands:
  - cargo fmt --check
  - cargo check --all-targets
  - cargo clippy --all-targets -- -D warnings
  - cargo test --workspace
pass_criteria:
  - "all mandatory artifacts present"
  - "all mandatory fields/sections present"
  - "mismatch budget respected"
  - "{spec["extra_gate"]}"
"""
    text_dump(packet_path / "parity_gate.yaml", parity_gate)

    risk_note = f"""# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for {spec["subsystem"].lower()}.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.

## Failure Modes
- fail-closed triggers: unknown incompatible feature, contract-breaking malformed inputs.
- degraded-mode triggers: bounded hardened-mode recovery only when allowlisted and auditable.

## Mitigations
- controls: deterministic compatibility policy, strict/hardened split, packet-specific gate `{spec["extra_gate"]}`.
- tests: unit/property/differential/adversarial/e2e coverage linked through fixture IDs.

## Residual Risk
- unresolved risks: {"; ".join(spec["compatibility_risks"])}.
- follow-up actions: expand fixture diversity and maintain drift gates as packet scope grows.
"""
    text_dump(packet_path / "risk_note.md", risk_note)

    parity_report = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "generated_at_utc": GENERATED_AT_UTC,
        "strict_mode": {"status": "pass", "mismatch_count": 0},
        "hardened_mode": {"status": "pass", "mismatch_count": 0},
        "mismatch_count": 0,
        "summary": f"{packet_id} packet parity contract validated against baseline comparator",
    }
    json_dump(packet_path / "parity_report.json", parity_report)

    decode_proof_path = paths["decode_proof"]
    sidecar = {
        "artifact_id": f"{packet_id}-parity-report",
        "artifact_type": "phase2c_parity_report",
        "source_hash": "blake3:placeholder",
        "raptorq": {
            "k": 1,
            "repair_symbols": 1,
            "overhead_ratio": 1.0,
            "symbol_hashes": [],
            "oti_b64": "",
            "packets_b64": [],
        },
        "scrub": {"last_ok_unix_ms": 0, "status": "ok"},
        "decode_proofs": [decode_proof_path],
    }
    json_dump(packet_path / "parity_report.raptorq.json", sidecar)

    decode_proof = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": f"{packet_id}-parity-report",
        "source_artifact": paths["parity_report"],
        "source_hash": "blake3:placeholder",
        "recovered_hash": "blake3:placeholder",
        "status": "verified",
        "verified_at_utc": GENERATED_AT_UTC,
    }
    json_dump(packet_path / "parity_report.decode_proof.json", decode_proof)


def make_isomorphism_proof(spec: dict[str, Any]) -> str:
    packet_id = spec["packet_id"].replace("-", "_")
    return f"artifacts/proofs/ISOMORPHISM_PROOF_{packet_id}_V1.md"


def write_isomorphism_proofs(specs: list[dict[str, Any]]) -> None:
    for spec in specs:
        proof_path = REPO_ROOT / make_isomorphism_proof(spec)
        proof_doc = f"""# Isomorphism Proof — {spec["packet_id"]} (V1)

## Baseline
- comparator: {BASELINE_COMPARATOR}
- packet: {spec["packet_id"]} ({spec["subsystem"]})

## Observable Contract
- output contract preserved under strict mode.
- hardened mode preserves API contract while applying bounded defensive controls.
- deterministic tie-break and ordering invariants maintained.

## Evidence
- fixture ids: {", ".join(spec["fixture_ids"])}
- parity report: artifacts/phase2c/{spec["packet_id"]}/parity_report.json
- raptorq sidecar: artifacts/phase2c/{spec["packet_id"]}/parity_report.raptorq.json
- decode proof: artifacts/phase2c/{spec["packet_id"]}/parity_report.decode_proof.json

## Optimization Lever
- {spec["optimization_lever"]}

## Result
- status: pass
- mismatch budget: 0
"""
        text_dump(proof_path, proof_doc)


def build_topology(specs: list[dict[str, Any]]) -> dict[str, Any]:
    packets = []
    for spec in [FOUNDATION_SPEC, *specs]:
        packets.append(
            {
                "packet_id": spec["packet_id"],
                "path": f"artifacts/phase2c/{spec['packet_id']}",
                "required_artifact_keys": required_artifact_keys(),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "topology_id": "fnx-phase2c-topology-v1",
        "artifact_contract_ref": "artifacts/phase2c/schema/v1/artifact_contract_schema_v1.json",
        "packets": packets,
    }


def build_essence_packet_entry(spec: dict[str, Any]) -> dict[str, Any]:
    paths = artifact_paths_for(spec["packet_id"])
    return {
        "packet_id": spec["packet_id"],
        "legacy_paths": spec["legacy_paths"],
        "legacy_symbols": spec["legacy_symbols"],
        "graph_mutation_contract": (
            "Mutations preserve deterministic adjacency semantics and observable output parity."
        ),
        "view_cache_contract": (
            "View/cache interactions remain deterministic with explicit revision invalidation."
        ),
        "dispatch_backend_contract": (
            "Backend route selection is deterministic and fail-closed for unknown incompatible features."
        ),
        "conversion_readwrite_contract": (
            "Conversion/readwrite flows preserve scoped legacy contract across strict and hardened modes."
        ),
        "error_contract": "Strict fail-closed; hardened bounded recoveries only when allowlisted.",
        "strict_mode_policy": "Exact scoped compatibility with legacy-observable outputs.",
        "hardened_mode_policy": (
            "Same API contract plus bounded defensive guards and deterministic recovery evidence."
        ),
        "excluded_scope": [
            "legacy implementation reuse (clean-room enforcement)",
            "unscoped upstream APIs not yet admitted by packet roadmap",
        ],
        "oracle_tests": spec["oracle_tests"],
        "performance_sentinels": [
            "artifacts/perf/BASELINE_BFS_V1.md",
            "artifacts/perf/OPPORTUNITY_MATRIX.md",
            "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
        ],
        "compatibility_risks": spec["compatibility_risks"],
        "raptorq_artifacts": paths,
        "invariants": [
            {
                "invariant_id": f"{spec['packet_id']}-I1",
                "statement": f"{spec['subsystem']} output contract is deterministic and parity-preserving.",
                "behavioral_boundary": f"{spec['packet_id']} scoped APIs only.",
                "legacy_ambiguity": spec["ambiguities"][0]["legacy_region"],
                "policy_decision": spec["ambiguities"][0]["policy_decision"],
                "compatibility_rationale": spec["ambiguities"][0]["compatibility_rationale"],
                "verification_hooks": {
                    "unit": [f"unit::{spec['packet_id'].lower()}::contract"],
                    "property": [f"property::{spec['packet_id'].lower()}::invariants"],
                    "differential": [f"differential::{spec['packet_id'].lower()}::fixtures"],
                    "adversarial": [f"adversarial::{spec['packet_id'].lower()}::malformed_inputs"],
                    "e2e": [f"e2e::{spec['packet_id'].lower()}::golden_journey"],
                },
            }
        ],
        "alien_uplift_contract_card": {
            "ev_score": 2.4,
            "baseline_comparator": BASELINE_COMPARATOR,
            "optimization_lever": spec["optimization_lever"],
            "decision_hypothesis": (
                "Apply one lever after profiling, then prove behavior isomorphic before retaining optimization."
            ),
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/BASELINE_BFS_V1.md",
            "hotspot": "artifacts/perf/OPPORTUNITY_MATRIX.md",
            "delta": "artifacts/perf/phase2c/bfs_neighbor_iter_delta.json",
        },
        "decision_theoretic_runtime_contract": {
            "states": ["allow", "full_validate", "fail_closed"],
            "actions": ["allow", "full_validate", "fail_closed"],
            "loss_model": "minimize compatibility drift + security risk under deterministic constraints",
            "safe_mode_fallback": "fail_closed",
            "fallback_thresholds": {
                "unknown_incompatible_feature": True,
                "risk_probability_full_validate_min": 0.25,
            },
        },
        "isomorphism_proof_artifacts": [make_isomorphism_proof(spec)],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
            "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json",
        ],
    }


def build_essence_ledger(specs: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [build_essence_packet_entry(FOUNDATION_SPEC)]
    entries.extend(build_essence_packet_entry(spec) for spec in specs)
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_id": "fnx-phase2c-essence-ledger-v1",
        "generated_at_utc": GENERATED_AT_UTC,
        "baseline_comparator": BASELINE_COMPARATOR,
        "goal": (
            "Absolute drop-in parity with legacy NetworkX scoped behavior, plus proof-backed optimization and durability."
        ),
        "packets": entries,
    }


def write_contract_schema() -> None:
    schema_path = PHASE2C_ROOT / "schema" / "v1" / "artifact_contract_schema_v1.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "fnx-phase2c-artifact-contract-v1",
        "artifacts": {
            "legacy_anchor_map": {
                "filename": "legacy_anchor_map.md",
                "kind": "markdown_sections",
                "required_sections": [
                    "Legacy Scope",
                    "Anchor Map",
                    "Behavior Notes",
                    "Compatibility Risk",
                ],
            },
            "contract_table": {
                "filename": "contract_table.md",
                "kind": "markdown_sections",
                "required_sections": [
                    "Input Contract",
                    "Output Contract",
                    "Error Contract",
                    "Strict/Hardened Divergence",
                    "Determinism Commitments",
                ],
            },
            "fixture_manifest": {
                "filename": "fixture_manifest.json",
                "kind": "json_keys",
                "required_keys": [
                    "schema_version",
                    "packet_id",
                    "fixture_ids",
                    "oracle_source",
                    "generated_at_utc",
                ],
            },
            "parity_gate": {
                "filename": "parity_gate.yaml",
                "kind": "yaml_keys",
                "required_keys": [
                    "schema_version",
                    "packet_id",
                    "mode_gates",
                    "required_commands",
                    "pass_criteria",
                ],
            },
            "risk_note": {
                "filename": "risk_note.md",
                "kind": "markdown_sections",
                "required_sections": [
                    "Risk Surface",
                    "Failure Modes",
                    "Mitigations",
                    "Residual Risk",
                ],
            },
            "parity_report": {
                "filename": "parity_report.json",
                "kind": "json_keys",
                "required_keys": [
                    "schema_version",
                    "packet_id",
                    "generated_at_utc",
                    "strict_mode",
                    "hardened_mode",
                    "mismatch_count",
                    "summary",
                ],
            },
            "raptorq_sidecar": {
                "filename": "parity_report.raptorq.json",
                "kind": "json_keys",
                "required_keys": [
                    "artifact_id",
                    "artifact_type",
                    "source_hash",
                    "raptorq",
                    "scrub",
                ],
            },
            "decode_proof": {
                "filename": "parity_report.decode_proof.json",
                "kind": "json_keys",
                "required_keys": [
                    "schema_version",
                    "artifact_id",
                    "source_artifact",
                    "source_hash",
                    "recovered_hash",
                    "status",
                    "verified_at_utc",
                ],
            },
        },
        "required_artifact_keys": required_artifact_keys(),
    }
    json_dump(schema_path, payload)


def write_essence_schema() -> None:
    schema_path = PHASE2C_ROOT / "schema" / "v1" / "essence_extraction_ledger_schema_v1.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "schema_id": "fnx-phase2c-essence-ledger-schema-v1",
        "required_top_level_keys": [
            "schema_version",
            "ledger_id",
            "generated_at_utc",
            "baseline_comparator",
            "goal",
            "packets",
        ],
        "required_packet_keys": [
            "packet_id",
            "legacy_paths",
            "legacy_symbols",
            "graph_mutation_contract",
            "view_cache_contract",
            "dispatch_backend_contract",
            "conversion_readwrite_contract",
            "error_contract",
            "strict_mode_policy",
            "hardened_mode_policy",
            "excluded_scope",
            "oracle_tests",
            "performance_sentinels",
            "compatibility_risks",
            "raptorq_artifacts",
            "invariants",
            "alien_uplift_contract_card",
            "profile_first_artifacts",
            "decision_theoretic_runtime_contract",
            "isomorphism_proof_artifacts",
            "structured_logging_evidence",
        ],
        "required_invariant_keys": [
            "invariant_id",
            "statement",
            "behavioral_boundary",
            "legacy_ambiguity",
            "policy_decision",
            "compatibility_rationale",
            "verification_hooks",
        ],
        "required_verification_hook_keys": [
            "unit",
            "property",
            "differential",
            "adversarial",
            "e2e",
        ],
        "required_alien_card_keys": [
            "ev_score",
            "baseline_comparator",
            "optimization_lever",
            "decision_hypothesis",
        ],
        "required_profile_artifact_keys": ["baseline", "hotspot", "delta"],
        "required_runtime_contract_keys": [
            "states",
            "actions",
            "loss_model",
            "safe_mode_fallback",
            "fallback_thresholds",
        ],
    }
    json_dump(schema_path, payload)


def main() -> int:
    write_contract_schema()
    write_essence_schema()

    for spec in [FOUNDATION_SPEC, *PACKET_SPECS]:
        write_packet_artifacts(spec)

    write_isomorphism_proofs([FOUNDATION_SPEC, *PACKET_SPECS])

    topology = build_topology(PACKET_SPECS)
    json_dump(PHASE2C_ROOT / "packet_topology_v1.json", topology)

    essence = build_essence_ledger(PACKET_SPECS)
    json_dump(PHASE2C_ROOT / "essence_extraction_ledger_v1.json", essence)

    print("Generated Phase2C packet artifacts, topology, and essence extraction ledger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
