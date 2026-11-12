#!/usr/bin/env python3
"""Generate profile-first hotspot evidence and one-lever optimization backlog."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


LEVER_BY_TOPOLOGY = {
    "grid": "borrowed-neighbor frontier iteration (remove transient frontier clone materialization)",
    "line": "queue preallocation with stable index reuse (remove growth-induced realloc churn)",
    "star": "hub-degree short-circuit traversal path (single-pass hub expansion without extra frontier copy)",
    "complete": "bidirectional BFS early-stop policy for dense graphs (single lever: frontier meeting cutoff)",
    "erdos_renyi": "frontier bitmap de-duplication (single-pass membership marking to avoid repeated queue insertions)",
}

PACKET_OPTIMIZATION_BEADS = [
    "bd-315.12.8",
    "bd-315.13.8",
    "bd-315.14.8",
    "bd-315.15.8",
    "bd-315.16.8",
    "bd-315.17.8",
    "bd-315.18.8",
    "bd-315.19.8",
    "bd-315.20.8",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix",
        default="artifacts/perf/phase2c/perf_baseline_matrix_v1.json",
    )
    parser.add_argument(
        "--events",
        default="artifacts/perf/phase2c/perf_baseline_matrix_events_v1.jsonl",
    )
    parser.add_argument(
        "--output",
        default="artifacts/perf/phase2c/hotspot_one_lever_backlog_v1.json",
    )
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    events_path = Path(args.events)
    output_path = Path(args.output)

    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    measurement_events = [row for row in events if row.get("phase") == "measurement"]
    event_count_by_scenario: dict[str, int] = {}
    for row in measurement_events:
        scenario_id = str(row["scenario_id"])
        event_count_by_scenario[scenario_id] = event_count_by_scenario.get(scenario_id, 0) + 1

    scenarios = sorted(
        matrix["scenarios"],
        key=lambda row: row["time_ms"]["p95"],
        reverse=True,
    )

    hotspot_profiles = []
    backlog = []
    for rank, scenario in enumerate(scenarios, start=1):
        scenario_id = scenario["scenario_id"]
        topology = scenario["topology"]
        p95_ms = float(scenario["time_ms"]["p95"])
        p99_ms = float(scenario["time_ms"]["p99"])
        memory_p95_kb = float(scenario["max_rss_kb"]["p95"])
        ev_score = round((p95_ms / 1000.0) * (1.0 + (memory_p95_kb / 20_000.0)), 3)
        lever = LEVER_BY_TOPOLOGY[topology]
        fallback_trigger = (
            "rollback if p95 or p99 regresses by >5% versus baseline for 2 consecutive gate runs"
        )
        rollback_path = "git revert <optimization-commit-sha>"

        hotspot_profiles.append(
            {
                "rank": rank,
                "scenario_id": scenario_id,
                "topology": topology,
                "size_bucket": scenario["size_bucket"],
                "density_class": scenario["density_class"],
                "node_count": scenario["node_count"],
                "edge_count_estimate": scenario["edge_count_estimate"],
                "event_count": event_count_by_scenario.get(scenario_id, 0),
                "latency_ms": {
                    "p50": scenario["time_ms"]["p50"],
                    "p95": scenario["time_ms"]["p95"],
                    "p99": scenario["time_ms"]["p99"],
                },
                "memory_kb": {
                    "p50": scenario["max_rss_kb"]["p50"],
                    "p95": scenario["max_rss_kb"]["p95"],
                    "p99": scenario["max_rss_kb"]["p99"],
                },
                "bottleneck_hypothesis": lever,
                "evidence_refs": [str(matrix_path), str(events_path)],
            }
        )

        backlog.append(
            {
                "entry_id": f"perf-one-lever-{rank:02d}",
                "rank": rank,
                "target_scenario_id": scenario_id,
                "expected_value_score": ev_score,
                "single_lever": lever,
                "lever_count": 1,
                "baseline_comparator": str(matrix_path),
                "fallback_trigger": fallback_trigger,
                "rollback_path": rollback_path,
                "decision_contract": {
                    "states": ["regression", "parity_preserved_speedup"],
                    "actions": ["ship_optimization", "rollback"],
                    "loss_model": "regression_cost >> unrealized_speedup",
                    "safe_mode_budget_trigger": ">5% p95/p99 regression across 2 consecutive runs",
                },
                "isomorphism_proof_refs": [
                    "artifacts/proofs/ISOMORPHISM_PROOF_NEIGHBOR_ITER_BFS_V2.md",
                    "artifacts/perf/proof/golden_checksums.txt",
                ],
                "risk_note_refs": [
                    "artifacts/perf/proof/2026-02-14_graph_kernel_clone_elision.md"
                ],
                "linked_packet_optimization_beads": PACKET_OPTIMIZATION_BEADS,
            }
        )

    backlog.sort(key=lambda row: row["expected_value_score"], reverse=True)
    for rank, entry in enumerate(backlog, start=1):
        entry["rank"] = rank
        entry["entry_id"] = f"perf-one-lever-{rank:02d}"

    payload = {
        "schema_version": "1.0.0",
        "backlog_id": "phase2c-hotspot-one-lever-backlog-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_matrix_path": str(matrix_path),
        "source_events_path": str(events_path),
        "optimization_protocol": {
            "profile_first_required": True,
            "one_lever_per_change": True,
            "behavior_isomorphism_proof_required": True,
            "minimum_ev_score": 2.0,
        },
        "hotspot_profiles": hotspot_profiles,
        "optimization_backlog": backlog,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"hotspot_one_lever_backlog:{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
