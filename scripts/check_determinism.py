#!/usr/bin/env python3
"""Cross-PYTHONHASHSEED / cross-process determinism gate for CGSE witnesses.

Reality-check bead rc-cgse-determinism-ci-job-4kr64.

Design principle 2 (README) promises byte-identical results across runs and
machines for CGSE-pinned algorithms. The decision-path Blake3 hash detects
tie-break ordering drift that output equality hides. This script:

1. Runs each candidate reference-algorithm route twice in-process
   (identical fresh graphs) and asserts identical witness decision-path
   hashes. NOTE: the algorithm must run INSIDE the armed
   `cgse.collect_witnesses` scope, so generator results are consumed inside
   the lambda (_materialize).
2. Spawns child processes of itself under DIFFERENT PYTHONHASHSEED values
   and asserts the per-algorithm hash vectors are identical across seeds
   and processes (hash-randomization must not leak into tie-break order).
3. Writes a receipt bundle to artifacts/determinism/latest/ with the
   resolved hash vector and its SHA-256, suitable for cross-runner
   comparison (G8's RaptorQ pipeline encodes everything under artifacts/).

Exit code 0 = deterministic; nonzero = a leak was found or an
EMIT_REQUIRED route stopped emitting or raised.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Routes where a witness MUST be emitted (README-documented emitting set).
EMIT_REQUIRED = {
    "connected_components": ("connected_components", "ring", ()),
    "topological_sort": ("topological_sort", "dag", ()),
    "bfs_edges": ("bfs_edges", "ring", ("0",)),
    "dfs_edges": ("dfs_edges", "ring", ("0",)),
    "minimum_spanning_tree": ("minimum_spanning_tree", "weighted_ring", ()),
    "bellman_ford_path": ("bellman_ford_path", "weighted_ring", ("0", "6")),
    "number_strongly_connected_components": (
        "number_strongly_connected_components",
        "dag",
        (),
    ),
}

# Routes that MAY emit (non-emitting public routes at the 2026-09-03 audit;
# if instrumentation lands they graduate into EMIT_REQUIRED).
MAY_EMIT = {
    "dijkstra": ("multi_source_dijkstra", "weighted_ring", (["0"],)),
    "prim": ("minimum_spanning_tree_prim", "weighted_ring", ()),
    "eulerian_circuit": ("eulerian_circuit", "ring", ("0",)),
    "max_weight_matching": ("max_weight_matching", "weighted_ring", ()),
    "min_weight_matching": ("min_weight_matching", "weighted_ring", ()),
}

NEEDS_WEIGHT_KWARG = {
    "minimum_spanning_tree",
    "minimum_spanning_tree_prim",
    "max_weight_matching",
    "min_weight_matching",
    "bellman_ford_path",
}


def build_graph(kind: str):
    import franken_networkx as fnx

    n = 12
    if kind == "dag":
        g = fnx.DiGraph()
        for i in range(n):
            g.add_node(str(i))
        for i in range(n - 1):
            g.add_edge(str(i), str(i + 1))
        g.add_edge("0", "5")
        g.add_edge("2", "9")
        return g
    g = fnx.Graph()
    for i in range(n):
        g.add_node(str(i))
    for i in range(n):
        g.add_edge(str(i), str((i + 1) % n))
    if kind == "weighted_ring":
        for i in range(n):
            g.add_edge(str(i), str((i + 1) % n), weight=1.0)
    return g


def _materialize(result):
    """Consume generators so lazy algorithms actually run inside the
    witness-collection scope."""
    if hasattr(result, "__next__"):
        return list(result)
    return result


def run_route(name: str):
    """Returns (hashes, detail) for one route run once."""
    from franken_networkx._fnx import cgse

    import franken_networkx as fnx

    func_name, kind, extra_args = EMIT_REQUIRED.get(name) or MAY_EMIT[name]
    g = build_graph(kind)
    func = getattr(fnx, func_name)
    kwargs = {"weight": "weight"} if func_name in NEEDS_WEIGHT_KWARG else {}

    result, witnesses = cgse.collect_witnesses(
        lambda: _materialize(func(g, *extra_args, **kwargs))
    )
    _ = result  # parity of the value itself is covered by the parity suites
    hashes = [
        w.decision_path_hash
        if isinstance(w.decision_path_hash, str)
        else bytes(w.decision_path_hash).hex()
        for w in witnesses
    ]
    detail = {
        "witnesses": len(hashes),
        "terms": [w.dominant_term for w in witnesses],
        "n": witnesses[0].n if witnesses else None,
        "m": witnesses[0].m if witnesses else None,
    }
    return hashes, detail


def collect_once() -> dict:
    out: dict = {"emit_required": {}, "may_emit": {}}
    for name in {**EMIT_REQUIRED, **MAY_EMIT}:
        bucket = "emit_required" if name in EMIT_REQUIRED else "may_emit"
        try:
            hashes, detail = run_route(name)
        except Exception as exc:  # noqa: BLE001 - record and continue
            out[bucket][name] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        out[bucket][name] = {"hashes": hashes, **detail}
    return out


def main() -> int:
    problems: list[str] = []

    # Phase 1: in-process stability (two runs, fresh graphs).
    first = collect_once()
    second = collect_once()
    for bucket in ("emit_required", "may_emit"):
        for name, run1 in first[bucket].items():
            if "error" in run1:
                if bucket == "emit_required":
                    problems.append(f"{name}: EMIT_REQUIRED route raised: {run1['error']}")
                continue
            run2 = second[bucket].get(name, {})
            if run1.get("hashes") != run2.get("hashes"):
                problems.append(
                    f"{name}: in-process runs differ: "
                    f"{run1.get('hashes')} vs {run2.get('hashes')}"
                )

    for name in EMIT_REQUIRED:
        entry = first["emit_required"].get(name, {})
        if not entry.get("hashes"):
            problems.append(f"{name}: EMIT_REQUIRED route emitted no witnesses")

    # Phase 2: cross-seed, cross-process stability.
    dumps: dict = {}
    for seed in ("0", "1", "random"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env["FNX_DETERMINISM_CHILD"] = "1"
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--dump"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO),
        )
        if proc.returncode != 0:
            problems.append(f"seed={seed}: child failed: {proc.stderr.strip()[-400:]}")
            continue
        dumps[seed] = json.loads(proc.stdout)

    vectors = {
        seed: payload["emit_required"] | payload["may_emit"]
        for seed, payload in dumps.items()
    }
    seeds = sorted(vectors)
    for other in seeds[1:]:
        base, cmp = vectors[seeds[0]], vectors[other]
        for name in base:
            if base.get(name) != cmp.get(name):
                problems.append(
                    f"{name}: PYTHONHASHSEED={seeds[0]} vs {other} witness vector differs"
                )

    # Phase 3: receipt bundle.
    out_dir = REPO / "artifacts" / "determinism" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "seed_vectors": vectors,
        "problems": problems,
    }
    blob = json.dumps(receipt, sort_keys=True, indent=1).encode()
    (out_dir / "determinism_receipt_v1.json").write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    (out_dir / "determinism_receipt_v1.sha256").write_text(digest + "\n")

    if problems:
        print("DETERMINISM GATE: FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print(f"DETERMINISM GATE: PASS (receipt sha256 {digest[:16]}…, seeds {seeds})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        print(json.dumps(collect_once()))
        sys.exit(0)
    sys.exit(main())
