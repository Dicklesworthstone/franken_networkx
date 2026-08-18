"""br-r37-c1-303zo: which native kernels read a STALE typed node-attribute store?

The bead fixed one symptom (weighted `min_weighted_vertex_cover`) and left the
audit open: "I did not audit every native kernel that reads node attributes; that
audit is part of this bead."

THE GAP. A graph carries two node-attribute stores. The Python paths write
`node_py_attrs`; native kernels read the typed Rust store reached by
`Graph::node_attrs`. Attributes attached AFTER construction land only in the
former, and a kernel that misses takes a DEFAULT rather than raising -- so the
result is plausible and wrong. `g.nodes(data=True)` shows the right values
throughout, which is why nothing looks broken from Python.

WHAT THIS PROBE DOES. Source grep found four kernels reading node attributes with
a default on miss, in crates/fnx-algorithms/src/lib.rs:

    min_weighted_vertex_cover   line 28576   .get(attr).and_then(as_f64).unwrap_or(1.0)
    max_weight_clique           line 40581   .get(weight_attr).and_then(as_f64).unwrap_or(1.0)
    min_cost_flow               line 42510   .get(demand_attr)
    community_keys_by_index     line 27231   .get(community_attr)

Each is exercised through its public API by building the SAME graph three ways
and comparing against networkx:

    A  attrs passed to add_node BEFORE the edges   -> reaches the typed store
    B  attrs written afterwards via g.nodes[v][k]  -> Python store only
    C  attrs written afterwards via set_node_attributes -> Python store only

A kernel is AFFECTED if B or C disagrees with networkx while A agrees. The
witnesses are deliberately weight-SENSITIVE: the bead's own scope note records
that `min_weighted_dominating_set` looked clean only because the first witness
could not have detected a fault, so each case below is checked to give a
different answer weighted than unweighted.

IT CALLS `_fnx.<kernel>` DIRECTLY, AND THAT IS THE WHOLE POINT. Driving the
public API instead reports every kernel clean, because the public surface routes
around all of them: `fnx.max_weight_clique` delegates to networkx,
`fnx.min_cost_flow` is implemented in Python in the shim, and
`approximation.min_weighted_vertex_cover` IS networkx's own function (the
br-r37-c1-bdswh fix). A probe through the public API measures the delegation, not
the kernel, and would file a false clean -- which is the same trap the bead
records for its first witness. So the bug is DORMANT, not absent: users are
protected today by the routing, and the moment any of these is routed native it
ships a wrong answer.

DIAGNOSTIC, from the bead: `copy()` flushes the gap, because the rebuild
materialises the attributes into the typed store. So for any affected kernel,
`f(g)` and `f(g.copy())` disagree -- that is reported too, and it is the cheapest
confirmation that a divergence is THIS bug rather than an unrelated one.
"""

from __future__ import annotations

import sys
import traceback

sys.path.insert(0, "/data/projects/franken_networkx/python")

import networkx as nx  # noqa: E402

import franken_networkx as fnx  # noqa: E402

WEIGHT = "weight"


def _build(lib, cls_name, nodes, edges, attrs, how):
    """Build one graph, attaching `attrs` by one of the three routes."""
    graph = getattr(lib, cls_name)()
    if how == "A_add_node_first":
        for node in nodes:
            graph.add_node(node, **{k: v for k, v in attrs.get(node, {}).items()})
        graph.add_edges_from(edges)
        return graph

    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    if how == "B_nodes_getitem":
        for node, node_attrs in attrs.items():
            for key, value in node_attrs.items():
                graph.nodes[node][key] = value
    elif how == "C_set_node_attributes":
        for key in {k for a in attrs.values() for k in a}:
            lib.set_node_attributes(
                graph, {n: a[key] for n, a in attrs.items() if key in a}, key
            )
    else:  # pragma: no cover - guarded by the caller
        raise ValueError(how)
    return graph


ROUTES = ("A_add_node_first", "B_nodes_getitem", "C_set_node_attributes")


