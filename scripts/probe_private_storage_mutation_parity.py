"""br-r37-c1-vbe1o companion: private-storage parity for MUTATIONS.

`probe_private_storage_parity.py` sweeps the READ surface and found 97
divergences. Every fix so far has been to a read path. This asks the other half
of the question: when a graph carries assigned private storage and you then
MUTATE it, does the resulting graph match networkx?

That matters more than a read divergence in one respect — a wrong read gives a
wrong answer once, while a wrong write leaves the graph itself wrong for
everything downstream.

Method: build the same graph in both libraries, assign the SAME private mapping,
apply one mutation, then compare the resulting OBSERVABLE STATE — node set, edge
set, and the adjacency contents — rather than the mutation's return value. An
exception is compared by type AND args, because a type-only comparison reports
false green.

Run:  PYTHONPATH=<arm>/python python3 scripts/probe_private_storage_mutation_parity.py

DIAGNOSTIC, not a test: it reports rather than asserts, so it stays usable while
the family is worked through.
"""

import networkx as nx

import franken_networkx as fnx

ADJ = {"a": {"b": {}}, "b": {"a": {}}, "ZZ": {"b": {}}}
SUCC = {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}
NODE = {"a": {}, "b": {}, "ZZ": {}}


def state(g):
    """Observable state after the mutation, normalised across libraries."""
    try:
        nodes = sorted(map(str, g.nodes()))
    except Exception as exc:  # noqa: BLE001
        nodes = f"<nodes:{type(exc).__name__}>"
    try:
        edges = sorted(str(tuple(map(str, e[:2]))) for e in g.edges())
    except Exception as exc:  # noqa: BLE001
        edges = f"<edges:{type(exc).__name__}>"
    try:
        rows = sorted(f"{k}:{sorted(map(str, v))}" for k, v in g.adj.items())
    except Exception as exc:  # noqa: BLE001
        rows = f"<adj:{type(exc).__name__}>"
    return f"nodes={nodes} edges={edges} adj={rows}"


def run(mod, cls, attr, mapping, mutate):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    try:
        setattr(g, attr, dict(mapping))
    except Exception as exc:  # noqa: BLE001
        return (f"SETATTR:{type(exc).__name__}", "")
    try:
        mutate(g)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc.args[0])[:50] if exc.args else "")
    return ("ok", state(g))


MUTATIONS = [
    ("add_edge('ZZ','a')", lambda g: g.add_edge("ZZ", "a")),
    ("add_edge('new1','new2')", lambda g: g.add_edge("new1", "new2")),
    ("add_node('QQ')", lambda g: g.add_node("QQ")),
    ("add_nodes_from(['QQ','RR'])", lambda g: g.add_nodes_from(["QQ", "RR"])),
    ("add_edges_from([('p','q')])", lambda g: g.add_edges_from([("p", "q")])),
    ("remove_node('ZZ')", lambda g: g.remove_node("ZZ")),
    ("remove_node('a')", lambda g: g.remove_node("a")),
    ("remove_edge('a','b')", lambda g: g.remove_edge("a", "b")),
    ("remove_edges_from([('a','b')])", lambda g: g.remove_edges_from([("a", "b")])),
    ("clear()", lambda g: g.clear()),
    ("clear_edges()", lambda g: g.clear_edges()),
    ("update nodes attr", lambda g: g.nodes["a"].update({"k": 1})),
    ("add_weighted_edges_from", lambda g: g.add_weighted_edges_from([("w1", "w2", 2)])),
]

CASES = [
    ("Graph", "_adj", ADJ), ("Graph", "_node", NODE),
    ("MultiGraph", "_adj", ADJ), ("MultiGraph", "_node", NODE),
    ("DiGraph", "_adj", ADJ), ("DiGraph", "_succ", SUCC), ("DiGraph", "_node", NODE),
    ("MultiDiGraph", "_adj", ADJ), ("MultiDiGraph", "_succ", SUCC),
    ("MultiDiGraph", "_node", NODE),
]


def main():
    total = 0
    diverged = []
    for cls, attr, mapping in CASES:
        for label, mutate in MUTATIONS:
            want = run(nx, cls, attr, mapping, mutate)
            got = run(fnx, cls, attr, mapping, mutate)
            total += 1
            if want != got:
                diverged.append((cls, attr, label, want, got))

    print(f"{len(diverged)} divergences out of {total} mutation comparisons\n")
    by_op = {}
    for cls, attr, label, w, g in diverged:
        by_op.setdefault(label, []).append((cls, attr, w, g))
    for label in sorted(by_op, key=lambda k: -len(by_op[k])):
        rows = by_op[label]
        print(f"=== {label}  ({len(rows)} case(s)) ===")
        for cls, attr, w, g in rows:
            print(f"    {cls:13s} {attr:6s}")
            print(f"        nx  {str(w)[:150]}")
            print(f"        fnx {str(g)[:150]}")


if __name__ == "__main__":
    main()
