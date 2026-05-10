"""br-r37-c1-cvrij: raw-vs-public algorithm consistency audit.

For every ``_raw_<NAME>`` re-exported from ``franken_networkx`` that
also has a public ``<NAME>`` wrapper, run both on a battery of small
fixtures and compare results. Classify each ``_raw_*`` kernel as:

- **identical**: raw and public agree on every fixture → public path
  could be raw with no wrapper (the "fixed-native" class).
- **wrapper-corrected**: raw and public disagree on at least one
  fixture, and public matches NetworkX. The wrapper is doing real
  work — either compensating for a Rust kernel bug, or post-processing
  output (sort, reorder, type-coerce).
- **wrapper-misalign**: raw and public agree, but neither matches
  NetworkX — the wrapper is not isolating users from a Rust bug.
- **error-divergence**: one path raises an exception while the other
  returns; same call shape produces incompatible outcomes.
- **untestable**: signature drift between raw and public (different
  required arguments) means we cannot run them side-by-side
  automatically; manual review is needed.

The output is a Markdown report at ``docs/raw_vs_public_audit.md`` and
a machine-readable ``docs/raw_vs_public_audit.json``.

Run with:

    python3 scripts/raw_vs_public_audit.py
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import math
import sys
import traceback
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _path_graph_5() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    return fg, ng


def _cycle_6() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.cycle_graph(6)
    ng = nx.cycle_graph(6)
    return fg, ng


def _star_5() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.star_graph(5)
    ng = nx.star_graph(5)
    return fg, ng


def _complete_4() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.complete_graph(4)
    ng = nx.complete_graph(4)
    return fg, ng


def _weighted_path_5() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.Graph()
    ng = nx.Graph()
    for i in range(4):
        fg.add_edge(i, i + 1, weight=i + 1.5)
        ng.add_edge(i, i + 1, weight=i + 1.5)
    return fg, ng


def _weighted_path_postmut_5() -> tuple[fnx.Graph, nx.Graph]:
    """Verifies br-r37-c1-sjf4t fix end-to-end: post-creation mutation."""
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    for i, (u, v) in enumerate(fg.edges):
        fg[u][v]["weight"] = i + 1.5
    for i, (u, v) in enumerate(ng.edges):
        ng[u][v]["weight"] = i + 1.5
    return fg, ng


def _bipartite_3_3() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.complete_bipartite_graph(3, 3)
    ng = nx.complete_bipartite_graph(3, 3)
    return fg, ng


def _petersen() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.petersen_graph()
    ng = nx.petersen_graph()
    return fg, ng


def _digraph_chain_5() -> tuple[fnx.DiGraph, nx.DiGraph]:
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for i in range(4):
        fg.add_edge(i, i + 1)
        ng.add_edge(i, i + 1)
    return fg, ng


def _multigraph_path_5() -> tuple[fnx.MultiGraph, nx.MultiGraph]:
    """Undirected multigraph with one extra parallel edge."""
    fg = fnx.MultiGraph()
    ng = nx.MultiGraph()
    for i in range(4):
        fg.add_edge(i, i + 1)
        ng.add_edge(i, i + 1)
    # Extra parallel edge to exercise multi-key paths.
    fg.add_edge(0, 1)
    ng.add_edge(0, 1)
    return fg, ng


def _multidigraph_chain_5() -> tuple[fnx.MultiDiGraph, nx.MultiDiGraph]:
    fg = fnx.MultiDiGraph()
    ng = nx.MultiDiGraph()
    for i in range(4):
        fg.add_edge(i, i + 1)
        ng.add_edge(i, i + 1)
    return fg, ng


def _empty_graph() -> tuple[fnx.Graph, nx.Graph]:
    return fnx.Graph(), nx.Graph()


def _single_node() -> tuple[fnx.Graph, nx.Graph]:
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_node(0)
    ng.add_node(0)
    return fg, ng


# Map fixture id -> (label, builder).
FIXTURES: list[tuple[str, callable]] = [
    ("path-5", _path_graph_5),
    ("cycle-6", _cycle_6),
    ("star-5", _star_5),
    ("complete-4", _complete_4),
    ("weighted-path-5", _weighted_path_5),
    ("weighted-postmut-5", _weighted_path_postmut_5),
    ("bipartite-3-3", _bipartite_3_3),
    ("petersen", _petersen),
    ("digraph-chain-5", _digraph_chain_5),
    ("multigraph-path-5", _multigraph_path_5),
    ("multidigraph-chain-5", _multidigraph_chain_5),
    ("empty", _empty_graph),
    ("single-node", _single_node),
]


# ---------------------------------------------------------------------------
# Per-function signatures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CallShape:
    """A way to invoke a function on a fixture: (args, kwargs)."""

    args_factory: callable  # given (fg, ng) → list of args (uses fg)
    kwargs: tuple[tuple[str, Any], ...] = ()
    nx_kwargs: tuple[tuple[str, Any], ...] = ()

    def fnx_args_kwargs(self, fg, ng):
        return self.args_factory(fg, ng, "fnx"), dict(self.kwargs)

    def nx_args_kwargs(self, fg, ng):
        return self.args_factory(fg, ng, "nx"), dict(self.nx_kwargs or self.kwargs)


def _arg_first_node(fg, ng, side):
    g = fg if side == "fnx" else ng
    nodes = list(g)
    return [nodes[0]] if nodes else []


def _arg_first_two_nodes(fg, ng, side):
    g = fg if side == "fnx" else ng
    nodes = list(g)
    return [nodes[0], nodes[-1]] if len(nodes) >= 2 else []


def _arg_none(fg, ng, side):
    return []


# Manually-curated function spec list. We sample a representative
# subset (shortest-path, centrality, planarity, structural) — extending
# fixture coverage is straightforward.
FUNCTION_SPECS: list[tuple[str, CallShape, set[str]]] = [
    # name, call shape, fixtures to skip (by id)
    # Shortest-path family
    ("single_source_dijkstra_path_length", CallShape(_arg_first_node), set()),
    ("single_source_dijkstra_path", CallShape(_arg_first_node), set()),
    ("single_source_bellman_ford_path_length", CallShape(_arg_first_node), set()),
    ("dijkstra_path_length", CallShape(_arg_first_two_nodes), {"weighted-postmut-5"}),
    ("astar_path_length", CallShape(_arg_first_two_nodes), set()),
    ("shortest_path_length", CallShape(_arg_first_two_nodes), set()),
    ("all_pairs_dijkstra_path_length", CallShape(_arg_none), set()),
    ("all_pairs_shortest_path_length", CallShape(_arg_none), set()),
    # Centrality
    ("betweenness_centrality", CallShape(_arg_none), set()),
    ("closeness_centrality", CallShape(_arg_none), set()),
    ("degree_centrality", CallShape(_arg_none), set()),
    ("clustering", CallShape(_arg_none), set()),
    ("average_clustering", CallShape(_arg_none), set()),
    ("harmonic_centrality", CallShape(_arg_none), set()),
    ("load_centrality", CallShape(_arg_none), set()),
    ("transitivity", CallShape(_arg_none), set()),
    ("triangles", CallShape(_arg_none), set()),
    ("square_clustering", CallShape(_arg_none), set()),
    # Structural
    ("articulation_points", CallShape(_arg_none), set()),
    ("bridges", CallShape(_arg_none), set()),
    ("is_planar", CallShape(_arg_none), set()),
    ("is_eulerian", CallShape(_arg_none), set()),
    ("is_connected", CallShape(_arg_none), set()),
    ("is_biconnected", CallShape(_arg_none), set()),
    ("is_bipartite", CallShape(_arg_none), set()),
    ("is_chordal", CallShape(_arg_none), set()),
    ("is_forest", CallShape(_arg_none), set()),
    ("is_tree", CallShape(_arg_none), set()),
    ("connected_components", CallShape(_arg_none), set()),
    ("number_connected_components", CallShape(_arg_none), set()),
    ("biconnected_components", CallShape(_arg_none), set()),
    ("density", CallShape(_arg_none), set()),
    ("number_of_edges", CallShape(_arg_none), set()),
    ("number_of_isolates", CallShape(_arg_none), set()),
    ("number_of_selfloops", CallShape(_arg_none), set()),
    # Distance
    ("diameter", CallShape(_arg_none), set()),
    ("radius", CallShape(_arg_none), set()),
    ("center", CallShape(_arg_none), set()),
    ("periphery", CallShape(_arg_none), set()),
    ("eccentricity", CallShape(_arg_none), set()),
    ("girth", CallShape(_arg_none), set()),
    ("barycenter", CallShape(_arg_none), set()),
    # Cliques / coloring
    ("find_cliques", CallShape(_arg_none), set()),
    ("graph_clique_number", CallShape(_arg_none), set()),
    ("number_of_cliques", CallShape(_arg_none), set()),
    ("greedy_color", CallShape(_arg_none), set()),
    ("core_number", CallShape(_arg_none), set()),
    # Tree / DAG
    ("topological_sort", CallShape(_arg_none), set()),
    ("dag_longest_path", CallShape(_arg_none), set()),
    ("dag_longest_path_length", CallShape(_arg_none), set()),
    # Counts
    ("degree_histogram", CallShape(_arg_none), set()),
]


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _normalize(value):
    """Reduce a result to a comparable canonical form."""
    if value is None:
        return None
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return ("float", "nan")
        return ("num", float(value))
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, dict):
        return ("dict", tuple(sorted((k, _normalize(v)) for k, v in value.items())))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted(_normalize(x) for x in value)))
    if isinstance(value, tuple):
        return ("tuple", tuple(_normalize(x) for x in value))
    if isinstance(value, list):
        return ("list", tuple(_normalize(x) for x in value))
    if isinstance(value, Iterable):
        try:
            collected = list(value)
        except Exception:
            return ("iter-unconsumed", repr(type(value).__name__))
        return _normalize(collected)
    return ("repr", repr(value))


def _approx_equal(a, b, tol: float = 1e-9) -> bool:
    """Compare normalized values, accepting small float deltas."""
    if a == b:
        return True
    if a is None or b is None:
        return False
    # Tagged 2-tuples emitted by ``_normalize``: ("num", float),
    # ("dict", kv_tuple), ("list", elements), etc. Detect tag equality
    # before falling through to generic element-wise tuple comparison.
    if (
        isinstance(a, tuple)
        and isinstance(b, tuple)
        and len(a) == 2
        and len(b) == 2
        and a[0] == b[0]
        and isinstance(a[0], str)
    ):
        if a[0] == "num":
            return math.isclose(a[1], b[1], rel_tol=1e-9, abs_tol=1e-12)
        if a[0] in ("dict", "list", "tuple", "set"):
            return _approx_equal(a[1], b[1], tol)
        # other tagged variants — fall through to element-wise compare
    if isinstance(a, tuple) and isinstance(b, tuple):
        if len(a) != len(b):
            return False
        return all(_approx_equal(x, y, tol) for x, y in zip(a, b))
    return False


@dataclass
class CallOutcome:
    ok: bool
    value: Any = None
    error_type: str | None = None
    error_msg: str | None = None


def _call(fn, args, kwargs) -> CallOutcome:
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:
        return CallOutcome(
            ok=False,
            error_type=type(exc).__name__,
            error_msg=str(exc)[:200],
        )
    # Materialize iterators so we can compare. Raising on iteration is
    # treated the same as raising on call — a `not_implemented_for`
    # decorator is allowed to defer until the first `next()`.
    if hasattr(result, "__iter__") and not isinstance(
        result, (str, bytes, dict, list, tuple, set, frozenset)
    ):
        try:
            result = list(result)
        except Exception as exc:
            return CallOutcome(
                ok=False,
                error_type=type(exc).__name__,
                error_msg=str(exc)[:200],
            )
    return CallOutcome(ok=True, value=result)


def _outcome_matches(left: CallOutcome, right: CallOutcome) -> bool:
    if left.ok and right.ok:
        return _approx_equal(_normalize(left.value), _normalize(right.value))
    if not left.ok and not right.ok:
        return left.error_type == right.error_type and left.error_msg == right.error_msg
    return False


@dataclass
class FixtureRow:
    fixture_id: str
    raw: CallOutcome
    public: CallOutcome
    nx_baseline: CallOutcome


@dataclass
class FuncReport:
    name: str
    raw_callable: bool
    public_callable: bool
    rows: list[FixtureRow] = field(default_factory=list)
    classification: str = "unclassified"
    notes: list[str] = field(default_factory=list)


def _classify(report: FuncReport) -> str:
    """Decide the classification bucket from the per-fixture rows."""
    if not report.raw_callable or not report.public_callable:
        return "untestable-not-exposed"

    has_disagreement = False
    public_matches_nx_everywhere = True
    raw_matches_nx_everywhere = True
    raw_stricter_than_public = False  # raw raises, public+nx return
    raw_looser_than_public = False    # raw returns, public+nx raise

    for row in report.rows:
        # Distinguish two kinds of error mismatch:
        # - raw raises while public + nx return → stricter raw kernel
        #   (intentional defensive guard; wrapper has richer handling)
        # - raw returns while public + nx raise → the audit's true bug
        #   class (the kernel must be tightened)
        if not row.raw.ok and row.public.ok and row.nx_baseline.ok:
            raw_stricter_than_public = True
        if row.raw.ok and not row.public.ok and not row.nx_baseline.ok:
            raw_looser_than_public = True

        if not _outcome_matches(row.raw, row.public):
            has_disagreement = True
        if not _outcome_matches(row.public, row.nx_baseline):
            public_matches_nx_everywhere = False
        if not _outcome_matches(row.raw, row.nx_baseline):
            raw_matches_nx_everywhere = False

        if not row.raw.ok or not row.public.ok or not row.nx_baseline.ok:
            continue

        rn = _normalize(row.raw.value)
        pn = _normalize(row.public.value)
        nn = _normalize(row.nx_baseline.value)

        if not _approx_equal(rn, pn):
            has_disagreement = True
        if not _approx_equal(pn, nn):
            public_matches_nx_everywhere = False
        if not _approx_equal(rn, nn):
            raw_matches_nx_everywhere = False

    if raw_looser_than_public:
        # raw returns garbage where nx + wrapper correctly raise — bug.
        return "error-divergence"
    if raw_stricter_than_public and public_matches_nx_everywhere:
        # raw is intentionally stricter; wrapper bridges to nx — same
        # category as wrapper-corrected: the wrapper is doing real work.
        return "wrapper-corrected"
    if not has_disagreement and raw_matches_nx_everywhere and public_matches_nx_everywhere:
        return "identical"
    if has_disagreement and public_matches_nx_everywhere and not raw_matches_nx_everywhere:
        return "wrapper-corrected"
    if not public_matches_nx_everywhere and not raw_matches_nx_everywhere:
        return "wrapper-misalign"
    if not has_disagreement and raw_matches_nx_everywhere and not public_matches_nx_everywhere:
        return "wrapper-broken"
    if has_disagreement and raw_matches_nx_everywhere and not public_matches_nx_everywhere:
        return "wrapper-broken"
    return "mixed"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run_audit() -> list[FuncReport]:
    reports: list[FuncReport] = []

    for fname, shape, skip_fixtures in FUNCTION_SPECS:
        raw_name = "_raw_" + fname
        raw_fn = getattr(fnx, raw_name, None)
        public_fn = getattr(fnx, fname, None)
        nx_fn = getattr(nx, fname, None)
        report = FuncReport(
            name=fname,
            raw_callable=callable(raw_fn),
            public_callable=callable(public_fn),
        )
        if not report.raw_callable:
            report.notes.append(f"`{raw_name}` not exposed")
        if not report.public_callable:
            report.notes.append(f"`{fname}` not exposed")
        if not callable(nx_fn):
            report.notes.append(f"`networkx.{fname}` not available")

        if not (report.raw_callable and report.public_callable and callable(nx_fn)):
            report.classification = "untestable-not-exposed"
            reports.append(report)
            continue

        for fid, builder in FIXTURES:
            if fid in skip_fixtures:
                continue
            try:
                fg, ng = builder()
            except Exception as exc:
                report.notes.append(
                    f"fixture `{fid}` build failed: {type(exc).__name__}: {exc}"
                )
                continue

            f_args, f_kwargs = shape.fnx_args_kwargs(fg, ng)
            n_args, n_kwargs = shape.nx_args_kwargs(fg, ng)
            row = FixtureRow(
                fixture_id=fid,
                raw=_call(raw_fn, [fg, *f_args], f_kwargs),
                public=_call(public_fn, [fg, *f_args], f_kwargs),
                nx_baseline=_call(nx_fn, [ng, *n_args], n_kwargs),
            )
            report.rows.append(row)

        report.classification = _classify(report)
        reports.append(report)

    return reports


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _row_summary(row: FixtureRow) -> str:
    def _short(out: CallOutcome) -> str:
        if not out.ok:
            return f"raise {out.error_type}"
        rep = repr(out.value)
        return rep if len(rep) <= 60 else rep[:57] + "..."

    return f"{row.fixture_id}: raw={_short(row.raw)} | public={_short(row.public)} | nx={_short(row.nx_baseline)}"


def write_markdown(reports: list[FuncReport], path: Path) -> None:
    by_class: dict[str, list[FuncReport]] = {}
    for r in reports:
        by_class.setdefault(r.classification, []).append(r)

    lines: list[str] = []
    lines.append("# Raw-vs-Public Algorithm Consistency Audit")
    lines.append("")
    lines.append("*Auto-generated by `scripts/raw_vs_public_audit.py` (br-r37-c1-cvrij).*")
    lines.append("")
    lines.append(f"Functions audited: **{len(reports)}**")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| classification | count | meaning |")
    lines.append("|----------------|-------|---------|")
    legend = {
        "identical": "raw and public agree on every fixture, both match nx — public could call raw directly",
        "wrapper-corrected": "raw and public disagree, public matches nx — wrapper is necessary",
        "wrapper-misalign": "neither raw nor public match nx on at least one fixture — needs investigation",
        "wrapper-broken": "raw matches nx but public does not — wrapper introduces a bug",
        "error-divergence": "raw and public differ on whether they raise — call shape is incompatible",
        "untestable-not-exposed": "raw or public not exposed in the audited shape; manual review",
        "mixed": "fixture-dependent — see per-row table below",
    }
    for cls, items in sorted(by_class.items()):
        lines.append(f"| `{cls}` | {len(items)} | {legend.get(cls, '')} |")
    lines.append("")

    for cls in sorted(by_class):
        lines.append(f"## {cls} ({len(by_class[cls])})")
        lines.append("")
        for report in sorted(by_class[cls], key=lambda r: r.name):
            lines.append(f"### `{report.name}`")
            lines.append("")
            if report.notes:
                for note in report.notes:
                    lines.append(f"- {note}")
                lines.append("")
            if report.rows:
                lines.append("| fixture | raw | public | nx |")
                lines.append("|---------|-----|--------|-----|")
                for row in report.rows:
                    cells = []
                    for out in (row.raw, row.public, row.nx_baseline):
                        if not out.ok:
                            cells.append(f"raises {out.error_type}")
                        else:
                            rep = repr(out.value)
                            if len(rep) > 50:
                                rep = rep[:47] + "..."
                            cells.append(f"`{rep}`")
                    lines.append(f"| {row.fixture_id} | {cells[0]} | {cells[1]} | {cells[2]} |")
                lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(reports: list[FuncReport], path: Path) -> None:
    out = []
    for r in reports:
        out.append(
            {
                "name": r.name,
                "raw_callable": r.raw_callable,
                "public_callable": r.public_callable,
                "classification": r.classification,
                "notes": r.notes,
                "rows": [
                    {
                        "fixture": row.fixture_id,
                        "raw": {
                            "ok": row.raw.ok,
                            "value": _stringify(row.raw.value) if row.raw.ok else None,
                            "error_type": row.raw.error_type,
                        },
                        "public": {
                            "ok": row.public.ok,
                            "value": _stringify(row.public.value) if row.public.ok else None,
                            "error_type": row.public.error_type,
                        },
                        "nx": {
                            "ok": row.nx_baseline.ok,
                            "value": _stringify(row.nx_baseline.value) if row.nx_baseline.ok else None,
                            "error_type": row.nx_baseline.error_type,
                        },
                    }
                    for row in r.rows
                ],
            }
        )
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")


def _stringify(value):
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): _stringify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_stringify(x) for x in value]
    return repr(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DOCS_DIR,
        help="directory to write markdown and json reports",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the per-class summary on stdout",
    )
    args = parser.parse_args(argv)

    reports = run_audit()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_markdown(reports, out_dir / "raw_vs_public_audit.md")
    write_json(reports, out_dir / "raw_vs_public_audit.json")

    if not args.quiet:
        by_class: dict[str, int] = {}
        for r in reports:
            by_class[r.classification] = by_class.get(r.classification, 0) + 1
        print(f"Audited {len(reports)} functions across {len(FIXTURES)} fixtures.")
        for cls, count in sorted(by_class.items()):
            print(f"  {cls:30s} {count:>4}")
        print(f"\nWrote {out_dir / 'raw_vs_public_audit.md'}")
        print(f"Wrote {out_dir / 'raw_vs_public_audit.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