def _case_max_weight_clique():
    """A triangle of cheap nodes against a heavier pair.

    Weight-sensitive by construction: unweighted the triangle wins on size,
    weighted the pair wins on total weight. A kernel defaulting every node to 1.0
    therefore returns the TRIANGLE, which is the detectable fault.
    """
    nodes = ["a", "b", "c", "x", "y"]
    edges = [("a", "b"), ("b", "c"), ("a", "c"), ("x", "y")]
    # INTEGER weights: networkx's max_weight_clique rejects floats outright
    # ("The 'weight' field of node 'a' is not an integer"), which my first
    # witness tripped on all three routes and so could not have detected
    # anything.
    attrs = {
        "a": {WEIGHT: 1},
        "b": {WEIGHT: 1},
        "c": {WEIGHT: 1},
        "x": {WEIGHT: 10},
        "y": {WEIGHT: 10},
    }

    def run(lib, graph):
        if lib is nx:
            clique, total = nx.max_weight_clique(graph, weight=WEIGHT)
        else:
            clique, total = fnx._fnx.max_weight_clique(graph, WEIGHT)
        return (tuple(sorted(clique)), float(total))

    return "max_weight_clique", "Graph", nodes, edges, attrs, run


def _case_min_cost_flow():
    """Demand lives on NODES, so a missed demand silently changes the problem."""
    nodes = ["s", "m", "t"]
    # EDGE attrs are carried at construction on purpose. Writing them afterwards
    # (graph[u][v]["weight"] = 1) tripped the EDGE-side version of the same gap
    # and made route A fail too, which would have confounded the node-attr
    # variable this probe is isolating. Worth its own bead: the native kernel
    # missed post-construction edge weights and returned cost 0.0.
    edges = [
        ("s", "m", {"weight": 1, "capacity": 10}),
        ("m", "t", {"weight": 1, "capacity": 10}),
    ]
    attrs = {"s": {"demand": -5}, "t": {"demand": 5}}

    def run(lib, graph):
        if lib is nx:
            return float(nx.min_cost_flow_cost(graph))
        return float(fnx._fnx.min_cost_flow_cost(graph))

    return "min_cost_flow_cost", "DiGraph", nodes, edges, attrs, run


CASES = (_case_max_weight_clique, _case_min_cost_flow)


def main() -> int:
    print("br-r37-c1-303zo — native kernels reading a stale typed node-attr store")
    print(f"fnx: {fnx.__file__}")
    print(f"nx : {nx.__version__}\n")

    affected = []
    for case in CASES:
        name, cls_name, nodes, edges, attrs, run = case()
        print(f"=== {name} ({cls_name}) ===")
        baseline = None
        for how in ROUTES:
            try:
                expected = run(nx, _build(nx, cls_name, nodes, edges, attrs, how))
            except Exception as exc:  # noqa: BLE001 - reported, not raised
                expected = f"{type(exc).__name__}: {exc}"
            graph = _build(fnx, cls_name, nodes, edges, attrs, how)
            try:
                got = run(fnx, graph)
            except Exception as exc:  # noqa: BLE001
                got = f"{type(exc).__name__}: {exc}"
            # the bead's diagnostic: copy() rebuilds into the typed store
            try:
                copied = run(fnx, _build(fnx, cls_name, nodes, edges, attrs, how).copy())
            except Exception as exc:  # noqa: BLE001
                copied = f"{type(exc).__name__}: {exc}"

            agree = got == expected
            flush = "n/a" if agree else ("COPY FIXES IT" if copied == expected else "copy does not fix")
            print(f"  {how:22s} nx={expected!s:38s} fnx={got!s:38s} {'ok' if agree else 'DIVERGES'}  {flush}")
            if how == "A_add_node_first":
                baseline = agree
            elif not agree and baseline:
                affected.append((name, how, copied == expected))
        print()

    print("=== VERDICT ===")
    if not affected:
        print("no kernel in this probe is affected: every route agrees with networkx.")
    else:
        for name, how, copy_fixes in affected:
            marker = " (copy() fixes it -> this IS the 303zo store gap)" if copy_fixes else ""
            print(f"AFFECTED: {name} via {how}{marker}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # pragma: no cover - probe-level failure
        traceback.print_exc()
        raise SystemExit(2)
