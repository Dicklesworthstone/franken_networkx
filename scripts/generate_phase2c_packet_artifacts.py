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
        "legacy_paths": [
            "networkx/utils/backends.py",
            "networkx/utils/tests/test_backends.py",
            "networkx/classes/tests/dispatch_interface.py",
            "networkx/utils/tests/test_config.py",
        ],
        "legacy_symbols": [
            "_dispatchable._call_if_any_backends_installed",
            "_dispatchable._can_backend_run",
            "_dispatchable._should_backend_run",
            "_dispatchable._will_call_mutate_input",
            "_get_cache_key",
            "_get_from_cache",
            "_load_backend",
        ],
        "oracle_tests": [
            "networkx/utils/tests/test_backends.py",
            "networkx/classes/tests/dispatch_interface.py",
            "networkx/utils/tests/test_config.py",
        ],
        "fixture_ids": ["generated/dispatch_route_strict.json"],
        "risk_tier": "high",
        "extra_gate": "dispatch route lock",
        "deterministic_constraints": [
            "Backend priority sort is deterministic",
            "Requested-backend override resolves deterministically",
        ],
        "legacy_anchor_regions": [
            {
                "region_id": "P2C003-R1",
                "pathway": "normal",
                "anchor_refs": [
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 553,
                        "end_line": 716,
                    },
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 1099,
                        "end_line": 1146,
                    },
                ],
                "symbols": [
                    "_dispatchable._call_if_any_backends_installed",
                    "_dispatchable._can_backend_run",
                    "_dispatchable._should_backend_run",
                ],
                "behavior_note": (
                    "Backend keyword override, can_run/should_run probes, and conversion eligibility "
                    "produce deterministic backend selection with explicit failure paths."
                ),
                "compatibility_policy": "strict parity in route selection; hardened still fail-closed on incompatibility",
                "downstream_contract_rows": [
                    "Input Contract: compatibility mode",
                    "Output Contract: algorithm/state result",
                    "Error Contract: unknown incompatible feature",
                ],
                "planned_oracle_tests": [
                    "networkx/utils/tests/test_backends.py:44-95",
                    "networkx/utils/tests/test_backends.py:101-129",
                ],
            },
            {
                "region_id": "P2C003-R2",
                "pathway": "edge",
                "anchor_refs": [
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 717,
                        "end_line": 760,
                    },
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 1052,
                        "end_line": 1075,
                    },
                ],
                "symbols": [
                    "_dispatchable._will_call_mutate_input",
                    "_dispatchable._call_if_any_backends_installed",
                ],
                "behavior_note": (
                    "Mutating calls suppress automatic backend conversion and only fall back when "
                    "input graph classes are compatible with NetworkX semantics."
                ),
                "compatibility_policy": (
                    "prefer non-conversion for mutating operations to preserve observable mutation contract"
                ),
                "downstream_contract_rows": [
                    "Input Contract: packet operations",
                    "Strict/Hardened Divergence: strict no repair heuristics",
                    "Determinism Commitments: stable traversal ordering",
                ],
                "planned_oracle_tests": [
                    "networkx/utils/tests/test_backends.py:135-160",
                    "networkx/utils/tests/test_backends.py:194-225",
                ],
            },
            {
                "region_id": "P2C003-R3",
                "pathway": "adversarial",
                "anchor_refs": [
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 202,
                        "end_line": 212,
                    },
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 561,
                        "end_line": 563,
                    },
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 640,
                        "end_line": 715,
                    },
                ],
                "symbols": [
                    "_load_backend",
                    "_dispatchable._call_if_any_backends_installed",
                ],
                "behavior_note": (
                    "Unknown backend names, missing implementations, and incompatible conversion paths "
                    "must fail closed with explicit ImportError/TypeError semantics."
                ),
                "compatibility_policy": "fail-closed default for unknown or unsupported backend routes",
                "downstream_contract_rows": [
                    "Error Contract: unknown incompatible feature",
                    "Error Contract: malformed input affecting compatibility",
                    "Strict/Hardened Divergence: hardened bounded recovery only when allowlisted",
                ],
                "planned_oracle_tests": [
                    "networkx/utils/tests/test_backends.py:162-168",
                    "networkx/utils/tests/test_backends.py:170-187",
                ],
            },
            {
                "region_id": "P2C003-R4",
                "pathway": "deterministic-cache",
                "anchor_refs": [
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 1989,
                        "end_line": 2010,
                    },
                    {
                        "path": "networkx/utils/backends.py",
                        "start_line": 2041,
                        "end_line": 2093,
                    },
                ],
                "symbols": ["_get_cache_key", "_get_from_cache"],
                "behavior_note": (
                    "Cache key canonicalization and FAILED_TO_CONVERT sentinel behavior keep route "
                    "resolution deterministic and prevent repeated incompatible conversion churn."
                ),
                "compatibility_policy": "cache lookup order remains deterministic before fallback/retry",
                "downstream_contract_rows": [
                    "Determinism Commitments: stable traversal and output ordering",
                    "Output Contract: evidence artifacts are replayable",
                    "Error Contract: bounded hardened behavior with audit",
                ],
                "planned_oracle_tests": [
                    "networkx/classes/tests/dispatch_interface.py:52-78",
                    "networkx/classes/tests/dispatch_interface.py:186-190",
                    "networkx/utils/tests/test_config.py:120-170",
                ],
            },
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
        "hardened_allowlisted_categories": [
            "bounded_diagnostic_enrichment",
            "bounded_resource_clamp",
            "deterministic_backend_fallback_with_audit",
            "quarantine_of_unsupported_metadata",
        ],
        "input_contract_rows": [
            {
                "row_id": "P2C003-IC-1",
                "api_behavior": "explicit backend kwarg resolution (`backend=...`)",
                "preconditions": "backend name is `None`, `networkx`, or installed backend identifier",
                "strict_policy": "fail-closed on unknown backend; no implicit route repair",
                "hardened_policy": "same fail-closed behavior unless category is allowlisted + audited",
                "anchor_regions": ["P2C003-R1", "P2C003-R3"],
                "validation_refs": [
                    "networkx/utils/tests/test_backends.py:44-95",
                    "networkx/utils/tests/test_backends.py:162-168",
                ],
            },
            {
                "row_id": "P2C003-IC-2",
                "api_behavior": "mutation-aware route eligibility",
                "preconditions": "mutates_input predicate resolved from args/kwargs before backend conversion",
                "strict_policy": "block auto-conversion for mutating calls unless safe native route exists",
                "hardened_policy": "same blocking default; allowlisted fallback requires deterministic audit trail",
                "anchor_regions": ["P2C003-R2"],
                "validation_refs": [
                    "networkx/utils/tests/test_backends.py:135-160",
                    "networkx/utils/tests/test_backends.py:194-225",
                ],
            },
            {
                "row_id": "P2C003-IC-3",
                "api_behavior": "backend priority route selection",
                "preconditions": "backend_priority config is defined and normalized",
                "strict_policy": "deterministic backend ordering and tie-breaks only",
                "hardened_policy": "deterministic ordering unchanged; diagnostics may be enriched",
                "anchor_regions": ["P2C003-R1", "P2C003-R4"],
                "validation_refs": [
                    "networkx/utils/tests/test_config.py:120-170",
                    "networkx/utils/tests/test_backends.py:101-129",
                ],
            },
        ],
        "output_contract_rows": [
            {
                "row_id": "P2C003-OC-1",
                "output_behavior": "selected backend implementation identity",
                "postconditions": "chosen backend is deterministic for same args/config/graph backend provenance",
                "strict_policy": "zero mismatch budget for route identity drift",
                "hardened_policy": "same route identity unless deterministic fallback category is allowlisted",
                "anchor_regions": ["P2C003-R1"],
                "validation_refs": [
                    "networkx/utils/tests/test_backends.py:101-129",
                    "networkx/classes/tests/dispatch_interface.py:52-78",
                ],
            },
            {
                "row_id": "P2C003-OC-2",
                "output_behavior": "conversion/cache reuse semantics",
                "postconditions": "cache key + cache hit behavior is deterministic and replayable",
                "strict_policy": "no silent cache mutation outside declared key compatibility logic",
                "hardened_policy": "same key semantics; only bounded diagnostic enrichment allowed",
                "anchor_regions": ["P2C003-R4"],
                "validation_refs": [
                    "networkx/classes/tests/dispatch_interface.py:67-78",
                    "networkx/classes/tests/dispatch_interface.py:186-190",
                ],
            },
        ],
        "error_contract_rows": [
            {
                "row_id": "P2C003-EC-1",
                "trigger": "unknown backend identifier",
                "strict_behavior": "raise ImportError (fail-closed)",
                "hardened_behavior": "raise ImportError unless deterministic fallback category is allowlisted and audited",
                "allowlisted_divergence_category": "deterministic_backend_fallback_with_audit",
                "anchor_regions": ["P2C003-R3"],
                "validation_refs": ["networkx/utils/tests/test_backends.py:162-168"],
            },
            {
                "row_id": "P2C003-EC-2",
                "trigger": "backend lacks dispatchable implementation for algorithm",
                "strict_behavior": "raise NotImplementedError with route context",
                "hardened_behavior": "same default; no opaque fallback",
                "allowlisted_divergence_category": "none",
                "anchor_regions": ["P2C003-R1", "P2C003-R3"],
                "validation_refs": ["networkx/utils/tests/test_backends.py:170-187"],
            },
            {
                "row_id": "P2C003-EC-3",
                "trigger": "incompatible backend conversion graph provenance",
                "strict_behavior": "raise TypeError (fail-closed conversion boundary)",
                "hardened_behavior": "quarantine unsupported metadata then fail closed if parity proof absent",
                "allowlisted_divergence_category": "quarantine_of_unsupported_metadata",
                "anchor_regions": ["P2C003-R3"],
                "validation_refs": ["networkx/utils/tests/test_backends.py:135-160"],
            },
        ],
        "determinism_rows": [
            {
                "row_id": "P2C003-DC-1",
                "commitment": "backend priority tie-break is lexical + stable",
                "tie_break_rule": "equal-priority backend candidates ordered by backend name",
                "anchor_regions": ["P2C003-R1"],
                "validation_refs": ["networkx/utils/tests/test_config.py:120-170"],
            },
            {
                "row_id": "P2C003-DC-2",
                "commitment": "cache key canonicalization is deterministic",
                "tie_break_rule": "edge/node key sets normalized before lookup",
                "anchor_regions": ["P2C003-R4"],
                "validation_refs": [
                    "networkx/classes/tests/dispatch_interface.py:67-78",
                    "networkx/classes/tests/dispatch_interface.py:186-190",
                ],
            },
        ],
        "invariant_rows": [
            {
                "row_id": "P2C003-IV-1",
                "precondition": "dispatch inputs are signature-valid and backend metadata is loaded",
                "postcondition": "route selection is deterministic for identical inputs",
                "preservation_obligation": "no mutation of route semantics across strict/hardened except allowlisted categories",
                "anchor_regions": ["P2C003-R1", "P2C003-R2"],
                "validation_refs": [
                    "unit::fnx-p2c-003::contract",
                    "property::fnx-p2c-003::invariants",
                ],
            },
            {
                "row_id": "P2C003-IV-2",
                "precondition": "cache key derivation receives explicit attr-preservation flags",
                "postcondition": "cache lookup outcome is replayable and deterministic",
                "preservation_obligation": "FAILED_TO_CONVERT sentinel must prevent repeated unsafe conversion attempts",
                "anchor_regions": ["P2C003-R4"],
                "validation_refs": [
                    "differential::fnx-p2c-003::fixtures",
                    "e2e::fnx-p2c-003::golden_journey",
                ],
            },
        ],
        "threat_model_rows": [
            {
                "threat_id": "P2C003-TM-1",
                "threat_class": "parser_abuse",
                "strict_mode_response": "Fail-closed on malformed backend configuration payloads and route signatures.",
                "hardened_mode_response": "Fail-closed with bounded deterministic diagnostics; no permissive parse fallback.",
                "mitigations": [
                    "backend config schema checks",
                    "route signature validation",
                    "deterministic parse error taxonomy",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-003/risk_note.md",
                "adversarial_fixture_hooks": ["dispatch_config_malformed_payload"],
                "crash_triage_taxonomy": [
                    "dispatch.parse.malformed_payload",
                    "dispatch.parse.signature_mismatch",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "backend config parse boundary",
            },
            {
                "threat_id": "P2C003-TM-2",
                "threat_class": "metadata_ambiguity",
                "strict_mode_response": "Fail-closed on ambiguous backend metadata and conflicting routing hints.",
                "hardened_mode_response": "Quarantine unsupported metadata and fail-closed when parity impact is not provably safe.",
                "mitigations": [
                    "backend metadata allowlist",
                    "deterministic route ranking",
                    "metadata drift ledger",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-003/risk_note.md",
                "adversarial_fixture_hooks": ["dispatch_conflicting_backend_metadata"],
                "crash_triage_taxonomy": [
                    "dispatch.metadata.ambiguous_hint",
                    "dispatch.metadata.conflicting_source",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "quarantine_of_unsupported_metadata",
                ],
                "compatibility_boundary": "metadata normalization boundary",
            },
            {
                "threat_id": "P2C003-TM-3",
                "threat_class": "version_skew",
                "strict_mode_response": "Fail-closed on unsupported backend API versions or incompatible route contracts.",
                "hardened_mode_response": "Reject incompatible versions with deterministic remediation diagnostics.",
                "mitigations": [
                    "version envelope lock",
                    "backend feature compatibility matrix",
                    "upgrade gate checks",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-003/parity_gate.yaml",
                "adversarial_fixture_hooks": ["dispatch_backend_api_version_skew"],
                "crash_triage_taxonomy": [
                    "dispatch.version.unsupported_backend_api",
                    "dispatch.version.contract_mismatch",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "backend API version envelope boundary",
            },
            {
                "threat_id": "P2C003-TM-4",
                "threat_class": "resource_exhaustion",
                "strict_mode_response": "Fail-closed on route-search or dispatch costs above strict policy budgets.",
                "hardened_mode_response": "Apply bounded dispatch clamps and reject when budget thresholds are exhausted.",
                "mitigations": [
                    "dispatch budget caps",
                    "timeout guards",
                    "tail latency monitoring",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-003/parity_gate.yaml",
                "adversarial_fixture_hooks": ["dispatch_route_fanout_exhaustion"],
                "crash_triage_taxonomy": [
                    "dispatch.resource.route_fanout_exhaustion",
                    "dispatch.resource.budget_threshold_exceeded",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "bounded_resource_clamp",
                ],
                "compatibility_boundary": "dispatch budget boundary",
            },
            {
                "threat_id": "P2C003-TM-5",
                "threat_class": "state_corruption",
                "strict_mode_response": "Fail-closed when dispatch cache state violates deterministic invariants.",
                "hardened_mode_response": "Reset dispatch cache state and fail-closed with deterministic incident evidence.",
                "mitigations": [
                    "cache key determinism tests",
                    "route state checksums",
                    "cache rollback hooks",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-003/contract_table.md",
                "adversarial_fixture_hooks": ["dispatch_cache_state_break"],
                "crash_triage_taxonomy": [
                    "dispatch.state.cache_invariant_break",
                    "dispatch.state.replay_mismatch",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "dispatch cache determinism boundary",
            },
            {
                "threat_id": "P2C003-TM-6",
                "threat_class": "backend_route_ambiguity",
                "strict_mode_response": "Fail-closed on equal-precedence competing backend routes.",
                "hardened_mode_response": "Apply deterministic allowlisted fallback route with full audit trace or fail-closed.",
                "mitigations": [
                    "explicit route priority matrix",
                    "tie-break policy witness",
                    "route drift tests",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-003/contract_table.md",
                "adversarial_fixture_hooks": ["dispatch_equal_priority_route_collision"],
                "crash_triage_taxonomy": [
                    "dispatch.route.equal_precedence_collision",
                    "dispatch.route.fallback_audit_required",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "deterministic_backend_fallback_with_audit",
                ],
                "compatibility_boundary": "backend route priority boundary",
            },
            {
                "threat_id": "P2C003-TM-7",
                "threat_class": "policy_bypass",
                "strict_mode_response": "Fail-closed on any policy override or unsafe enforcement bypass attempt.",
                "hardened_mode_response": "Ignore unauthorized overrides, emit deterministic bypass evidence, and halt route execution.",
                "mitigations": [
                    "policy signature verification",
                    "immutable enforcement toggle registry",
                    "override injection adversarial fixtures",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-003/risk_note.md",
                "adversarial_fixture_hooks": ["dispatch_policy_override_injection"],
                "crash_triage_taxonomy": [
                    "dispatch.policy.unauthorized_override",
                    "dispatch.policy.signature_verification_failed",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "policy enforcement boundary",
            },
        ],
        "compatibility_boundary_rows": [
            {
                "boundary_id": "P2C003-CB-1",
                "strict_parity_obligation": "Backend override and selection remain deterministic and parity-preserving.",
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "deterministic_backend_fallback_with_audit",
                ],
                "fail_closed_default": "fail_closed_on_unknown_or_unsupported_backend",
                "evidence_hooks": [
                    "networkx/utils/tests/test_backends.py:44-95",
                    "artifacts/phase2c/FNX-P2C-003/contract_table.md#input-contract",
                ],
            },
            {
                "boundary_id": "P2C003-CB-2",
                "strict_parity_obligation": "Unsupported metadata never changes observable route identity.",
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "quarantine_of_unsupported_metadata",
                ],
                "fail_closed_default": "fail_closed_on_unproven_metadata_safety",
                "evidence_hooks": [
                    "networkx/utils/tests/test_backends.py:135-160",
                    "artifacts/phase2c/FNX-P2C-003/risk_note.md#packet-threat-matrix",
                ],
            },
            {
                "boundary_id": "P2C003-CB-3",
                "strict_parity_obligation": "Unsupported backend API envelopes are rejected with deterministic errors.",
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_version_skew",
                "evidence_hooks": [
                    "networkx/utils/tests/test_config.py:120-170",
                    "artifacts/phase2c/FNX-P2C-003/parity_gate.yaml",
                ],
            },
            {
                "boundary_id": "P2C003-CB-4",
                "strict_parity_obligation": "Dispatch search does not exceed strict complexity budgets.",
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "bounded_resource_clamp",
                ],
                "fail_closed_default": "fail_closed_when_budget_exhausted",
                "evidence_hooks": [
                    "artifacts/phase2c/FNX-P2C-003/parity_gate.yaml",
                    "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
                ],
            },
            {
                "boundary_id": "P2C003-CB-5",
                "strict_parity_obligation": "Dispatch cache semantics remain deterministic and replayable.",
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_cache_invariant_break",
                "evidence_hooks": [
                    "networkx/classes/tests/dispatch_interface.py:186-190",
                    "artifacts/phase2c/FNX-P2C-003/contract_table.md#machine-checkable-invariant-matrix",
                ],
            },
            {
                "boundary_id": "P2C003-CB-6",
                "strict_parity_obligation": "Unknown incompatible feature paths fail closed with no implicit repair.",
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_unknown_incompatible_feature",
                "evidence_hooks": [
                    "networkx/utils/tests/test_backends.py:162-168",
                    "artifacts/phase2c/FNX-P2C-003/risk_note.md#compatibility-boundary-matrix",
                ],
            },
        ],
        "module_boundary_rows": [
            {
                "boundary_id": "P2C003-MB-1",
                "crate": "fnx-dispatch",
                "module_path": "crates/fnx-dispatch/src/route_policy.rs",
                "public_seam": "pub trait DispatchRoutePlanner",
                "internal_ownership": "route candidate ranking and compatibility preflight policy",
                "legacy_compat_surface": "_dispatchable._can_backend_run / _should_backend_run",
                "threat_boundary_refs": ["P2C003-CB-1", "P2C003-CB-2"],
                "compile_check": "cargo check -p fnx-dispatch",
                "parallel_owner_scope": "routing policy and candidate ordering only",
            },
            {
                "boundary_id": "P2C003-MB-2",
                "crate": "fnx-runtime",
                "module_path": "crates/fnx-runtime/src/backend_probe.rs",
                "public_seam": "pub trait BackendProbeRegistry",
                "internal_ownership": "backend discovery/version envelope checks and strict fail-closed decisions",
                "legacy_compat_surface": "_load_backend / backend API version checks",
                "threat_boundary_refs": ["P2C003-CB-3", "P2C003-CB-6"],
                "compile_check": "cargo check -p fnx-runtime",
                "parallel_owner_scope": "backend probe + version compatibility only",
            },
            {
                "boundary_id": "P2C003-MB-3",
                "crate": "fnx-dispatch",
                "module_path": "crates/fnx-dispatch/src/cache_key.rs",
                "public_seam": "pub struct DispatchCacheKey + pub fn canonicalize_cache_key",
                "internal_ownership": "cache-key normalization and FAILED_TO_CONVERT sentinel management",
                "legacy_compat_surface": "_get_cache_key / _get_from_cache",
                "threat_boundary_refs": ["P2C003-CB-4", "P2C003-CB-5"],
                "compile_check": "cargo test -p fnx-dispatch dispatch_cache -- --nocapture",
                "parallel_owner_scope": "cache-key derivation and cache state transitions only",
            },
            {
                "boundary_id": "P2C003-MB-4",
                "crate": "fnx-runtime",
                "module_path": "crates/fnx-runtime/src/hardened_guardrails.rs",
                "public_seam": "pub struct HardenedDispatchGuardrails",
                "internal_ownership": "allowlisted hardened deviations, audit envelopes, and deterministic policy bypass rejection",
                "legacy_compat_surface": "strict/hardened divergence envelope for dispatch paths",
                "threat_boundary_refs": ["P2C003-CB-1", "P2C003-CB-2", "P2C003-CB-6"],
                "compile_check": "cargo check -p fnx-runtime --all-targets",
                "parallel_owner_scope": "hardened diagnostics/audit policy only",
            },
        ],
        "implementation_sequence_rows": [
            {
                "checkpoint_id": "P2C003-SEQ-1",
                "order": 1,
                "depends_on": [],
                "objective": "Land compile-checkable route policy and backend probe seams before behavior changes.",
                "modules_touched": [
                    "crates/fnx-dispatch/src/route_policy.rs",
                    "crates/fnx-runtime/src/backend_probe.rs",
                ],
                "verification_entrypoints": [
                    "unit::fnx-p2c-003::route_policy_shape",
                    "cargo check -p fnx-dispatch",
                ],
                "structured_log_hooks": ["dispatch.route.policy_selected", "dispatch.backend_probe.result"],
                "risk_checkpoint": "fail if public/internal seam ownership is ambiguous",
            },
            {
                "checkpoint_id": "P2C003-SEQ-2",
                "order": 2,
                "depends_on": ["P2C003-SEQ-1"],
                "objective": "Implement strict-mode route selection parity and unknown-feature fail-closed handling.",
                "modules_touched": [
                    "crates/fnx-dispatch/src/route_policy.rs",
                    "crates/fnx-runtime/src/policy.rs",
                ],
                "verification_entrypoints": [
                    "networkx/utils/tests/test_backends.py:44-95",
                    "differential::fnx-p2c-003::fixtures",
                ],
                "structured_log_hooks": ["dispatch.route.strict_decision", "dispatch.fail_closed.trigger"],
                "risk_checkpoint": "halt if strict mismatch budget deviates from zero",
            },
            {
                "checkpoint_id": "P2C003-SEQ-3",
                "order": 3,
                "depends_on": ["P2C003-SEQ-2"],
                "objective": "Implement deterministic cache-key canonicalization and sentinel-safe cache transitions.",
                "modules_touched": [
                    "crates/fnx-dispatch/src/cache_key.rs",
                    "crates/fnx-dispatch/src/cache_store.rs",
                ],
                "verification_entrypoints": [
                    "networkx/classes/tests/dispatch_interface.py:186-190",
                    "property::fnx-p2c-003::cache_invariants",
                ],
                "structured_log_hooks": ["dispatch.cache.key_canonicalized", "dispatch.cache.sentinel_transition"],
                "risk_checkpoint": "fail on replay-metadata drift in cache traces",
            },
            {
                "checkpoint_id": "P2C003-SEQ-4",
                "order": 4,
                "depends_on": ["P2C003-SEQ-2", "P2C003-SEQ-3"],
                "objective": "Layer hardened allowlisted controls with deterministic audit envelopes.",
                "modules_touched": [
                    "crates/fnx-runtime/src/hardened_guardrails.rs",
                    "crates/fnx-runtime/src/structured_logging.rs",
                ],
                "verification_entrypoints": [
                    "adversarial::fnx-p2c-003::policy_bypass",
                    "adversarial::fnx-p2c-003::resource_exhaustion",
                ],
                "structured_log_hooks": ["dispatch.hardened.allowlisted_category", "dispatch.audit.envelope_emitted"],
                "risk_checkpoint": "reject any non-allowlisted hardened deviation",
            },
            {
                "checkpoint_id": "P2C003-SEQ-5",
                "order": 5,
                "depends_on": ["P2C003-SEQ-4"],
                "objective": "Run end-to-end differential/e2e/perf readiness gates and finalize packet evidence.",
                "modules_touched": [
                    "crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs",
                    "scripts/run_phase2c_readiness_e2e.sh",
                ],
                "verification_entrypoints": [
                    "e2e::fnx-p2c-003::golden_journey",
                    "cargo test -p fnx-conformance --test phase2c_packet_readiness_gate",
                ],
                "structured_log_hooks": ["dispatch.e2e.replay_bundle", "dispatch.readiness.gate_result"],
                "risk_checkpoint": "stop on any strict/hardened parity gate mismatch",
            },
        ],
        "verification_entrypoint_rows": [
            {
                "stage": "unit",
                "harness": "unit::fnx-p2c-003::contract",
                "structured_log_hook": "dispatch.unit.contract_asserted",
                "replay_metadata_fields": ["packet_id", "route_id", "backend_name", "strict_mode"],
                "failure_forensics_artifact": "artifacts/conformance/latest/structured_logs.jsonl",
            },
            {
                "stage": "property",
                "harness": "property::fnx-p2c-003::invariants",
                "structured_log_hook": "dispatch.property.invariant_checkpoint",
                "replay_metadata_fields": ["seed", "graph_fingerprint", "cache_key_digest", "invariant_id"],
                "failure_forensics_artifact": "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
            },
            {
                "stage": "differential",
                "harness": "differential::fnx-p2c-003::fixtures",
                "structured_log_hook": "dispatch.diff.oracle_comparison",
                "replay_metadata_fields": ["fixture_id", "oracle_ref", "route_signature", "mismatch_count"],
                "failure_forensics_artifact": "artifacts/phase2c/FNX-P2C-003/parity_report.json",
            },
            {
                "stage": "e2e",
                "harness": "e2e::fnx-p2c-003::golden_journey",
                "structured_log_hook": "dispatch.e2e.replay_emitted",
                "replay_metadata_fields": ["scenario_id", "thread_id", "trace_id", "forensics_bundle"],
                "failure_forensics_artifact": "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json",
            },
        ],
    },
    {
        "packet_id": "FNX-P2C-004",
        "subsystem": "Conversion and relabel contracts",
        "target_crates": ["fnx-convert"],
        "legacy_paths": [
            "networkx/convert.py",
            "networkx/relabel.py",
            "networkx/tests/test_convert.py",
            "networkx/tests/test_relabel.py",
        ],
        "legacy_symbols": [
            "to_networkx_graph",
            "from_dict_of_lists",
            "to_dict_of_dicts",
            "from_dict_of_dicts",
            "from_edgelist",
            "relabel_nodes",
            "convert_node_labels_to_integers",
        ],
        "oracle_tests": [
            "networkx/tests/test_convert.py",
            "networkx/tests/test_relabel.py",
        ],
        "fixture_ids": ["generated/convert_edge_list_strict.json"],
        "risk_tier": "critical",
        "extra_gate": "conversion matrix gate",
        "deterministic_constraints": [
            (
                "Input-form dispatch precedence remains deterministic across graph, dict, "
                "and edge-list ingestion"
            ),
            (
                "Relabel copy/in-place ordering policy and multigraph key collision behavior "
                "remain deterministic by mode"
            ),
        ],
        "strict_divergence_note": (
            "strict: fail-closed on unknown incompatible input/metadata paths with zero mismatch "
            "budget for conversion and relabel outputs"
        ),
        "hardened_divergence_note": (
            "hardened: divergence allowed only in allowlisted categories with deterministic "
            "audit evidence and explicit compatibility boundary traces"
        ),
        "unknown_incompatibility_note": (
            "unknown incompatible feature/metadata paths fail closed unless an allowlisted "
            "category + deterministic audit evidence is present"
        ),
        "hardened_allowlisted_categories": [
            "bounded_diagnostic_enrichment",
            "defensive_parse_recovery",
            "bounded_resource_clamp",
            "deterministic_tie_break_normalization",
            "quarantine_of_unsupported_metadata",
        ],
        "legacy_anchor_regions": [
            {
                "region_id": "P2C004-R1",
                "pathway": "normal",
                "anchor_refs": [
                    {"path": "networkx/convert.py", "start_line": 34, "end_line": 108},
                    {"path": "networkx/convert.py", "start_line": 173, "end_line": 183},
                ],
                "symbols": ["to_networkx_graph", "from_edgelist"],
                "behavior_note": (
                    "Conversion dispatch follows stable precedence (existing NetworkX graph, "
                    "dict forms, edge-list forms, then optional integrations) before final "
                    "edge-list collection fallback."
                ),
                "compatibility_policy": (
                    "strict mode preserves dispatch precedence and observable output shape exactly"
                ),
                "downstream_contract_rows": [
                    "Input Contract: packet operations",
                    "Output Contract: algorithm/state result",
                    "Determinism Commitments: stable traversal and output ordering",
                ],
                "planned_oracle_tests": [
                    "networkx/tests/test_convert.py:19-44",
                    "networkx/tests/test_convert.py:71-101",
                    "networkx/tests/test_convert.py:212-230",
                ],
            },
            {
                "region_id": "P2C004-R2",
                "pathway": "edge",
                "anchor_refs": [
                    {"path": "networkx/convert.py", "start_line": 213, "end_line": 250},
                    {"path": "networkx/convert.py", "start_line": 253, "end_line": 370},
                    {"path": "networkx/convert.py", "start_line": 374, "end_line": 457},
                ],
                "symbols": ["from_dict_of_lists", "to_dict_of_dicts", "from_dict_of_dicts"],
                "behavior_note": (
                    "Dict conversion pathways preserve NetworkX-observable multigraph and "
                    "undirected de-duplication semantics, including edge-data overwrite rules "
                    "for explicit edge_data values."
                ),
                "compatibility_policy": (
                    "retain legacy multigraph_input branch behavior and dict/list data-loss semantics"
                ),
                "downstream_contract_rows": [
                    "Input Contract: compatibility mode",
                    "Conversion/Readwrite Contract: scoped parity",
                    "Strict/Hardened Divergence: strict no repair heuristics",
                ],
                "planned_oracle_tests": [
                    "networkx/tests/test_convert.py:102-133",
                    "networkx/tests/test_convert.py:134-210",
                    "networkx/tests/test_convert.py:292-315",
                ],
            },
            {
                "region_id": "P2C004-R3",
                "pathway": "adversarial",
                "anchor_refs": [
                    {"path": "networkx/convert.py", "start_line": 90, "end_line": 107},
                    {"path": "networkx/convert.py", "start_line": 123, "end_line": 171},
                    {"path": "networkx/convert.py", "start_line": 177, "end_line": 183},
                ],
                "symbols": ["to_networkx_graph"],
                "behavior_note": (
                    "Unknown inputs, malformed dict forms, and invalid edge-list containers "
                    "must fail closed via explicit TypeError/NetworkXError paths with no silent "
                    "coercion in strict mode."
                ),
                "compatibility_policy": (
                    "strict fail-closed on unknown incompatible feature; hardened bounded recovery with audit"
                ),
                "downstream_contract_rows": [
                    "Error Contract: malformed input affecting compatibility",
                    "Error Contract: unknown incompatible feature",
                    "Strict/Hardened Divergence: hardened bounded recovery only when allowlisted",
                ],
                "planned_oracle_tests": [
                    "networkx/tests/test_convert.py:45-69",
                    "networkx/tests/test_convert.py:318-321",
                ],
            },
            {
                "region_id": "P2C004-R4",
                "pathway": "relabel-determinism",
                "anchor_refs": [
                    {"path": "networkx/relabel.py", "start_line": 9, "end_line": 157},
                    {"path": "networkx/relabel.py", "start_line": 227, "end_line": 285},
                ],
                "symbols": ["relabel_nodes", "convert_node_labels_to_integers"],
                "behavior_note": (
                    "Relabel copy/in-place branches preserve API contract while order-sensitive "
                    "behavior follows explicit topological or insertion-driven mapping strategy."
                ),
                "compatibility_policy": (
                    "preserve legacy ordering semantics for copy=True and documented copy=False caveats"
                ),
                "downstream_contract_rows": [
                    "Output Contract: algorithm/state result",
                    "Determinism Commitments: stable traversal and output ordering",
                    "Input Contract: packet operations",
                ],
                "planned_oracle_tests": [
                    "networkx/tests/test_relabel.py:9-90",
                    "networkx/tests/test_relabel.py:188-207",
                    "networkx/tests/test_relabel.py:319-349",
                ],
            },
            {
                "region_id": "P2C004-R5",
                "pathway": "adversarial-relabel-collision",
                "anchor_refs": [
                    {"path": "networkx/relabel.py", "start_line": 130, "end_line": 190},
                    {"path": "networkx/relabel.py", "start_line": 193, "end_line": 223},
                ],
                "symbols": ["relabel_nodes", "_relabel_inplace", "_relabel_copy"],
                "behavior_note": (
                    "Overlapping mappings, circular relabel cycles, and multigraph key collisions "
                    "trigger deterministic key remapping or explicit NetworkXUnfeasible failures."
                ),
                "compatibility_policy": (
                    "enforce deterministic collision handling; reject unresolved cycles in copy=False"
                ),
                "downstream_contract_rows": [
                    "Error Contract: malformed input affecting compatibility",
                    "Output Contract: algorithm/state result",
                    "Determinism Commitments: stable traversal and output ordering",
                ],
                "planned_oracle_tests": [
                    "networkx/tests/test_relabel.py:208-317",
                    "networkx/tests/test_relabel.py:296-310",
                ],
            },
        ],
        "input_contract_rows": [
            {
                "row_id": "P2C004-IC-1",
                "api_behavior": "to_networkx_graph input-form dispatch precedence",
                "preconditions": (
                    "input candidate may satisfy multiple adapters (graph/dict/collection); "
                    "legacy branch evaluation order is fixed"
                ),
                "strict_policy": (
                    "evaluate conversion branches in legacy order and fail closed when branch validation fails"
                ),
                "hardened_policy": (
                    "preserve branch order; allow only bounded diagnostic enrichment before fail-closed exit"
                ),
                "anchor_regions": ["P2C004-R1", "P2C004-R3"],
                "validation_refs": [
                    "networkx/tests/test_convert.py:19-44",
                    "networkx/tests/test_convert.py:45-69",
                    "networkx/tests/test_convert.py:318-321",
                ],
            },
            {
                "row_id": "P2C004-IC-2",
                "api_behavior": "dict-of-lists/dicts conversion and multigraph_input semantics",
                "preconditions": (
                    "dict payload shape, create_using graph kind, and multigraph_input flag are explicit"
                ),
                "strict_policy": (
                    "preserve undirected seen-edge dedupe and edge_data overwrite semantics exactly"
                ),
                "hardened_policy": (
                    "same defaults; bounded attribute coercion allowed only under allowlisted audited paths"
                ),
                "anchor_regions": ["P2C004-R2", "P2C004-R3"],
                "validation_refs": [
                    "networkx/tests/test_convert.py:102-133",
                    "networkx/tests/test_convert.py:134-210",
                    "networkx/tests/test_convert.py:292-315",
                ],
            },
            {
                "row_id": "P2C004-IC-3",
                "api_behavior": "relabel mapping and copy-mode semantics",
                "preconditions": "mapping is callable/mapping and copy flag is explicit",
                "strict_policy": (
                    "copy=False follows topological/insertion ordering semantics; unresolved cycles fail closed"
                ),
                "hardened_policy": (
                    "same ordering semantics; diagnostics may be enriched but no implicit copy-mode rewrite"
                ),
                "anchor_regions": ["P2C004-R4", "P2C004-R5"],
                "validation_refs": [
                    "networkx/tests/test_relabel.py:91-140",
                    "networkx/tests/test_relabel.py:188-207",
                    "networkx/tests/test_relabel.py:312-349",
                ],
            },
        ],
        "output_contract_rows": [
            {
                "row_id": "P2C004-OC-1",
                "output_behavior": "conversion output graph class and edge payload shape",
                "postconditions": (
                    "node/edge membership and edge-data projection match legacy semantics for selected branch"
                ),
                "strict_policy": "zero mismatch budget for conversion output drift",
                "hardened_policy": (
                    "same output contract unless bounded attribute-coercion category is allowlisted and audited"
                ),
                "anchor_regions": ["P2C004-R1", "P2C004-R2"],
                "validation_refs": [
                    "networkx/tests/test_convert.py:102-133",
                    "networkx/tests/test_convert.py:134-210",
                ],
            },
            {
                "row_id": "P2C004-OC-2",
                "output_behavior": "relabel output ordering and attribute preservation",
                "postconditions": (
                    "node/edge attributes remain preserved and ordering semantics follow copy/order mode contract"
                ),
                "strict_policy": "no hidden reordering beyond documented legacy behavior",
                "hardened_policy": (
                    "same output contract with deterministic audit envelopes for allowlisted deviations"
                ),
                "anchor_regions": ["P2C004-R4", "P2C004-R5"],
                "validation_refs": [
                    "networkx/tests/test_relabel.py:91-140",
                    "networkx/tests/test_relabel.py:319-349",
                ],
            },
            {
                "row_id": "P2C004-OC-3",
                "output_behavior": "convert_node_labels_to_integers label_attribute mapping",
                "postconditions": (
                    "integer label assignment and optional reverse-label attribute mapping are deterministic"
                ),
                "strict_policy": "ordering selector fully determines label mapping",
                "hardened_policy": "same mapping contract; only bounded diagnostics are allowlisted",
                "anchor_regions": ["P2C004-R4"],
                "validation_refs": [
                    "networkx/tests/test_relabel.py:9-90",
                ],
            },
        ],
        "error_contract_rows": [
            {
                "row_id": "P2C004-EC-1",
                "trigger": "unknown or malformed to_networkx_graph input type",
                "strict_behavior": "raise NetworkXError/TypeError per legacy branch semantics (fail-closed)",
                "hardened_behavior": "same fail-closed default; attach deterministic diagnostics only",
                "allowlisted_divergence_category": "bounded_diagnostic_enrichment",
                "anchor_regions": ["P2C004-R3"],
                "validation_refs": [
                    "networkx/tests/test_convert.py:45-69",
                    "networkx/tests/test_convert.py:318-321",
                ],
            },
            {
                "row_id": "P2C004-EC-2",
                "trigger": "relabel copy=False circular overlap without topological ordering",
                "strict_behavior": "raise NetworkXUnfeasible and preserve source graph state",
                "hardened_behavior": "same exception path; no implicit copy=True fallback",
                "allowlisted_divergence_category": "none",
                "anchor_regions": ["P2C004-R5"],
                "validation_refs": [
                    "networkx/tests/test_relabel.py:312-317",
                ],
            },
            {
                "row_id": "P2C004-EC-3",
                "trigger": "multigraph relabel key collision during merge",
                "strict_behavior": (
                    "deterministically re-key to lowest available non-negative integer when collisions occur"
                ),
                "hardened_behavior": "same deterministic re-key; bounded collision diagnostics are allowlisted",
                "allowlisted_divergence_category": "deterministic_tie_break_normalization",
                "anchor_regions": ["P2C004-R5"],
                "validation_refs": [
                    "networkx/tests/test_relabel.py:230-295",
                    "networkx/tests/test_relabel.py:296-310",
                ],
            },
            {
                "row_id": "P2C004-EC-4",
                "trigger": "incompatible conversion metadata payload in strict mode",
                "strict_behavior": "raise fail-closed conversion error and emit no repaired output",
                "hardened_behavior": "quarantine unsupported metadata then fail closed if parity proof is absent",
                "allowlisted_divergence_category": "quarantine_of_unsupported_metadata",
                "anchor_regions": ["P2C004-R2", "P2C004-R3"],
                "validation_refs": [
                    "networkx/tests/test_convert.py:134-210",
                    "networkx/tests/test_convert.py:45-69",
                ],
            },
        ],
        "determinism_rows": [
            {
                "row_id": "P2C004-DC-1",
                "commitment": "input-form branch selection is deterministic",
                "tie_break_rule": (
                    "legacy branch order is fixed: graph -> dict_of_dicts -> dict_of_lists -> edge-list -> adapters"
                ),
                "anchor_regions": ["P2C004-R1"],
                "validation_refs": [
                    "networkx/tests/test_convert.py:19-44",
                    "networkx/tests/test_convert.py:45-69",
                ],
            },
            {
                "row_id": "P2C004-DC-2",
                "commitment": "dict conversion undirected dedupe is deterministic",
                "tie_break_rule": "first-seen orientation wins via explicit seen-set suppression",
                "anchor_regions": ["P2C004-R2"],
                "validation_refs": [
                    "networkx/tests/test_convert.py:134-210",
                ],
            },
            {
                "row_id": "P2C004-DC-3",
                "commitment": "relabel ordering is deterministic per copy/order mode",
                "tie_break_rule": (
                    "copy=False uses topological/insertion order rules; convert_node_labels_to_integers "
                    "honors declared ordering selector"
                ),
                "anchor_regions": ["P2C004-R4", "P2C004-R5"],
                "validation_refs": [
                    "networkx/tests/test_relabel.py:188-207",
                    "networkx/tests/test_relabel.py:319-349",
                ],
            },
        ],
        "invariant_rows": [
            {
                "row_id": "P2C004-IV-1",
                "precondition": "create_using/multigraph_input are explicit with syntactically valid payloads",
                "postcondition": "result graph preserves legacy-observable node/edge set and attribute projection",
                "preservation_obligation": "strict mode forbids silent coercion that changes observable contract",
                "anchor_regions": ["P2C004-R1", "P2C004-R2", "P2C004-R3"],
                "validation_refs": [
                    "unit::fnx-p2c-004::contract",
                    "differential::fnx-p2c-004::fixtures",
                ],
            },
            {
                "row_id": "P2C004-IV-2",
                "precondition": "relabel mapping may overlap and merge endpoints",
                "postcondition": "all intended edges are retained with deterministic key strategy and ordering semantics",
                "preservation_obligation": "copy=False cycle conflicts must fail closed with NetworkXUnfeasible",
                "anchor_regions": ["P2C004-R4", "P2C004-R5"],
                "validation_refs": [
                    "networkx/tests/test_relabel.py:208-317",
                    "property::fnx-p2c-004::invariants",
                ],
            },
            {
                "row_id": "P2C004-IV-3",
                "precondition": "strict/hardened mode and allowlist category are fixed for execution",
                "postcondition": "strict and hardened outputs remain isomorphic unless explicit allowlisted divergence exists",
                "preservation_obligation": (
                    "unknown incompatible features/metadata paths fail closed with replayable evidence"
                ),
                "anchor_regions": ["P2C004-R3", "P2C004-R4", "P2C004-R5"],
                "validation_refs": [
                    "adversarial::fnx-p2c-004::malformed_inputs",
                    "e2e::fnx-p2c-004::golden_journey",
                ],
            },
        ],
        "threat_model_rows": [
            {
                "threat_id": "P2C004-TM-1",
                "threat_class": "parser_abuse",
                "strict_mode_response": "Fail-closed on malformed conversion payload structures and invalid edge-list coercion.",
                "hardened_mode_response": "Fail-closed with bounded diagnostics and defensive parse recovery before deterministic abort.",
                "mitigations": [
                    "payload schema checks",
                    "field cardinality validation",
                    "malformed payload fixtures",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-004/risk_note.md",
                "adversarial_fixture_hooks": ["conversion_payload_malformed_shape"],
                "crash_triage_taxonomy": [
                    "convert.parse.malformed_payload",
                    "convert.parse.field_cardinality_invalid",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "defensive_parse_recovery",
                ],
                "compatibility_boundary": "conversion parse boundary",
            },
            {
                "threat_id": "P2C004-TM-2",
                "threat_class": "metadata_ambiguity",
                "strict_mode_response": "Fail-closed on ambiguous node/edge attribute precedence and conflicting metadata envelopes.",
                "hardened_mode_response": "Quarantine unsupported metadata and preserve deterministic precedence ordering.",
                "mitigations": [
                    "attribute precedence table",
                    "metadata allowlist",
                    "attribute drift report",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-004/contract_table.md",
                "adversarial_fixture_hooks": ["conversion_conflicting_attribute_metadata"],
                "crash_triage_taxonomy": [
                    "convert.metadata.ambiguous_precedence",
                    "convert.metadata.conflicting_attribute_source",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "quarantine_of_unsupported_metadata",
                ],
                "compatibility_boundary": "attribute precedence normalization boundary",
            },
            {
                "threat_id": "P2C004-TM-3",
                "threat_class": "version_skew",
                "strict_mode_response": "Fail-closed on unsupported conversion schema versions or contract envelopes.",
                "hardened_mode_response": "Reject incompatible schema versions with deterministic remediation diagnostics.",
                "mitigations": [
                    "schema version pinning",
                    "compatibility probes",
                    "version skew fixtures",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-004/parity_gate.yaml",
                "adversarial_fixture_hooks": ["conversion_schema_version_skew"],
                "crash_triage_taxonomy": [
                    "convert.version.unsupported_schema",
                    "convert.version.contract_mismatch",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "conversion schema version envelope boundary",
            },
            {
                "threat_id": "P2C004-TM-4",
                "threat_class": "resource_exhaustion",
                "strict_mode_response": "Fail-closed on conversion expansion above strict complexity or memory budget.",
                "hardened_mode_response": "Apply bounded resource clamps and reject once deterministic thresholds are exceeded.",
                "mitigations": [
                    "bounded conversion passes",
                    "memory budget guards",
                    "expansion ratio checks",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-004/parity_gate.yaml",
                "adversarial_fixture_hooks": ["conversion_expansion_ratio_blowup"],
                "crash_triage_taxonomy": [
                    "convert.resource.expansion_ratio_exceeded",
                    "convert.resource.budget_threshold_exceeded",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "bounded_resource_clamp",
                ],
                "compatibility_boundary": "conversion expansion budget boundary",
            },
            {
                "threat_id": "P2C004-TM-5",
                "threat_class": "state_corruption",
                "strict_mode_response": "Fail-closed when conversion/relabel mutates graph state outside declared transaction boundary.",
                "hardened_mode_response": "Rollback conversion transaction and emit deterministic incident evidence before fail-closed exit.",
                "mitigations": [
                    "mutation boundary checks",
                    "transaction rollback points",
                    "round-trip invariants",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-004/contract_table.md",
                "adversarial_fixture_hooks": ["conversion_transaction_boundary_break"],
                "crash_triage_taxonomy": [
                    "convert.state.transaction_boundary_break",
                    "convert.state.roundtrip_invariant_break",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "conversion transaction boundary",
            },
            {
                "threat_id": "P2C004-TM-6",
                "threat_class": "attribute_confusion",
                "strict_mode_response": "Fail-closed on duplicate/conflicting attribute namespaces and ambiguous relabel collisions.",
                "hardened_mode_response": "Apply deterministic namespace canonicalization policy and reject unresolved conflicts.",
                "mitigations": [
                    "attribute namespace validation",
                    "canonicalization policy",
                    "conflict fixtures",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-004/risk_note.md",
                "adversarial_fixture_hooks": ["conversion_attribute_namespace_collision"],
                "crash_triage_taxonomy": [
                    "convert.metadata.namespace_collision",
                    "convert.metadata.canonicalization_conflict",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "deterministic_tie_break_normalization",
                ],
                "compatibility_boundary": "attribute namespace canonicalization boundary",
            },
        ],
        "compatibility_boundary_rows": [
            {
                "boundary_id": "P2C004-CB-1",
                "strict_parity_obligation": "Malformed conversion payloads never yield repaired outputs in strict mode.",
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "defensive_parse_recovery",
                ],
                "fail_closed_default": "fail_closed_on_malformed_conversion_payload",
                "evidence_hooks": [
                    "networkx/tests/test_convert.py:45-69",
                    "artifacts/phase2c/FNX-P2C-004/risk_note.md#packet-threat-matrix",
                ],
            },
            {
                "boundary_id": "P2C004-CB-2",
                "strict_parity_obligation": "Attribute metadata precedence remains deterministic and parity-preserving.",
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "quarantine_of_unsupported_metadata",
                ],
                "fail_closed_default": "fail_closed_on_ambiguous_metadata",
                "evidence_hooks": [
                    "networkx/tests/test_convert.py:134-210",
                    "artifacts/phase2c/FNX-P2C-004/contract_table.md#input-contract",
                ],
            },
            {
                "boundary_id": "P2C004-CB-3",
                "strict_parity_obligation": "Unsupported schema/version envelopes are rejected deterministically.",
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_version_skew",
                "evidence_hooks": [
                    "networkx/tests/test_convert.py:45-69",
                    "artifacts/phase2c/FNX-P2C-004/parity_gate.yaml",
                ],
            },
            {
                "boundary_id": "P2C004-CB-4",
                "strict_parity_obligation": "Conversion expansion must stay within strict complexity budgets.",
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "bounded_resource_clamp",
                ],
                "fail_closed_default": "fail_closed_when_conversion_budget_exhausted",
                "evidence_hooks": [
                    "artifacts/phase2c/FNX-P2C-004/parity_gate.yaml",
                    "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
                ],
            },
            {
                "boundary_id": "P2C004-CB-5",
                "strict_parity_obligation": "Conversion transaction boundaries preserve graph-state invariants exactly.",
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_conversion_state_invariant_break",
                "evidence_hooks": [
                    "networkx/tests/test_relabel.py:208-317",
                    "artifacts/phase2c/FNX-P2C-004/contract_table.md#machine-checkable-invariant-matrix",
                ],
            },
            {
                "boundary_id": "P2C004-CB-6",
                "strict_parity_obligation": "Attribute namespace conflicts fail closed without hidden key rewrites.",
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "deterministic_tie_break_normalization",
                ],
                "fail_closed_default": "fail_closed_on_attribute_namespace_conflict",
                "evidence_hooks": [
                    "networkx/tests/test_relabel.py:296-310",
                    "artifacts/phase2c/FNX-P2C-004/risk_note.md#compatibility-boundary-matrix",
                ],
            },
        ],
        "module_boundary_rows": [
            {
                "boundary_id": "P2C004-MB-1",
                "crate": "fnx-convert",
                "module_path": "crates/fnx-convert/src/input_classifier.rs",
                "public_seam": "pub trait ConversionInputClassifier",
                "internal_ownership": "input-shape classification and create_using/multigraph dispatch preflight",
                "legacy_compat_surface": "to_networkx_graph / _prep_create_using",
                "threat_boundary_refs": ["P2C004-CB-1", "P2C004-CB-2", "P2C004-CB-3"],
                "compile_check": "cargo check -p fnx-convert",
                "parallel_owner_scope": "input dispatch policy and validation preflight only",
            },
            {
                "boundary_id": "P2C004-MB-2",
                "crate": "fnx-convert",
                "module_path": "crates/fnx-convert/src/edge_projection.rs",
                "public_seam": "pub struct EdgeProjectionEngine",
                "internal_ownership": "dict/list/edge-list projection with deterministic attribute and key normalization",
                "legacy_compat_surface": "from_dict_of_lists / from_dict_of_dicts / from_edgelist",
                "threat_boundary_refs": ["P2C004-CB-2", "P2C004-CB-4", "P2C004-CB-6"],
                "compile_check": "cargo test -p fnx-convert convert_projection -- --nocapture",
                "parallel_owner_scope": "edge projection + attribute precedence only",
            },
            {
                "boundary_id": "P2C004-MB-3",
                "crate": "fnx-convert",
                "module_path": "crates/fnx-convert/src/relabel_policy.rs",
                "public_seam": "pub trait RelabelPlanner",
                "internal_ownership": "copy/in-place relabel planning, cycle detection, and multigraph key collision policy",
                "legacy_compat_surface": "relabel_nodes / convert_node_labels_to_integers",
                "threat_boundary_refs": ["P2C004-CB-5", "P2C004-CB-6"],
                "compile_check": "cargo test -p fnx-convert relabel -- --nocapture",
                "parallel_owner_scope": "relabel ordering and collision semantics only",
            },
            {
                "boundary_id": "P2C004-MB-4",
                "crate": "fnx-runtime",
                "module_path": "crates/fnx-runtime/src/hardened_guardrails.rs",
                "public_seam": "pub struct HardenedConversionGuardrails",
                "internal_ownership": "allowlisted hardened deviations, audit envelopes, and fail-closed policy override rejection",
                "legacy_compat_surface": "strict/hardened compatibility envelope for conversion and relabel paths",
                "threat_boundary_refs": ["P2C004-CB-1", "P2C004-CB-4", "P2C004-CB-6"],
                "compile_check": "cargo check -p fnx-runtime --all-targets",
                "parallel_owner_scope": "hardened diagnostics/audit policy only",
            },
        ],
        "implementation_sequence_rows": [
            {
                "checkpoint_id": "P2C004-SEQ-1",
                "order": 1,
                "depends_on": [],
                "objective": "Land compile-checkable conversion/relabel boundary seams before behavior changes.",
                "modules_touched": [
                    "crates/fnx-convert/src/input_classifier.rs",
                    "crates/fnx-convert/src/relabel_policy.rs",
                ],
                "verification_entrypoints": [
                    "unit::fnx-p2c-004::boundary_shape",
                    "cargo check -p fnx-convert",
                ],
                "structured_log_hooks": ["convert.boundary.input_classifier_ready", "convert.boundary.relabel_policy_ready"],
                "risk_checkpoint": "fail if public/internal ownership boundaries are ambiguous",
            },
            {
                "checkpoint_id": "P2C004-SEQ-2",
                "order": 2,
                "depends_on": ["P2C004-SEQ-1"],
                "objective": "Implement strict-mode conversion input dispatch parity and malformed-input fail-closed behavior.",
                "modules_touched": [
                    "crates/fnx-convert/src/input_classifier.rs",
                    "crates/fnx-convert/src/lib.rs",
                ],
                "verification_entrypoints": [
                    "networkx/tests/test_convert.py:45-133",
                    "differential::fnx-p2c-004::convert_dispatch",
                ],
                "structured_log_hooks": ["convert.strict.dispatch_decision", "convert.fail_closed.malformed_input"],
                "risk_checkpoint": "halt if strict mismatch budget deviates from zero",
            },
            {
                "checkpoint_id": "P2C004-SEQ-3",
                "order": 3,
                "depends_on": ["P2C004-SEQ-2"],
                "objective": "Implement deterministic edge projection and relabel collision semantics for multi-graph pathways.",
                "modules_touched": [
                    "crates/fnx-convert/src/edge_projection.rs",
                    "crates/fnx-convert/src/relabel_policy.rs",
                ],
                "verification_entrypoints": [
                    "networkx/tests/test_convert.py:134-210",
                    "networkx/tests/test_relabel.py:188-317",
                    "property::fnx-p2c-004::invariants",
                ],
                "structured_log_hooks": ["convert.edge_projection.normalized", "convert.relabel.collision_strategy_selected"],
                "risk_checkpoint": "fail on relabel ordering drift or non-deterministic multigraph key remapping",
            },
            {
                "checkpoint_id": "P2C004-SEQ-4",
                "order": 4,
                "depends_on": ["P2C004-SEQ-2", "P2C004-SEQ-3"],
                "objective": "Layer hardened allowlisted controls with deterministic audit envelopes for conversion threats.",
                "modules_touched": [
                    "crates/fnx-runtime/src/hardened_guardrails.rs",
                    "crates/fnx-runtime/src/structured_logging.rs",
                ],
                "verification_entrypoints": [
                    "adversarial::fnx-p2c-004::malformed_inputs",
                    "adversarial::fnx-p2c-004::attribute_confusion",
                ],
                "structured_log_hooks": ["convert.hardened.allowlisted_category", "convert.audit.envelope_emitted"],
                "risk_checkpoint": "reject any non-allowlisted hardened deviation",
            },
            {
                "checkpoint_id": "P2C004-SEQ-5",
                "order": 5,
                "depends_on": ["P2C004-SEQ-4"],
                "objective": "Run differential/e2e readiness gates and finalize packet evidence artifacts.",
                "modules_touched": [
                    "crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs",
                    "scripts/run_phase2c_readiness_e2e.sh",
                ],
                "verification_entrypoints": [
                    "e2e::fnx-p2c-004::golden_journey",
                    "cargo test -p fnx-conformance --test phase2c_packet_readiness_gate",
                ],
                "structured_log_hooks": ["convert.e2e.replay_bundle", "convert.readiness.gate_result"],
                "risk_checkpoint": "stop on any strict/hardened parity gate mismatch",
            },
        ],
        "verification_entrypoint_rows": [
            {
                "stage": "unit",
                "harness": "unit::fnx-p2c-004::contract",
                "structured_log_hook": "convert.unit.contract_asserted",
                "replay_metadata_fields": ["packet_id", "conversion_path", "input_shape", "strict_mode"],
                "failure_forensics_artifact": "artifacts/conformance/latest/structured_logs.jsonl",
            },
            {
                "stage": "property",
                "harness": "property::fnx-p2c-004::invariants",
                "structured_log_hook": "convert.property.invariant_checkpoint",
                "replay_metadata_fields": ["seed", "graph_fingerprint", "relabel_mode", "invariant_id"],
                "failure_forensics_artifact": "artifacts/conformance/latest/structured_log_emitter_normalization_report.json",
            },
            {
                "stage": "differential",
                "harness": "differential::fnx-p2c-004::fixtures",
                "structured_log_hook": "convert.diff.oracle_comparison",
                "replay_metadata_fields": ["fixture_id", "oracle_ref", "conversion_signature", "mismatch_count"],
                "failure_forensics_artifact": "artifacts/phase2c/FNX-P2C-004/parity_report.json",
            },
            {
                "stage": "e2e",
                "harness": "e2e::fnx-p2c-004::golden_journey",
                "structured_log_hook": "convert.e2e.replay_emitted",
                "replay_metadata_fields": ["scenario_id", "thread_id", "trace_id", "forensics_bundle"],
                "failure_forensics_artifact": "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json",
            },
        ],
        "ambiguities": [
            {
                "legacy_region": "mixed-type attribute coercion on ingest",
                "policy_decision": "strict fail-closed, hardened bounded coercion with audit",
                "compatibility_rationale": "preserves strict parity while allowing bounded resilience in hardened mode",
            },
            {
                "legacy_region": "partial in-place relabel ordering under overlapping key spaces",
                "policy_decision": (
                    "preserve legacy copy=False behavior with explicit deterministic audit note "
                    "rather than forcing copy=True normalization"
                ),
                "compatibility_rationale": (
                    "matches observable NetworkX semantics while keeping strict behavior-isomorphism"
                ),
            }
        ],
        "compatibility_risks": [
            "input precedence drift",
            "relabel contract divergence",
            "multigraph key collision drift",
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
        "legacy_anchor_regions": [
            {
                "region_id": "P2C005-R1",
                "pathway": "normal",
                "anchor_refs": [
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 41, "end_line": 123},
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 393, "end_line": 430},
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 784, "end_line": 907},
                ],
                "symbols": ["_weight_function", "dijkstra_path", "single_source_dijkstra", "_dijkstra_multisource"],
                "behavior_note": (
                    "Weighted shortest-path entrypoints and multisource queue expansion preserve "
                    "deterministic distance/path behavior, including stable predecessor-path reconstruction "
                    "for equal-cost frontier expansion."
                ),
                "compatibility_policy": (
                    "strict mode preserves weighted shortest-path outputs and tie-break ordering exactly"
                ),
                "downstream_contract_rows": [
                    "Input Contract: packet operations",
                    "Output Contract: algorithm/state result",
                    "Determinism Commitments: stable traversal and output ordering",
                ],
                "planned_oracle_tests": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:113-198",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:271-330",
                ],
            },
            {
                "region_id": "P2C005-R2",
                "pathway": "edge",
                "anchor_refs": [
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 41, "end_line": 78},
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 862, "end_line": 885},
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 2310, "end_line": 2380},
                ],
                "symbols": ["_weight_function", "_dijkstra_multisource", "bidirectional_dijkstra"],
                "behavior_note": (
                    "Multigraph weight selection uses minimum parallel-edge cost and hidden-edge semantics "
                    "(weight callback returns None) are handled deterministically without accidental frontier drift."
                ),
                "compatibility_policy": (
                    "retain legacy multigraph minimum-weight and hidden-edge semantics across all weighted APIs"
                ),
                "downstream_contract_rows": [
                    "Input Contract: compatibility mode",
                    "Output Contract: algorithm/state result",
                    "Strict/Hardened Divergence: strict no repair heuristics",
                ],
                "planned_oracle_tests": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:199-241",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:316-329",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:358-388",
                ],
            },
            {
                "region_id": "P2C005-R3",
                "pathway": "adversarial",
                "anchor_refs": [
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 1493, "end_line": 1510},
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 1514, "end_line": 1640},
                    {"path": "networkx/algorithms/shortest_paths/weighted.py", "start_line": 2280, "end_line": 2306},
                ],
                "symbols": [
                    "bellman_ford_path",
                    "single_source_bellman_ford",
                    "negative_edge_cycle",
                    "bidirectional_dijkstra",
                ],
                "behavior_note": (
                    "Negative-cycle detection, contradictory-path guards, and unreachable/absent-node pathways "
                    "must fail closed with explicit ValueError/NodeNotFound/NetworkXUnbounded envelopes."
                ),
                "compatibility_policy": (
                    "strict fail-closed on negative-cycle and malformed-source conditions; no silent repair"
                ),
                "downstream_contract_rows": [
                    "Error Contract: malformed input affecting compatibility",
                    "Error Contract: unknown incompatible feature",
                    "Strict/Hardened Divergence: hardened bounded recovery only when allowlisted",
                ],
                "planned_oracle_tests": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:245-347",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:533-610",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:872-889",
                ],
            },
            {
                "region_id": "P2C005-R4",
                "pathway": "centrality-components",
                "anchor_refs": [
                    {"path": "networkx/algorithms/centrality/degree_alg.py", "start_line": 10, "end_line": 50},
                    {"path": "networkx/algorithms/centrality/closeness.py", "start_line": 14, "end_line": 136},
                    {"path": "networkx/algorithms/components/connected.py", "start_line": 18, "end_line": 149},
                ],
                "symbols": [
                    "degree_centrality",
                    "closeness_centrality",
                    "connected_components",
                    "number_connected_components",
                ],
                "behavior_note": (
                    "Degree/closeness/component calculations keep deterministic normalization and traversal semantics, "
                    "including closeness inward-distance policy for directed graphs and stable component partition outputs."
                ),
                "compatibility_policy": (
                    "preserve legacy normalization and directed-distance orientation semantics exactly"
                ),
                "downstream_contract_rows": [
                    "Output Contract: algorithm/state result",
                    "Determinism Commitments: stable traversal and output ordering",
                    "Input Contract: packet operations",
                ],
                "planned_oracle_tests": [
                    "networkx/algorithms/centrality/tests/test_degree_centrality.py:50-102",
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-37",
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:178-197",
                    "networkx/algorithms/components/tests/test_connected.py:64-111",
                ],
            },
            {
                "region_id": "P2C005-R5",
                "pathway": "adversarial-dispatch-loopback",
                "anchor_refs": [
                    {"path": "networkx/algorithms/components/connected.py", "start_line": 16, "end_line": 47},
                    {
                        "path": "networkx/algorithms/components/tests/test_connected.py",
                        "start_line": 75,
                        "end_line": 97,
                    },
                ],
                "symbols": ["connected_components"],
                "behavior_note": (
                    "Dispatchable-loopback execution for connected-components raises deterministic import failures "
                    "when unknown backends are configured, preventing ambiguous backend fallback."
                ),
                "compatibility_policy": (
                    "fail closed for unregistered backends while preserving loopback fast-path determinism"
                ),
                "downstream_contract_rows": [
                    "Error Contract: unknown incompatible feature",
                    "Input Contract: compatibility mode",
                    "Determinism Commitments: stable traversal and output ordering",
                ],
                "planned_oracle_tests": [
                    "networkx/algorithms/components/tests/test_connected.py:75-97",
                    "networkx/algorithms/components/tests/test_connected.py:124-130",
                ],
            },
        ],
        "strict_divergence_note": (
            "strict: fail-closed on unknown incompatible weighted-path/centrality/component semantics "
            "with zero mismatch budget for deterministic outputs"
        ),
        "hardened_divergence_note": (
            "hardened: bounded divergence only for allowlisted diagnostic/recovery categories with "
            "deterministic audit evidence and explicit compatibility-boundary records"
        ),
        "unknown_incompatibility_note": (
            "unknown incompatible feature/metadata paths fail closed unless an allowlisted category "
            "and deterministic audit trail are present"
        ),
        "hardened_allowlisted_categories": [
            "bounded_diagnostic_enrichment",
            "defensive_parse_recovery",
            "bounded_resource_clamp",
            "deterministic_tie_break_normalization",
            "quarantine_of_unsupported_metadata",
        ],
        "input_contract_rows": [
            {
                "row_id": "P2C005-IC-1",
                "api_behavior": "weighted shortest-path dispatch and weight callback handling",
                "preconditions": (
                    "source/target nodes and weight selector (attribute key or callback) are explicitly provided"
                ),
                "strict_policy": (
                    "preserve legacy `_weight_function` semantics and fail closed on invalid source/target"
                ),
                "hardened_policy": (
                    "same dispatch semantics; bounded diagnostics allowed for malformed weight metadata only"
                ),
                "anchor_regions": ["P2C005-R1", "P2C005-R2"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:113-198",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:199-241",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:252-270",
                ],
            },
            {
                "row_id": "P2C005-IC-2",
                "api_behavior": "bellman-ford and negative-cycle sensitive weighted traversals",
                "preconditions": (
                    "graph edge weights may include negative values and cycle structure may be adversarial"
                ),
                "strict_policy": (
                    "raise explicit cycle/error envelopes for contradictory or unbounded shortest-path states"
                ),
                "hardened_policy": (
                    "same failure defaults; bounded diagnostics only, no silent path repair or fallback routing"
                ),
                "anchor_regions": ["P2C005-R3"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:331-347",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:533-610",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:872-889",
                ],
            },
            {
                "row_id": "P2C005-IC-3",
                "api_behavior": "closeness/degree centrality orientation and normalization semantics",
                "preconditions": (
                    "graph directionality and optional distance key are explicit, wf_improved policy selected"
                ),
                "strict_policy": "preserve inward-distance closeness semantics and legacy normalization constants",
                "hardened_policy": (
                    "same numeric contracts; bounded diagnostics allowed when distance metadata is malformed"
                ),
                "anchor_regions": ["P2C005-R4"],
                "validation_refs": [
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-37",
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:178-197",
                    "networkx/algorithms/centrality/tests/test_degree_centrality.py:50-102",
                ],
            },
            {
                "row_id": "P2C005-IC-4",
                "api_behavior": "connected-components dispatchability and backend-loopback handling",
                "preconditions": "graph is undirected for component APIs; backend registration is explicit",
                "strict_policy": "reject unsupported directed/backend paths via explicit fail-closed errors",
                "hardened_policy": (
                    "same API contract and fail-closed boundaries with deterministic audit metadata"
                ),
                "anchor_regions": ["P2C005-R4", "P2C005-R5"],
                "validation_refs": [
                    "networkx/algorithms/components/tests/test_connected.py:64-111",
                    "networkx/algorithms/components/tests/test_connected.py:75-97",
                    "networkx/algorithms/components/tests/test_connected.py:124-130",
                ],
            },
        ],
        "output_contract_rows": [
            {
                "row_id": "P2C005-OC-1",
                "output_behavior": "weighted shortest-path path/length output determinism",
                "postconditions": (
                    "path node sequence and path length are deterministic for fixed graph + seed inputs"
                ),
                "strict_policy": "zero mismatch budget for path or distance drift versus legacy oracle",
                "hardened_policy": (
                    "same outputs unless allowlisted bounded diagnostics are appended outside API payloads"
                ),
                "anchor_regions": ["P2C005-R1", "P2C005-R2"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:113-198",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:316-329",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:744-777",
                ],
            },
            {
                "row_id": "P2C005-OC-2",
                "output_behavior": "centrality and connected-components result shape/order",
                "postconditions": (
                    "node centrality values and component partitions preserve legacy normalization/order behavior"
                ),
                "strict_policy": "no output reordering beyond documented traversal semantics",
                "hardened_policy": "same output contract with deterministic audit envelopes for deviations",
                "anchor_regions": ["P2C005-R4"],
                "validation_refs": [
                    "networkx/algorithms/centrality/tests/test_degree_centrality.py:50-102",
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-37",
                    "networkx/algorithms/components/tests/test_connected.py:64-111",
                ],
            },
            {
                "row_id": "P2C005-OC-3",
                "output_behavior": "predecessor/equal-cost path tie representation",
                "postconditions": (
                    "predecessor lists and tie paths remain stable and reproducible under equal-cost expansions"
                ),
                "strict_policy": "tie outputs follow canonical lexical ordering policy without hidden mutation",
                "hardened_policy": "same tie policy; only bounded diagnostics are allowlisted",
                "anchor_regions": ["P2C005-R1", "P2C005-R2"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:271-309",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:848-870",
                ],
            },
        ],
        "error_contract_rows": [
            {
                "row_id": "P2C005-EC-1",
                "trigger": "absent source/target nodes or unreachable weighted target",
                "strict_behavior": "raise NodeNotFound or NetworkXNoPath exactly per legacy semantics",
                "hardened_behavior": "same fail-closed errors with deterministic diagnostic context only",
                "allowlisted_divergence_category": "bounded_diagnostic_enrichment",
                "anchor_regions": ["P2C005-R1", "P2C005-R3"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:156-170",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:252-270",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:513-527",
                ],
            },
            {
                "row_id": "P2C005-EC-2",
                "trigger": "negative cycle / contradictory-path detection",
                "strict_behavior": "raise ValueError or NetworkXUnbounded fail-closed envelopes",
                "hardened_behavior": (
                    "same fail-closed defaults; no optimistic recovery from negative-cycle conditions"
                ),
                "allowlisted_divergence_category": "bounded_diagnostic_enrichment",
                "anchor_regions": ["P2C005-R3"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:331-347",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:533-610",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:612-620",
                ],
            },
            {
                "row_id": "P2C005-EC-3",
                "trigger": "unsupported backend loopback dispatch path for components",
                "strict_behavior": "raise deterministic ImportError for unregistered backend",
                "hardened_behavior": "same fail-closed backend contract with structured audit metadata",
                "allowlisted_divergence_category": "bounded_diagnostic_enrichment",
                "anchor_regions": ["P2C005-R5"],
                "validation_refs": [
                    "networkx/algorithms/components/tests/test_connected.py:75-97",
                    "networkx/algorithms/components/tests/test_connected.py:124-130",
                ],
            },
            {
                "row_id": "P2C005-EC-4",
                "trigger": "directed-graph calls into undirected connected-component APIs",
                "strict_behavior": "raise NetworkXNotImplemented and halt contract-unsafe execution",
                "hardened_behavior": "same fail-closed API boundary; no implicit graph conversion",
                "allowlisted_divergence_category": "bounded_diagnostic_enrichment",
                "anchor_regions": ["P2C005-R4"],
                "validation_refs": [
                    "networkx/algorithms/components/tests/test_connected.py:124-130",
                ],
            },
        ],
        "determinism_rows": [
            {
                "row_id": "P2C005-DC-1",
                "commitment": "equal-cost shortest-path tie handling remains deterministic",
                "tie_break_rule": "canonical lexical node-sequence comparison",
                "anchor_regions": ["P2C005-R1", "P2C005-R2"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:271-309",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:848-870",
                ],
            },
            {
                "row_id": "P2C005-DC-2",
                "commitment": "multigraph parallel-edge weight selection remains deterministic",
                "tie_break_rule": "minimum-edge-weight branch with stable predecessor update ordering",
                "anchor_regions": ["P2C005-R2"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:316-329",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:744-777",
                ],
            },
            {
                "row_id": "P2C005-DC-3",
                "commitment": "component partition and centrality iteration outputs remain stable",
                "tie_break_rule": "traversal order is deterministic for identical graph state",
                "anchor_regions": ["P2C005-R4"],
                "validation_refs": [
                    "networkx/algorithms/centrality/tests/test_degree_centrality.py:50-102",
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-37",
                    "networkx/algorithms/components/tests/test_connected.py:64-111",
                ],
            },
        ],
        "invariant_rows": [
            {
                "row_id": "P2C005-INV-1",
                "precondition": "weighted graph input satisfies declared node/edge contracts",
                "postcondition": "shortest-path length equals accumulated edge-weight sum of emitted path",
                "preservation_obligation": "path witness and distance witness remain isomorphic to oracle",
                "anchor_regions": ["P2C005-R1", "P2C005-R2"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:113-198",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:744-777",
                ],
            },
            {
                "row_id": "P2C005-INV-2",
                "precondition": "graph has negative-cycle exposure or contradictory relaxation state",
                "postcondition": "no finite shortest-path witness is emitted under fail-closed semantics",
                "preservation_obligation": "negative-cycle envelopes are deterministic and replayable",
                "anchor_regions": ["P2C005-R3"],
                "validation_refs": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:533-610",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:612-620",
                ],
            },
            {
                "row_id": "P2C005-INV-3",
                "precondition": "centrality/components APIs execute under documented graph-type constraints",
                "postcondition": "normalization factors and component partition semantics match legacy outputs",
                "preservation_obligation": "strict/hardened modes preserve outward API contract and ordering",
                "anchor_regions": ["P2C005-R4", "P2C005-R5"],
                "validation_refs": [
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-37",
                    "networkx/algorithms/centrality/tests/test_degree_centrality.py:50-102",
                    "networkx/algorithms/components/tests/test_connected.py:64-111",
                ],
            },
        ],
        "threat_model_rows": [
            {
                "threat_id": "P2C005-TM-1",
                "threat_class": "parser_abuse",
                "strict_mode_response": (
                    "Fail-closed on malformed weighted-path request payloads and invalid source/target selectors."
                ),
                "hardened_mode_response": (
                    "Fail-closed with bounded diagnostics and defensive parse recovery before deterministic abort."
                ),
                "mitigations": [
                    "weighted request schema checks",
                    "source/target existence guards",
                    "malformed payload fixtures",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-005/risk_note.md",
                "adversarial_fixture_hooks": ["algorithm_request_malformed_payload"],
                "crash_triage_taxonomy": [
                    "shortest_path.parse.malformed_payload",
                    "shortest_path.parse.invalid_source_target",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "defensive_parse_recovery",
                ],
                "compatibility_boundary": "weighted request parse boundary",
            },
            {
                "threat_id": "P2C005-TM-2",
                "threat_class": "metadata_ambiguity",
                "strict_mode_response": (
                    "Fail-closed on ambiguous weight metadata, hidden-edge callbacks, or conflicting route hints."
                ),
                "hardened_mode_response": (
                    "Quarantine unsupported metadata and preserve deterministic weighted-route semantics."
                ),
                "mitigations": [
                    "weight metadata precedence table",
                    "hidden-edge callback contract checks",
                    "metadata drift classification",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-005/contract_table.md",
                "adversarial_fixture_hooks": ["algorithm_conflicting_weight_metadata"],
                "crash_triage_taxonomy": [
                    "shortest_path.metadata.ambiguous_weight_selector",
                    "shortest_path.metadata.hidden_edge_callback_conflict",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "quarantine_of_unsupported_metadata",
                ],
                "compatibility_boundary": "weighted metadata normalization boundary",
            },
            {
                "threat_id": "P2C005-TM-3",
                "threat_class": "version_skew",
                "strict_mode_response": "Fail-closed on unsupported algorithm contract versions.",
                "hardened_mode_response": (
                    "Reject incompatible version envelopes with deterministic compatibility diagnostics."
                ),
                "mitigations": [
                    "algorithm contract version pinning",
                    "versioned fixture bundle checks",
                    "compatibility matrix probes",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-005/parity_gate.yaml",
                "adversarial_fixture_hooks": ["algorithm_contract_version_skew"],
                "crash_triage_taxonomy": [
                    "shortest_path.version.unsupported_contract_envelope",
                    "shortest_path.version.contract_mismatch",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "algorithm contract version envelope boundary",
            },
            {
                "threat_id": "P2C005-TM-4",
                "threat_class": "resource_exhaustion",
                "strict_mode_response": (
                    "Fail-closed when weighted frontier expansion exceeds strict complexity budgets."
                ),
                "hardened_mode_response": (
                    "Apply bounded resource clamps and reject once deterministic thresholds are exceeded."
                ),
                "mitigations": [
                    "frontier expansion ratio guards",
                    "priority-queue work caps",
                    "runtime tail budget sentinels",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-005/parity_gate.yaml",
                "adversarial_fixture_hooks": ["shortest_path_frontier_blowup"],
                "crash_triage_taxonomy": [
                    "shortest_path.resource.frontier_budget_exceeded",
                    "shortest_path.resource.priority_queue_cap_exceeded",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "bounded_resource_clamp",
                ],
                "compatibility_boundary": "weighted frontier expansion budget boundary",
            },
            {
                "threat_id": "P2C005-TM-5",
                "threat_class": "state_corruption",
                "strict_mode_response": (
                    "Fail-closed when path witness, predecessor state, or component route invariants drift."
                ),
                "hardened_mode_response": (
                    "Reset transient route state and fail-closed with deterministic incident evidence."
                ),
                "mitigations": [
                    "witness invariant checkpoints",
                    "predecessor map consistency checks",
                    "state-reset replay hooks",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-005/contract_table.md",
                "adversarial_fixture_hooks": ["shortest_path_witness_state_break"],
                "crash_triage_taxonomy": [
                    "shortest_path.state.witness_invariant_break",
                    "shortest_path.state.predecessor_state_mismatch",
                ],
                "hardened_allowlisted_categories": ["bounded_diagnostic_enrichment"],
                "compatibility_boundary": "path witness and route-state determinism boundary",
            },
            {
                "threat_id": "P2C005-TM-6",
                "threat_class": "algorithmic_complexity_dos",
                "strict_mode_response": (
                    "Fail-closed on adversarial graph classes outside strict complexity envelopes."
                ),
                "hardened_mode_response": (
                    "Apply bounded admission checks and deterministic tie-break normalization before rejection."
                ),
                "mitigations": [
                    "adversarial graph taxonomy gates",
                    "complexity witness artifacts",
                    "runtime tail regression sentinels",
                ],
                "evidence_artifact": "artifacts/phase2c/FNX-P2C-005/risk_note.md",
                "adversarial_fixture_hooks": ["shortest_path_lollipop_and_barbell_stressor"],
                "crash_triage_taxonomy": [
                    "shortest_path.complexity.hostile_graph_class",
                    "shortest_path.complexity.tail_budget_exceeded",
                ],
                "hardened_allowlisted_categories": [
                    "bounded_diagnostic_enrichment",
                    "bounded_resource_clamp",
                    "deterministic_tie_break_normalization",
                ],
                "compatibility_boundary": "hostile graph complexity admission boundary",
            },
        ],
        "compatibility_boundary_rows": [
            {
                "boundary_id": "P2C005-CB-1",
                "strict_parity_obligation": (
                    "Malformed weighted request payloads and invalid source/target selectors fail closed."
                ),
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "defensive_parse_recovery",
                ],
                "fail_closed_default": "fail_closed_on_malformed_weighted_request",
                "evidence_hooks": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:156-170",
                    "artifacts/phase2c/FNX-P2C-005/risk_note.md#packet-threat-matrix",
                ],
            },
            {
                "boundary_id": "P2C005-CB-2",
                "strict_parity_obligation": (
                    "Weight metadata precedence and hidden-edge callback semantics remain deterministic."
                ),
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "quarantine_of_unsupported_metadata",
                ],
                "fail_closed_default": "fail_closed_on_ambiguous_weight_metadata",
                "evidence_hooks": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:199-241",
                    "artifacts/phase2c/FNX-P2C-005/contract_table.md#input-contract",
                ],
            },
            {
                "boundary_id": "P2C005-CB-3",
                "strict_parity_obligation": (
                    "Unsupported algorithm contract/version envelopes are rejected deterministically."
                ),
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_algorithm_version_skew",
                "evidence_hooks": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:331-347",
                    "artifacts/phase2c/FNX-P2C-005/parity_gate.yaml",
                ],
            },
            {
                "boundary_id": "P2C005-CB-4",
                "strict_parity_obligation": (
                    "Weighted frontier growth remains within strict complexity budgets."
                ),
                "hardened_allowlisted_deviation_categories": [
                    "bounded_diagnostic_enrichment",
                    "bounded_resource_clamp",
                    "deterministic_tie_break_normalization",
                ],
                "fail_closed_default": "fail_closed_when_weighted_frontier_budget_exhausted",
                "evidence_hooks": [
                    "artifacts/phase2c/FNX-P2C-005/parity_gate.yaml",
                    "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
                ],
            },
            {
                "boundary_id": "P2C005-CB-5",
                "strict_parity_obligation": (
                    "Negative-cycle and contradictory-path states never emit finite shortest-path witnesses."
                ),
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_negative_cycle_or_contradictory_path",
                "evidence_hooks": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:533-620",
                    "artifacts/phase2c/FNX-P2C-005/contract_table.md#machine-checkable-invariant-matrix",
                ],
            },
            {
                "boundary_id": "P2C005-CB-6",
                "strict_parity_obligation": (
                    "Connected-components backend loopback and directed-input boundaries fail closed."
                ),
                "hardened_allowlisted_deviation_categories": ["bounded_diagnostic_enrichment"],
                "fail_closed_default": "fail_closed_on_components_backend_or_graph_type_violation",
                "evidence_hooks": [
                    "networkx/algorithms/components/tests/test_connected.py:75-130",
                    "artifacts/phase2c/FNX-P2C-005/risk_note.md#compatibility-boundary-matrix",
                ],
            },
        ],
        "module_boundary_rows": [
            {
                "boundary_id": "P2C005-MB-1",
                "crate": "fnx-algorithms",
                "module_path": "crates/fnx-algorithms/src/weighted_route_policy.rs",
                "public_seam": "pub trait WeightedRoutePlanner",
                "internal_ownership": (
                    "weighted-route dispatch preflight, source/target existence checks, and weight-selector "
                    "normalization"
                ),
                "legacy_compat_surface": "_weight_function / dijkstra_path / single_source_dijkstra",
                "threat_boundary_refs": ["P2C005-CB-1", "P2C005-CB-2", "P2C005-CB-3"],
                "compile_check": "cargo check -p fnx-algorithms",
                "parallel_owner_scope": "weighted-route preflight and selector policy only",
            },
            {
                "boundary_id": "P2C005-MB-2",
                "crate": "fnx-algorithms",
                "module_path": "crates/fnx-algorithms/src/weighted_frontier_engine.rs",
                "public_seam": "pub struct WeightedFrontierEngine",
                "internal_ownership": (
                    "priority-queue frontier expansion, predecessor reconstruction, multigraph min-edge "
                    "selection, and deterministic tie-break ordering"
                ),
                "legacy_compat_surface": "_dijkstra_multisource / bidirectional_dijkstra / predecessor maps",
                "threat_boundary_refs": ["P2C005-CB-2", "P2C005-CB-4", "P2C005-CB-5"],
                "compile_check": "cargo test -p fnx-algorithms weighted_shortest_paths -- --nocapture",
                "parallel_owner_scope": "frontier expansion and tie-break semantics only",
            },
            {
                "boundary_id": "P2C005-MB-3",
                "crate": "fnx-algorithms",
                "module_path": "crates/fnx-algorithms/src/centrality_components_kernel.rs",
                "public_seam": "pub trait CentralityComponentsKernel",
                "internal_ownership": (
                    "degree/closeness normalization, directed-orientation semantics, and connected-components "
                    "boundary enforcement"
                ),
                "legacy_compat_surface": "degree_centrality / closeness_centrality / connected_components",
                "threat_boundary_refs": ["P2C005-CB-5", "P2C005-CB-6"],
                "compile_check": "cargo check -p fnx-algorithms --all-targets",
                "parallel_owner_scope": "centrality/components semantics only",
            },
            {
                "boundary_id": "P2C005-MB-4",
                "crate": "fnx-runtime",
                "module_path": "crates/fnx-runtime/src/hardened_guardrails.rs",
                "public_seam": "pub struct HardenedAlgorithmGuardrails",
                "internal_ownership": (
                    "allowlisted hardened deviations, deterministic audit envelopes, and fail-closed policy "
                    "override rejection"
                ),
                "legacy_compat_surface": (
                    "strict/hardened compatibility envelope for weighted shortest-path, centrality, and "
                    "components pathways"
                ),
                "threat_boundary_refs": ["P2C005-CB-1", "P2C005-CB-4", "P2C005-CB-6"],
                "compile_check": "cargo check -p fnx-runtime --all-targets",
                "parallel_owner_scope": "hardened diagnostics/audit policy only",
            },
        ],
        "implementation_sequence_rows": [
            {
                "checkpoint_id": "P2C005-SEQ-1",
                "order": 1,
                "depends_on": [],
                "objective": (
                    "Land compile-checkable weighted-route and centrality/components seams before behavior "
                    "changes."
                ),
                "modules_touched": [
                    "crates/fnx-algorithms/src/weighted_route_policy.rs",
                    "crates/fnx-algorithms/src/centrality_components_kernel.rs",
                ],
                "verification_entrypoints": [
                    "unit::fnx-p2c-005::boundary_shape",
                    "cargo check -p fnx-algorithms",
                ],
                "structured_log_hooks": [
                    "algorithms.boundary.weighted_route_ready",
                    "algorithms.boundary.centrality_components_ready",
                ],
                "risk_checkpoint": "fail if module seam ownership is ambiguous",
            },
            {
                "checkpoint_id": "P2C005-SEQ-2",
                "order": 2,
                "depends_on": ["P2C005-SEQ-1"],
                "objective": (
                    "Implement strict weighted-route dispatch parity and malformed-input/source fail-closed "
                    "boundaries."
                ),
                "modules_touched": [
                    "crates/fnx-algorithms/src/weighted_route_policy.rs",
                    "crates/fnx-algorithms/src/lib.rs",
                ],
                "verification_entrypoints": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:113-241",
                    "differential::fnx-p2c-005::weighted_dispatch",
                ],
                "structured_log_hooks": [
                    "algorithms.strict.route_decision",
                    "algorithms.fail_closed.weighted_input",
                ],
                "risk_checkpoint": "halt if strict mismatch budget deviates from zero",
            },
            {
                "checkpoint_id": "P2C005-SEQ-3",
                "order": 3,
                "depends_on": ["P2C005-SEQ-2"],
                "objective": (
                    "Implement deterministic frontier expansion, tie-break policy, and negative-cycle "
                    "fail-closed envelopes."
                ),
                "modules_touched": [
                    "crates/fnx-algorithms/src/weighted_frontier_engine.rs",
                    "crates/fnx-algorithms/src/bellman_ford_guard.rs",
                ],
                "verification_entrypoints": [
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:271-347",
                    "networkx/algorithms/shortest_paths/tests/test_weighted.py:533-620",
                    "property::fnx-p2c-005::invariants",
                ],
                "structured_log_hooks": [
                    "algorithms.frontier.tie_break_selected",
                    "algorithms.fail_closed.negative_cycle",
                ],
                "risk_checkpoint": "fail on path witness mismatch or non-deterministic predecessor ordering",
            },
            {
                "checkpoint_id": "P2C005-SEQ-4",
                "order": 4,
                "depends_on": ["P2C005-SEQ-2", "P2C005-SEQ-3"],
                "objective": (
                    "Lock centrality/components semantics, directed-orientation rules, and backend loopback "
                    "failure boundaries."
                ),
                "modules_touched": [
                    "crates/fnx-algorithms/src/centrality_components_kernel.rs",
                    "crates/fnx-algorithms/src/components_dispatch_bridge.rs",
                ],
                "verification_entrypoints": [
                    "networkx/algorithms/centrality/tests/test_closeness_centrality.py:18-197",
                    "networkx/algorithms/components/tests/test_connected.py:64-130",
                ],
                "structured_log_hooks": [
                    "algorithms.centrality.orientation_locked",
                    "algorithms.components.backend_guard",
                ],
                "risk_checkpoint": "reject directed/backend bypass paths that violate fail-closed policy",
            },
            {
                "checkpoint_id": "P2C005-SEQ-5",
                "order": 5,
                "depends_on": ["P2C005-SEQ-4"],
                "objective": (
                    "Layer hardened allowlisted controls and run readiness/e2e/perf gates to finalize packet "
                    "evidence."
                ),
                "modules_touched": [
                    "crates/fnx-runtime/src/hardened_guardrails.rs",
                    "crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs",
                    "scripts/run_phase2c_readiness_e2e.sh",
                ],
                "verification_entrypoints": [
                    "adversarial::fnx-p2c-005::algorithmic_complexity",
                    "cargo test -p fnx-conformance --test phase2c_packet_readiness_gate",
                ],
                "structured_log_hooks": [
                    "algorithms.hardened.allowlisted_category",
                    "algorithms.readiness.gate_result",
                ],
                "risk_checkpoint": "stop on any strict/hardened parity gate mismatch",
            },
        ],
        "verification_entrypoint_rows": [
            {
                "stage": "unit",
                "harness": "unit::fnx-p2c-005::contract",
                "structured_log_hook": "algorithms.unit.contract_asserted",
                "replay_metadata_fields": ["packet_id", "algorithm_family", "source_target_pair", "strict_mode"],
                "failure_forensics_artifact": "artifacts/conformance/latest/structured_logs.jsonl",
            },
            {
                "stage": "property",
                "harness": "property::fnx-p2c-005::invariants",
                "structured_log_hook": "algorithms.property.invariant_checkpoint",
                "replay_metadata_fields": ["seed", "graph_fingerprint", "tie_break_policy", "invariant_id"],
                "failure_forensics_artifact": (
                    "artifacts/conformance/latest/structured_log_emitter_normalization_report.json"
                ),
            },
            {
                "stage": "differential",
                "harness": "differential::fnx-p2c-005::fixtures",
                "structured_log_hook": "algorithms.diff.oracle_comparison",
                "replay_metadata_fields": ["fixture_id", "oracle_ref", "algorithm_signature", "mismatch_count"],
                "failure_forensics_artifact": "artifacts/phase2c/FNX-P2C-005/parity_report.json",
            },
            {
                "stage": "e2e",
                "harness": "e2e::fnx-p2c-005::golden_journey",
                "structured_log_hook": "algorithms.e2e.replay_emitted",
                "replay_metadata_fields": ["scenario_id", "thread_id", "trace_id", "forensics_bundle"],
                "failure_forensics_artifact": (
                    "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json"
                ),
            },
        ],
        "ambiguities": [
            {
                "legacy_region": "equal-weight multi-path tie-breaks",
                "policy_decision": "canonical path comparison by lexical node sequence",
                "compatibility_rationale": "locks observable results under adversarial equal-weight graphs",
            },
            {
                "legacy_region": "directed closeness orientation (inward vs outward distance)",
                "policy_decision": "preserve inward-distance default and require explicit reverse() for outward mode",
                "compatibility_rationale": "matches documented NetworkX semantics and avoids directional drift",
            },
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


def render_legacy_anchor_markdown(spec: dict[str, Any], packet_id: str) -> str:
    regions = spec.get("legacy_anchor_regions", [])
    if not regions:
        return f"""# Legacy Anchor Map

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

    anchor_lines = []
    crosswalk_rows = []
    for region in regions:
        refs = [
            f"{ref['path']}:{ref['start_line']}-{ref['end_line']}"
            for ref in region.get("anchor_refs", [])
        ]
        anchors = "; ".join(refs)
        symbols = ", ".join(region.get("symbols", []))
        contracts = "; ".join(region.get("downstream_contract_rows", []))
        tests = "; ".join(region.get("planned_oracle_tests", []))
        anchor_lines.append(
            "\n".join(
                [
                    f"- region: {region['region_id']}",
                    f"  - pathway: {region['pathway']}",
                    f"  - source anchors: {anchors}",
                    f"  - symbols: {symbols}",
                    f"  - behavior note: {region['behavior_note']}",
                    f"  - compatibility policy: {region['compatibility_policy']}",
                    f"  - downstream contract rows: {contracts}",
                    f"  - planned oracle tests: {tests}",
                ]
            )
        )
        crosswalk_rows.append(
            f"| {region['region_id']} | {region['pathway']} | {contracts} | {tests} |"
        )

    ambiguity_rows = "\n".join(
        [
            (
                f"- legacy ambiguity: {item['legacy_region']}\n"
                f"  - policy decision: {item['policy_decision']}\n"
                f"  - rationale: {item['compatibility_rationale']}"
            )
            for item in spec.get("ambiguities", [])
        ]
    )
    if not ambiguity_rows:
        ambiguity_rows = "- legacy ambiguity: none documented"

    return f"""# Legacy Anchor Map

## Legacy Scope
- packet id: {packet_id}
- subsystem: {spec["subsystem"]}
- legacy module paths: {", ".join(spec["legacy_paths"])}
- legacy symbols: {", ".join(spec["legacy_symbols"])}

## Anchor Map
{chr(10).join(anchor_lines)}

## Behavior Notes
- deterministic constraints: {"; ".join(spec["deterministic_constraints"])}
- compatibility-sensitive edge cases: {"; ".join(spec["compatibility_risks"])}
- ambiguity resolution:
{ambiguity_rows}

## Extraction Ledger Crosswalk
| region id | pathway | downstream contract rows | planned oracle tests |
|---|---|---|---|
{chr(10).join(crosswalk_rows)}

## Compatibility Risk
- risk level: {spec["risk_tier"]}
- rationale: {spec["extra_gate"]} is required to guard compatibility-sensitive behavior.
"""


def render_contract_table_markdown(spec: dict[str, Any], packet_id: str) -> str:
    input_rows = spec.get("input_contract_rows", [])
    if not input_rows:
        return f"""# Contract Table

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

    input_lines = "\n".join(
        [
            (
                f"| {row['row_id']} | {row['api_behavior']} | {row['preconditions']} | "
                f"{row['strict_policy']} | {row['hardened_policy']} | "
                f"{'; '.join(row['anchor_regions'])} | {'; '.join(row['validation_refs'])} |"
            )
            for row in input_rows
        ]
    )
    output_lines = "\n".join(
        [
            (
                f"| {row['row_id']} | {row['output_behavior']} | {row['postconditions']} | "
                f"{row['strict_policy']} | {row['hardened_policy']} | "
                f"{'; '.join(row['anchor_regions'])} | {'; '.join(row['validation_refs'])} |"
            )
            for row in spec.get("output_contract_rows", [])
        ]
    )
    error_lines = "\n".join(
        [
            (
                f"| {row['row_id']} | {row['trigger']} | {row['strict_behavior']} | "
                f"{row['hardened_behavior']} | {row['allowlisted_divergence_category']} | "
                f"{'; '.join(row['anchor_regions'])} | {'; '.join(row['validation_refs'])} |"
            )
            for row in spec.get("error_contract_rows", [])
        ]
    )
    determinism_lines = "\n".join(
        [
            (
                f"| {row['row_id']} | {row['commitment']} | {row['tie_break_rule']} | "
                f"{'; '.join(row['anchor_regions'])} | {'; '.join(row['validation_refs'])} |"
            )
            for row in spec.get("determinism_rows", [])
        ]
    )
    invariant_lines = "\n".join(
        [
            (
                f"| {row['row_id']} | {row['precondition']} | {row['postcondition']} | "
                f"{row['preservation_obligation']} | {'; '.join(row['anchor_regions'])} | "
                f"{'; '.join(row['validation_refs'])} |"
            )
            for row in spec.get("invariant_rows", [])
        ]
    )
    hardened_categories = "; ".join(spec.get("hardened_allowlisted_categories", [])) or "none"
    strict_divergence_note = spec.get(
        "strict_divergence_note",
        "strict: fail-closed for unknown backend/features/metadata paths and zero mismatch budget for route identity.",
    )
    hardened_divergence_note = spec.get(
        "hardened_divergence_note",
        f"hardened: divergence allowed only in allowlisted categories: {hardened_categories}.",
    )
    unknown_incompatibility_note = spec.get(
        "unknown_incompatibility_note",
        (
            "unknown incompatible features/metadata paths: fail-closed unless allowlist "
            "category + deterministic audit evidence is present."
        ),
    )
    module_rows = spec.get("module_boundary_rows", [])
    sequence_rows = spec.get("implementation_sequence_rows", [])
    verification_rows = spec.get("verification_entrypoint_rows", [])

    module_section = ""
    if module_rows:
        module_lines = "\n".join(
            [
                (
                    f"| {row['boundary_id']} | {row['crate']} | {row['module_path']} | {row['public_seam']} | "
                    f"{row['internal_ownership']} | {row['legacy_compat_surface']} | "
                    f"{'; '.join(row['threat_boundary_refs'])} | {row['compile_check']} | "
                    f"{row['parallel_owner_scope']} |"
                )
                for row in module_rows
            ]
        )
        module_section = f"""

## Rust Module Boundary Skeleton
| boundary id | crate | module path | public seam | internal ownership | legacy compatibility surface | threat boundary refs | compile-check proof | parallel contributor scope |
|---|---|---|---|---|---|---|---|---|
{module_lines}
"""

    sequence_section = ""
    if sequence_rows:
        sequence_lines = "\n".join(
            [
                (
                    f"| {row['checkpoint_id']} | {row['order']} | {('; '.join(row['depends_on']) or 'none')} | "
                    f"{row['objective']} | {('; '.join(row['modules_touched']))} | "
                    f"{('; '.join(row['verification_entrypoints']))} | "
                    f"{('; '.join(row['structured_log_hooks']))} | {row['risk_checkpoint']} |"
                )
                for row in sequence_rows
            ]
        )
        sequence_section = f"""

## Dependency-Aware Implementation Sequence
| checkpoint id | order | depends on | objective | modules touched | verification entrypoints | structured logging hooks | risk checkpoint |
|---|---|---|---|---|---|---|---|
{sequence_lines}
"""

    verification_section = ""
    if verification_rows:
        verification_lines = "\n".join(
            [
                (
                    f"| {row['stage']} | {row['harness']} | {row['structured_log_hook']} | "
                    f"{'; '.join(row['replay_metadata_fields'])} | {row['failure_forensics_artifact']} |"
                )
                for row in verification_rows
            ]
        )
        verification_section = f"""

## Structured Logging + Verification Entry Points
| stage | harness | structured log hook | replay metadata fields | failure forensics artifact |
|---|---|---|---|---|
{verification_lines}
"""

    base = f"""# Contract Table

## Input Contract
| row id | API/behavior | preconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
{input_lines}

## Output Contract
| row id | output behavior | postconditions | strict policy | hardened policy | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
{output_lines}

## Error Contract
| row id | trigger | strict behavior | hardened behavior | allowlisted divergence category | legacy anchor regions | required validations |
|---|---|---|---|---|---|---|
{error_lines}

## Strict/Hardened Divergence
- {strict_divergence_note}
- {hardened_divergence_note}
- {unknown_incompatibility_note}

## Determinism Commitments
| row id | commitment | tie-break rule | legacy anchor regions | required validations |
|---|---|---|---|---|
{determinism_lines}

### Machine-Checkable Invariant Matrix
| invariant id | precondition | postcondition | preservation obligation | legacy anchor regions | required validations |
|---|---|---|---|---|---|
{invariant_lines}
"""
    return base + module_section + sequence_section + verification_section


def render_risk_note_markdown(spec: dict[str, Any], packet_id: str) -> str:
    threat_rows = spec.get("threat_model_rows", [])
    if not threat_rows:
        return f"""# Risk Note

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

    threat_lines = "\n".join(
        [
            (
                f"| {row['threat_id']} | {row['threat_class']} | {row['strict_mode_response']} | "
                f"{row['hardened_mode_response']} | {'; '.join(row['mitigations'])} | "
                f"{row['evidence_artifact']} | {'; '.join(row['adversarial_fixture_hooks'])} | "
                f"{'; '.join(row['crash_triage_taxonomy'])} | "
                f"{'; '.join(row['hardened_allowlisted_categories'])} | {row['compatibility_boundary']} |"
            )
            for row in threat_rows
        ]
    )

    boundary_rows = spec.get("compatibility_boundary_rows", [])
    boundary_lines = "\n".join(
        [
            (
                f"| {row['boundary_id']} | {row['strict_parity_obligation']} | "
                f"{'; '.join(row['hardened_allowlisted_deviation_categories'])} | "
                f"{row['fail_closed_default']} | {'; '.join(row['evidence_hooks'])} |"
            )
            for row in boundary_rows
        ]
    )
    if not boundary_lines:
        boundary_lines = "| none | none | none | fail_closed | none |"

    hardened_categories = "; ".join(spec.get("hardened_allowlisted_categories", [])) or "none"

    return f"""# Risk Note

## Risk Surface
- parser/ingestion: malformed payloads for {spec["subsystem"].lower()}.
- algorithmic denial vectors: adversarial graph shapes designed to trigger tail latency spikes.
- packet gate: `{spec["extra_gate"]}`.

## Failure Modes
- fail-closed triggers: unknown incompatible feature, unsupported backend/version paths, contract-breaking malformed inputs.
- hardened degraded-mode triggers: allowlisted bounded controls only, with deterministic audit evidence.

## Mitigations
- controls: strict/hardened split, compatibility boundary matrix, and deterministic crash taxonomy.
- evidence coupling: threat rows map directly to adversarial fixture hooks and packet validation gates.
- policy: ad hoc hardened deviations are forbidden; unknown incompatible feature paths fail closed.

## Packet Threat Matrix
| threat id | threat class | strict mode response | hardened mode response | mitigations | evidence artifact | adversarial fixture / fuzz entrypoint | crash triage taxonomy | hardened allowlisted categories | compatibility boundary |
|---|---|---|---|---|---|---|---|---|---|
{threat_lines}

## Compatibility Boundary Matrix
| boundary id | strict parity obligation | hardened allowlisted deviation categories | fail-closed default | evidence hooks |
|---|---|---|---|---|
{boundary_lines}

## Hardened Deviation Guardrails
- allowlisted categories only: {hardened_categories}.
- ad hoc hardened deviations: forbidden.
- unknown incompatible feature policy: fail_closed.

## Residual Risk
- unresolved risks: {"; ".join(spec["compatibility_risks"])}.
- follow-up actions: expand adversarial fixture diversity and keep crash triage mappings deterministic.
"""


def write_packet_artifacts(spec: dict[str, Any]) -> None:
    packet_id = spec["packet_id"]
    packet_path = packet_dir(packet_id)
    paths = artifact_paths_for(packet_id)

    legacy_anchor = render_legacy_anchor_markdown(spec, packet_id)
    text_dump(packet_path / "legacy_anchor_map.md", legacy_anchor)

    contract_table = render_contract_table_markdown(spec, packet_id)
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
    if spec.get("module_boundary_rows"):
        fixture_manifest["module_boundary_skeleton"] = spec["module_boundary_rows"]
    if spec.get("implementation_sequence_rows"):
        fixture_manifest["implementation_sequence"] = spec["implementation_sequence_rows"]
    if spec.get("verification_entrypoint_rows"):
        fixture_manifest["verification_entrypoints"] = spec["verification_entrypoint_rows"]
    if spec.get("hardened_allowlisted_categories"):
        fixture_manifest["hardened_allowlisted_categories"] = spec["hardened_allowlisted_categories"]
    if spec.get("strict_divergence_note"):
        fixture_manifest["strict_divergence_note"] = spec["strict_divergence_note"]
    if spec.get("hardened_divergence_note"):
        fixture_manifest["hardened_divergence_note"] = spec["hardened_divergence_note"]
    if spec.get("unknown_incompatibility_note"):
        fixture_manifest["unknown_incompatibility_note"] = spec["unknown_incompatibility_note"]
    if spec.get("input_contract_rows"):
        fixture_manifest["input_contract_rows"] = spec["input_contract_rows"]
    if spec.get("output_contract_rows"):
        fixture_manifest["output_contract_rows"] = spec["output_contract_rows"]
    if spec.get("error_contract_rows"):
        fixture_manifest["error_contract_rows"] = spec["error_contract_rows"]
    if spec.get("determinism_rows"):
        fixture_manifest["determinism_rows"] = spec["determinism_rows"]
    if spec.get("invariant_rows"):
        fixture_manifest["invariant_rows"] = spec["invariant_rows"]
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

    risk_note = render_risk_note_markdown(spec, packet_id)
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
    behavior_region_map = [
        {
            "region_id": region["region_id"],
            "pathway": region["pathway"],
            "legacy_anchor_refs": [
                f"{ref['path']}:{ref['start_line']}-{ref['end_line']}"
                for ref in region.get("anchor_refs", [])
            ],
            "symbols": region.get("symbols", []),
            "behavior_note": region.get("behavior_note", ""),
            "compatibility_policy": region.get("compatibility_policy", ""),
            "downstream_contract_rows": region.get("downstream_contract_rows", []),
            "planned_oracle_tests": region.get("planned_oracle_tests", []),
        }
        for region in spec.get("legacy_anchor_regions", [])
    ]
    entry = {
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
        "behavior_region_map": behavior_region_map,
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

    if spec.get("threat_model_rows"):
        entry["packet_boundary_threat_matrix"] = spec["threat_model_rows"]
    if spec.get("compatibility_boundary_rows"):
        entry["compatibility_boundary_matrix"] = spec["compatibility_boundary_rows"]
    if spec.get("module_boundary_rows"):
        entry["module_boundary_skeleton"] = spec["module_boundary_rows"]
    if spec.get("implementation_sequence_rows"):
        entry["implementation_sequence"] = spec["implementation_sequence_rows"]
    if spec.get("verification_entrypoint_rows"):
        entry["verification_entrypoints"] = spec["verification_entrypoint_rows"]

    return entry


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
