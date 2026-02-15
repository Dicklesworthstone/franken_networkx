#!/usr/bin/env python3
"""Generate CGSE legacy tie-break and ordering behavior ledger artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def anchor(path: str, lines: str, symbols: list[str], legacy_behavior: str) -> dict[str, Any]:
    return {
        "path": path,
        "lines": lines,
        "symbols": symbols,
        "legacy_behavior": legacy_behavior,
    }


def hook(hook_id: str, path: str, lines: str, assertion: str) -> dict[str, str]:
    return {
        "hook_id": hook_id,
        "path": path,
        "lines": lines,
        "assertion": assertion,
    }


def build_rules() -> list[dict[str, Any]]:
    common_property = hook(
        "CGSE-PROP-BASE",
        "crates/fnx-conformance/tests/phase2c_packet_readiness_gate.rs",
        "51-187",
        "Phase2C readiness gate preserves deterministic + fail-closed invariants.",
    )
    common_e2e = hook(
        "CGSE-E2E-BASE",
        "scripts/run_phase2c_readiness_e2e.sh",
        "1-120",
        "End-to-end execution must keep replay metadata + deterministic ordering artifacts.",
    )

    rules: list[dict[str, Any]] = [
        {
            "rule_id": "CGSE-R01",
            "operation_family": "graph_core_mutation",
            "title": "MultiGraph auto-key allocation tie-break",
            "behavior_claim": "Auto-generated edge keys choose the first unused integer based on existing keydict occupancy.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/classes/multigraph.py",
                    "413-440",
                    ["MultiGraph.new_edge_key"],
                    "New key starts at len(keydict) then increments until an unused key is found.",
                )
            ],
            "tie_break_policy": "first-unused-integer key scan",
            "ordering_policy": "stable for fixed keydict state; gaps may be skipped after deletions",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-001",
                    "description": "Auto-key sequence may contain gaps after remove/reinsert cycles.",
                    "policy_options": [
                        "preserve first-unused scan exactly",
                        "normalize to contiguous sequence (rejected)",
                    ],
                    "selected_policy": "preserve first-unused scan exactly",
                    "risk_note": "Reindexing keys would alter observable MultiGraph edge-key contracts.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R01",
                        "legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py",
                        "320-362",
                        "Edge-key assignment semantics and multigraph constructor ingestion remain parity-safe.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R01",
                        "crates/fnx-conformance/fixtures/graph_core_mutation_hardened.json",
                        "1-200",
                        "Graph mutation fixture bundle must preserve key behavior under strict/hardened paths.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "critical",
        },
        {
            "rule_id": "CGSE-R02",
            "operation_family": "graph_core_mutation",
            "title": "Keyless multiedge removal ordering",
            "behavior_claim": "When key is omitted, multiedge removal is LIFO by insertion order via popitem().",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/classes/multigraph.py",
                    "635-700",
                    ["MultiGraph.remove_edge"],
                    "Docs and implementation specify reverse insertion-order deletion for key=None.",
                ),
                anchor(
                    "legacy_networkx_code/networkx/networkx/classes/multidigraph.py",
                    "525-587",
                    ["MultiDiGraph.remove_edge"],
                    "Directed multigraph path mirrors keyless LIFO removal semantics.",
                ),
            ],
            "tie_break_policy": "remove newest edge first when key=None",
            "ordering_policy": "LIFO across multiedges between same endpoints",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-002",
                    "description": "Behavior depends on dict insertion-order guarantees backing popitem().",
                    "policy_options": [
                        "enforce insertion-order LIFO behavior",
                        "choose arbitrary key removal (rejected)",
                    ],
                    "selected_policy": "enforce insertion-order LIFO behavior",
                    "risk_note": "Changing keyless removal order mutates user-visible edge deletion outcomes.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R02A",
                        "legacy_networkx_code/networkx/networkx/classes/tests/test_multigraph.py",
                        "363-406",
                        "Keyed and keyless remove_edge branches remain behavior-compatible.",
                    ),
                    hook(
                        "CGSE-UT-R02B",
                        "legacy_networkx_code/networkx/networkx/classes/tests/test_multidigraph.py",
                        "329-392",
                        "MultiDiGraph keyless removal and silent bulk-removal behavior remain parity-safe.",
                    ),
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R02",
                        "crates/fnx-conformance/fixtures/graph_core_mutation_hardened.json",
                        "1-200",
                        "Differential fixture validates multiedge mutation behavior under hardened mode.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "critical",
        },
        {
            "rule_id": "CGSE-R03",
            "operation_family": "graph_core_mutation",
            "title": "Directed-to-undirected attribute conflict ordering",
            "behavior_claim": "When opposing directed edges disagree on attributes, to_undirected keeps one using encounter-order-dependent merge behavior.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/classes/digraph.py",
                    "1264-1295",
                    ["DiGraph.to_undirected"],
                    "Docs explicitly call attr choice arbitrary and encounter-order dependent.",
                ),
                anchor(
                    "legacy_networkx_code/networkx/networkx/classes/multidigraph.py",
                    "879-897",
                    ["MultiDiGraph.to_undirected"],
                    "MultiDiGraph path carries same arbitrary-choice warning for conflicting attrs.",
                ),
            ],
            "tie_break_policy": "preserve encounter-order attr selection",
            "ordering_policy": "directed edge traversal order determines conflict winner",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-003",
                    "description": "Legacy contract marks conflict resolution as arbitrary.",
                    "policy_options": [
                        "preserve encounter-order semantics",
                        "canonicalize by lexical node ordering (rejected)",
                    ],
                    "selected_policy": "preserve encounter-order semantics",
                    "risk_note": "Canonicalization would intentionally diverge from legacy observable payload selection.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R03A",
                        "legacy_networkx_code/networkx/networkx/classes/tests/test_digraph.py",
                        "101-123",
                        "Reciprocal to_undirected behavior and reverse view interactions remain compatible.",
                    ),
                    hook(
                        "CGSE-UT-R03B",
                        "legacy_networkx_code/networkx/networkx/classes/tests/test_multidigraph.py",
                        "223-244",
                        "Multidigraph reciprocal filtering and attribute conflict surfaces remain compatible.",
                    ),
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R03",
                        "crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json",
                        "1-220",
                        "Strict fixture corpus catches drift in graph transformation semantics that affect algorithm output.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "critical",
        },
        {
            "rule_id": "CGSE-R04",
            "operation_family": "view_semantics",
            "title": "Core view iteration order and union ambiguity",
            "behavior_claim": "AtlasView delegates directly to backing dict iteration, while UnionAtlas combines keys via set union with undefined ordering.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/classes/coreviews.py",
                    "23-53",
                    ["AtlasView.__iter__"],
                    "AtlasView iteration returns iter(self._atlas), inheriting dict insertion order.",
                ),
                anchor(
                    "legacy_networkx_code/networkx/networkx/classes/coreviews.py",
                    "137-143",
                    ["UnionAtlas.__iter__"],
                    "UnionAtlas iterates set(self._succ.keys()) | set(self._pred.keys()), exposing set-order ambiguity.",
                ),
            ],
            "tie_break_policy": "prefer direct dict-order surfaces; treat set-union surfaces as ambiguity hotspots",
            "ordering_policy": "deterministic for pure dict proxies; ambiguous for set-union composites",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-004",
                    "description": "UnionAtlas key iteration uses set union and may vary by hash-seed/process state.",
                    "policy_options": [
                        "document and preserve legacy ambiguity",
                        "force sorted order in engine (rejected for strict mode)",
                    ],
                    "selected_policy": "document and preserve legacy ambiguity",
                    "risk_note": "Imposing sorted iteration in strict mode would alter observable legacy traversal order.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R04",
                        "legacy_networkx_code/networkx/networkx/classes/tests/test_coreviews.py",
                        "26-81",
                        "AtlasView/AdjacencyView iteration parity and view semantics must remain stable.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R04",
                        "crates/fnx-conformance/fixtures/generated/view_neighbors_strict.json",
                        "1-220",
                        "View neighbor-order fixture validates deterministic strict-mode view behavior.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
        {
            "rule_id": "CGSE-R05",
            "operation_family": "dispatch_routing",
            "title": "Backend-priority environment normalization",
            "behavior_claim": "Backend-priority environment keys are normalized and remaining suffix keys are applied in sorted order.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/utils/backends.py",
                    "164-183",
                    ["_set_configs_from_environment"],
                    "Priority suffixes are processed with sorted(priorities) for deterministic assignment order.",
                )
            ],
            "tie_break_policy": "sorted-key application for unknown priority categories",
            "ordering_policy": "stable env-variable fold order after normalization",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-005",
                    "description": "Conflicting priority sources (NETWORKX_BACKEND_PRIORITY vs suffix variants) can shadow values.",
                    "policy_options": [
                        "preserve legacy precedence exactly",
                        "merge all priority lists (rejected)",
                    ],
                    "selected_policy": "preserve legacy precedence exactly",
                    "risk_note": "Merging would change backend dispatch routing expectations.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R05",
                        "legacy_networkx_code/networkx/networkx/utils/tests/test_backends.py",
                        "217-218",
                        "Configured backend-priority contexts drive dispatch behavior deterministically.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R05",
                        "crates/fnx-conformance/fixtures/generated/dispatch_route_strict.json",
                        "1-220",
                        "Dispatch route fixture confirms route-selection behavior and fail-closed outcomes.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
        {
            "rule_id": "CGSE-R06",
            "operation_family": "dispatch_routing",
            "title": "Dispatch try-order grouping and no-guess rule",
            "behavior_claim": "Dispatch ordering is derived from five priority groups and explicitly avoids guessing tie-breaks for multiple unspecified backends.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/utils/backends.py",
                    "848-930",
                    ["_dispatchable._call_if_any_backends_installed"],
                    "Group1..5 ordering and explicit refusal to guess when len(group3)>1 are hard-coded.",
                )
            ],
            "tie_break_policy": "grouped-priority try-order with no implicit alphabetical fallback for ambiguous group3",
            "ordering_policy": "group1 -> group2 -> group3 -> group4 -> group5",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-006",
                    "description": "Multiple unspecified backend inputs create unresolved tie in group3.",
                    "policy_options": [
                        "fail/skip conversions rather than guess",
                        "alphabetical fallback ordering (rejected)",
                    ],
                    "selected_policy": "fail/skip conversions rather than guess",
                    "risk_note": "Guessing a backend can silently alter output/backend type semantics.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R06",
                        "legacy_networkx_code/networkx/networkx/utils/tests/test_backends.py",
                        "136-158",
                        "Mixing backend graphs should follow configured routing behavior and conversion boundaries.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R06",
                        "crates/fnx-conformance/fixtures/generated/dispatch_route_strict.json",
                        "1-220",
                        "Dispatch differential fixture captures routing + fallback outputs.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
        {
            "rule_id": "CGSE-R07",
            "operation_family": "conversion_contracts",
            "title": "to_networkx_graph conversion precedence",
            "behavior_claim": "Conversion probes input types in fixed order: NX graph-like, dict, edgelist-like, then specialized adapters.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/convert.py",
                    "34-122",
                    ["to_networkx_graph"],
                    "Control flow enforces deterministic conversion precedence with fallback chain and mode-sensitive dict handling.",
                )
            ],
            "tie_break_policy": "fixed probe-order precedence",
            "ordering_policy": "first successful conversion branch wins",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-007",
                    "description": "Dict inputs may satisfy multiple representations (dict-of-dicts vs dict-of-lists).",
                    "policy_options": [
                        "preserve dict-of-dicts attempt before dict-of-lists",
                        "auto-score/guess structure by content (rejected)",
                    ],
                    "selected_policy": "preserve dict-of-dicts attempt before dict-of-lists",
                    "risk_note": "Changing precedence can alter graph type/edge payload interpretation.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R07",
                        "legacy_networkx_code/networkx/networkx/tests/test_convert.py",
                        "21-31",
                        "Convert tests validate dict/list/graph conversion precedence contracts.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R07",
                        "crates/fnx-conformance/fixtures/generated/convert_edge_list_strict.json",
                        "1-220",
                        "Conversion fixture ensures strict conversion semantics remain parity-safe.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "critical",
        },
        {
            "rule_id": "CGSE-R08",
            "operation_family": "shortest_path_algorithms",
            "title": "Dijkstra fringe tie-break and predecessor selection",
            "behavior_claim": "Dijkstra heap entries include a monotonic counter and path reconstruction chooses the first predecessor in stored order.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/weighted.py",
                    "837-903",
                    ["_dijkstra_multisource"],
                    "Heap uses (distance, next(count), node); path reconstruction selects pred_dict[v][0].",
                )
            ],
            "tie_break_policy": "distance then insertion counter then predecessor-list first element",
            "ordering_policy": "equal-weight predecessors tracked in encounter order",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-008",
                    "description": "Equal-cost predecessor lists may contain multiple valid orderings.",
                    "policy_options": [
                        "preserve predecessor encounter order",
                        "lexicographically sort predecessors (rejected)",
                    ],
                    "selected_policy": "preserve predecessor encounter order",
                    "risk_note": "Sorting predecessors changes returned path for equal-cost alternatives.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R08",
                        "legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py",
                        "271-286",
                        "Predecessor and distance tests allow documented equal-cost ordering variants.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R08",
                        "crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json",
                        "1-220",
                        "Shortest-path fixture validates deterministic path outputs under strict mode.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "critical",
        },
        {
            "rule_id": "CGSE-R09",
            "operation_family": "shortest_path_algorithms",
            "title": "Bidirectional Dijkstra queue ordering",
            "behavior_claim": "Bidirectional Dijkstra alternates direction and uses counter-augmented heaps to avoid node-comparison tie breaks.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/weighted.py",
                    "2398-2453",
                    ["bidirectional_dijkstra"],
                    "Forward/backward fringes use (distance, next(count), node) and alternate expansion direction.",
                )
            ],
            "tie_break_policy": "alternating direction + monotonic fringe counter",
            "ordering_policy": "first discovered best meet-node wins unless shorter path found",
            "ambiguity_tags": [],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R09",
                        "legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py",
                        "165-182",
                        "Bidirectional shortest-path tests verify distance/path parity for representative graph families.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R09",
                        "crates/fnx-conformance/fixtures/graph_core_shortest_path_strict.json",
                        "1-220",
                        "Bidirectional behavior contributes to strict shortest-path fixture parity.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
        {
            "rule_id": "CGSE-R10",
            "operation_family": "readwrite_serialization",
            "title": "Edgelist emission ordering",
            "behavior_claim": "generate_edgelist emits lines in G.edges iteration order and preserves encountered edge-data key/value projection behavior.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/readwrite/edgelist.py",
                    "43-123",
                    ["generate_edgelist"],
                    "Emission loops directly over G.edges(data=...), inheriting graph iteration order.",
                )
            ],
            "tie_break_policy": "graph-edge iteration order",
            "ordering_policy": "output row order follows edge iterator traversal",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-009",
                    "description": "Stringified dict payload order depends on underlying dict key order.",
                    "policy_options": [
                        "preserve native dict order in strict mode",
                        "sort edge-attribute keys before stringify (hardened optional)",
                    ],
                    "selected_policy": "preserve native dict order in strict mode",
                    "risk_note": "Forced key sorting alters textual output parity for write_edgelist snapshots.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R10",
                        "legacy_networkx_code/networkx/networkx/readwrite/tests/test_edgelist.py",
                        "187-217",
                        "write_edgelist variants validate no-data/data/key-filter serialization behavior.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R10",
                        "crates/fnx-conformance/fixtures/generated/readwrite_roundtrip_strict.json",
                        "1-220",
                        "Read/write strict roundtrip fixture checks serialized edge-order stability.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
        {
            "rule_id": "CGSE-R11",
            "operation_family": "readwrite_serialization",
            "title": "Edgelist parse sequencing and coercion",
            "behavior_claim": "parse_edgelist consumes input lines sequentially and applies node/data type coercions before add_edge insertion.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/readwrite/edgelist.py",
                    "249-296",
                    ["parse_edgelist"],
                    "Line splitting, coercion, and add_edge happen in stream order; conversion errors are fail-fast.",
                )
            ],
            "tie_break_policy": "first-seen line order for duplicate/same-endpoint edges",
            "ordering_policy": "edge insertion order matches parsed line order",
            "ambiguity_tags": [],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R11",
                        "legacy_networkx_code/networkx/networkx/readwrite/tests/test_edgelist.py",
                        "117-170",
                        "parse_edgelist variants validate typed coercion, delimiter, and malformed input handling.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R11",
                        "crates/fnx-conformance/fixtures/generated/readwrite_json_roundtrip_strict.json",
                        "1-220",
                        "JSON/edgelist roundtrip fixture captures parse + serialization sequencing invariants.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
        {
            "rule_id": "CGSE-R12",
            "operation_family": "generator_semantics",
            "title": "Classic generator ordering contracts",
            "behavior_claim": "cycle_graph enforces increasing directed edge orientation and path_graph preserves iterable node order for edge construction.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/generators/classic.py",
                    "478-505",
                    ["cycle_graph"],
                    "Directed cycle orientation is documented as increasing order and built via pairwise(nodes, cyclic=True).",
                ),
                anchor(
                    "legacy_networkx_code/networkx/networkx/generators/classic.py",
                    "788-808",
                    ["path_graph"],
                    "Path edges are built in the iterable order provided by caller.",
                ),
            ],
            "tie_break_policy": "input-iterable order and documented directed orientation",
            "ordering_policy": "generator edge emission follows pairwise traversal",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-010",
                    "description": "Duplicate nodes in iterable input are accepted and can create surprising structures.",
                    "policy_options": [
                        "preserve legacy duplicate-node behavior",
                        "deduplicate input iterable (rejected)",
                    ],
                    "selected_policy": "preserve legacy duplicate-node behavior",
                    "risk_note": "Deduplication changes graph topology for user-supplied repeated nodes.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R12",
                        "legacy_networkx_code/networkx/networkx/generators/tests/test_classic.py",
                        "212-232",
                        "cycle_graph directed ordering and duplicate iterable behavior remain covered.",
                    ),
                    hook(
                        "CGSE-UT-R12B",
                        "legacy_networkx_code/networkx/networkx/generators/tests/test_classic.py",
                        "409-442",
                        "path_graph iterable-order semantics remain parity-safe.",
                    ),
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R12",
                        "crates/fnx-conformance/fixtures/generated/generators_cycle_strict.json",
                        "1-220",
                        "Generator cycle fixture validates deterministic construction order.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
        {
            "rule_id": "CGSE-R13",
            "operation_family": "runtime_config",
            "title": "Config validation ordering and unknown-backend reporting",
            "behavior_claim": "Runtime config validation sorts unknown backend names before rendering error messages for deterministic diagnostics.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/utils/configs.py",
                    "252-270",
                    ["BackendPriorities._on_setattr"],
                    "Unknown backend list is rendered via sorted(missing), stabilizing diagnostics.",
                ),
                anchor(
                    "legacy_networkx_code/networkx/networkx/utils/configs.py",
                    "366-381",
                    ["NetworkXConfig._on_setattr"],
                    "Backends config validation also sorts missing backend names before raising.",
                ),
            ],
            "tie_break_policy": "deterministic sorted error-report ordering",
            "ordering_policy": "stable validation message ordering across runs",
            "ambiguity_tags": [],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R13",
                        "legacy_networkx_code/networkx/networkx/utils/tests/test_config.py",
                        "120-169",
                        "Config tests assert backend-priority typing and unknown-backend error behavior.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R13",
                        "crates/fnx-conformance/fixtures/generated/runtime_config_optional_strict.json",
                        "1-220",
                        "Runtime optional-config fixture validates strict-mode config resolution paths.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "medium",
        },
        {
            "rule_id": "CGSE-R14",
            "operation_family": "oracle_test_surface",
            "title": "Legacy oracle acceptance of equal-cost predecessor ordering",
            "behavior_claim": "Legacy weighted shortest-path tests explicitly accept either predecessor ordering for equal-cost paths.",
            "source_anchors": [
                anchor(
                    "legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py",
                    "271-286",
                    ["test_dijkstra_predecessor2"],
                    "Oracle test permits pred[2] in [[1, 3], [3, 1]], confirming intentional ambiguity envelope.",
                )
            ],
            "tie_break_policy": "accept multiple equivalent predecessor orderings where legacy oracle permits",
            "ordering_policy": "maintain compatibility allowlist for equal-cost ambiguity",
            "ambiguity_tags": [
                {
                    "ambiguity_id": "CGSE-AMB-011",
                    "description": "Equal-cost predecessor ordering is intentionally non-unique in oracle contract.",
                    "policy_options": [
                        "allow documented permutation set",
                        "force single canonical predecessor sequence (rejected)",
                    ],
                    "selected_policy": "allow documented permutation set",
                    "risk_note": "Over-canonicalization risks false negative drift findings in differential conformance.",
                }
            ],
            "test_hooks": {
                "unit": [
                    hook(
                        "CGSE-UT-R14",
                        "legacy_networkx_code/networkx/networkx/algorithms/shortest_paths/tests/test_weighted.py",
                        "271-286",
                        "Oracle test itself encodes allowed predecessor-order permutations.",
                    )
                ],
                "property": [common_property],
                "differential": [
                    hook(
                        "CGSE-DIFF-R14",
                        "crates/fnx-conformance/fixtures/generated/conformance_harness_strict.json",
                        "1-220",
                        "Harness fixture tracks expected outputs and ambiguity-tolerant comparison semantics.",
                    )
                ],
                "e2e": [common_e2e],
            },
            "compatibility_risk": "high",
        },
    ]

    return rules


def build_artifact() -> dict[str, Any]:
    rules = build_rules()
    ambiguity_register = []
    for rule in rules:
        for tag in rule["ambiguity_tags"]:
            row = {
                "ambiguity_id": tag["ambiguity_id"],
                "rule_id": rule["rule_id"],
                "operation_family": rule["operation_family"],
                "description": tag["description"],
                "selected_policy": tag["selected_policy"],
                "risk_note": tag["risk_note"],
            }
            ambiguity_register.append(row)

    artifact = {
        "schema_version": "1.0.0",
        "artifact_id": "cgse-legacy-tiebreak-ordering-ledger-v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "baseline_comparator": "legacy_networkx_code/networkx/networkx (repository checkout in current workspace)",
        "scope_statement": "Source-anchored tie-break and ordering behavior ledger for legacy NetworkX surfaces used by FrankenNetworkX CGSE policy compilation.",
        "rule_families": [
            "graph_core_mutation",
            "view_semantics",
            "dispatch_routing",
            "conversion_contracts",
            "shortest_path_algorithms",
            "readwrite_serialization",
            "generator_semantics",
            "runtime_config",
            "oracle_test_surface",
        ],
        "rules": rules,
        "ambiguity_register": ambiguity_register,
        "alien_uplift_contract_card": {
            "artifact_track": "cgse",
            "ev_score": 2.6,
            "baseline": "Direct parity extraction from legacy source anchors without heuristic reinterpretation.",
            "notes": "Focuses on deterministic policy compilation inputs and ambiguity containment for strict/hardened splits.",
        },
        "profile_first_artifacts": {
            "baseline": "artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
            "hotspot": "artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
            "delta": "artifacts/perf/phase2c/perf_regression_gate_report_v1.json",
        },
        "decision_theoretic_runtime_contract": {
            "states": ["strict", "hardened", "fail_closed"],
            "actions": ["preserve_legacy_order", "allow_ambiguity_register", "reject_incompatible"],
            "loss_model": "behavioral-drift-major > deterministic-noise-minor > diagnostic-verbosity",
            "safe_mode_fallback": "reject unknown incompatible ordering surfaces and emit audit-ready ambiguity tags",
        },
        "isomorphism_proof_artifacts": [
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_001_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_FNX_P2C_005_V1.md",
            "artifacts/proofs/ISOMORPHISM_PROOF_NEIGHBOR_ITER_BFS_V2.md",
        ],
        "structured_logging_evidence": [
            "artifacts/conformance/latest/structured_logs.json",
            "artifacts/conformance/latest/structured_logs.jsonl",
            "artifacts/conformance/latest/telemetry_dependent_unblock_matrix_v1.json",
        ],
    }
    return artifact


def render_markdown(artifact: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# CGSE Legacy Tie-Break and Ordering Ledger")
    lines.append("")
    lines.append(f"- artifact id: `{artifact['artifact_id']}`")
    lines.append(f"- generated at (utc): `{artifact['generated_at_utc']}`")
    lines.append(f"- baseline comparator: `{artifact['baseline_comparator']}`")
    lines.append("")
    lines.append("## Scope")
    lines.append(artifact["scope_statement"])
    lines.append("")
    lines.append("## Rule Index")
    lines.append("| rule id | family | title | tie-break policy | ordering policy |")
    lines.append("|---|---|---|---|---|")
    for rule in artifact["rules"]:
        lines.append(
            "| {rule_id} | {family} | {title} | {tie} | {order} |".format(
                rule_id=rule["rule_id"],
                family=rule["operation_family"],
                title=rule["title"],
                tie=rule["tie_break_policy"],
                order=rule["ordering_policy"],
            )
        )

    lines.append("")
    lines.append("## Source Anchors")
    for rule in artifact["rules"]:
        lines.append(f"### {rule['rule_id']} - {rule['title']}")
        for src in rule["source_anchors"]:
            sym = ", ".join(src["symbols"])
            lines.append(
                f"- `{src['path']}:{src['lines']}` | symbols: `{sym}` | behavior: {src['legacy_behavior']}"
            )
        if rule["ambiguity_tags"]:
            lines.append("- ambiguity tags:")
            for tag in rule["ambiguity_tags"]:
                lines.append(
                    f"  - `{tag['ambiguity_id']}` selected=`{tag['selected_policy']}` - {tag['description']}"
                )
        lines.append("- planned hooks:")
        for channel, hooks in rule["test_hooks"].items():
            for row in hooks:
                lines.append(
                    f"  - `{channel}` `{row['hook_id']}` -> `{row['path']}:{row['lines']}` ({row['assertion']})"
                )
        lines.append("")

    lines.append("## Ambiguity Register")
    lines.append("| ambiguity id | rule id | family | selected policy | risk note |")
    lines.append("|---|---|---|---|---|")
    for row in artifact["ambiguity_register"]:
        lines.append(
            "| {ambiguity_id} | {rule_id} | {family} | {policy} | {risk} |".format(
                ambiguity_id=row["ambiguity_id"],
                rule_id=row["rule_id"],
                family=row["operation_family"],
                policy=row["selected_policy"],
                risk=row["risk_note"],
            )
        )

    lines.append("")
    lines.append("## Evidence References")
    lines.append("- profile baseline: `{}`".format(artifact["profile_first_artifacts"]["baseline"]))
    lines.append("- profile hotspot: `{}`".format(artifact["profile_first_artifacts"]["hotspot"]))
    lines.append("- profile delta: `{}`".format(artifact["profile_first_artifacts"]["delta"]))
    for path in artifact["isomorphism_proof_artifacts"]:
        lines.append(f"- isomorphism proof: `{path}`")
    for path in artifact["structured_logging_evidence"]:
        lines.append(f"- structured logging evidence: `{path}`")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json-out",
        default="artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.json",
        help="Output JSON artifact path",
    )
    parser.add_argument(
        "--md-out",
        default="artifacts/cgse/v1/cgse_legacy_tiebreak_ordering_ledger_v1.md",
        help="Output markdown artifact path",
    )
    args = parser.parse_args()

    root = repo_root()
    json_path = root / args.json_out
    md_path = root / args.md_out

    artifact = build_artifact()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(artifact), encoding="utf-8")

    print(json.dumps({
        "artifact_json": str(json_path.relative_to(root)),
        "artifact_markdown": str(md_path.relative_to(root)),
        "rule_count": len(artifact["rules"]),
        "ambiguity_count": len(artifact["ambiguity_register"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
