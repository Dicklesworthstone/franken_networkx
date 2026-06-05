"""br-r37-c1-fmggo: find _raw_<X> exposures in franken_networkx.__init__.py
that are imported but never invoked from any wrapper body.

Three outcomes per binding:

- **keep-public-api**: The public wrapper deliberately uses a different
  Rust path (e.g. composes from a more general _raw_, or re-implements
  in Python for nx tie-break parity). The _raw_<X> exposure is kept as
  the direct-Rust API surface for users who want to bypass the wrapper.
- **wire-up**: The wrapper currently routes to nx fallback even though
  the _raw_<X> exists. Could be a perf win to wire it up — file a
  follow-up bead.
- **remove**: No clear reason to keep the binding; not used internally,
  not part of a documented direct-Rust API. Could be removed.

Output: ``docs/unused_raw_exposures.md`` plus the triage classification
that humans use to decide cleanup vs. wiring work.

Usage::

    python3 scripts/find_unused_raw_exposures.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import franken_networkx as fnx

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_PATH = REPO_ROOT / "python" / "franken_networkx" / "__init__.py"
DOCS_DIR = REPO_ROOT / "docs"


# Triage decisions made via per-function review of __init__.py.
# Decisions made on 2026-05-09 by TealOtter; rationale documented in
# the dict for future review.
TRIAGE = {
    # ---- keep-public-api: wrapper uses a different path on purpose ----
    "_raw_symmetric_difference": ("keep-public-api",
        "br-r37-c1-aun4c: wrapper replicates installed nx verbatim in "
        "Python (check sequence, with_data=False copy depth, batched "
        "edge passes) — the Rust kernel collapsed multigraph parallel "
        "edges and its rebuild was ~8x nx"),
    "_raw_topological_sort": ("keep-public-api",
        "wrapper re-implements Kahn's in Python for byte-identical nx "
        "tie-break order (br-codtrav)"),
    "_raw_lexicographic_topological_sort": ("keep-public-api",
        "called from lexicographic_topological_sort wrapper after preflight"),
    "_raw_single_source_dijkstra_path_length": ("keep-public-api",
        "wrapper composes from _raw_single_source_dijkstra (more general — "
        "yields dists+paths in one pass)"),
    "_raw_floyd_warshall_predecessor_and_distance": ("keep-public-api",
        "wrapper delegates to nx for iteration-order parity (br-r37-c1-h1kf2)"),
    "_raw_max_weight_matching": ("keep-public-api",
        "exposed for direct callers; public wrapper has additional "
        "tuple-direction parity logic (br-r37-c1-edgekeyfirstwins / matching)"),
    "_raw_min_weight_matching": ("keep-public-api",
        "same rationale as _raw_max_weight_matching"),
    "_raw_kosaraju_strongly_connected_components": ("keep-public-api",
        "wrapper uses Tarjan-style native path; Kosaraju kept as alternative"),
    "_raw_shortest_simple_paths": ("keep-public-api",
        "wrapper has Yen's-algorithm Python orchestration; raw kernel is "
        "BFS-based primitive"),
    "_raw_min_edge_cover": ("keep-public-api",
        "exposed for direct callers; public wrapper has nx-parity post-process"),
    "_raw_minimum_node_cut": ("keep-public-api",
        "wrapper has additional flow-based handling for s/t cases"),
    "_raw_transitive_reduction": ("keep-public-api",
        "exposed for direct DAG callers; public wrapper has DiGraph-only check"),
    "_raw_random_spanning_tree": ("keep-public-api",
        "wrapper has seed/multiplicity handling layer"),
    "_raw_voterank": ("keep-public-api",
        "wrapper has number_of_results / max_iter handling"),
    "_raw_eulerian_circuit": ("keep-public-api",
        "wrapper has source-node selection and order normalization"),
    "_raw_find_cliques_recursive": ("keep-public-api",
        "exposed for direct callers; public uses iterative variant"),
    "_raw_compose": ("keep-public-api",
        "wrapper handles MultiGraph/MultiDiGraph dispatch"),
    "_raw_intersection": ("keep-public-api",
        "wrapper handles MultiGraph/MultiDiGraph dispatch"),
    "_raw_non_edges": ("keep-public-api",
        "wrapper has DiGraph special-case for direction"),
    "_raw_dag_longest_path_length": ("keep-public-api",
        "wrapper has int/float type-coerce post-process (br-r37-c1-oqspv)"),
    "_raw_efficiency": ("keep-public-api",
        "wrapper has u/v node-existence pre-check"),
    "_raw_jaccard_coefficient": ("keep-public-api",
        "wrapper handles ebunch=None case via Python iterator"),
    "_raw_adamic_adar_index": ("keep-public-api",
        "wrapper handles ebunch=None case via Python iterator"),
    "_raw_resource_allocation_index": ("keep-public-api",
        "wrapper handles ebunch=None case via Python iterator"),
    "_raw_preferential_attachment": ("keep-public-api",
        "wrapper handles ebunch=None case via Python iterator"),
    "_raw_common_neighbors": ("keep-public-api",
        "wrapper materializes neighbors via G.adj for nx parity"),
    "_raw_antichains": ("keep-public-api",
        "wrapper accepts topo_order kwarg the binding lacks"),
    "_raw_biconnected_component_edges": ("keep-public-api",
        "wrapper produces edge-tuple format from raw component output"),
    "_raw_degree_histogram": ("keep-public-api",
        "wrapper handles MultiGraph parallel-edge counting"),
    "_raw_is_aperiodic": ("keep-public-api",
        "wrapper does emptyish-graph short-circuit before Rust call"),
    "_raw_is_attracting_component": ("keep-public-api",
        "wrapper accepts a node, raw works on components — different shape"),
    "_raw_is_isolate": ("keep-public-api",
        "wrapper checks G.is_directed() to dispatch correctly"),
    "_raw_dag_longest_path": ("keep-public-api",
        "wrapper handles weight callable and topological_sort kwarg"),
    "_raw_find_cliques": ("keep-public-api",
        "wrapper handles nodes-subset kwarg and iteration order"),
    "_raw_floyd_warshall": ("keep-public-api",
        "wrapper delegates to nx for iteration-order parity (br-r37-c1-h1kf2); "
        "raw kept as direct-Rust API"),
    "_raw_single_source_dijkstra_path": ("keep-public-api",
        "wrapper composes from _raw_single_source_dijkstra (yields paths "
        "alongside dists in one pass)"),
    # ---- keep-public-api: namespace-hide batches removed the public
    # top-level wrappers (the algorithm is reachable via nx through
    # fnx.community.X / fnx.approximation.X), but the Rust kernel
    # remains exposed for direct callers (br-r37-c1-{ccr8k, uwm5v,
    # xgqo1, 02sx1}). ----
    "_raw_clique_removal": ("keep-public-api",
        "br-r37-c1-xgqo1: nx.approximation.clique_removal routes "
        "fnx.approximation.X; raw kept as direct-Rust API"),
    "_raw_global_node_connectivity": ("keep-public-api",
        "br-r37-c1-ccr8k: fnx-only top-level removed; raw kept for "
        "direct callers (use node_connectivity for nx parity)"),
    "_raw_greedy_modularity_communities": ("keep-public-api",
        "br-r37-c1-uwm5v: fnx.community.X falls through to nx; "
        "raw kept as direct-Rust API"),
    "_raw_large_clique_size": ("keep-public-api",
        "br-r37-c1-dytcs: fnx.approximation.large_clique_size falls "
        "through to nx; raw kept as direct-Rust API"),
    "_raw_louvain_communities": ("keep-public-api",
        "br-r37-c1-uwm5v: fnx.community.louvain_communities falls "
        "through to nx (with fg->ng conversion); raw kept as direct"
        "-Rust API"),
    "_raw_max_clique": ("keep-public-api",
        "br-r37-c1-xgqo1: fnx.approximation.max_clique falls through "
        "to nx; raw kept as direct-Rust API"),
    "_raw_maximum_independent_set": ("keep-public-api",
        "br-r37-c1-xgqo1: fnx.approximation.maximum_independent_set "
        "falls through to nx; raw kept as direct-Rust API"),
    "_raw_min_weighted_vertex_cover": ("keep-public-api",
        "br-r37-c1-xgqo1: fnx.approximation.min_weighted_vertex_cover "
        "falls through to nx; raw kept as direct-Rust API"),
    # ---- 2026-05-22 (br-r37-c1-rebzj cousin): wrappers delegate to nx ----
    "_raw_bellman_ford_path": ("keep-public-api",
        "br-r37-c1-9axrp: Rust bellman_ford_path returns incorrect paths "
        "(direct edge instead of shorter multi-hop); wrapper delegates "
        "to nx until the Rust binding is fixed.  Raw kept as direct API."),
    "_raw_bellman_ford_path_length": ("keep-public-api",
        "br-r37-c1-9axrp: same Rust bug as _raw_bellman_ford_path; "
        "wrapper delegates to nx.  Raw kept as direct API."),
    "_raw_max_weight_clique": ("keep-public-api",
        "br-r37-c1-07gkp: Rust max_weight_clique returns clique *size* "
        "instead of summing node weights, and rejects weight=None "
        "(br-mwclqnone). Wrapper delegates to nx; raw kept as direct API."),
    "_raw_average_node_connectivity": ("keep-public-api",
        "br-r37-c1-qz40o: Rust BFS-based local_node_connectivity is a "
        "heuristic that mis-reports in non-trivial cases; wrapper "
        "delegates to nx's max-flow-on-auxiliary-graph path.  Raw kept "
        "as direct API."),
    "_raw_pagerank": ("keep-public-api",
        "br-r37-c1-y5y7i: wrapper uses scipy.sparse matvec for 2x+ "
        "speedup over pure-Rust scalar iteration on dense graphs.  Raw "
        "Rust kernel kept as direct API for callers who want Rust-only."),
}


def find_unused_raw_exposures() -> dict[str, int]:
    """Return ``{raw_name: reference_count}`` for every _raw_<X> in fnx
    whose only mention in __init__.py is the import line."""
    text = INIT_PATH.read_text(encoding="utf-8")
    raw_exports = [n for n in dir(fnx) if n.startswith("_raw_")]
    unused: dict[str, int] = {}
    for raw in sorted(raw_exports):
        # Use word-boundary regex to avoid false positives from substrings.
        count = len(re.findall(rf"\b{re.escape(raw)}\b", text))
        if count <= 1:
            unused[raw] = count
    return unused


def write_report(unused: dict[str, int], path: Path) -> None:
    by_decision: dict[str, list[tuple[str, str]]] = {}
    untriaged: list[str] = []
    for name in unused:
        if name in TRIAGE:
            decision, rationale = TRIAGE[name]
            by_decision.setdefault(decision, []).append((name, rationale))
        else:
            untriaged.append(name)

    lines = [
        "# Unused `_raw_<X>` Exposures Triage",
        "",
        "*Auto-generated by `scripts/find_unused_raw_exposures.py` (br-r37-c1-fmggo).*",
        "",
        f"Total `_raw_*` exposures with only the import-line reference: **{len(unused)}**",
        "",
        "## Triage decisions",
        "",
        "Three categories:",
        "",
        "- **keep-public-api**: the wrapper deliberately takes a different path "
        "(byte-identical nx tie-break, type-coerce post-process, ebunch handling, "
        "etc.) but the `_raw_<X>` is kept as the direct-Rust API surface.",
        "- **wire-up**: a wrapper currently delegates to nx even though `_raw_<X>` "
        "exists — perf win opportunity if wired up.",
        "- **remove**: no rationale to keep; candidate for deletion.",
        "",
    ]
    for decision in ("keep-public-api", "wire-up", "remove"):
        rows = by_decision.get(decision, [])
        lines.append(f"## {decision} ({len(rows)})")
        lines.append("")
        if not rows:
            lines.append("_No entries._")
            lines.append("")
            continue
        lines.append("| binding | rationale |")
        lines.append("|---------|-----------|")
        for name, rationale in sorted(rows):
            lines.append(f"| `{name}` | {rationale} |")
        lines.append("")

    if untriaged:
        lines.append(f"## untriaged ({len(untriaged)})")
        lines.append("")
        lines.append("New `_raw_<X>` exposures discovered since the last triage. "
                     "Add a TRIAGE entry to `scripts/find_unused_raw_exposures.py`.")
        lines.append("")
        for name in sorted(untriaged):
            lines.append(f"- `{name}`")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    unused = find_unused_raw_exposures()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_report(unused, out_dir / "unused_raw_exposures.md")

    if not args.quiet:
        print(f"Found {len(unused)} _raw_<X> exposures with only import-line reference.")
        triaged = sum(1 for n in unused if n in TRIAGE)
        print(f"  Triaged:   {triaged}")
        print(f"  Untriaged: {len(unused) - triaged}")
        print(f"\nWrote {out_dir / 'unused_raw_exposures.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
