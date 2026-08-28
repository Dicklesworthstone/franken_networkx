"""br-r37-c1-vbe1o: systematic private-storage parity sweep across the public read API.

Run:  PYTHONPATH=<arm>/python python3 scripts/probe_private_storage_parity.py

A DIAGNOSTIC, not a test -- it reports divergences rather than asserting, so it
stays useful while the family is being worked through. Read the caveats at the
bottom of this docstring before treating a row as a bug.

Three defect families in this area were found one at a time by hand
(br-r37-c1-ppiei, br-r37-c1-2r06n and the getitem layer under it). Each was found
by asking the same question of a neighbouring accessor. This asks it of the whole
read surface at once.

Method: build the same graph in networkx and fnx, assign the SAME private mapping
carrying a node the native store does not have, then compare every read by VALUE
-- and compare raised exceptions by type AND args, because a type-only sweep
reports false green (that lesson cost a previous sweep its credibility).

CAVEATS -- two classes of row are NOT necessarily defects:

  * WRAPPER ROWS. Where fnx returns the assigned mapping raw and networkx wraps
    it in an AdjacencyView/AtlasView, `norm()` renders one as a dict and the
    other as its keys, so `G.adj`, `G.succ`, `G.pred` and `G[n]` show as
    divergent. That IS a real type difference, but it is a different family
    from the value bugs and is tracked separately.
  * CASCADES. `nx.density`, `number_of_edges` and `size` are derived, so they
    move whenever a node/edge count moves. Fix the primary and re-run before
    counting them.
"""
import networkx as nx

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
PRED = {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}}
NODE = {"a": {}, "b": {}, "ZZ": {}}


def norm(v):
    """Normalise a result to something comparable across the two libraries."""
    if isinstance(v, (int, float, bool, str)) or v is None:
        return repr(v)
    if isinstance(v, dict):
        return "{" + ",".join(f"{k!s}:{norm(x)}" for k, x in sorted(v.items(), key=str)) + "}"
    try:
        items = list(v)
    except TypeError:
        return f"<{type(v).__name__}>"
    out = []
    for it in items:
        if isinstance(it, tuple):
            out.append("(" + ",".join(norm(x) for x in it) + ")")
        else:
            out.append(str(it))
    return "[" + ",".join(sorted(out)) + "]"


def call(fn):
    try:
        return ("ok", norm(fn()))
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc.args[0])[:60] if exc.args else "")


OPS = [
    ("len(G)", lambda g: len(g)),
    ("list(G)", lambda g: list(g)),
    ("'ZZ' in G", lambda g: "ZZ" in g),
    ("G.number_of_nodes()", lambda g: g.number_of_nodes()),
    ("G.order()", lambda g: g.order()),
    ("G.nodes", lambda g: g.nodes),
    ("len(G.nodes)", lambda g: len(g.nodes)),
    ("G.has_node('ZZ')", lambda g: g.has_node("ZZ")),
    ("G.edges", lambda g: g.edges),
    ("G.number_of_edges()", lambda g: g.number_of_edges()),
    ("G.size()", lambda g: g.size()),
    ("G.has_edge('ZZ','b')", lambda g: g.has_edge("ZZ", "b")),
    ("G.get_edge_data('ZZ','b')", lambda g: g.get_edge_data("ZZ", "b")),
    ("G.adj", lambda g: g.adj),
    ("len(G.adj)", lambda g: len(g.adj)),
    ("G['ZZ']", lambda g: g["ZZ"]),
    ("G.neighbors('ZZ')", lambda g: list(g.neighbors("ZZ"))),
    ("G.degree", lambda g: dict(g.degree)),
    ("G.degree('ZZ')", lambda g: g.degree("ZZ")),
    ("list(G.adjacency())", lambda g: [n for n, _ in g.adjacency()]),
    ("list(G.nbunch_iter())", lambda g: list(g.nbunch_iter())),
    ("G.subgraph(['a','ZZ'])", lambda g: sorted(map(str, g.subgraph(["a", "ZZ"])))),
    ("G.copy()", lambda g: sorted(map(str, g.copy()))),
    ("nx.density", lambda g: round(nx.density(g), 6)),
]

DIRECTED_OPS = [
    ("G.succ", lambda g: g.succ),
    ("G.pred", lambda g: g.pred),
    ("len(G.succ)", lambda g: len(g.succ)),
    ("G.successors('ZZ')", lambda g: list(g.successors("ZZ"))),
    ("G.predecessors('ZZ')", lambda g: list(g.predecessors("ZZ"))),
    ("G.in_degree", lambda g: dict(g.in_degree)),
    ("G.out_degree", lambda g: dict(g.out_degree)),
    ("G.out_degree('ZZ')", lambda g: g.out_degree("ZZ")),
    ("G.has_successor('ZZ','b')", lambda g: g.has_successor("ZZ", "b")),
    ("G.reverse(copy=False)", lambda g: sorted(map(str, g.reverse(copy=False)))),
]

CASES = [
    ("Graph", "_adj", ADJ), ("Graph", "_node", NODE),
    ("MultiGraph", "_adj", ADJ), ("MultiGraph", "_node", NODE),
    ("DiGraph", "_adj", ADJ), ("DiGraph", "_succ", SUCC),
    ("DiGraph", "_pred", PRED), ("DiGraph", "_node", NODE),
    ("MultiDiGraph", "_adj", ADJ), ("MultiDiGraph", "_succ", SUCC),
    ("MultiDiGraph", "_pred", PRED), ("MultiDiGraph", "_node", NODE),
]

def compare_one(cls, attr, mapping, fn):
    """Run one (class, assignment, read) cell and return the (nx, fnx) outcomes.

    br-r37-c1-vbe1o: split out so the sweep has ONE definition shared by this
    diagnostic and the regression lock in
    tests/python/test_private_storage_read_api_parity.py. The family this probe was
    written to survey is closed - 97 divergences when it landed, 0 on HEAD - so the
    surface is now asserted rather than only reported, and duplicating the case table
    into the test would let the two drift.
    """
    res = []
    for mod in (nx, fnx):
        g = getattr(mod, cls)()
        g.add_edge("a", "b")
        try:
            setattr(g, attr, dict(mapping))
        except Exception as exc:  # noqa: BLE001
            res.append((f"SETATTR:{type(exc).__name__}", ""))
            continue
        res.append(call(lambda: fn(g)))
    return res[0], res[1]


def iter_cells():
    """Yield every (cls, attr, mapping, label, fn) cell the sweep compares."""
    for cls, attr, mapping in CASES:
        for label, fn in OPS + (DIRECTED_OPS if "Di" in cls else []):
            yield cls, attr, mapping, label, fn


def run_sweep():
    """Return (total, diverged) over the whole surface."""
    total = 0
    diverged = []
    for cls, attr, mapping, label, fn in iter_cells():
        expected, got = compare_one(cls, attr, mapping, fn)
        total += 1
        if expected != got:
            diverged.append((cls, attr, label, expected, got))
    return total, diverged


def main():
    total, diverged = run_sweep()

    print(f"{len(diverged)} divergences out of {total} comparisons\n")
    by_op = {}
    for cls, attr, label, e, g in diverged:
        by_op.setdefault(label, []).append((cls, attr, e, g))
    for label in sorted(by_op, key=lambda k: -len(by_op[k])):
        rows = by_op[label]
        print(f"=== {label}  ({len(rows)} case(s)) ===")
        for cls, attr, e, g in rows:
            print(f"    {cls:13s} {attr:6s} nx={str(e)[:44]:46s} fnx={str(g)[:44]}")


if __name__ == "__main__":
    main()
